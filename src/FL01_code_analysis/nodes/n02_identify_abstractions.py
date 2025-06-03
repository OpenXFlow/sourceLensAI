# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

"""Node responsible for identifying core abstractions from the codebase using an LLM."""

import contextlib
import logging
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import CodeAbstractionItem, CodeAbstractionsList, FilePathContentList
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from ..prompts.abstraction_prompts import AbstractionPrompts

IdentifyAbstractionsPreparedInputs: TypeAlias = dict[str, Any]
"""Type alias for the preparation result of IdentifyAbstractions node.
   Contains keys like 'context_str', 'file_listing_str', 'file_count',
   'project_name', 'language', 'llm_config', 'cache_config', 'files_data_ref'.
"""
IdentifyAbstractionsExecutionResult: TypeAlias = CodeAbstractionsList
"""Execution result is the list of identified abstractions."""


PathToIndexMap: TypeAlias = dict[str, int]
RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]

module_logger: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500

ABSTRACTION_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "description": {"type": "string", "minLength": 1},
        "file_indices": {"type": "array", "items": {"type": ["integer", "string", "number"]}},
    },
    "required": ["name", "description", "file_indices"],
    "additionalProperties": False,
}


class IdentifyAbstractions(BaseNode[IdentifyAbstractionsPreparedInputs, IdentifyAbstractionsExecutionResult]):
    """Identify core abstractions from the codebase using an LLM.

    This node takes the fetched file data, constructs a prompt for the LLM
    to identify key conceptual abstractions, calls the LLM, and then validates
    and processes the YAML response. The identified abstractions are stored
    in the shared context.
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
        raw_indices: list[Any],
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

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyAbstractionsPreparedInputs:
        """Prepare context and parameters for abstraction identification LLM prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing context for the `execution` method.
        """
        self._log_info("Preparing context for abstraction identification...")
        files_data_any: Any = self._get_required_shared(shared_context, "files")
        project_name_any: Any = self._get_required_shared(shared_context, "project_name")
        llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
        language_any: Any = shared_context.get("language", "english")

        files_data: FilePathContentList = files_data_any if isinstance(files_data_any, list) else []
        project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
        llm_config: dict[str, Any] = llm_config_any if isinstance(llm_config_any, dict) else {}
        cache_config: dict[str, Any] = cache_config_any if isinstance(cache_config_any, dict) else {}
        language: str = str(language_any)

        context_list: list[str] = [
            f"--- File Index {i}: {path} ---\n{content}\n\n" for i, (path, content) in enumerate(files_data)
        ]
        file_info_for_prompt: list[str] = [f"- {i} # {path}" for i, (path, _) in enumerate(files_data)]

        prepared_inputs: IdentifyAbstractionsPreparedInputs = {
            "context_str": "".join(context_list),
            "file_listing_str": "\n".join(file_info_for_prompt),
            "file_count": len(files_data),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "files_data_ref": files_data,
        }
        return prepared_inputs

    def _process_raw_abstractions(
        self, raw_abstractions_list: list[Any], files_data_ref: FilePathContentList, file_count: int
    ) -> CodeAbstractionsList:
        """Process and validate a list of raw abstraction items from LLM response.

        Args:
            raw_abstractions_list: List of items parsed from LLM's YAML response.
            files_data_ref: Original list of (path, content) tuples from `shared_context`.
            file_count: Total number of files, for validating index ranges.

        Returns:
            A list of `CodeAbstractionItem` dictionaries.
        """
        validated_abstractions: CodeAbstractionsList = []
        path_to_index_map: PathToIndexMap = {path: i for i, (path, _) in enumerate(files_data_ref)}

        for item_dict_any in raw_abstractions_list:
            if not isinstance(item_dict_any, dict):
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
            processed_item: CodeAbstractionItem = {
                "name": item_name,
                "description": item_desc,
                "files": unique_indices,
            }
            validated_abstractions.append(processed_item)
        return validated_abstractions

    def execution(self, prepared_inputs: IdentifyAbstractionsPreparedInputs) -> IdentifyAbstractionsExecutionResult:
        """Execute LLM call, parse, and validate identified abstractions.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.

        Returns:
            A list of identified and validated abstraction dictionaries.
            Returns an empty list if the LLM call fails or validation fails.
        """
        llm_config: dict[str, Any] = prepared_inputs["llm_config"]
        cache_config: dict[str, Any] = prepared_inputs["cache_config"]
        project_name: str = prepared_inputs["project_name"]
        self._log_info("Identifying abstractions for '%s' using LLM...", project_name)

        prompt = AbstractionPrompts.format_identify_abstractions_prompt(
            project_name=project_name,
            context=prepared_inputs["context_str"],
            file_listing=prepared_inputs["file_listing_str"],
            language=prepared_inputs["language"],
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed during abstraction identification: %s", e, exc_info=True)
            return []

        raw_abstractions_from_yaml: list[Any]
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
            files_data_ref: FilePathContentList = prepared_inputs["files_data_ref"]
            file_count: int = prepared_inputs["file_count"]
            validated_abstractions = self._process_raw_abstractions(
                raw_abstractions_from_yaml, files_data_ref, file_count
            )
            if not validated_abstractions and raw_abstractions_from_yaml:
                log_msg = "LLM parsed YAML for abstractions, but no valid items remained after processing file indices."
                self._log_warning(log_msg)
            elif not validated_abstractions:
                self._log_warning("No valid abstractions found in LLM response or after processing.")
            else:
                self._log_info("Successfully processed %d abstractions.", len(validated_abstractions))
            return validated_abstractions
        except (ValueError, TypeError, KeyError) as e_proc:
            self._log_error("Error processing validated abstractions: %s", e_proc, exc_info=True)
            return []

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: IdentifyAbstractionsPreparedInputs,
        execution_outputs: IdentifyAbstractionsExecutionResult,
    ) -> None:
        """Update the shared context with identified abstractions.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from the `pre_execution` phase (unused here).
            execution_outputs: List of abstractions from the `execution` phase.
        """
        del prepared_inputs
        shared_context["abstractions"] = execution_outputs
        self._log_info("Stored %d abstractions in shared context.", len(execution_outputs))


# End of src/FL01_code_analysis/nodes/n02_identify_abstractions.py
