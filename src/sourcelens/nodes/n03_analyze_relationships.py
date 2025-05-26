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

"""Node responsible for analyzing relationships between identified abstractions using an LLM."""

import logging
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

from sourcelens.prompts import AbstractionPrompts
from sourcelens.utils.helpers import get_content_for_indices
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_dict

from .base_node import BaseNode, SLSharedContext  # Updated import

# Type Aliases with new naming convention
AbstractionItemInternal: TypeAlias = dict[str, Union[str, list[int]]]  # Internal consistency
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]

RelationshipDetail: TypeAlias = dict[str, Union[int, str]]
"""Type alias for a single relationship detail. Keys: 'from', 'to', 'label'."""

AnalyzeRelationshipsPreparedInputs: TypeAlias = dict[str, Any]
"""Type alias for the preparation result.
   Contains: 'num_abstractions', 'project_name', 'language', 'llm_config',
             'cache_config', 'context_str', 'abstraction_listing_str'.
"""
AnalyzeRelationshipsExecutionResult: TypeAlias = dict[str, Union[str, list[RelationshipDetail]]]
"""Type alias for the execution result. Keys: 'summary', 'details'."""


FileDataListInternal: TypeAlias = list[tuple[str, str]]  # Kept internal naming
RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]

module_logger: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500
DEFAULT_ERROR_SUMMARY: Final[str] = "Error during relationship analysis."

RELATIONSHIP_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from_abstraction": {"type": ["integer", "string", "number"]},
        "to_abstraction": {"type": ["integer", "string", "number"]},
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


class AnalyzeRelationships(BaseNode[AnalyzeRelationshipsPreparedInputs, AnalyzeRelationshipsExecutionResult]):
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
            A tuple (RelationshipDetail, set of involved indices) if valid, otherwise None.
        """
        try:
            from_entry_any: Any = rel_item.get("from_abstraction")
            to_entry_any: Any = rel_item.get("to_abstraction")
            label_val_any: Any = rel_item.get("label")

            # Ensure type compatibility with RawLLMIndexEntry
            from_entry: RawLLMIndexEntry = (
                from_entry_any
                if isinstance(from_entry_any, (str, int, float)) or from_entry_any is None
                else str(from_entry_any)
            )
            to_entry: RawLLMIndexEntry = (
                to_entry_any
                if isinstance(to_entry_any, (str, int, float)) or to_entry_any is None
                else str(to_entry_any)
            )

            from_idx_str: Optional[str] = None
            if isinstance(from_entry, (str, int, float)):  # Check if it's one of the expected types
                from_idx_str = str(from_entry).split("#", 1)[0].strip()

            to_idx_str: Optional[str] = None
            if isinstance(to_entry, (str, int, float)):  # Check if it's one of the expected types
                to_idx_str = str(to_entry).split("#", 1)[0].strip()

            from_idx: Optional[int] = int(from_idx_str) if from_idx_str and from_idx_str.isdigit() else None
            to_idx: Optional[int] = int(to_idx_str) if to_idx_str and to_idx_str.isdigit() else None
            label: Optional[str] = (
                str(label_val_any).strip() if isinstance(label_val_any, str) and label_val_any.strip() else None
            )

            if from_idx is None or to_idx is None or label is None:
                raise ValueError("Missing or invalid 'from_abstraction', 'to_abstraction', or 'label'.")
            if not (0 <= from_idx < num_abstractions and 0 <= to_idx < num_abstractions):
                msg = f"Relationship index out of range [0-{num_abstractions - 1}]: from={from_idx}, to={to_idx}."
                raise ValueError(msg)
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
            raw_rels_list: The raw list of relationship items from YAML.
            num_abstractions: Total number of abstractions for index validation.

        Returns:
            A tuple containing a list of validated `RelationshipDetail` and a set of involved indices.
        """
        validated_relationships: list[RelationshipDetail] = []
        involved_indices: set[int] = set()
        if not isinstance(raw_rels_list, list):
            module_logger.warning(
                "Expected 'relationships' field to be a list, got %s. Treating as empty.", type(raw_rels_list).__name__
            )
            return [], set()

        for rel_item_any in raw_rels_list:
            if not isinstance(rel_item_any, dict):
                module_logger.warning("Skipping non-dictionary relationship item: %s", rel_item_any)
                continue
            rel_item: dict[str, Any] = rel_item_any  # Type assertion
            parsed_result = self._parse_single_relationship(rel_item, num_abstractions)
            if parsed_result:
                validated_rel, involved = parsed_result
                validated_relationships.append(validated_rel)
                involved_indices.update(involved)
        return validated_relationships, involved_indices

    def _build_relationship_context(
        self, abstractions: AbstractionsListInternal, files_data: FileDataListInternal
    ) -> tuple[str, str]:
        """Build context string and abstraction listing for the LLM prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            files_data: List of (path, content) tuples for all project files.

        Returns:
            A tuple: (context_string, abstraction_listing_str).
        """
        context_builder: list[str] = ["Identified Abstractions:"]
        all_relevant_file_indices: set[int] = set()
        abstraction_info_for_prompt: list[str] = []

        for i, abstr in enumerate(abstractions):
            abstr_name = str(abstr.get("name", f"Unnamed Abstraction {i}"))
            abstr_desc = str(abstr.get("description", "N/A"))
            # Ensure file_indices is a list of ints
            file_indices_raw: Any = abstr.get("files", [])
            file_indices: list[int] = (
                [idx for idx in file_indices_raw if isinstance(idx, int)] if isinstance(file_indices_raw, list) else []
            )

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
                path_display = path_display_part1.replace("\\", "/")
                snippet_parts.append(f"--- File: {path_display} ---\n{content}")
            snippet_context = "\n\n".join(snippet_parts)
            context_builder.append(snippet_context)
        else:
            context_builder.append("No specific file content linked for relationship analysis based on abstractions.")
        return "\n".join(context_builder), "\n".join(abstraction_info_for_prompt)

    def pre_execution(self, shared_context: SLSharedContext) -> AnalyzeRelationshipsPreparedInputs:
        """Prepare context for relationship analysis LLM prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing all necessary context for the `execution` method.
        """
        self._log_info("Preparing context for relationship analysis...")
        abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
        llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
        project_name_any: Any = self._get_required_shared(shared_context, "project_name")
        language_any: Any = shared_context.get("language", "english")

        # Ensure types after retrieval
        abstractions: AbstractionsListInternal = abstractions_any if isinstance(abstractions_any, list) else []
        llm_config: dict[str, Any] = llm_config_any if isinstance(llm_config_any, dict) else {}
        cache_config: dict[str, Any] = cache_config_any if isinstance(cache_config_any, dict) else {}
        project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
        language: str = str(language_any)

        prepared_data: AnalyzeRelationshipsPreparedInputs = {
            "num_abstractions": len(abstractions),
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "context_str": "No abstractions to analyze.",
            "abstraction_listing_str": "N/A",
        }
        if not abstractions:
            self._log_warning("No abstractions provided for relationship analysis. Exec will produce default output.")
            return prepared_data

        files_data_any: Any = self._get_required_shared(shared_context, "files")
        files_data: FileDataListInternal = files_data_any if isinstance(files_data_any, list) else []
        context_str, abstraction_listing_str = self._build_relationship_context(abstractions, files_data)
        prepared_data["context_str"] = context_str
        prepared_data["abstraction_listing_str"] = abstraction_listing_str
        return prepared_data

    def _call_llm_and_validate_response(
        self, prompt: str, llm_config: dict[str, Any], cache_config: dict[str, Any]
    ) -> Optional[dict[str, Any]]:
        """Call the LLM and perform initial YAML validation for relationship data.

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
    ) -> AnalyzeRelationshipsExecutionResult:
        """Process validated YAML data to extract and refine relationship details.

        Args:
            relationships_data_yaml: The schema-validated dictionary from the LLM.
            num_abstractions: The total number of abstractions.

        Returns:
            An `AnalyzeRelationshipsExecutionResult` dictionary.
        """
        default_output: AnalyzeRelationshipsExecutionResult = {"summary": DEFAULT_ERROR_SUMMARY, "details": []}
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
                msg = (
                    "Relationship analysis may be incomplete. Abstractions not involved in any "
                    f"valid reported relationship (indices): {sorted(missing_indices)}"
                )
                self._log_warning(msg)
        self._log_info("Generated relationship summary and %d valid relationships.", len(valid_rels))
        return {"summary": summary_text, "details": valid_rels}

    def execution(self, prepared_inputs: AnalyzeRelationshipsPreparedInputs) -> AnalyzeRelationshipsExecutionResult:
        """Execute LLM call to analyze relationships, parse, and validate.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.

        Returns:
            A dictionary containing the relationship 'summary' and 'details'.
        """
        num_abstractions: int = prepared_inputs["num_abstractions"]
        project_name: str = prepared_inputs["project_name"]
        default_output: AnalyzeRelationshipsExecutionResult = {"summary": "Analysis not performed.", "details": []}

        if num_abstractions == 0:
            self._log_info("Skipping relationship analysis due to no abstractions.")
            default_output["summary"] = "No abstractions were available to analyze."
            return default_output

        prompt = AbstractionPrompts.format_analyze_relationships_prompt(
            project_name=project_name,
            context=prepared_inputs["context_str"],
            abstraction_listing=prepared_inputs["abstraction_listing_str"],
            num_abstractions=num_abstractions,
            language=prepared_inputs["language"],
        )

        llm_config: dict[str, Any] = prepared_inputs["llm_config"]
        cache_config: dict[str, Any] = prepared_inputs["cache_config"]
        validated_yaml_data: Optional[dict[str, Any]] = self._call_llm_and_validate_response(
            prompt, llm_config, cache_config
        )

        if validated_yaml_data is None:
            default_output["summary"] = "Failed to get valid relationship data from LLM."
            return default_output

        try:
            return self._process_validated_yaml_data(validated_yaml_data, num_abstractions)
        except (ValueError, TypeError, KeyError) as e_proc:  # Catch specific processing errors
            self._log_error("Critical error processing relationships from validated YAML: %s", e_proc, exc_info=True)
            default_output["summary"] = "Critical error processing relationship data after validation."
            return default_output

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: AnalyzeRelationshipsPreparedInputs,
        execution_outputs: AnalyzeRelationshipsExecutionResult,
    ) -> None:
        """Update shared context with analyzed relationships.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from the `pre_execution` phase (unused).
            execution_outputs: Dictionary of relationships from the `execution` phase.
        """
        del prepared_inputs  # Mark as unused
        shared_context["relationships"] = execution_outputs
        summary_snippet_raw: Any = execution_outputs.get("summary", "")
        summary_snippet: str = str(summary_snippet_raw)[:50]
        details_raw: Any = execution_outputs.get("details", [])
        # Ensure details_list is list[RelationshipDetail] if possible, or list[Any] for safety
        details_list: list[Any] = details_raw if isinstance(details_raw, list) else []

        details_count = len(details_list)
        self._log_info(
            "Stored relationship analysis results. Summary: '%s...', Details count: %d",
            summary_snippet,
            details_count,
        )


# End of src/sourcelens/nodes/n03_analyze_relationships.py
