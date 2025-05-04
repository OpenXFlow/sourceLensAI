# src/sourcelens/nodes/analyze.py

"""Nodes responsible for analyzing the codebase using an LLM."""

import logging
from typing import Any, Optional, TypeAlias, Union

from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import (
    format_analyze_relationships_prompt,
    format_identify_abstractions_prompt,
)
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
# Refining Any - Expecting primarily these types from YAML parse
RawIndexEntry: TypeAlias = Union[str, int, float, None]

logger = logging.getLogger(__name__)

# --- Schemas for LLM Output Validation ---
ABSTRACTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "file_indices": {
            "type": "array",
            "items": {"type": ["integer", "string"]},
        },
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
        "relationships": {
            "type": "array",
            "items": RELATIONSHIP_ITEM_SCHEMA,
            # minItems set dynamically in exec
        },
    },
    "required": ["summary", "relationships"],
    "additionalProperties": False,
}


# --- IdentifyAbstractions Node ---


class IdentifyAbstractions(BaseNode):
    """Identify core abstractions from the codebase using an LLM.

    Prepares context, prompts LLM (using centralized prompt function),
    parses YAML response, validates structure, and stores the results.
    """

    # C901, PLR0912: Complexity/Branches remain high - requires deeper refactoring.
    def _parse_single_index(  # noqa: C901, PLR0912
        self, idx_entry: RawIndexEntry, path_to_index_map: PathToIndexMap, file_count: int
    ) -> Optional[int]:
        """Parse a single file index entry from the LLM response.

        Args:
            idx_entry: Raw entry from 'file_indices' list (int, str, float, None).
            path_to_index_map: Mapping from file paths to their index.
            file_count: Total number of files for bounds checking.

        Returns:
            Parsed integer index if valid and within bounds, otherwise None.

        """
        parsed_idx: Optional[int] = None
        try:
            if isinstance(idx_entry, int):
                parsed_idx = idx_entry
            elif isinstance(idx_entry, str):
                entry_str = idx_entry.strip()
                if "#" in entry_str:
                    # Use contextlib.suppress for concise error ignoring
                    # if the goal is just to try the next parsing method.
                    # Here, 'pass' is okay as we check parsed_idx later.
                    try:
                        parsed_idx = int(entry_str.split("#", 1)[0].strip())
                    except (ValueError, IndexError):
                        # If split fails, could be a path with '#' or just an index
                        pass  # Fall through
                if parsed_idx is None:  # Only try parsing as int if '#' parse failed or wasn't present
                    try:
                        parsed_idx = int(entry_str)
                    except ValueError:  # If not an int string, check if it's a path
                        if entry_str in path_to_index_map:
                            parsed_idx = path_to_index_map[entry_str]
                        else:
                            logger.debug("Failed parse index string or match path: '%s'", entry_str)
            elif isinstance(idx_entry, float) and idx_entry.is_integer():
                parsed_idx = int(idx_entry)
            elif idx_entry is None:
                logger.debug("Skipping None value in file_indices.")
                return None
            else:
                # Log unexpected type but don't raise error, return None
                logger.warning(
                    "Unexpected type '%s' for index entry '%s'. Skipping.", type(idx_entry).__name__, idx_entry
                )
                return None

            # Validate bounds if parsing was successful
            if parsed_idx is not None:
                if 0 <= parsed_idx < file_count:
                    return parsed_idx
                logger.warning("Index %d out of range [0, %d).", parsed_idx, file_count)
                return None  # Out of bounds

        except (ValueError, TypeError) as e:
            # Catch potential errors during int() conversion
            logger.warning("Could not parse index entry '%s': %s.", idx_entry, e)

        return None  # Return None if any parsing step failed

    def _parse_and_validate_indices(
        self, raw_indices: list[Any], path_to_index_map: PathToIndexMap, file_count: int, item_name: str
    ) -> list[int]:
        """Parse and validate file indices from LLM response for one abstraction item.

        Args:
            raw_indices: The raw 'file_indices' list from the parsed YAML item.
            path_to_index_map: A mapping from file paths to their index.
            file_count: The total number of files for bounds checking.
            item_name: The name of the abstraction item for logging context.

        Returns:
            A sorted list of unique, valid integer file indices.

        """
        validated_indices: set[int] = set()
        if not isinstance(raw_indices, list):
            logger.warning(
                "Invalid type for 'file_indices' in '%s': %s. Skipping.", item_name, type(raw_indices).__name__
            )
            return []

        for idx_entry in raw_indices:
            valid_idx = self._parse_single_index(idx_entry, path_to_index_map, file_count)
            if valid_idx is not None:
                validated_indices.add(valid_idx)

        if not validated_indices:
            logger.warning("No valid file indices found/parsed for '%s'.", item_name)

        return sorted(validated_indices)

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare the context and parameters needed for the LLM prompt.

        Args:
            shared: The shared state dictionary.

        Returns:
            A dictionary containing context, file listing, counts, configurations,
            and other data required for the `exec` step.

        Raises:
            ValueError: If required keys are missing from the shared state.

        """
        self._log_info("Preparing context for abstraction identification...")
        # Retrieve required data
        files_data: FileData = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        language: str = shared.get("language", "english")

        # Build context string and file info list
        context_list: list[str] = []
        file_info: list[tuple[int, str]] = []
        for i, (path, content) in enumerate(files_data):
            entry = f"--- File Index {i}: {path} ---\n{content}\n\n"
            context_list.append(entry)
            file_info.append((i, path))

        context = "".join(context_list)
        file_listing_for_prompt = "\n".join([f"- {idx} # {path}" for idx, path in file_info])

        # Return prepared data dictionary
        prep_data = {
            "context": context,
            "file_listing": file_listing_for_prompt,
            "file_count": len(files_data),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "files_data": files_data,  # Keep original data for path mapping
        }
        return prep_data

    def exec(self, prep_res: dict[str, Any]) -> AbstractionsList:
        """Execute the core logic: call LLM, parse, validate, and return abstractions.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A list of validated abstraction dictionaries.

        Raises:
            LlmApiError: If the LLM API call fails after retries.
            ValidationFailure: If the LLM response cannot be parsed, validated,
                               or yields no valid abstractions.

        """
        # Extract data from prep_res
        context: str = prep_res["context"]
        file_listing: str = prep_res["file_listing"]
        file_count: int = prep_res["file_count"]
        project_name: str = prep_res["project_name"]
        language: str = prep_res["language"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        files_data: FileData = prep_res["files_data"]

        self._log_info(f"Identifying abstractions for '{project_name}' using LLM...")
        prompt = format_identify_abstractions_prompt(
            project_name=project_name, context=context, file_listing=file_listing, language=language
        )

        response: str
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed for abstractions: %s", e, exc=e)
            raise

        try:
            # Parse and validate the list of abstractions from LLM response
            raw_abstractions = validate_yaml_list(raw_llm_output=response, item_schema=ABSTRACTION_ITEM_SCHEMA)

            validated_abstractions: AbstractionsList = []
            path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data)}

            # Process each raw abstraction item
            for item in raw_abstractions:
                item_name = item.get("name")
                item_desc = item.get("description")
                raw_indices_list = item.get("file_indices", [])

                # Basic check for required fields (though schema should cover this)
                if not item_name or not item_desc:
                    logger.warning("Skipping abstraction missing name/description: %s", item)
                    continue

                # Ensure indices list is actually a list
                if not isinstance(raw_indices_list, list):
                    logger.warning("Indices for '%s' not a list, setting empty.", item_name)
                    raw_indices_list = []

                unique_indices = self._parse_and_validate_indices(
                    raw_indices_list, path_to_index_map, file_count, str(item_name)
                )
                # Append validated item
                validated_abstractions.append(
                    {
                        "name": str(item_name),  # Ensure string type
                        "description": str(item_desc),  # Ensure string type
                        "files": unique_indices,
                    }
                )

            # Check if any valid abstractions were found
            if not validated_abstractions:
                raise ValidationFailure("No valid abstractions found in LLM response.")

            self._log_info(f"Identified and validated {len(validated_abstractions)} abstractions.")
            return validated_abstractions

        except ValidationFailure as e:
            # Log and re-raise specific validation errors
            self._log_error("Validation failed processing abstractions: %s", e)
            raise
        except Exception as e:
            # Log and wrap unexpected errors
            self._log_error("Unexpected error processing abstractions: %s", e, exc=e)
            raise ValidationFailure(f"Unexpected processing error: {e}") from e

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: AbstractionsList) -> None:
        """Update the shared state with the identified abstractions.

        Args:
            shared: The shared state dictionary.
            prep_res: The dictionary returned by `prep` (unused here).
            exec_res: The list of abstractions returned by `exec`.

        """
        if isinstance(exec_res, list):
            shared["abstractions"] = exec_res
            self._log_info(f"Stored {len(exec_res)} abstractions.")
        else:
            self._log_error("Invalid exec result: %s. Storing empty.", type(exec_res).__name__)
            shared["abstractions"] = []


# --- AnalyzeRelationships Node ---


class AnalyzeRelationships(BaseNode):
    """Analyze relationships between identified abstractions using an LLM.

    Prompts LLM based on abstractions/code (using centralized prompt function),
    parses/validates YAML response, stores results.
    """

    def _parse_single_relationship(
        self, rel_item: dict[str, Any], num_abstractions: int
    ) -> Optional[tuple[RelationshipDetail, set[int]]]:
        """Parse and validate a single relationship item from the LLM response.

        Args:
            rel_item: The dictionary representing a single relationship.
            num_abstractions: The total number of abstractions for index validation.

        Returns:
            A tuple containing (validated_relationship_dict, involved_indices_set)
            if parsing and validation succeed, otherwise None.

        """
        # --- Implementation remains the same ---
        try:
            from_entry = rel_item.get("from_abstraction")
            from_idx: int
            if isinstance(from_entry, int):
                from_idx = from_entry
            elif isinstance(from_entry, str):
                from_idx = int(from_entry.split("#", 1)[0].strip())
            else:
                from_idx = int(str(from_entry).strip())
            to_entry = rel_item.get("to_abstraction")
            to_idx: int
            if isinstance(to_entry, int):
                to_idx = to_entry
            elif isinstance(to_entry, str):
                to_idx = int(to_entry.split("#", 1)[0].strip())
            else:
                to_idx = int(str(to_entry).strip())
            label = rel_item.get("label")
            if not isinstance(label, str) or not label.strip():
                raise ValueError("Missing 'label'.")
            label = label.strip()
            if not (0 <= from_idx < num_abstractions and 0 <= to_idx < num_abstractions):
                raise ValueError(f"Index out of range: from={from_idx}, to={to_idx}.")  # noqa E501
            validated_rel: RelationshipDetail = {"from": from_idx, "to": to_idx, "label": label}
            involved: set[int] = {from_idx, to_idx}  # noqa E701 E702
            return validated_rel, involved
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.warning("Could not parse relationship: %s. Error: %s.", rel_item, e)
            return None  # noqa E701 E702
        # --- End of unchanged _parse_single_relationship ---

    def _parse_and_validate_relationships(
        self, raw_rels_list: list[Any], num_abstractions: int
    ) -> tuple[list[RelationshipDetail], set[int]]:
        """Parse and validate the list of relationship details from LLM response.

        Args:
            raw_rels_list: The raw list from the 'relationships' key.
            num_abstractions: The total number of abstractions for index validation.

        Returns:
            A tuple: (list of validated relationships, set of involved indices).

        """
        # --- Implementation remains the same ---
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            logger.warning("Expected list, got %s.", type(raw_rels_list).__name__)
            return [], set()  # noqa E701 E702
        for rel_item in raw_rels_list:
            if not isinstance(rel_item, dict):
                logger.warning("Skipping non-dict: %s", rel_item)
                continue  # noqa E701 E702
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)  # noqa E701 E702
        return validated_relationships, involved_indices
        # --- End of unchanged _parse_and_validate_relationships ---

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare context for relationship analysis prompt.

        Args:
            shared: The shared state dictionary.

        Returns:
            A dictionary containing context, counts, configuration, etc., for `exec`.

        Raises:
            ValueError: If required keys are missing from the shared state.

        """
        # --- Implementation remains the same ---
        self._log_info("Preparing context for relationship analysis...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        files_data: FileData = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = shared.get("language", "english")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")  # noqa E701 E702 E501
        num_abstractions = len(abstractions)
        if num_abstractions == 0:
            self._log_warning("No abstractions found.")
            return {"num_abstractions": 0}
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []  # noqa E701 E702
        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            file_indices = [idx for idx in abstr.get("files", []) if isinstance(idx, int)]
            file_indices_str = ", ".join(map(str, file_indices)) if file_indices else "None"
            info_line = f"- Index {i}: {abstr_name}\n  Desc: {abstr_desc}\n  Files: [{file_indices_str}]"
            context_builder.append(info_line)
            abstraction_info_for_prompt.append(f"- {i} # {abstr_name}")
            all_relevant_indices.update(file_indices)  # noqa E701 E702 E501
        context_builder.append("\nRelevant File Snippets:")
        relevant_files_content_map = get_content_for_indices(files_data, sorted(all_relevant_indices))
        if relevant_files_content_map:
            snippet_context = "\n\n".join(
                f"--- File: {idx_path.split('# ', 1)[1] if '# ' in idx_path else idx_path} ---\n{content}"
                for idx_path, content in relevant_files_content_map.items()
            )
            context_builder.append(snippet_context)  # noqa E701 E501
        else:
            context_builder.append("No specific file content linked.")
        context_str = "\n".join(context_builder)
        abstraction_listing_str = "\n".join(abstraction_info_for_prompt)
        return {
            "context": context_str,
            "abstraction_listing": abstraction_listing_str,
            "num_abstractions": num_abstractions,
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }  # noqa E501
        # --- End of unchanged prep ---

    def exec(self, prep_res: dict[str, Any]) -> RelationshipsDict:
        """Execute the relationship analysis: call LLM, parse, validate response.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A dictionary (RelationshipsDict) containing results.

        Raises:
            LlmApiError: If the LLM API call fails.
            ValidationFailure: If the LLM response fails validation.

        """
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        project_name: str = prep_res.get("project_name", "Unknown Project")

        if num_abstractions == 0:
            return {"summary": "No abstractions identified.", "details": []}

        # Extract needed vars
        context: str = prep_res["context"]
        abstraction_listing: str = prep_res["abstraction_listing"]
        language: str = prep_res["language"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info(f"Analyzing relationships for '{project_name}' using LLM...")
        prompt = format_analyze_relationships_prompt(
            project_name=project_name,
            context=context,
            abstraction_listing=abstraction_listing,
            num_abstractions=num_abstractions,
            language=language,
        )

        response: str
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed for relationships: %s", e, exc=e)
            raise

        try:
            current_dict_schema = RELATIONSHIPS_DICT_SCHEMA.copy()
            min_rels = 1 if num_abstractions > 1 else 0
            if "properties" in current_dict_schema and "relationships" in current_dict_schema.get("properties", {}):
                current_dict_schema["properties"]["relationships"]["minItems"] = min_rels
            else:
                logger.error("Base RELATIONSHIPS_DICT_SCHEMA structure error.")
                raise ValidationFailure("Internal schema definition error.")

            relationships_data = validate_yaml_dict(raw_llm_output=response, dict_schema=current_dict_schema)
            raw_rels_list = relationships_data.get("relationships", [])
            validated_rels, involved = self._parse_and_validate_relationships(raw_rels_list, num_abstractions)

            # Check coverage and validity
            if num_abstractions > 1:
                missing = set(range(num_abstractions)) - involved
                if missing:
                    logger.warning("Relationship analysis incomplete. Missing: %s", sorted(missing))  # noqa E701
            if not validated_rels and num_abstractions > 1:
                raise ValidationFailure("No valid relationships found.")  # noqa E701

            self._log_info("Generated summary and %d valid relationships.", len(validated_rels))
            return {"summary": relationships_data["summary"], "details": validated_rels}

        except ValidationFailure as e:
            self._log_error("Validation failed processing relationships: %s", e)
            raise
        except Exception as e:
            self._log_error("Unexpected error processing relationships: %s", e, exc=e)
            raise ValidationFailure(f"Unexpected processing error: {e}") from e

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: RelationshipsDict) -> None:
        """Update the shared state with the analyzed relationships and summary.

        Args:
            shared: The shared state dictionary.
            prep_res: The dictionary returned by `prep` (unused here).
            exec_res: The dictionary containing relationship results from `exec`.

        """
        # --- Implementation remains the same ---
        if isinstance(exec_res, dict):
            shared["relationships"] = exec_res
            self._log_info("Stored relationship analysis results.")
        else:
            self._log_error("Invalid exec result: %s. Storing error.", type(exec_res).__name__)
            shared["relationships"] = {"summary": "Error.", "details": []}
        # --- End of unchanged post ---


# End of src/sourcelens/nodes/analyze.py
