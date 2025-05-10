# src/sourcelens/nodes/analyze.py

"""Nodes responsible for analyzing the codebase using an LLM."""

import contextlib
import logging
from typing import Any, Final, Optional, TypeAlias, Union

# BaseNode now relies on exec_res parameter in post
from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import AbstractionPrompts
from sourcelens.utils.helpers import get_content_for_indices
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import (
    ValidationFailure,
    validate_yaml_dict,
    validate_yaml_list,
)

# --- Type Aliases ---
FileData: TypeAlias = list[tuple[str, str]]
AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]
RelationshipDetail: TypeAlias = dict[str, Any]
RelationshipsDict: TypeAlias = dict[str, Any]
PathToIndexMap: TypeAlias = dict[str, int]
RawIndexEntry: TypeAlias = Union[str, int, float, None]

# Module-level logger for utility functions if needed outside classes
module_logger = logging.getLogger(__name__)

# --- Constants ---
MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500

# --- Schemas ---
ABSTRACTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "file_indices": {"type": "array", "items": {"type": ["integer", "string"]}},
    },
    "required": ["name", "description", "file_indices"],
    "additionalProperties": False,
}
RELATIONSHIP_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from_abstraction": {"type": ["integer", "string"]},
        "to_abstraction": {"type": ["integer", "string"]},
        "label": {"type": "string", "minLength": 1},
    },
    "required": ["from_abstraction", "to_abstraction", "label"],
    "additionalProperties": False,
}
RELATIONSHIPS_DICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "summary": {"type": "string", "minLength": 1},
        "relationships": {"type": "array", "items": RELATIONSHIP_ITEM_SCHEMA},
    },
    "required": ["summary", "relationships"],
    "additionalProperties": False,
}


class IdentifyAbstractions(BaseNode):
    """Identify core abstractions from the codebase using an LLM.

    This node takes the fetched file data, constructs a prompt for the LLM
    to identify key conceptual abstractions, calls the LLM, and then validates
    and processes the YAML response. The identified abstractions are stored
    in the shared state.
    """

    def _try_parse_index_from_string(self, entry_str: str, path_to_index_map: PathToIndexMap) -> Optional[int]:
        """Attempt to parse an integer index from a string entry.

        Handles formats like "idx # comment", "idx", or a direct file path
        present in the `path_to_index_map`.

        Args:
            entry_str: The string entry to parse.
            path_to_index_map: Mapping from file paths to their integer index.

        Returns:
            The parsed integer index if successful, otherwise None.

        """
        parsed_idx: Optional[int] = None
        # Attempt to parse "idx # comment" format first
        if "#" in entry_str:
            with contextlib.suppress(ValueError, IndexError):
                parsed_idx = int(entry_str.split("#", 1)[0].strip())

        # If not parsed, try to parse as a simple integer
        if parsed_idx is None:
            with contextlib.suppress(ValueError):
                parsed_idx = int(entry_str)

        # If still not parsed, check if it's a file path in the map
        if parsed_idx is None and entry_str in path_to_index_map:
            parsed_idx = path_to_index_map[entry_str]
        elif parsed_idx is None and entry_str not in path_to_index_map and not entry_str.isdigit():
            # Log only if it's not a simple number string and not in path map
            # Using module_logger as this helper might be used in contexts without self._logger
            module_logger.debug("Failed to parse index string or match path: '%s'", entry_str)
        return parsed_idx

    def _parse_single_index(
        self, idx_entry: RawIndexEntry, path_to_index_map: PathToIndexMap, file_count: int
    ) -> Optional[int]:
        """Parse a single file index entry from the LLM response.

        Validates the type and range of the parsed index.

        Args:
            idx_entry: Raw entry from 'file_indices' list (can be int, str, float, None).
            path_to_index_map: Mapping from file paths to their integer index.
            file_count: Total number of files for bounds checking.

        Returns:
            Parsed integer index if valid and within bounds [0, file_count-1],
            otherwise None.

        """
        parsed_idx: Optional[int] = None
        try:
            if isinstance(idx_entry, int):
                parsed_idx = idx_entry
            elif isinstance(idx_entry, str):
                parsed_idx = self._try_parse_index_from_string(idx_entry.strip(), path_to_index_map)
            elif isinstance(idx_entry, float) and idx_entry.is_integer():
                # Allow floats if they represent whole numbers
                parsed_idx = int(idx_entry)
            elif idx_entry is None:
                return None  # Explicitly ignore None entries
            else:
                module_logger.warning("Unexpected type '%s' for file index: '%s'.", type(idx_entry).__name__, idx_entry)
                return None

            # Validate range if successfully parsed
            if parsed_idx is not None and 0 <= parsed_idx < file_count:
                return parsed_idx
            if parsed_idx is not None:  # Log out-of-range only if parsing was successful
                module_logger.warning("File index %d is out of valid range [0, %d).", parsed_idx, file_count)
            return None  # Parsed but out of range, or failed parsing
        except (ValueError, TypeError) as e:  # Catch errors from int() or string ops
            module_logger.warning("Could not parse file index entry '%s': %s.", idx_entry, e)
            return None

    def _parse_and_validate_indices(
        self, raw_indices: list[Any], path_to_index_map: PathToIndexMap, file_count: int, item_name: str
    ) -> list[int]:
        """Parse and validate file indices from LLM response for one abstraction item.

        Iterates through a list of raw index entries, attempts to parse each,
        validates them, and returns a sorted list of unique valid indices.

        Args:
            raw_indices: List of items parsed from 'file_indices' in LLM's YAML response.
            path_to_index_map: Mapping from file paths to their integer index.
            file_count: Total number of files for bounds checking.
            item_name: The name of the abstraction item for logging context.

        Returns:
            A sorted list of unique, valid integer file indices.

        """
        validated_indices: set[int] = set()
        if not isinstance(raw_indices, list):
            module_logger.warning(
                "Invalid type for 'file_indices' in abstraction '%s': Expected list, got %s.",
                item_name,
                type(raw_indices).__name__,
            )
            return []  # Return empty if not a list

        for idx_entry in raw_indices:
            valid_idx = self._parse_single_index(idx_entry, path_to_index_map, file_count)
            if valid_idx is not None:
                validated_indices.add(valid_idx)

        if not validated_indices:
            module_logger.warning(
                "No valid file indices found or parsed for abstraction '%s'. Original: %s", item_name, raw_indices
            )
        return sorted(validated_indices)

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare context and parameters for abstraction identification LLM prompt."""
        self._logger.info("Preparing context for abstraction identification...")
        files_data: FileData = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        language: str = shared.get("language", "english")

        context_list: list[str] = [
            f"--- File Index {i}: {path} ---\n{content}\n\n" for i, (path, content) in enumerate(files_data)
        ]
        file_info_for_prompt: list[str] = [f"- {i} # {path}" for i, (path, _) in enumerate(files_data)]
        return {
            "context": "".join(context_list),
            "file_listing": "\n".join(file_info_for_prompt),
            "file_count": len(files_data),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "files_data": files_data,  # Pass for validation in _process_raw_abstractions
        }

    def _process_raw_abstractions(
        self, raw_abstractions: list[Any], files_data: FileData, file_count: int
    ) -> AbstractionsList:
        """Process and validate a list of raw abstraction items from LLM response.

        Iterates through raw abstraction items, validates their structure and
        file indices, and compiles a list of valid abstraction dictionaries.

        Args:
            raw_abstractions: List of items parsed from LLM's YAML response.
            files_data: Original list of (path, content) tuples from `shared_state`.
            file_count: Total number of files, for validating indices.

        Returns:
            A list of validated abstraction dictionaries.

        """
        validated_abstractions: AbstractionsList = []
        path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data)}

        for item in raw_abstractions:
            if not isinstance(item, dict):  # Ensure item is a dictionary
                module_logger.warning("Skipping non-dictionary abstraction item: %s", item)
                continue

            item_name = item.get("name")
            item_desc = item.get("description")
            raw_indices_list = item.get("file_indices", [])

            if not (
                isinstance(item_name, str) and item_name.strip() and isinstance(item_desc, str) and item_desc.strip()
            ):
                module_logger.warning("Skipping abstraction with missing/invalid name or description: %s", item)
                continue

            # Ensure raw_indices_list is actually a list before parsing
            if not isinstance(raw_indices_list, list):
                module_logger.warning(
                    "File indices for abstraction '%s' is not a list, but %s. Treating as empty.",
                    item_name,
                    type(raw_indices_list).__name__,
                )
                raw_indices_list = []  # Default to empty list

            unique_indices = self._parse_and_validate_indices(
                raw_indices_list, path_to_index_map, file_count, item_name
            )
            # Only add abstraction if it has a name, description, and potentially some files
            # (though an abstraction might not be tied to specific files, e.g., a general concept)
            validated_abstractions.append({"name": item_name, "description": item_desc, "files": unique_indices})
        return validated_abstractions

    def exec(self, prep_res: dict[str, Any]) -> AbstractionsList:
        """Execute LLM call, parse, and validate identified abstractions."""
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        project_name: str = prep_res["project_name"]
        self._logger.info(f"Identifying abstractions for '{project_name}' using LLM...")
        prompt = AbstractionPrompts.format_identify_abstractions_prompt(
            project_name=project_name,
            context=prep_res["context"],
            file_listing=prep_res["file_listing"],
            language=prep_res["language"],
        )
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._logger.error("LLM call failed during abstraction identification: %s", e, exc_info=True)
            return []
        try:
            raw_abstractions = validate_yaml_list(response, ABSTRACTION_ITEM_SCHEMA)
        except ValidationFailure as e_val:
            self._logger.error("YAML validation failed for abstractions: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN] + (
                    "..." if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN else ""
                )
                module_logger.warning("Problematic raw LLM output for abstractions:\n---\n%s\n---", snippet)
            return []
        try:
            validated_abstractions = self._process_raw_abstractions(
                raw_abstractions, prep_res["files_data"], prep_res["file_count"]
            )
            if not validated_abstractions and raw_abstractions:
                self._logger.warning("LLM parsed YAML for abstractions, but no valid items remained after processing.")
            elif not validated_abstractions:
                self._logger.warning("No valid abstractions found in LLM response or after processing.")
            else:
                self._logger.info(f"Successfully processed {len(validated_abstractions)} abstractions.")
            return validated_abstractions
        except (ValueError, TypeError) as e_proc:
            self._logger.error("Error processing validated abstractions: %s", e_proc, exc_info=True)
            return []

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: AbstractionsList) -> None:
        """Update the shared state with identified abstractions.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from `prep` (unused in this specific `post`).
            exec_res: Result from `exec` (list of abstractions), passed by the
                      flow runner.

        """
        # Now using exec_res directly from PocketFlow
        if isinstance(exec_res, list):
            shared["abstractions"] = exec_res
            self._logger.info(f"Stored {len(exec_res)} abstractions in shared state.")
        else:
            self._logger.error(
                "Invalid exec_res type for abstractions: %s. Expected list. Storing empty list.",
                type(exec_res).__name__,
            )
            shared["abstractions"] = []


class AnalyzeRelationships(BaseNode):
    """Analyze relationships between identified abstractions using an LLM.

    This node uses the previously identified abstractions and relevant code snippets
    to prompt an LLM for a summary of their interactions and a list of specific
    relationships (from_abstraction, to_abstraction, label). The response is
    validated against a schema.
    """

    def _parse_single_relationship(
        self, rel_item: dict[str, Any], num_abstractions: int
    ) -> Optional[tuple[RelationshipDetail, set[int]]]:
        """Parse and validate a single relationship item from LLM response.

        Args:
            rel_item: A dictionary representing one relationship.
            num_abstractions: Total number of abstractions for index validation.

        Returns:
            A tuple (RelationshipDetail, set of involved indices) if valid,
            otherwise None.

        """
        try:
            from_entry = rel_item.get("from_abstraction")
            to_entry = rel_item.get("to_abstraction")
            label = rel_item.get("label")

            from_idx_str = (
                str(from_entry).split("#", 1)[0].strip() if isinstance(from_entry, (str, int, float)) else None
            )
            to_idx_str = str(to_entry).split("#", 1)[0].strip() if isinstance(to_entry, (str, int, float)) else None

            from_idx = int(from_idx_str) if from_idx_str and from_idx_str.isdigit() else None
            to_idx = int(to_idx_str) if to_idx_str and to_idx_str.isdigit() else None

            if from_idx is None or to_idx is None or not isinstance(label, str) or not label.strip():
                raise ValueError("Missing or invalid 'from_abstraction', 'to_abstraction', or 'label'.")
            if not (0 <= from_idx < num_abstractions and 0 <= to_idx < num_abstractions):
                raise ValueError(
                    f"Relationship index out of range [{0}-{num_abstractions - 1}]: from={from_idx}, to={to_idx}."
                )
            return {"from": from_idx, "to": to_idx, "label": label.strip()}, {from_idx, to_idx}
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            module_logger.warning("Could not parse relationship item: %s. Error: %s", rel_item, e)
            return None

    def _parse_and_validate_relationships(
        self, raw_rels_list: list[Any], num_abstractions: int
    ) -> tuple[list[RelationshipDetail], set[int]]:
        """Parse and validate the list of relationship details from LLM response.

        Args:
            raw_rels_list: The raw list of relationship items from YAML.
            num_abstractions: Total number of abstractions for index validation.

        Returns:
            A tuple containing:
                - A list of validated RelationshipDetail dictionaries.
                - A set of all abstraction indices involved in valid relationships.

        """
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            module_logger.warning("Expected list for relationships, got %s.", type(raw_rels_list).__name__)
            return [], set()

        for rel_item in raw_rels_list:
            if not isinstance(rel_item, dict):
                module_logger.warning("Skipping non-dictionary relationship item: %s", rel_item)
                continue
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)
        return validated_relationships, involved_indices

    def _build_relationship_context(self, abstractions: AbstractionsList, files_data: FileData) -> tuple[str, str]:
        """Build context string and abstraction listing for the LLM prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            files_data: List of (path, content) tuples for all project files.

        Returns:
            A tuple containing:
                - context_string (str): Abstraction details and relevant code snippets.
                - abstraction_listing_str (str): Formatted list of "Index # Name".

        """
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []
        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed Abstraction {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            # Ensure 'files' is a list of integers
            file_indices = [idx for idx in abstr.get("files", []) if isinstance(idx, int)]
            file_indices_str = ", ".join(map(str, file_indices)) if file_indices else "None"
            context_builder.append(f"- Index {i}: {abstr_name}\n  Desc: {abstr_desc}\n  Files: [{file_indices_str}]")
            abstraction_info_for_prompt.append(f"- {i} # {abstr_name}")
            all_relevant_indices.update(file_indices)

        context_builder.append("\nRelevant File Snippets:")
        relevant_files_content_map = get_content_for_indices(files_data, sorted(all_relevant_indices))
        if relevant_files_content_map:
            snippet_context = "\n\n".join(
                f"--- File: {idx_path.split('# ', 1)[1] if '# ' in idx_path else idx_path} ---\n{content}"
                for idx_path, content in relevant_files_content_map.items()
            )
            context_builder.append(snippet_context)
        else:
            context_builder.append("No specific file content linked for relationship analysis.")
        return "\n".join(context_builder), "\n".join(abstraction_info_for_prompt)

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare context for relationship analysis LLM prompt."""
        self._logger.info("Preparing context for relationship analysis...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = shared.get("language", "english")

        if not abstractions:
            self._logger.warning("No abstractions provided for relationship analysis. Skipping exec.")
            return {
                "num_abstractions": 0,
                "project_name": project_name,
                "language": language,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "context": "No abstractions to analyze.",
                "abstraction_listing": "N/A",
            }

        files_data: FileData = self._get_required_shared(shared, "files")
        context_str, abstraction_listing_str = self._build_relationship_context(abstractions, files_data)
        return {
            "context": context_str,
            "abstraction_listing": abstraction_listing_str,
            "num_abstractions": len(abstractions),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }

    def exec(self, prep_res: dict[str, Any]) -> RelationshipsDict:
        """Execute LLM call to analyze relationships, parse, and validate."""
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        project_name: str = prep_res.get("project_name", "Unknown Project")
        if num_abstractions == 0:
            self._logger.info("Skipping relationship analysis due to no abstractions.")
            return {"summary": "No abstractions were available to analyze.", "details": []}

        language: str = prep_res["language"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        self._logger.info(f"Analyzing relationships for '{project_name}' using LLM...")
        prompt = AbstractionPrompts.format_analyze_relationships_prompt(
            project_name=project_name,
            context=prep_res["context"],
            abstraction_listing=prep_res["abstraction_listing"],
            num_abstractions=num_abstractions,
            language=language,
        )
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._logger.error("LLM call failed for relationships: %s", e, exc_info=True)
            return {"summary": "LLM API Error during relationship analysis.", "details": []}
        try:
            # Ensure minItems is correctly set based on num_abstractions
            schema = RELATIONSHIPS_DICT_SCHEMA.copy()
            if (
                isinstance(schema.get("properties"), dict)
                and isinstance(schema["properties"].get("relationships"), dict)
                and isinstance(schema["properties"]["relationships"].get("items"), dict)
            ):
                # Check if we expect any relationships at all
                if num_abstractions <= 1:
                    schema["properties"]["relationships"]["minItems"] = 0
                # No else needed, default minItems might be 0 or undefined, handled by validation
            else:
                module_logger.error("Internal schema structure error for RELATIONSHIPS_DICT_SCHEMA.")
                raise ValidationFailure("Internal schema error: Malformed relationships schema.")

            relationships_data = validate_yaml_dict(response, schema)
            raw_rels = relationships_data.get("relationships", [])
            if not isinstance(raw_rels, list):
                raw_rels = []  # Default to empty list if not a list

            valid_rels, involved = self._parse_and_validate_relationships(raw_rels, num_abstractions)
            if num_abstractions > 1 and not valid_rels and raw_rels:
                self._logger.warning("Relationships parsed from LLM, but none were valid after processing.")
            elif num_abstractions > 1 and not valid_rels:
                self._logger.warning("No valid relationships found in LLM response.")

            if num_abstractions > 1 and len(involved) < num_abstractions:
                missing_indices = set(range(num_abstractions)) - involved
                self._logger.warning(
                    "Relationship analysis may be incomplete. Abstractions not involved in any "
                    "valid reported relationship: %s",
                    sorted(missing_indices),
                )
            self._logger.info(f"Generated relationship summary and {len(valid_rels)} valid relationships.")
            return {"summary": str(relationships_data.get("summary", "No summary provided.")), "details": valid_rels}
        except ValidationFailure as e_val:
            self._logger.error("Validation failed for relationships: %s", e_val)
            if e_val.raw_output:
                module_logger.warning(
                    "Problematic YAML for relationships:\n%s", e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN]
                )
            return {"summary": "Validation error during relationship analysis.", "details": []}
        except (ValueError, TypeError, KeyError) as e_proc:
            self._logger.error("Error processing relationships: %s", e_proc, exc_info=True)
            return {"summary": "Processing error during relationship analysis.", "details": []}

    # --- UPDATED post method ---
    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: RelationshipsDict) -> None:
        """Update shared state with analyzed relationships.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from `prep` (unused).
            exec_res: Result from `exec` (dictionary of relationships), passed by
                      the flow runner.

        """
        if isinstance(exec_res, dict) and "summary" in exec_res and "details" in exec_res:
            shared["relationships"] = exec_res
            self._logger.info("Stored relationship analysis results.")
        else:
            self._logger.error(
                "Invalid exec_res type for relationships: %s. Storing empty structure.", type(exec_res).__name__
            )
            shared["relationships"] = {"summary": "Error or no data from analysis.", "details": []}


# End of src/sourcelens/nodes/analyze.py
