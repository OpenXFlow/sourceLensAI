# src/sourcelens/nodes/structure.py

"""Node responsible for determining the logical order of tutorial chapters.

This node uses an LLM to analyze identified code abstractions and their
relationships to suggest a pedagogical sequence for the tutorial chapters.
"""

import contextlib
import logging
from typing import Any, Final, Union  # Pridaný Optional

from typing_extensions import TypeAlias

from sourcelens.prompts import ChapterPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# Import BaseNode and SLSharedState from base_node module
from .base_node import BaseNode, SLSharedState

# --- Type Aliases specific to this Node ---
StructurePrepResult: TypeAlias = dict[str, Any]
"""Result of the prep phase: context for LLM, including number of abstractions.
   Keys: 'num_abstractions', 'project_name', 'language', 'llm_config', 'cache_config',
         'abstraction_listing_str', 'context_str', 'list_lang_note_str'.
"""
ChapterOrderList: TypeAlias = list[int]
"""Type alias for a list of integer indices representing chapter order."""
StructureExecResult: TypeAlias = ChapterOrderList
"""Result of the exec phase: the ordered list of chapter indices."""

# --- Other Type Aliases used within this module ---
AbstractionItem: TypeAlias = dict[str, Any]  # Predpoklad: {'name': str, 'description': str, 'files': list[int]}
AbstractionsList: TypeAlias = list[AbstractionItem]

RelationshipDetail: TypeAlias = dict[str, Any]  # Predpoklad: {'from': int, 'to': int, 'label': str}
RelationshipsDict: TypeAlias = dict[str, Union[str, list[RelationshipDetail]]]

RawLLMIndexEntry: TypeAlias = Union[str, int, float, None]  # Index entry direct from LLM YAML

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

# Module-level logger
module_logger: logging.Logger = logging.getLogger(__name__)

# Constants
MAX_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 500


class OrderChapters(BaseNode[StructurePrepResult, StructureExecResult]):
    """Determine the optimal chapter order for the tutorial using an LLM.

    This node takes the list of identified code abstractions and their analyzed
    relationships as input. It constructs a prompt for an LLM, asking it
    to suggest a logical sequence for these abstractions, which forms the
    basis of the tutorial's chapter order. The LLM's YAML response (a list
    of abstraction indices) is validated for correctness.
    """

    def _parse_single_index_entry(self, entry: RawLLMIndexEntry, position: int) -> int:
        """Parse a single entry from the LLM's ordered list of indices.

        Attempts to convert various raw entry types (int, str, float) into
        a valid integer index. Handles simple comments like "index # comment".

        Args:
            entry: The raw entry from the YAML list (e.g., 1, "2", "3 # Abc").
            position: The zero-based position of the entry in the list, for error reporting.

        Returns:
            The parsed integer index.

        Raises:
            ValidationFailure: If the entry cannot be parsed as a valid integer index
                               or if it's an unexpected type.

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
                raise ValidationFailure(
                    f"String entry '{entry}' at position {position} is not a valid integer index representation."
                )
            if isinstance(entry, float):
                if entry.is_integer():
                    return int(entry)
                raise ValidationFailure(f"Float entry '{entry}' at position {position} is not a whole number.")
            raise ValidationFailure(
                f"Unexpected entry type '{type(entry).__name__}' at position {position}: '{entry}'. "
                "Expected int, str, or float."
            )
        except ValueError as e:
            raise ValidationFailure(
                f"Could not parse index at position {position}: '{entry}'. Original error: {e}"
            ) from e
        except Exception as e:
            raise ValidationFailure(
                f"Unexpected error parsing index at position {position}: '{entry}'. Error: {e}"
            ) from e

    def _parse_and_validate_order(self, ordered_indices_raw: list[Any], num_abstractions: int) -> ChapterOrderList:
        """Parse and validate the chapter order list from LLM response.

        Ensures the list contains the correct number of unique indices,
        all within the valid range [0, num_abstractions - 1].

        Args:
            ordered_indices_raw: The raw list parsed from YAML (expected list of int/str/float).
            num_abstractions: The expected number of chapters/abstractions.

        Returns:
            A validated list of integer indices representing the chapter order.

        Raises:
            ValidationFailure: If list structure, parsing of individual indices,
                               index range, or uniqueness checks fail.

        """
        if not isinstance(ordered_indices_raw, list):
            raise ValidationFailure(f"Expected YAML list for chapter order, got {type(ordered_indices_raw).__name__}.")
        if len(ordered_indices_raw) != num_abstractions:
            raise ValidationFailure(
                f"Expected {num_abstractions} indices for chapter order, got {len(ordered_indices_raw)}."
            )

        ordered_indices: ChapterOrderList = []
        seen_indices: set[int] = set()
        for i, entry_any in enumerate(ordered_indices_raw):
            # Ensure entry_any is of a type that _parse_single_index_entry expects
            if not isinstance(entry_any, (str, int, float)) and entry_any is not None:
                raise ValidationFailure(
                    f"Invalid type in raw chapter order at position {i}: {entry_any} (type: {type(entry_any).__name__})"
                )
            entry: RawLLMIndexEntry = entry_any

            parsed_idx = self._parse_single_index_entry(entry, i)
            if not (0 <= parsed_idx < num_abstractions):
                raise ValidationFailure(
                    f"Invalid index {parsed_idx} at position {i} for chapter order. "
                    f"Must be between 0 and {num_abstractions - 1}."
                )
            if parsed_idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {parsed_idx} found at position {i} in chapter order.")
            ordered_indices.append(parsed_idx)
            seen_indices.add(parsed_idx)
        return ordered_indices

    def _build_order_chapters_context(
        self, abstractions: AbstractionsList, relationships: RelationshipsDict, language: str
    ) -> tuple[str, str, str]:
        """Build context string, abstraction listing, and language note for prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            relationships: Dictionary of relationship details including summary and list of relations.
            language: The target language for the tutorial.

        Returns:
            A tuple containing:
                - abstraction_listing_str (str): Formatted list of "Index # Name".
                - context_str (str): Formatted project summary and relationships.
                - list_lang_note_str (str): Language hint for the abstraction list.

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
            rel: RelationshipDetail = rel_any  # type: ignore[assignment]

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

    def prep(self, shared: SLSharedState) -> StructurePrepResult:
        """Prepare context for the LLM chapter ordering prompt.

        Args:
            shared: The shared state dictionary. Expected to contain 'abstractions',
                    'relationships', 'project_name', 'llm_config', 'cache_config'.
                    'language' is optional.

        Returns:
            A `StructurePrepResult` dictionary containing context for the `exec`
            method. If no abstractions are found, 'num_abstractions' will be 0.

        """
        self._log_info("Preparing context for chapter ordering...")
        abstractions_any: Any = self._get_required_shared(shared, "abstractions")
        llm_config_any: Any = self._get_required_shared(shared, "llm_config")
        cache_config_any: Any = self._get_required_shared(shared, "cache_config")
        project_name_any: Any = self._get_required_shared(shared, "project_name")
        language_any: Any = shared.get("language", "english")

        abstractions: AbstractionsList = abstractions_any if isinstance(abstractions_any, list) else []
        llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
        cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
        project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
        language: str = str(language_any) if isinstance(language_any, str) else "english"

        num_abstractions = len(abstractions)
        prep_data: StructurePrepResult = {
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
            return prep_data

        relationships_any: Any = self._get_required_shared(shared, "relationships")
        relationships: RelationshipsDict = relationships_any if isinstance(relationships_any, dict) else {}

        abstraction_listing, context_str, list_lang_note = self._build_order_chapters_context(
            abstractions, relationships, language
        )
        prep_data["abstraction_listing_str"] = abstraction_listing
        prep_data["context_str"] = context_str
        prep_data["list_lang_note_str"] = list_lang_note
        return prep_data

    def exec(self, prep_res: StructurePrepResult) -> StructureExecResult:
        """Call LLM to determine chapter order and validate the response.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A `ChapterOrderList` (list of integer indices). Returns an empty list
            if no abstractions were provided, or if LLM call or validation fails.

        """
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        if num_abstractions == 0:
            self._log_warning("Skipping chapter ordering execution: No abstractions were provided.")
            return []

        project_name: str = prep_res["project_name"]  # type: ignore[assignment]
        llm_config: LlmConfigDictTyped = prep_res["llm_config"]  # type: ignore[assignment]
        cache_config: CacheConfigDictTyped = prep_res["cache_config"]  # type: ignore[assignment]
        abstraction_listing_str: str = prep_res["abstraction_listing_str"]  # type: ignore[assignment]
        context_str_val: str = prep_res["context_str"]  # type: ignore[assignment]
        list_lang_note_val: str = prep_res["list_lang_note_str"]  # type: ignore[assignment]

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
            return []

        try:
            list_item_schema = {"type": ["integer", "string", "number"]}  # Allow float for int-like numbers
            list_schema_validation = {
                "type": "array",
                "items": list_item_schema,
                "minItems": num_abstractions,
                "maxItems": num_abstractions,
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
            return []
        except (TypeError, ValueError) as e_proc:
            self._log_error("Unexpected error processing chapter order: %s", e_proc, exc_info=True)
            return []

    def post(self, shared: SLSharedState, prep_res: StructurePrepResult, exec_res: StructureExecResult) -> None:
        """Update the shared state with the determined chapter order.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from the `prep` phase.
            exec_res: List of ordered chapter indices from the `exec` phase.

        """
        del prep_res
        shared["chapter_order"] = exec_res
        self._log_info("Stored chapter order in shared state: %s", exec_res)


# End of src/sourcelens/nodes/structure.py
