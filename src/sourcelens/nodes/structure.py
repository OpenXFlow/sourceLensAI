# src/sourcelens/nodes/structure.py

"""Node responsible for determining the logical order of tutorial chapters.

This node uses an LLM to analyze identified code abstractions and their
relationships to suggest a pedagogical sequence for the tutorial chapters.
"""

import contextlib
import logging
from typing import Any, Final, Union

from typing_extensions import TypeAlias  # Using typing_extensions for TypeAlias

from sourcelens.prompts import ChapterPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# Import BaseNode
from .base_node import BaseNode, SharedState

# --- Type Aliases specific to this Node ---
StructurePrepResult: TypeAlias = dict[str, Any]
"""Result of the prep phase: context for LLM, including number of abstractions."""
ChapterOrderList: TypeAlias = list[int]
"""Type alias for a list of integer indices representing chapter order."""
StructureExecResult: TypeAlias = ChapterOrderList
"""Result of the exec phase: the ordered list of chapter indices."""

# --- Other Type Aliases used within this module ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
RawIndexEntry: TypeAlias = Union[str, int, float, None]  # From LLM response

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

    def _parse_single_index_entry(self: "OrderChapters", entry: RawIndexEntry, position: int) -> int:
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
                # Handle "index # comment" format
                if "#" in stripped_entry:
                    with contextlib.suppress(ValueError, IndexError):  # Ignore errors if split fails
                        return int(stripped_entry.split("#", 1)[0].strip())
                # Try direct conversion if no comment or if comment parsing failed
                with contextlib.suppress(ValueError):
                    return int(stripped_entry)
                # If it reaches here, string is not a simple int nor "int # comment"
                raise ValidationFailure(
                    f"String entry '{entry}' at position {position} is not a valid integer index representation."
                )
            if isinstance(entry, float):
                if entry.is_integer():
                    return int(entry)
                raise ValidationFailure(f"Float entry '{entry}' at position {position} is not a whole number.")
            # If none of the above types matched
            raise ValidationFailure(
                f"Unexpected entry type '{type(entry).__name__}' at position {position}: '{entry}'. "
                "Expected int, str, or float."
            )
        except ValueError as e:  # Catch int() conversion errors not caught by suppress
            raise ValidationFailure(
                f"Could not parse index at position {position}: '{entry}'. Original error: {e}"
            ) from e
        except Exception as e:  # Catch any other unexpected error during parsing
            raise ValidationFailure(
                f"Unexpected error parsing index at position {position}: '{entry}'. Error: {e}"
            ) from e

    def _parse_and_validate_order(
        self: "OrderChapters", ordered_indices_raw: list[Any], num_abstractions: int
    ) -> ChapterOrderList:
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
        for i, entry in enumerate(ordered_indices_raw):
            parsed_idx = self._parse_single_index_entry(entry, i)  # Raises ValidationFailure on error
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
        self: "OrderChapters", abstractions: AbstractionsList, relationships: RelationshipsDict, language: str
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
            name_val: Any = abstr_item.get("name", f"Unnamed Abstraction {i}")
            abstraction_info_parts.append(f"- {i} # {str(name_val)}")
        abstraction_listing_str: str = "\n".join(abstraction_info_parts)

        list_lang_note_str = f" (Names in {language.capitalize()})" if language.lower() != "english" else ""
        summary_lang_note = f" (Summary/labels in {language.capitalize()})" if language.lower() != "english" else ""

        summary_raw: Any = relationships.get("summary", "N/A")
        summary: str = str(summary_raw if summary_raw is not None else "N/A")

        context_parts: list[str] = [
            f"Project Summary{summary_lang_note}:\n{summary}\n",
            "Relationships (Indices refer to abstractions above):",
        ]

        rel_details_raw: Any = relationships.get("details", [])
        rel_details_list = rel_details_raw if isinstance(rel_details_raw, list) else []
        num_abstractions = len(abstractions)

        for rel in rel_details_list:
            if not isinstance(rel, dict):
                module_logger.warning("Skipping non-dictionary item in relationship details: %s", rel)
                continue
            from_idx_val: Any = rel.get("from")
            to_idx_val: Any = rel.get("to")
            label_raw: Any = rel.get("label", "interacts")
            label: str = str(label_raw or "interacts")

            if (
                isinstance(from_idx_val, int)
                and 0 <= from_idx_val < num_abstractions
                and isinstance(to_idx_val, int)
                and 0 <= to_idx_val < num_abstractions
            ):
                from_name_val: Any = abstractions[from_idx_val].get("name", f"Idx {from_idx_val}")
                to_name_val: Any = abstractions[to_idx_val].get("name", f"Idx {to_idx_val}")
                from_name: str = str(from_name_val)
                to_name: str = str(to_name_val)
                context_parts.append(f"- From {from_idx_val} ({from_name}) to {to_idx_val} ({to_name}): {label}")
            else:
                module_logger.warning("Skipping relationship with invalid/missing indices: %s", rel)
        context_str: str = "\n".join(context_parts)
        return abstraction_listing_str, context_str, list_lang_note_str

    def prep(self, shared: SharedState) -> StructurePrepResult:
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
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = str(shared.get("language", "english"))

        num_abstractions = len(abstractions)
        prep_data: StructurePrepResult = {
            "num_abstractions": num_abstractions,
            "project_name": project_name,
            "language": language,  # Will be used by prompt formatting
            "llm_config": llm_config,
            "cache_config": cache_config,
            "abstraction_listing_str": "",  # Default empty
            "context_str": "",  # Default empty
            "list_lang_note_str": "",  # Default empty
        }

        if not abstractions:  # num_abstractions will be 0
            self._log_warning("No abstractions found. Chapter order cannot be determined by LLM.")
            return prep_data  # Return with num_abstractions = 0

        relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
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

        project_name: str = prep_res["project_name"]  # Expected to be present if num_abstractions > 0
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info("Determining chapter order for '%s' using LLM...", project_name)
        prompt = ChapterPrompts.format_order_chapters_prompt(
            project_name=project_name,
            abstraction_listing=prep_res["abstraction_listing_str"],
            context=prep_res["context_str"],
            num_abstractions=num_abstractions,
            list_lang_note=prep_res["list_lang_note_str"],
        )
        try:
            response_text: str = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed during chapter ordering: %s", e, exc_info=True)
            return []

        try:
            list_item_schema = {"type": ["integer", "string"]}  # Items can be int or string (e.g. "1 # Comment")
            list_schema_validation = {  # Schema for the list itself
                "type": "array",
                "items": list_item_schema,
                "minItems": num_abstractions,
                "maxItems": num_abstractions,
            }
            ordered_indices_raw: list[Any] = validate_yaml_list(response_text, list_schema=list_schema_validation)
            # Further validation (parsing strings to int, checking range and uniqueness)
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
        except (TypeError, ValueError) as e_proc:  # Catch unexpected errors during parsing/validation
            self._log_error("Unexpected error processing chapter order: %s", e_proc, exc_info=True)
            return []

    def post(self, shared: SharedState, prep_res: StructurePrepResult, exec_res: StructureExecResult) -> None:
        """Update the shared state with the determined chapter order.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from the `prep` phase (unused in this method).
            exec_res: List of ordered chapter indices from the `exec` phase.
                      This will be an empty list if preceding steps failed or
                      if no abstractions were available.

        """
        del prep_res  # Mark as unused
        shared["chapter_order"] = exec_res  # exec_res is ChapterOrderList (or [])
        self._log_info("Stored chapter order in shared state: %s", exec_res)


# End of src/sourcelens/nodes/structure.py
