# src/sourcelens/nodes/analyze.py

"""Nodes responsible for analyzing the codebase using an LLM.

This module contains nodes that leverage Large Language Models (LLMs) to
identify core conceptual abstractions within the fetched source code and
then to analyze the relationships and interactions between these identified
abstractions.
"""

import contextlib
import logging
from typing import Any, Final, Optional, TypeAlias, Union

from sourcelens.prompts import AbstractionPrompts
from sourcelens.utils.helpers import get_content_for_indices
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import (
    ValidationFailure,
    validate_yaml_dict,
    validate_yaml_list,
)

# Import BaseNode and SharedState type alias from base_node module
from .base_node import BaseNode, SLSharedState  # Corrected import for SLSharedState

# --- Type Aliases for IdentifyAbstractions ---
AbstractionItem: TypeAlias = dict[str, Union[str, list[int]]]
"""Type alias for a single identified abstraction after processing.
   Keys: 'name' (str), 'description' (str), 'files' (list[int] - validated indices).
"""
AbstractionsList: TypeAlias = list[AbstractionItem]
"""Type alias for the list of identified abstractions (execution result for IdentifyAbstractions)."""

IdentifyAbstractionsPrepResult: TypeAlias = dict[str, Any]
"""Type alias for the preparation result of IdentifyAbstractions node.
   Contains keys like 'context_str', 'file_listing_str', 'file_count',
   'project_name', 'language', 'llm_config', 'cache_config', 'files_data_ref'.
"""

# --- Type Aliases for AnalyzeRelationships ---
RelationshipDetail: TypeAlias = dict[str, Union[int, str]]
"""Type alias for a single relationship detail.
   Keys: 'from' (int), 'to' (int), 'label' (str).
"""
RelationshipsOutput: TypeAlias = dict[str, Union[str, list[RelationshipDetail]]]
"""Type alias for the execution result of AnalyzeRelationships node.
   Keys: 'summary' (str), 'details' (list[RelationshipDetail]).
"""
AnalyzeRelationshipsPrepResult: TypeAlias = dict[str, Any]
"""Type alias for the preparation result of AnalyzeRelationships node.
   Contains keys like 'num_abstractions', 'project_name', 'language',
   'llm_config', 'cache_config', 'context_str', 'abstraction_listing_str'.
"""


# Common Type Aliases used within this module
FileDataList: TypeAlias = list[tuple[str, str]]
PathToIndexMap: TypeAlias = dict[str, int]
RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]  # Index entry direct from LLM YAML

# Module-level logger
module_logger: logging.Logger = logging.getLogger(__name__)

# Constants
MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500
DEFAULT_ERROR_SUMMARY: Final[str] = "Error during analysis."

# Schemas
ABSTRACTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "file_indices": {"type": "array", "items": {"type": ["integer", "string", "number"]}},  # Allow number for float
    },
    "required": ["name", "description", "file_indices"],
    "additionalProperties": False,
}
RELATIONSHIP_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from_abstraction": {"type": ["integer", "string", "number"]},  # Allow number for float
        "to_abstraction": {"type": ["integer", "string", "number"]},  # Allow number for float
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


class IdentifyAbstractions(BaseNode[IdentifyAbstractionsPrepResult, AbstractionsList]):
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
        if "#" in entry_str:
            with contextlib.suppress(ValueError, IndexError):
                parsed_idx = int(entry_str.split("#", 1)[0].strip())

        if parsed_idx is None:
            with contextlib.suppress(ValueError):
                parsed_idx = int(entry_str.strip())

        if parsed_idx is None and entry_str in path_to_index_map:
            parsed_idx = path_to_index_map[entry_str]
        elif parsed_idx is None and not entry_str.strip().isdigit():
            module_logger.debug("Failed to parse index string or match path: '%s'", entry_str)
        return parsed_idx

    def _parse_single_index(
        self, idx_entry: RawLLMIndexEntry, path_to_index_map: PathToIndexMap, file_count: int
    ) -> Optional[int]:
        """Parse a single file index entry from the LLM response.

        Validates the type and range of the parsed index.

        Args:
            idx_entry: Raw entry from 'file_indices' list.
            path_to_index_map: Mapping from file paths to their integer index.
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
                module_logger.warning(
                    "Unexpected type '%s' for file index: '%s'. Ignoring entry.", type(idx_entry).__name__, idx_entry
                )
                return None

            if parsed_idx is not None and 0 <= parsed_idx < file_count:
                return parsed_idx
            if parsed_idx is not None:
                module_logger.warning(
                    "File index %d is out of valid range [0, %d). Ignoring index.", parsed_idx, file_count
                )
            return None
        except (ValueError, TypeError) as e:
            module_logger.warning("Could not parse file index entry '%s': %s. Ignoring.", idx_entry, e)
            return None

    def _parse_and_validate_indices(
        self,
        raw_indices: list[Any],  # LLM can return various types in the list
        path_to_index_map: PathToIndexMap,
        file_count: int,
        item_name: str,
    ) -> list[int]:
        """Parse and validate file indices from LLM response for one abstraction item.

        Args:
            raw_indices: List of items parsed from 'file_indices'.
            path_to_index_map: Mapping from file paths to their integer index.
            file_count: Total number of files for bounds checking.
            item_name: The name of the abstraction item for logging context.

        Returns:
            A sorted list of unique, valid integer file indices.

        """
        validated_indices: set[int] = set()
        if not isinstance(raw_indices, list):
            module_logger.warning(
                "Invalid type for 'file_indices' in abstraction '%s': Expected list, got %s. Treating as empty.",
                item_name,
                type(raw_indices).__name__,
            )
            return []

        for idx_entry_any in raw_indices:
            # Ensure idx_entry_any is of a type that _parse_single_index expects
            if not isinstance(idx_entry_any, (str, int, float)) and idx_entry_any is not None:
                module_logger.warning(
                    "Skipping invalid type in raw_indices for abstraction '%s': %s (type: %s)",
                    item_name,
                    idx_entry_any,
                    type(idx_entry_any).__name__,
                )
                continue
            idx_entry: RawLLMIndexEntry = idx_entry_any

            valid_idx = self._parse_single_index(idx_entry, path_to_index_map, file_count)
            if valid_idx is not None:
                validated_indices.add(valid_idx)

        if not validated_indices and raw_indices:
            module_logger.warning(
                "No valid file indices found or parsed for abstraction '%s'. Original raw_indices: %s",
                item_name,
                raw_indices,
            )
        return sorted(validated_indices)

    def prep(self, shared: SLSharedState) -> IdentifyAbstractionsPrepResult:
        """Prepare context and parameters for abstraction identification LLM prompt.

        Args:
            shared: The shared state dictionary, expected to contain 'files',
                    'project_name', 'llm_config', and 'cache_config'.
                    'language' is optional and defaults to 'english'.

        Returns:
            A dictionary containing all necessary context for the `exec` method,
            including formatted strings for the LLM prompt and references to
            configurations and original file data.

        """
        self._log_info("Preparing context for abstraction identification...")
        files_data: FileDataList = self._get_required_shared(shared, "files")
        project_name: str = self._get_required_shared(shared, "project_name")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        language: str = str(shared.get("language", "english"))

        context_list: list[str] = [
            f"--- File Index {i}: {path} ---\n{content}\n\n" for i, (path, content) in enumerate(files_data)
        ]
        file_info_for_prompt: list[str] = [f"- {i} # {path}" for i, (path, _) in enumerate(files_data)]

        return {
            "context_str": "".join(context_list),
            "file_listing_str": "\n".join(file_info_for_prompt),
            "file_count": len(files_data),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "files_data_ref": files_data,  # Reference for _process_raw_abstractions
        }

    def _process_raw_abstractions(
        self, raw_abstractions_list: list[Any], files_data_ref: FileDataList, file_count: int
    ) -> AbstractionsList:
        """Process and validate a list of raw abstraction items from LLM response.

        This method refines the initially parsed list of abstractions by
        specifically validating and converting the 'file_indices' field for
        each abstraction item.

        Args:
            raw_abstractions_list: List of items parsed from LLM's YAML response.
                                   These items are expected to have already passed
                                   the ABSTRACTION_ITEM_SCHEMA validation.
            files_data_ref: Original list of (path, content) tuples from `shared_state`,
                            used to map file paths to indices if necessary.
            file_count: Total number of files, for validating index ranges.

        Returns:
            A list of `AbstractionItem` dictionaries, where 'file_indices' key now
            contains a list of validated integer indices.

        """
        validated_abstractions: AbstractionsList = []
        path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data_ref)}

        for item_dict_any in raw_abstractions_list:
            if not isinstance(item_dict_any, dict):  # Should be caught by validate_yaml_list with item_schema
                module_logger.warning("Skipping non-dictionary item in raw_abstractions_list: %s", item_dict_any)
                continue
            item_dict: dict[str, Any] = item_dict_any

            item_name_raw: Any = item_dict.get("name", "Unknown Abstraction")
            item_desc_raw: Any = item_dict.get("description", "")
            item_name: str = str(item_name_raw).strip() if isinstance(item_name_raw, str) else "Unknown Abstraction"
            item_desc: str = str(item_desc_raw).strip() if isinstance(item_desc_raw, str) else ""

            raw_indices_list_val: Any = item_dict.get("file_indices", [])
            raw_indices_list = raw_indices_list_val if isinstance(raw_indices_list_val, list) else []

            unique_indices: list[int] = self._parse_and_validate_indices(
                raw_indices_list, path_to_index_map, file_count, item_name
            )
            processed_item: AbstractionItem = {
                "name": item_name,
                "description": item_desc,
                "files": unique_indices,
            }
            validated_abstractions.append(processed_item)
        return validated_abstractions

    def exec(self, prep_res: IdentifyAbstractionsPrepResult) -> AbstractionsList:
        """Execute LLM call, parse, and validate identified abstractions.

        Args:
            prep_res: The dictionary returned by the `prep` method, containing
                      all necessary context for the LLM call.

        Returns:
            A list of identified and validated abstraction dictionaries (`AbstractionsList`).
            Returns an empty list if the LLM call fails, YAML parsing/validation
            fails, or subsequent processing of abstractions fails.

        """
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]
        project_name: str = prep_res["project_name"]
        self._log_info("Identifying abstractions for '%s' using LLM...", project_name)

        prompt = AbstractionPrompts.format_identify_abstractions_prompt(
            project_name=project_name,
            context=prep_res["context_str"],
            file_listing=prep_res["file_listing_str"],
            language=prep_res["language"],
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed during abstraction identification: %s", e, exc_info=True)
            return []

        raw_abstractions_from_yaml: list[Any]  # Type from validate_yaml_list
        try:
            raw_abstractions_from_yaml = validate_yaml_list(response_text, ABSTRACTION_ITEM_SCHEMA)
        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for abstractions: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN:
                    snippet += "..."
                module_logger.warning("Problematic raw LLM output for abstractions:\n---\n%s\n---", snippet)
            return []

        try:
            # files_data_ref and file_count are present in prep_res
            validated_abstractions = self._process_raw_abstractions(
                raw_abstractions_from_yaml, prep_res["files_data_ref"], prep_res["file_count"]
            )
            if not validated_abstractions and raw_abstractions_from_yaml:
                self._log_warning(
                    "LLM parsed YAML for abstractions, but no valid items remained after processing file indices."
                )
            elif not validated_abstractions:
                self._log_warning("No valid abstractions found in LLM response or after processing.")
            else:
                self._log_info("Successfully processed %d abstractions.", len(validated_abstractions))
            return validated_abstractions
        except (ValueError, TypeError, KeyError) as e_proc:
            self._log_error("Error processing validated abstractions: %s", e_proc, exc_info=True)
            return []

    def post(self, shared: SLSharedState, prep_res: IdentifyAbstractionsPrepResult, exec_res: AbstractionsList) -> None:
        """Update the shared state with identified abstractions.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from the `prep` phase (unused in this method).
            exec_res: List of abstractions from the `exec` phase. This will be
                      an empty list if any preceding step failed.

        """
        del prep_res  # Mark prep_res as unused
        shared["abstractions"] = exec_res
        self._log_info("Stored %d abstractions in shared state.", len(exec_res))


class AnalyzeRelationships(BaseNode[AnalyzeRelationshipsPrepResult, RelationshipsOutput]):
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
            rel_item: A dictionary representing one relationship, expected to conform
                      to RELATIONSHIP_ITEM_SCHEMA after initial YAML validation.
            num_abstractions: Total number of abstractions for index validation.

        Returns:
            A tuple (RelationshipDetail, set of involved indices) if valid, otherwise None.
            RelationshipDetail contains 'from', 'to' (as int), and 'label' (as str).

        """
        try:
            from_entry_any: Any = rel_item.get("from_abstraction")
            to_entry_any: Any = rel_item.get("to_abstraction")
            label_val_any: Any = rel_item.get("label")

            from_entry: RawLLMIndexEntry = from_entry_any
            to_entry: RawLLMIndexEntry = to_entry_any

            from_idx_str: Optional[str] = None
            if isinstance(from_entry, (str, int, float)):  # float can be int-like
                from_idx_str = str(from_entry).split("#", 1)[0].strip()

            to_idx_str: Optional[str] = None
            if isinstance(to_entry, (str, int, float)):  # float can be int-like
                to_idx_str = str(to_entry).split("#", 1)[0].strip()

            from_idx: Optional[int] = int(from_idx_str) if from_idx_str and from_idx_str.isdigit() else None
            to_idx: Optional[int] = int(to_idx_str) if to_idx_str and to_idx_str.isdigit() else None
            label: Optional[str] = (
                str(label_val_any).strip() if isinstance(label_val_any, str) and label_val_any.strip() else None
            )

            if from_idx is None or to_idx is None or label is None:
                raise ValueError("Missing or invalid 'from_abstraction', 'to_abstraction', or 'label'.")
            if not (0 <= from_idx < num_abstractions and 0 <= to_idx < num_abstractions):
                raise ValueError(
                    f"Relationship index out of range [0-{num_abstractions - 1}]: from={from_idx}, to={to_idx}."
                )
            relationship_detail: RelationshipDetail = {"from": from_idx, "to": to_idx, "label": label}
            return relationship_detail, {from_idx, to_idx}
        except (ValueError, TypeError, AttributeError) as e:
            module_logger.warning("Could not parse relationship item: %s. Error: %s", rel_item, e)
            return None

    def _parse_and_validate_relationships(
        self, raw_rels_list: list[Any], num_abstractions: int
    ) -> tuple[list[RelationshipDetail], set[int]]:
        """Parse and validate the list of relationship details from LLM response.

        Args:
            raw_rels_list: The raw list of relationship items from YAML, where each item
                           is expected to be a dictionary (enforced by schema).
            num_abstractions: Total number of abstractions for index validation.

        Returns:
            A tuple containing:
                - A list of validated `RelationshipDetail` dictionaries.
                - A set of all abstraction indices involved in valid relationships.

        """
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            module_logger.warning(
                "Expected 'relationships' field to be a list, got %s. Treating as empty.", type(raw_rels_list).__name__
            )
            return [], set()

        for rel_item_any in raw_rels_list:
            if not isinstance(rel_item_any, dict):  # Should be guaranteed by RELATIONSHIP_ITEM_SCHEMA
                module_logger.warning("Skipping non-dictionary relationship item: %s", rel_item_any)
                continue
            rel_item: dict[str, Any] = rel_item_any
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)
        return validated_relationships, involved_indices

    def _build_relationship_context(self, abstractions: AbstractionsList, files_data: FileDataList) -> tuple[str, str]:
        """Build context string and abstraction listing for the LLM prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            files_data: List of (path, content) tuples for all project files.

        Returns:
            A tuple:
                - context_string (str): Formatted string with abstraction details
                                        and relevant code snippets.
                - abstraction_listing_str (str): Formatted string listing
                                                 "Index # Name" for abstractions.

        """
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_file_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []

        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed Abstraction {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            # 'files' in AbstractionItem is list[int]
            file_indices: list[int] = abstr.get("files", [])  # type: ignore[assignment]
            file_indices_str = ", ".join(map(str, file_indices)) if file_indices else "None"

            context_builder.append(f"- Index {i}: {abstr_name}\n  Desc: {abstr_desc}\n  Files: [{file_indices_str}]")
            abstraction_info_for_prompt.append(f"- {i} # {abstr_name}")
            all_relevant_file_indices.update(file_indices)

        context_builder.append("\nRelevant File Snippets (if any):")
        relevant_files_content_map = get_content_for_indices(files_data, sorted(all_relevant_file_indices))
        if relevant_files_content_map:
            snippet_parts: list[str] = []
            for idx_path, content in relevant_files_content_map.items():
                path_display_part1 = idx_path.split("# ", 1)[1] if "# " in idx_path else idx_path
                path_display = path_display_part1.replace(chr(92), "/")
                snippet_parts.append(f"--- File: {path_display} ---\n{content}")
            snippet_context = "\n\n".join(snippet_parts)
            context_builder.append(snippet_context)
        else:
            context_builder.append("No specific file content linked for relationship analysis based on abstractions.")
        return "\n".join(context_builder), "\n".join(abstraction_info_for_prompt)

    def prep(self, shared: SLSharedState) -> AnalyzeRelationshipsPrepResult:
        """Prepare context for relationship analysis LLM prompt.

        Args:
            shared: The shared state dictionary. Must contain 'abstractions',
                    'llm_config', 'cache_config', 'project_name', 'files'.
                    'language' is optional and defaults to 'english'.

        Returns:
            A dictionary containing all necessary context for the `exec` method.
            If no abstractions are found, relevant context fields will indicate this.

        """
        self._log_info("Preparing context for relationship analysis...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = str(shared.get("language", "english"))

        prep_data: AnalyzeRelationshipsPrepResult = {
            "num_abstractions": len(abstractions),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "context_str": "No abstractions to analyze.",  # Default
            "abstraction_listing_str": "N/A",  # Default
        }
        if not abstractions:
            self._log_warning("No abstractions provided for relationship analysis. Exec will produce default output.")
            return prep_data

        files_data: FileDataList = self._get_required_shared(shared, "files")
        context_str, abstraction_listing_str = self._build_relationship_context(abstractions, files_data)
        prep_data["context_str"] = context_str
        prep_data["abstraction_listing_str"] = abstraction_listing_str
        return prep_data

    def _call_llm_and_validate_response(
        self, prompt: str, llm_config: dict[str, Any], cache_config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Call the LLM and perform initial YAML validation for relationship data.

        This helper method encapsulates the LLM call and the subsequent validation
        of the raw response against the `RELATIONSHIPS_DICT_SCHEMA`.

        Args:
            prompt: The formatted prompt string for the LLM.
            llm_config: Configuration dictionary for the LLM API.
            cache_config: Configuration dictionary for LLM response caching.

        Returns:
            A dictionary parsed from the LLM's YAML response if successful and valid,
            otherwise None.

        """
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
            # validate_yaml_dict returns dict[str, Any] or raises ValidationFailure
            return validate_yaml_dict(response_text, RELATIONSHIPS_DICT_SCHEMA)
        except LlmApiError as e:
            self._log_error("LLM call failed for relationships: %s", e, exc_info=True)
            return None
        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for relationships: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN:
                    snippet += "..."
                module_logger.warning("Problematic YAML for relationships:\n%s", snippet)
            return None

    def _process_validated_yaml_data(
        self, relationships_data_yaml: Optional[dict[str, Any]], num_abstractions: int
    ) -> RelationshipsOutput:
        """Process validated YAML data to extract and refine relationship details.

        This helper method takes the schema-validated dictionary from the LLM,
        parses the individual relationship items, validates their indices,
        and formats the final output structure.

        Args:
            relationships_data_yaml: The schema-validated dictionary from the LLM,
                                     or None if prior steps failed.
            num_abstractions: The total number of abstractions, used for
                              validating relationship indices.

        Returns:
            A `RelationshipsOutput` dictionary containing the 'summary' and
            a list of processed 'details'.

        """
        default_output: RelationshipsOutput = {"summary": DEFAULT_ERROR_SUMMARY, "details": []}
        if not isinstance(relationships_data_yaml, dict):
            if relationships_data_yaml is not None:
                self._log_error(
                    "Invalid data type for relationships_data_yaml: expected dict or None, got %s",
                    type(relationships_data_yaml).__name__,
                )
            default_output["summary"] = "Failed to obtain or validate relationship data from LLM."
            return default_output

        raw_rels_list_val: Any = relationships_data_yaml.get("relationships", [])
        raw_rels_list = raw_rels_list_val if isinstance(raw_rels_list_val, list) else []
        valid_rels, involved_indices = self._parse_and_validate_relationships(raw_rels_list, num_abstractions)
        summary_text_raw: Any = relationships_data_yaml.get("summary", "No summary provided by LLM.")
        summary_text: str = str(summary_text_raw)

        if num_abstractions > 1 and not valid_rels and raw_rels_list:
            self._log_warning("Relationships parsed from LLM, but none were valid after processing.")
        elif num_abstractions > 1 and not valid_rels:
            self._log_warning("No valid relationships found in LLM response for a multi-abstraction project.")

        if num_abstractions > 1 and len(involved_indices) < num_abstractions:
            missing_indices = set(range(num_abstractions)) - involved_indices
            if missing_indices:
                self._log_warning(
                    "Relationship analysis may be incomplete. Abstractions not involved in any "
                    "valid reported relationship (indices): %s",
                    sorted(missing_indices),
                )
        self._log_info("Generated relationship summary and %d valid relationships.", len(valid_rels))
        return {"summary": summary_text, "details": valid_rels}

    def exec(self, prep_res: AnalyzeRelationshipsPrepResult) -> RelationshipsOutput:
        """Execute LLM call to analyze relationships, parse, and validate.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A dictionary containing the relationship 'summary' and 'details'.
            Returns a default error structure if any step fails.

        """
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        project_name: str = prep_res.get("project_name", "Unknown Project")
        default_output: RelationshipsOutput = {"summary": "Analysis not performed.", "details": []}

        if num_abstractions == 0:
            self._log_info("Skipping relationship analysis due to no abstractions.")
            default_output["summary"] = "No abstractions were available to analyze."
            return default_output

        prompt = AbstractionPrompts.format_analyze_relationships_prompt(
            project_name=project_name,
            context=prep_res["context_str"],
            abstraction_listing=prep_res["abstraction_listing_str"],
            num_abstractions=num_abstractions,
            language=prep_res["language"],
        )

        validated_yaml_data: Optional[dict[str, Any]] = self._call_llm_and_validate_response(
            prompt, prep_res["llm_config"], prep_res["cache_config"]
        )

        if validated_yaml_data is None:
            default_output["summary"] = "Failed to get valid relationship data from LLM."
            return default_output

        try:
            return self._process_validated_yaml_data(validated_yaml_data, num_abstractions)
        except (ValueError, TypeError, KeyError) as e_proc:
            self._log_error("Critical error processing relationships from validated YAML: %s", e_proc, exc_info=True)
            default_output["summary"] = "Critical error processing relationship data after validation."
            return default_output

    def post(
        self, shared: SLSharedState, prep_res: AnalyzeRelationshipsPrepResult, exec_res: RelationshipsOutput
    ) -> None:
        """Update shared state with analyzed relationships.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from the `prep` phase (unused in this method).
            exec_res: Dictionary of relationships from the `exec` phase. This will
                      contain an error summary if preceding steps failed.

        """
        del prep_res  # Mark as unused
        shared["relationships"] = exec_res
        summary_snippet_raw: Any = exec_res.get("summary", "")
        summary_snippet: str = str(summary_snippet_raw)[:50]
        details_raw: Any = exec_res.get("details", [])
        details_list: list[RelationshipDetail] = details_raw if isinstance(details_raw, list) else []
        details_count = len(details_list)
        self._log_info(
            "Stored relationship analysis results. Summary: '%s...', Details count: %d",
            summary_snippet,
            details_count,
        )


# End of src/sourcelens/nodes/analyze.py
