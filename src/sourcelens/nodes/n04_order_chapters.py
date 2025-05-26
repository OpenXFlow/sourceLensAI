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

"""Node responsible for determining the logical order of tutorial chapters.

This node uses an LLM to analyze identified code abstractions and their
relationships to suggest a pedagogical sequence for the tutorial chapters.
"""

import contextlib
import logging
from typing import Any, Final, Union

from typing_extensions import TypeAlias

from sourcelens.prompts import ChapterPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from .base_node import BaseNode, SLSharedContext  # Updated import

# Renamed Type Aliases
OrderChaptersPreparedInputs: TypeAlias = dict[str, Any]
"""Result of the pre-execution phase: context for LLM, including number of abstractions."""
ChapterOrderList: TypeAlias = list[int]
"""Type alias for a list of integer indices representing chapter order."""
OrderChaptersExecutionResult: TypeAlias = ChapterOrderList
"""Result of the execution phase: the ordered list of chapter indices."""

# Internal type consistency
AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
RelationshipDetailInternal: TypeAlias = dict[str, Any]
RelationshipsDictInternal: TypeAlias = dict[str, Union[str, list[RelationshipDetailInternal]]]

RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500


class OrderChapters(BaseNode[OrderChaptersPreparedInputs, OrderChaptersExecutionResult]):
    """Determine the optimal chapter order for the tutorial using an LLM.

    This node takes the list of identified code abstractions and their analyzed
    relationships as input. It constructs a prompt for an LLM, asking it
    to suggest a logical sequence for these abstractions, which forms the
    basis of the tutorial's chapter order. The LLM's YAML response (a list
    of abstraction indices) is validated for correctness.
    """

    def _parse_single_index_entry(self, entry: RawLLMIndexEntry, position: int) -> int:
        """Parse a single entry from the LLM's ordered list of indices.

        Args:
            entry: The raw entry from the YAML list.
            position: The zero-based position of the entry in the list.

        Returns:
            The parsed integer index.

        Raises:
            ValidationFailure: If the entry cannot be parsed.
        """
        try:
            if isinstance(entry, int):
                return entry
            if isinstance(entry, str):
                stripped_entry = entry.strip()
                if "#" in stripped_entry:  # Allows for comments like "0 # Chapter Name"
                    with contextlib.suppress(ValueError, IndexError):
                        return int(stripped_entry.split("#", 1)[0].strip())
                with contextlib.suppress(ValueError):  # Try parsing the whole stripped string as int
                    return int(stripped_entry)
                raise ValidationFailure(  # If all attempts fail
                    f"String entry '{entry}' at position {position} is not a valid integer index representation."
                )
            if isinstance(entry, float):
                if entry.is_integer():
                    return int(entry)
                raise ValidationFailure(f"Float entry '{entry}' at position {position} is not a whole number.")
            # If entry is None or any other type not handled above
            raise ValidationFailure(
                f"Unexpected entry type '{type(entry).__name__}' at position {position}: '{entry}'. "
                "Expected int, str, or float."
            )
        except ValueError as e:  # Catch ValueError from int() specifically
            raise ValidationFailure(
                f"Could not parse index at position {position}: '{entry}'. Original error: {e}"
            ) from e
        # Removed broad Exception catch for BLE001, specific errors handled

    def _parse_and_validate_order(self, ordered_indices_raw: list[Any], num_abstractions: int) -> ChapterOrderList:
        """Parse and validate the chapter order list from LLM response.

        Args:
            ordered_indices_raw: The raw list parsed from YAML.
            num_abstractions: The expected number of chapters/abstractions.

        Returns:
            A validated list of integer indices representing the chapter order.

        Raises:
            ValidationFailure: If validation checks fail.
        """
        if not isinstance(ordered_indices_raw, list):
            raise ValidationFailure(f"Expected YAML list for chapter order, got {type(ordered_indices_raw).__name__}.")
        if len(ordered_indices_raw) != num_abstractions:
            msg = f"Expected {num_abstractions} indices for chapter order, got {len(ordered_indices_raw)}."
            raise ValidationFailure(msg)

        ordered_indices: ChapterOrderList = []
        seen_indices: set[int] = set()
        for i, entry_any in enumerate(ordered_indices_raw):
            # Ensure entry is of a type that _parse_single_index_entry can handle
            if not isinstance(entry_any, (str, int, float)) and entry_any is not None:
                raise ValidationFailure(
                    f"Invalid type in raw chapter order at position {i}: {entry_any} (type: {type(entry_any).__name__})"
                )
            entry: RawLLMIndexEntry = entry_any  # Type assertion

            parsed_idx = self._parse_single_index_entry(entry, i)
            if not (0 <= parsed_idx < num_abstractions):
                msg = (
                    f"Invalid index {parsed_idx} at position {i} for chapter order. "
                    f"Must be between 0 and {num_abstractions - 1}."
                )
                raise ValidationFailure(msg)
            if parsed_idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {parsed_idx} found at position {i} in chapter order.")
            ordered_indices.append(parsed_idx)
            seen_indices.add(parsed_idx)
        return ordered_indices

    def _build_order_chapters_context(
        self, abstractions: AbstractionsListInternal, relationships: RelationshipsDictInternal, language: str
    ) -> tuple[str, str, str]:
        """Build context string, abstraction listing, and language note for prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            relationships: Dictionary of relationship details.
            language: The target language for the tutorial.

        Returns:
            A tuple: (abstraction_listing_str, context_str, list_lang_note_str).
        """
        abstraction_info_parts: list[str] = []
        for i, abstr_item in enumerate(abstractions):
            name_val_any: Any = abstr_item.get("name", f"Unnamed Abstraction {i}")
            name_val: str = str(name_val_any)
            abstraction_info_parts.append(f"- {i} # {name_val}")
        abstraction_listing_str: str = "\n".join(abstraction_info_parts)

        list_lang_note_str = f" (Names in {language.capitalize()})" if language.lower() != "english" else ""
        summary_lang_note = f" (Summary/labels in {language.capitalize()})" if language.lower() != "english" else ""

        summary_raw_any: Any = relationships.get("summary", "N/A")
        summary: str = str(summary_raw_any if summary_raw_any is not None else "N/A")

        context_parts: list[str] = [
            f"Project Summary{summary_lang_note}:\n{summary}\n",
            "Relationships (Indices refer to abstractions above):",
        ]

        rel_details_raw_any: Any = relationships.get("details", [])
        rel_details_list_any: list[Any] = rel_details_raw_any if isinstance(rel_details_raw_any, list) else []
        num_abstractions = len(abstractions)

        for rel_any in rel_details_list_any:
            if not isinstance(rel_any, dict):
                module_logger.warning("Skipping non-dictionary item in relationship details: %s", rel_any)
                continue
            rel: RelationshipDetailInternal = rel_any  # Type assertion

            from_idx_val_any: Any = rel.get("from")
            to_idx_val_any: Any = rel.get("to")
            label_raw_any: Any = rel.get("label", "interacts")
            label: str = str(label_raw_any or "interacts")

            if (
                isinstance(from_idx_val_any, int)
                and 0 <= from_idx_val_any < num_abstractions
                and isinstance(to_idx_val_any, int)
                and 0 <= to_idx_val_any < num_abstractions
            ):
                from_idx: int = from_idx_val_any
                to_idx: int = to_idx_val_any
                from_name_val_any: Any = abstractions[from_idx].get("name", f"Idx {from_idx}")
                to_name_val_any: Any = abstractions[to_idx].get("name", f"Idx {to_idx}")
                from_name: str = str(from_name_val_any)
                to_name: str = str(to_name_val_any)
                context_parts.append(f"- From {from_idx} ({from_name}) to {to_idx} ({to_name}): {label}")
            else:
                module_logger.warning("Skipping relationship with invalid/missing indices: %s", rel)
        context_str: str = "\n".join(context_parts)
        return abstraction_listing_str, context_str, list_lang_note_str

    def pre_execution(self, shared_context: SLSharedContext) -> OrderChaptersPreparedInputs:
        """Prepare context for the LLM chapter ordering prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A `OrderChaptersPreparedInputs` dictionary for the `execution` method.
        """
        self._log_info("Preparing context for chapter ordering...")
        abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
        llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
        project_name_any: Any = self._get_required_shared(shared_context, "project_name")
        language_any: Any = shared_context.get("language", "english")

        # Type assertions after retrieval
        abstractions: AbstractionsListInternal = abstractions_any if isinstance(abstractions_any, list) else []
        llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
        cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
        project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
        language: str = str(language_any) if isinstance(language_any, str) else "english"

        num_abstractions = len(abstractions)
        prepared_data: OrderChaptersPreparedInputs = {
            "num_abstractions": num_abstractions,
            "project_name": project_name,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "abstraction_listing_str": "",
            "context_str": "",
            "list_lang_note_str": "",
        }

        if not abstractions:
            self._log_warning("No abstractions found. Chapter order cannot be determined by LLM.")
            return prepared_data

        relationships_any: Any = self._get_required_shared(shared_context, "relationships")
        relationships: RelationshipsDictInternal = relationships_any if isinstance(relationships_any, dict) else {}

        abstraction_listing, context_str, list_lang_note = self._build_order_chapters_context(
            abstractions, relationships, language
        )
        prepared_data["abstraction_listing_str"] = abstraction_listing
        prepared_data["context_str"] = context_str
        prepared_data["list_lang_note_str"] = list_lang_note
        return prepared_data

    def execution(self, prepared_inputs: OrderChaptersPreparedInputs) -> OrderChaptersExecutionResult:
        """Call LLM to determine chapter order and validate the response.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.

        Returns:
            A `ChapterOrderList`. Returns empty list on failure or if no abstractions.
        """
        num_abstractions: int = prepared_inputs.get("num_abstractions", 0)
        if num_abstractions == 0:
            self._log_warning("Skipping chapter ordering execution: No abstractions were provided.")
            return []

        project_name: str = prepared_inputs["project_name"]
        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]  # type: ignore[assignment]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]  # type: ignore[assignment]
        abstraction_listing_str: str = prepared_inputs["abstraction_listing_str"]
        context_str_val: str = prepared_inputs["context_str"]
        list_lang_note_val: str = prepared_inputs["list_lang_note_str"]

        self._log_info("Determining chapter order for '%s' using LLM...", project_name)
        prompt = ChapterPrompts.format_order_chapters_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing_str,
            context=context_str_val,
            num_abstractions=num_abstractions,
            list_lang_note=list_lang_note_val,
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed during chapter ordering: %s", e, exc_info=True)
            return []  # Return empty list on LLM error

        try:
            list_item_schema = {"type": ["integer", "string", "number"]}  # Schema for each item in the list
            list_schema_validation = {  # Schema for the list itself
                "type": "array",
                "items": list_item_schema,
                "minItems": num_abstractions,  # Must contain all abstractions
                "maxItems": num_abstractions,  # Exactly all abstractions
            }
            ordered_indices_raw: list[Any] = validate_yaml_list(response_text, list_schema=list_schema_validation)
            ordered_indices = self._parse_and_validate_order(ordered_indices_raw, num_abstractions)
            self._log_info("Determined valid chapter order (indices): %s", ordered_indices)
            return ordered_indices
        except ValidationFailure as e_val:
            self._log_error("Validation failed processing chapter order from LLM response: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN:
                    snippet += "..."
                module_logger.warning("Problematic YAML for chapter order:\n%s", snippet)
            return []  # Return empty list on validation failure
        except (TypeError, ValueError) as e_proc:  # Catch specific processing errors
            self._log_error("Unexpected error processing chapter order: %s", e_proc, exc_info=True)
            return []  # Return empty list

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: OrderChaptersPreparedInputs,
        execution_outputs: OrderChaptersExecutionResult,
    ) -> None:
        """Update the shared context with the determined chapter order.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from the `pre_execution` phase (unused).
            execution_outputs: List of ordered chapter indices from the `execution` phase.
        """
        del prepared_inputs  # Mark as unused
        shared_context["chapter_order"] = execution_outputs
        self._log_info("Stored chapter order in shared context: %s", execution_outputs)


# End of src/sourcelens/nodes/n04_order_chapters.py
