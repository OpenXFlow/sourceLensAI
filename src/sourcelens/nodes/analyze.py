# src/sourcelens/nodes/analyze.py

"""Nodes responsible for analyzing the codebase using an LLM."""

import logging

# Import Mapping from collections.abc for type hints
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
RawIndexEntry: TypeAlias = Union[str, int, float, None]

logger = logging.getLogger(__name__)

# --- Schemas for LLM Output Validation ---
ABSTRACTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        # Ensure name and description are required and are strings
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "file_indices": {
            "type": "array",
            "items": {"type": ["integer", "string"]},  # Allow string representation of index
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
    """Identify core abstractions from the codebase using an LLM."""

    def _parse_single_index(
        self, idx_entry: RawIndexEntry, path_to_index_map: PathToIndexMap, file_count: int
    ) -> Optional[int]:
        """Parse a single file index entry from the LLM response."""
        # ... (Implementation remains the same) ...
        parsed_idx: Optional[int] = None
        try:
            if isinstance(idx_entry, int):
                parsed_idx = idx_entry
            elif isinstance(idx_entry, str):
                entry_str = idx_entry.strip()
                if "#" in entry_str:
                    try:
                        parsed_idx = int(entry_str.split("#", 1)[0].strip())
                    except (ValueError, IndexError):
                        pass
                if parsed_idx is None:
                    try:
                        parsed_idx = int(entry_str)
                    except ValueError:
                        if entry_str in path_to_index_map:
                            parsed_idx = path_to_index_map[entry_str]
                        else:
                            logger.debug("Failed parse/match index str: '%s'", entry_str)
            elif isinstance(idx_entry, float) and idx_entry.is_integer():
                parsed_idx = int(idx_entry)
            elif idx_entry is None:
                return None  # Skip None values silently now
            else:
                logger.warning("Unexpected type '%s' for index: '%s'.", type(idx_entry).__name__, idx_entry)
                return None
            if parsed_idx is not None:
                if 0 <= parsed_idx < file_count:
                    return parsed_idx
                logger.warning("Index %d out of range [0, %d).", parsed_idx, file_count)
                return None
        except (ValueError, TypeError) as e:
            logger.warning("Could not parse index '%s': %s.", idx_entry, e)
        return None

    def _parse_and_validate_indices(
        self, raw_indices: list[Any], path_to_index_map: PathToIndexMap, file_count: int, item_name: str
    ) -> list[int]:
        """Parse and validate file indices from LLM response for one item."""
        # ... (Implementation remains the same) ...
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
        return sorted(validated_indices)

    def prep(self, shared: SharedState) -> dict[str, Any]:
        """Prepare the context and parameters needed for the LLM prompt.

        Parameters
        ----------
        shared : SharedState
            The shared state containing data required for preparation.

        Returns
        -------
        dict[str, Any]
            A dictionary containing the prepared context and parameters.

        """
        # ... (Implementation remains the same) ...
        self._log_info("Preparing context for abstraction identification...")
        files_data: FileData = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        language: str = shared.get("language", "english")
        context_list: list[str] = []
        file_info: list[tuple[int, str]] = []
        for i, (path, content) in enumerate(files_data):
            entry = f"--- File Index {i}: {path} ---\n{content}\n\n"
            context_list.append(entry)
            file_info.append((i, path))
        context = "".join(context_list)
        file_listing_for_prompt = "\n".join([f"- {idx} # {path}" for idx, path in file_info])
        return {
            "context": context,
            "file_listing": file_listing_for_prompt,
            "file_count": len(files_data),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "files_data": files_data,
        }

    def exec(self, prep_res: dict[str, Any]) -> AbstractionsList:
        """Execute the core logic: call LLM, parse, validate abstractions."""
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
            # If LLM call itself fails after retries, return empty list to allow flow continuation
            # This prevents crashing the entire process for transient API issues
            return []  # Allow continuation

        # --- MODIFIED: Wrap validation/parsing in try/except ---
        try:
            raw_abstractions = validate_yaml_list(raw_llm_output=response, item_schema=ABSTRACTION_ITEM_SCHEMA)
        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for abstractions: %s", e_val)
            if e_val.raw_output:
                MAX_SNIPPET_LENGTH = 500
                snippet = e_val.raw_output[:MAX_SNIPPET_LENGTH] + (
                    "..." if len(e_val.raw_output) > MAX_SNIPPET_LENGTH else ""
                )
                logger.warning("Problematic raw LLM output snippet:\n---\n%s\n---", snippet)
            return []  # Return empty on validation/parsing failure

        # --- Processing valid YAML (if validation passed) ---
        try:
            validated_abstractions: AbstractionsList = []
            path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data)}

            for item in raw_abstractions:  # raw_abstractions is now guaranteed to be a list
                item_name = item.get("name")
                item_desc = item.get("description")
                raw_indices_list = item.get("file_indices", [])
                if not item_name or not item_desc:
                    logger.warning("Skip abstraction missing name/desc: %s", item)
                    continue
                if not isinstance(raw_indices_list, list):
                    logger.warning("Indices not list for '%s'.", item_name)
                    raw_indices_list = []
                unique_indices = self._parse_and_validate_indices(
                    raw_indices_list, path_to_index_map, file_count, str(item_name)
                )
                validated_abstractions.append(
                    {"name": str(item_name), "description": str(item_desc), "files": unique_indices}
                )

            if not validated_abstractions and raw_abstractions:
                self._log_warning("LLM response parsed, but no valid abstractions remained after processing.")
            elif not validated_abstractions:
                self._log_warning("No valid abstractions found in LLM response (potentially filtered by schema).")

            self._log_info(f"Successfully processed {len(validated_abstractions)} abstractions.")
            return validated_abstractions

        except Exception as e_proc:  # Catch other unexpected processing errors AFTER validation
            self._log_error("Unexpected error processing validated abstractions: %s", e_proc, exc=e_proc)
            return []  # Return empty on internal processing error

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: AbstractionsList) -> None:
        """Update the shared state with the identified abstractions."""
        # ... (Implementation remains the same) ...
        if isinstance(exec_res, list):
            shared["abstractions"] = exec_res
            self._log_info(f"Stored {len(exec_res)} abstractions.")
        else:
            self._log_error("Invalid exec result: %s. Storing empty.", type(exec_res).__name__)
            shared["abstractions"] = []


# --- AnalyzeRelationships Node (remains the same) ---
class AnalyzeRelationships(BaseNode):
    """Analyze relationships between identified abstractions using an LLM."""

    def _parse_single_relationship(
        self, rel_item: dict[str, Any], num_abstractions: int
    ) -> Optional[tuple[RelationshipDetail, set[int]]]:
        # ...
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
                raise ValueError(f"Index out of range: {from_idx}, {to_idx}.")
            validated_rel: RelationshipDetail = {"from": from_idx, "to": to_idx, "label": label}
            involved: set[int] = {from_idx, to_idx}
            return validated_rel, involved
        except (ValueError, TypeError, KeyError, AttributeError) as e:
            logger.warning("Could not parse relationship: %s. Error: %s.", rel_item, e)
            return None

    def _parse_and_validate_relationships(
        self, raw_rels_list: list[Any], num_abstractions: int
    ) -> tuple[list[RelationshipDetail], set[int]]:
        # ...
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            logger.warning("Expected list, got %s.", type(raw_rels_list).__name__)
            return [], set()
        for rel_item in raw_rels_list:
            if not isinstance(rel_item, dict):
                logger.warning("Skipping non-dict: %s", rel_item)
                continue
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)
        return validated_relationships, involved_indices

    def prep(self, shared: SharedState) -> dict[str, Any]:
        # ...
        self._log_info("Preparing context for relationship analysis...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        files_data: FileData = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = shared.get("language", "english")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        num_abstractions = len(abstractions)
        if num_abstractions == 0:
            self._log_warning("No abstractions found.")
            return {"num_abstractions": 0}
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []
        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            file_indices = [idx for idx in abstr.get("files", []) if isinstance(idx, int)]
            file_indices_str = ", ".join(map(str, file_indices)) if file_indices else "None"
            info_line = f"- Index {i}: {abstr_name}\n  Desc: {abstr_desc}\n  Files: [{file_indices_str}]"
            context_builder.append(info_line)
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
        }

    def exec(self, prep_res: dict[str, Any]) -> RelationshipsDict:
        """Execute the core logic for analyzing relationships.

        Parameters
        ----------
        prep_res : dict[str, Any]
            The prepared context and parameters needed for the analysis.

        Returns
        -------
        RelationshipsDict
            A dictionary containing the summary and details of the analyzed relationships.

        Raises
        ------
        ValidationFailure
            If validation of the LLM response fails or no valid relationships are found.

        """
        # ...
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        project_name: str = prep_res.get("project_name", "Unknown Project")
        if num_abstractions == 0:
            return {"summary": "No abstractions identified.", "details": []}
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
                logger.error("Schema structure error.")
                raise ValidationFailure("Internal schema error.")
            relationships_data = validate_yaml_dict(raw_llm_output=response, dict_schema=current_dict_schema)
            raw_rels_list = relationships_data.get("relationships", [])
            validated_rels, involved = self._parse_and_validate_relationships(raw_rels_list, num_abstractions)
            if num_abstractions > 1:
                missing = set(range(num_abstractions)) - involved
            if missing:
                logger.warning("Relationship analysis incomplete. Missing: %s", sorted(missing))
            if not validated_rels and num_abstractions > 1:
                raise ValidationFailure("No valid relationships found.")
            self._log_info("Generated summary and %d valid relationships.", len(validated_rels))
            return {"summary": relationships_data["summary"], "details": validated_rels}
        except ValidationFailure as e:
            self._log_error("Validation failed processing relationships: %s", e)
            raise
        except Exception as e:
            self._log_error("Unexpected error processing relationships: %s", e, exc=e)
            raise ValidationFailure(f"Unexpected processing error: {e}") from e

    def post(self, shared: SharedState, prep_res: dict[str, Any], exec_res: RelationshipsDict) -> None:
        """Update the shared state with the analyzed relationships.

        Parameters
        ----------
        shared : SharedState
            The shared state to be updated with the relationships data.
        prep_res : dict[str, Any]
            The prepared context and parameters used for the analysis.
        exec_res : RelationshipsDict
            The results of the relationship analysis to be stored in the shared state.

        """
        # ...
        if isinstance(exec_res, dict):
            shared["relationships"] = exec_res
            self._log_info("Stored relationship analysis results.")
        else:
            self._log_error("Invalid exec result: %s. Storing error.", type(exec_res).__name__)
            shared["relationships"] = {"summary": "Error.", "details": []}


# End of src/sourcelens/nodes/analyze.py
