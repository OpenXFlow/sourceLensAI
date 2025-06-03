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

"""Node responsible for determining the logical order of tutorial chapters for web content."""

import contextlib
import logging
from typing import Any, Final, Union, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import WebContentConceptsList, WebContentRelationshipsDict
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from ..prompts.chapter_prompts import WebChapterPrompts

# Type Aliases
OrderWebChaptersPreparedInputs: TypeAlias = dict[str, Any]
WebChapterOrderList: TypeAlias = list[int]  # List of concept indices
OrderWebChaptersExecutionResult: TypeAlias = WebChapterOrderList


RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]
LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_order: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_ORDER: Final[int] = 500


class OrderWebChapters(BaseNode[OrderWebChaptersPreparedInputs, OrderWebChaptersExecutionResult]):
    """Determine the optimal chapter order for a web content summary/tutorial using an LLM.

    This node uses identified web concepts (derived from chunks) and their
    analyzed relationships to suggest a logical sequence for chapters.
    """

    def _parse_single_index_entry(self, entry: RawLLMIndexEntry, position: int) -> int:
        """Parse a single entry from the LLM's ordered list of concept indices.

        Args:
            entry: The raw entry from the YAML list.
            position: The zero-based position of the entry in the list, for error reporting.

        Returns:
            The parsed integer index.

        Raises:
            ValidationFailure: If the entry cannot be parsed into a valid integer index.
        """
        try:
            if isinstance(entry, int):
                return entry
            if isinstance(entry, str):
                stripped_entry = entry.strip()
                if "#" in stripped_entry:
                    with contextlib.suppress(ValueError, IndexError):
                        return int(stripped_entry.split("#", 1)[0].strip())
                with contextlib.suppress(ValueError):
                    return int(stripped_entry)
                raise ValidationFailure(f"String entry '{entry}' at pos {position} is not a valid int index.")
            if isinstance(entry, float):
                if entry.is_integer():
                    return int(entry)
                raise ValidationFailure(f"Float entry '{entry}' at pos {position} is not whole.")
            raise ValidationFailure(f"Unexpected entry type '{type(entry).__name__}' at pos {position}: '{entry}'.")
        except ValueError as e:
            raise ValidationFailure(f"Could not parse index at pos {position}: '{entry}'. Error: {e}") from e

    def _parse_and_validate_web_order(self, ordered_indices_raw: list[Any], num_concepts: int) -> WebChapterOrderList:
        """Parse and validate the chapter order list for web concepts from LLM response.

        Args:
            ordered_indices_raw: The raw list parsed from YAML by `validate_yaml_list`.
            num_concepts: The expected number of concepts/chapters.

        Returns:
            A validated list of integer indices for chapter order.

        Raises:
            ValidationFailure: If validation checks fail (e.g., wrong count, duplicates, out of range).
        """
        if not isinstance(ordered_indices_raw, list):
            raise ValidationFailure(f"Expected YAML list for chapter order, got {type(ordered_indices_raw).__name__}.")
        if len(ordered_indices_raw) != num_concepts:
            msg = f"Expected {num_concepts} indices for chapter order, got {len(ordered_indices_raw)}."
            raise ValidationFailure(msg)

        ordered_indices: WebChapterOrderList = []
        seen_indices: set[int] = set()
        for i, entry_any in enumerate(ordered_indices_raw):
            if not isinstance(entry_any, (str, int, float)) and entry_any is not None:
                raise ValidationFailure(
                    f"Invalid type in raw chapter order at pos {i}: {entry_any} (type: {type(entry_any).__name__})"
                )
            entry: RawLLMIndexEntry = entry_any

            parsed_idx = self._parse_single_index_entry(entry, i)
            if not (0 <= parsed_idx < num_concepts):
                msg = (
                    f"Invalid index {parsed_idx} at pos {i} for chapter order. "
                    f"Must be between 0 and {num_concepts - 1}."
                )
                raise ValidationFailure(msg)
            if parsed_idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {parsed_idx} found at pos {i} in chapter order.")
            ordered_indices.append(parsed_idx)
            seen_indices.add(parsed_idx)
        return ordered_indices

    def _build_web_chapters_context(
        self, concepts: WebContentConceptsList, relationships: WebContentRelationshipsDict
    ) -> tuple[str, str]:
        """Build concept listing and relationship summary for the order prompt.

        Args:
            concepts: List of identified web concept dictionaries.
                      Each should have 'name' and 'summary'.
            relationships: Dictionary of web relationship details.
                           Should have 'overall_summary'.

        Returns:
            A tuple containing:
                             - The string listing concepts with summaries.
                             - The string summarizing relationships.
        """
        concepts_listing_parts: list[str] = []
        for i, concept_item in enumerate(concepts):
            name = str(concept_item.get("name", f"Unnamed Concept {i}"))
            summary = str(concept_item.get("summary", "No summary."))
            concepts_listing_parts.append(f"{i}. {name} - Summary: {summary}")
        concepts_listing_str: str = "\n".join(concepts_listing_parts)

        relationships_summary_raw: Any = relationships.get("overall_summary", "No relationship summary available.")
        relationships_summary_str: str = str(relationships_summary_raw)

        return concepts_listing_str, relationships_summary_str

    def pre_execution(self, shared_context: SLSharedContext) -> OrderWebChaptersPreparedInputs:
        """Prepare context for the LLM web chapter ordering prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary for the `execution` method.
        """
        self._log_info("Preparing context for web chapter ordering...")
        try:
            text_concepts_any: Any = self._get_required_shared(shared_context, "text_concepts")
            text_relationships_any: Any = self._get_required_shared(shared_context, "text_relationships")
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            target_language_any: Any = shared_context.get("language", "english")

            text_concepts: WebContentConceptsList = (
                cast(WebContentConceptsList, text_concepts_any) if isinstance(text_concepts_any, list) else []
            )
            # Ensure concepts have the correct structure for _build_web_chapters_context
            valid_text_concepts: WebContentConceptsList = [
                item for item in text_concepts if isinstance(item, dict) and "name" in item and "summary" in item
            ]
            if len(valid_text_concepts) != len(text_concepts):
                self._log_warning("Some items in 'text_concepts' were invalid and filtered out.")

            text_relationships: WebContentRelationshipsDict = (
                cast(WebContentRelationshipsDict, text_relationships_any)
                if isinstance(text_relationships_any, dict)
                else {}
            )

            llm_config: LlmConfigDictTyped = (
                cast(LlmConfigDictTyped, llm_config_any) if isinstance(llm_config_any, dict) else {}
            )
            cache_config: CacheConfigDictTyped = (
                cast(CacheConfigDictTyped, cache_config_any) if isinstance(cache_config_any, dict) else {}
            )
            project_name: str = str(project_name_any)
            target_language: str = str(target_language_any)

        except ValueError as e_val:
            self._log_error("Pre-execution for OrderWebChapters failed (missing shared data): %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {str(e_val)}"}

        num_concepts = len(valid_text_concepts)
        prepared_data: OrderWebChaptersPreparedInputs = {
            "skip": not valid_text_concepts,
            "reason": "No web concepts provided for chapter ordering." if not valid_text_concepts else "",
            "num_concepts": num_concepts,
            "document_collection_name": project_name,
            "target_language": target_language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "concepts_listing_with_summaries": "",
            "relationships_summary": "",
        }

        if not valid_text_concepts:
            self._log_warning("No valid web concepts found. Chapter order cannot be determined by LLM.")
            return prepared_data

        concepts_listing_str, rels_summary_str = self._build_web_chapters_context(
            valid_text_concepts, text_relationships
        )
        prepared_data["concepts_listing_with_summaries"] = concepts_listing_str
        prepared_data["relationships_summary"] = rels_summary_str
        return prepared_data

    def execution(self, prepared_inputs: OrderWebChaptersPreparedInputs) -> OrderWebChaptersExecutionResult:
        """Call LLM to determine web chapter order and validate the response.

        Args:
            prepared_inputs: From `pre_execution`.

        Returns:
            A list of ordered concept indices.
            Returns empty list on failure or if skipped.
        """
        if prepared_inputs.get("skip", True):
            reason = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web chapter ordering execution. Reason: %s", reason)
            return []

        num_concepts: int = prepared_inputs["num_concepts"]
        if num_concepts == 0:  # Should have been caught by skip logic
            self._log_warning("Skipping web chapter ordering: No concepts were provided.")
            return []

        collection_name: str = prepared_inputs["document_collection_name"]
        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]

        self._log_info("Determining web chapter order for '%s' using LLM...", collection_name)
        prompt = WebChapterPrompts.format_order_web_chapters_prompt(
            document_collection_name=collection_name,
            concepts_listing_with_summaries=prepared_inputs["concepts_listing_with_summaries"],
            relationships_summary=prepared_inputs["relationships_summary"],  # Pass this along
            num_concepts=num_concepts,
            target_language=prepared_inputs["target_language"],
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e_llm:
            self._log_error("LLM call failed during web chapter ordering: %s", e_llm, exc_info=True)
            return []

        try:
            list_item_schema = {"type": ["integer", "string", "number"]}
            list_schema_validation = {
                "type": "array",
                "items": list_item_schema,
                "minItems": num_concepts,
                "maxItems": num_concepts,
            }
            ordered_indices_raw: list[Any] = validate_yaml_list(response_text, list_schema=list_schema_validation)
            ordered_indices = self._parse_and_validate_web_order(ordered_indices_raw, num_concepts)
            self._log_info("Determined valid web chapter order (indices): %s", ordered_indices)
            return ordered_indices
        except ValidationFailure as e_val:
            self._log_error("Validation failed processing web chapter order from LLM: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_ORDER]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_ORDER:
                    snippet += "..."
                module_logger_web_order.warning("Problematic YAML for web chapter order:\n%s", snippet)
            return []
        except (TypeError, ValueError) as e_proc:
            self._log_error("Unexpected error processing web chapter order: %s", e_proc, exc_info=True)
            return []

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: OrderWebChaptersPreparedInputs,
        execution_outputs: OrderWebChaptersExecutionResult,
    ) -> None:
        """Update the shared context with the determined web chapter order.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from `pre_execution`.
            execution_outputs: List of ordered concept indices.
        """
        del prepared_inputs
        shared_context["text_chapter_order"] = execution_outputs
        self._log_info("Stored web chapter order in shared_context['text_chapter_order']: %s", execution_outputs)


# End of src/FL02_web_crawling/nodes/n04_order_web_chapters.py
