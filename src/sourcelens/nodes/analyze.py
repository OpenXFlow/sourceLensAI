# src/sourcelens/nodes/analyze.py

"""Nodes responsible for analyzing the codebase using an LLM."""

import contextlib  # For SIM105
import logging
from typing import Any, Final, Optional, TypeAlias, Union

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

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500  # For PLR2004

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
    """Identify core abstractions from the codebase using an LLM."""

    def _try_parse_index_from_string(self, entry_str: str, path_to_index_map: PathToIndexMap) -> Optional[int]:
        """Attempt to parse an integer index from a string entry.

        Handles formats like "idx # comment" or just "idx" or a file path.

        Args:
            entry_str: The string entry to parse.
            path_to_index_map: Mapping from file paths to their index.

        Returns:
            The parsed integer index if successful, otherwise None.

        """
        parsed_idx: Optional[int] = None
        # SIM105 Fix: Use contextlib.suppress
        if "#" in entry_str:
            with contextlib.suppress(ValueError, IndexError):
                parsed_idx = int(entry_str.split("#", 1)[0].strip())

        if parsed_idx is None:  # Check if still None after attempting to parse with comment
            with contextlib.suppress(ValueError):
                parsed_idx = int(entry_str)

        if parsed_idx is None and entry_str in path_to_index_map:  # Check path map if other parsing failed
            parsed_idx = path_to_index_map[entry_str]
        elif parsed_idx is None and entry_str not in path_to_index_map and not entry_str.isdigit():
            # Log only if it's not a simple number string and not in path map
            logger.debug("Failed to parse index string or match path: '%s'", entry_str)
        return parsed_idx

    def _parse_single_index(
        self, idx_entry: RawIndexEntry, path_to_index_map: PathToIndexMap, file_count: int
    ) -> Optional[int]:
        """Parse a single file index entry from the LLM response.

        Args:
            idx_entry: Raw entry from 'file_indices' list.
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
                parsed_idx = self._try_parse_index_from_string(idx_entry.strip(), path_to_index_map)
            elif isinstance(idx_entry, float) and idx_entry.is_integer():
                parsed_idx = int(idx_entry)
            elif idx_entry is None:
                return None
            else:
                logger.warning("Unexpected type '%s' for index: '%s'.", type(idx_entry).__name__, idx_entry)
                return None

            if parsed_idx is not None and 0 <= parsed_idx < file_count:
                return parsed_idx
            if parsed_idx is not None:
                logger.warning("Index %d out of range [0, %d).", parsed_idx, file_count)
            return None
        except (ValueError, TypeError) as e:
            logger.warning("Could not parse index entry '%s': %s.", idx_entry, e)
            return None

    def _parse_and_validate_indices(
        self, raw_indices: list[Any], path_to_index_map: PathToIndexMap, file_count: int, item_name: str
    ) -> list[int]:
        """Parse and validate file indices from LLM response for one item."""
        validated_indices: set[int] = set()
        if not isinstance(raw_indices, list):
            logger.warning("Invalid type for 'file_indices' in '%s': %s.", item_name, type(raw_indices).__name__)
            return []
        for idx_entry in raw_indices:
            valid_idx = self._parse_single_index(idx_entry, path_to_index_map, file_count)
            if valid_idx is not None:
                validated_indices.add(valid_idx)
        if not validated_indices:
            logger.warning("No valid indices found/parsed for '%s'.", item_name)
        return sorted(validated_indices)  # C414 Fix: No list() needed for set

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare context and parameters for abstraction identification LLM prompt.

        Args:
            shared: The shared state dictionary.

        Returns:
            A dictionary with context, file listing, counts, and configs for `exec`.

        Raises:
            ValueError: If required keys are missing from `shared`.

        """
        self._log_info("Preparing context for abstraction identification...")
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
            "files_data": files_data,
        }

    def _process_raw_abstractions(
        self, raw_abstractions: list[Any], files_data: FileData, file_count: int
    ) -> AbstractionsList:
        """Process and validate a list of raw abstraction items.

        Args:
            raw_abstractions: List of items parsed from LLM's YAML response.
            files_data: Original list of (path, content) tuples.
            file_count: Total number of files.

        Returns:
            A list of validated abstraction dictionaries.

        """
        validated_abstractions: AbstractionsList = []
        path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data)}
        for item in raw_abstractions:
            item_name = item.get("name")
            item_desc = item.get("description")
            raw_indices_list = item.get("file_indices", [])
            if not (isinstance(item_name, str) and item_name and isinstance(item_desc, str) and item_desc):
                logger.warning("Skip abstraction missing/invalid name/desc: %s", item)
                continue
            if not isinstance(raw_indices_list, list):
                logger.warning("File indices for '%s' not list.", item_name)
                raw_indices_list = []
            unique_indices = self._parse_and_validate_indices(
                raw_indices_list, path_to_index_map, file_count, item_name
            )
            validated_abstractions.append({"name": item_name, "description": item_desc, "files": unique_indices})
        return validated_abstractions

    def exec(self, prep_res: dict[str, Any]) -> AbstractionsList:
        """Execute LLM call, parse, and validate identified abstractions.

        Args:
            prep_res: Dictionary from the `prep` method.

        Returns:
            A list of validated abstraction dictionaries, or an empty list on failure.

        """
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        project_name: str = prep_res["project_name"]
        self._log_info(f"Identifying abstractions for '{project_name}' using LLM...")
        prompt = AbstractionPrompts.format_identify_abstractions_prompt(
            project_name=project_name,
            context=prep_res["context"],
            file_listing=prep_res["file_listing"],
            language=prep_res["language"],
        )
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed: %s", e, exc=e)
            return []
        try:
            raw_abstractions = validate_yaml_list(response, ABSTRACTION_ITEM_SCHEMA)
        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for abstractions: %s", e_val)
            if e_val.raw_output:  # PLR2004 Fix: Use constant
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN] + (
                    "..." if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN else ""
                )
                logger.warning("Problematic raw LLM output:\n---\n%s\n---", snippet)
            return []
        try:
            validated_abstractions = self._process_raw_abstractions(
                raw_abstractions, prep_res["files_data"], prep_res["file_count"]
            )
            if not validated_abstractions and raw_abstractions:
                self._log_warning("LLM parsed, but no valid abstractions remained.")
            elif not validated_abstractions:
                self._log_warning("No valid abstractions in LLM response.")
            else:
                self._log_info(f"Successfully processed {len(validated_abstractions)} abstractions.")
            return validated_abstractions
        except (ValueError, TypeError) as e_proc:  # Catching specific exceptions
            self._log_error("Error processing validated abstractions: %s", e_proc, exc=e_proc)
            return []

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: AbstractionsList) -> None:
        """Update the shared state with identified abstractions.

        Args:
            shared: The shared state dictionary.
            prep_res: Result from `prep` (unused).
            exec_res: Result from `exec` (list of abstractions).

        """
        if isinstance(exec_res, list):
            shared["abstractions"] = exec_res
            self._log_info(f"Stored {len(exec_res)} abstractions.")
        else:
            self._log_error("Invalid exec result type: %s.", type(exec_res).__name__)
            shared["abstractions"] = []


class AnalyzeRelationships(BaseNode):
    """Analyze relationships between identified abstractions using an LLM."""

    def _parse_single_relationship(
        self, rel_item: dict[str, Any], num_abstractions: int
    ) -> Optional[tuple[RelationshipDetail, set[int]]]:
        """Parse and validate a single relationship item from LLM response."""
        try:
            from_entry = rel_item.get("from_abstraction")
            to_entry = rel_item.get("to_abstraction")
            label = rel_item.get("label")
            from_idx = (
                int(str(from_entry).split("#", 1)[0].strip()) if isinstance(from_entry, (str, int, float)) else None
            )
            to_idx = int(str(to_entry).split("#", 1)[0].strip()) if isinstance(to_entry, (str, int, float)) else None
            if from_idx is None or to_idx is None or not isinstance(label, str) or not label.strip():
                raise ValueError("Missing/invalid from/to or label.")
            if not (0 <= from_idx < num_abstractions and 0 <= to_idx < num_abstractions):
                raise ValueError(f"Index out of range: {from_idx}, {to_idx}.")
            return {"from": from_idx, "to": to_idx, "label": label.strip()}, {from_idx, to_idx}
        except (ValueError, TypeError, KeyError, AttributeError) as e:  # PLE1206 Fix: Pass all format args
            logger.warning("Could not parse relationship. Item: %s. Error: %s", rel_item, e)
            return None

    def _parse_and_validate_relationships(
        self, raw_rels_list: list[Any], num_abstractions: int
    ) -> tuple[list[RelationshipDetail], set[int]]:
        """Parse and validate the list of relationship details."""
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            logger.warning("Expected list for relationships, got %s.", type(raw_rels_list).__name__)
            return [], set()
        for rel_item in raw_rels_list:
            if not isinstance(rel_item, dict):
                logger.warning("Skipping non-dict rel item: %s", rel_item)
                continue
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)
        return validated_relationships, involved_indices

    def _build_relationship_context(self, abstractions: AbstractionsList, files_data: FileData) -> tuple[str, str]:
        """Build context string and abstraction listing for the LLM prompt."""
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []
        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            file_indices = [idx for idx in abstr.get("files", []) if isinstance(idx, int)]
            file_indices_str = ", ".join(map(str, file_indices)) if file_indices else "None"
            context_builder.append(f"- Index {i}: {abstr_name}\n  Desc: {abstr_desc}\n  Files: [{file_indices_str}]")
            abstraction_info_for_prompt.append(f"- {i} # {abstr_name}")
            all_relevant_indices.update(file_indices)
        context_builder.append("\nRelevant File Snippets:")
        relevant_files_content_map = get_content_for_indices(files_data, sorted(all_relevant_indices))  # C414 Fix
        if relevant_files_content_map:
            snippet_context = "\n\n".join(
                f"--- File: {idx_path.split('# ', 1)[1] if '# ' in idx_path else idx_path} ---\n{content}"
                for idx_path, content in relevant_files_content_map.items()
            )
            context_builder.append(snippet_context)
        else:
            context_builder.append("No specific file content linked.")
        return "\n".join(context_builder), "\n".join(abstraction_info_for_prompt)

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare context for relationship analysis LLM prompt."""
        self._log_info("Preparing context for relationship analysis...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = shared.get("language", "english")
        if not abstractions:
            self._log_warning("No abstractions for relationship analysis.")
            return {
                "num_abstractions": 0,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": project_name,
                "language": language,
                "context": "",
                "abstraction_listing": "",
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
            return {"summary": "No abstractions to analyze.", "details": []}
        language: str = prep_res["language"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        self._log_info(f"Analyzing relationships for '{project_name}' using LLM...")
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
            self._log_error("LLM call failed for relationships: %s", e, exc=e)
            return {"summary": "LLM API Error.", "details": []}
        try:
            schema = RELATIONSHIPS_DICT_SCHEMA.copy()
            properties = schema.get("properties")
            # PGH003 Fix: More specific ignore or check type
            if isinstance(properties, dict) and isinstance(properties.get("relationships"), dict):
                properties["relationships"]["minItems"] = 1 if num_abstractions > 1 else 0
            else:
                logger.error("Schema structure error.")
                raise ValidationFailure("Internal schema error.")
            relationships_data = validate_yaml_dict(response, schema)
            raw_rels = relationships_data.get("relationships", [])
            if not isinstance(raw_rels, list):
                raw_rels = []
            valid_rels, involved = self._parse_and_validate_relationships(raw_rels, num_abstractions)
            if num_abstractions > 1 and not valid_rels:
                self._log_warning("No valid relationships found.")
            elif num_abstractions > 1 and len(involved) < num_abstractions:
                missing_indices = set(range(num_abstractions)) - involved
                self._log_warning("Relationship analysis incomplete. Missing: %s", sorted(missing_indices))  # C414 Fix
            self._log_info(f"Generated summary and {len(valid_rels)} relationships.")
            return {"summary": str(relationships_data.get("summary", "")), "details": valid_rels}
        except ValidationFailure as e_val:
            self._log_error("Validation failed for relationships: %s", e_val)
            if e_val.raw_output:
                logger.warning(
                    "Problematic YAML for relationships:\n%s", e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN]
                )  # PLR2004 Fix
            return {"summary": "Validation error.", "details": []}
        except (ValueError, TypeError, KeyError) as e_proc:  # Catch specific exceptions
            self._log_error("Error processing relationships: %s", e_proc, exc=e_proc)
            return {"summary": "Processing error.", "details": []}

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: RelationshipsDict) -> None:
        """Update shared state with analyzed relationships."""
        if isinstance(exec_res, dict) and "summary" in exec_res and "details" in exec_res:
            shared["relationships"] = exec_res
            self._log_info("Stored relationship analysis results.")
        else:
            self._log_error("Invalid exec result for relationships: %s.", type(exec_res).__name__)
            shared["relationships"] = {"summary": "Error or no data.", "details": []}


# End of src/sourcelens/nodes/analyze.py
