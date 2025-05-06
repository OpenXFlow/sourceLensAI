# src/sourcelens/nodes/structure.py

"""Node responsible for determining the logical order of tutorial chapters.

Based on identified code abstractions and their relationships using an LLM.
"""

import contextlib
import logging
from typing import Any, TypeAlias, Union

# Import base class and types
from sourcelens.nodes.base_node import BaseNode, SharedState

# >>> Updated import for prompts <<<
from sourcelens.prompts import ChapterPrompts

# Import LLM call utility and potential errors
from sourcelens.utils.llm_api import LlmApiError, call_llm

# Import validation utilities
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ChapterOrderList: TypeAlias = list[int]
RawIndexEntry: TypeAlias = Union[str, int, float, None]

logger = logging.getLogger(__name__)

# Specific types for this node's prep/exec results
StructurePrepResult: TypeAlias = dict[str, Any]
StructureExecResult: TypeAlias = ChapterOrderList


class OrderChapters(BaseNode):
    """Determine the optimal chapter order for the tutorial using an LLM.

    Takes identified abstractions and relationships as context, prompts the LLM
    for a logical sequence using a centralized prompt function, validates the
    response, and stores the ordered list of abstraction indices.
    """

    def _parse_single_index_entry(self, entry: RawIndexEntry, position: int) -> int:
        """Parse a single entry from the LLM's ordered list.

        Args:
            entry: The raw entry from YAML list (expected int, str, float).
            position: The index position for error reporting.

        Returns:
            The parsed integer index.

        Raises:
            ValidationFailure: If the entry cannot be parsed as a valid integer index.

        """
        # ... (Implementation remains the same as previous fix) ...
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
                raise ValidationFailure(f"Float entry '{entry}' at pos {position} is not whole number.")
            raise ValidationFailure(f"Unexpected entry type '{type(entry).__name__}' at pos {position}: '{entry}'.")
        except (ValueError, TypeError) as e:
            raise ValidationFailure(f"Could not parse index at pos {position}: '{entry}'. Error: {e}") from e

    def _parse_and_validate_order(self, ordered_indices_raw: list[Any], num_abstractions: int) -> ChapterOrderList:
        """Parse and validate the chapter order list from LLM response.

        Args:
            ordered_indices_raw: The raw list parsed from YAML.
            num_abstractions: The expected number of chapters/abstractions.

        Returns:
            A validated list of integer indices representing the chapter order.

        Raises:
            ValidationFailure: If list structure, parsing, indices, or uniqueness fail.

        """
        # ... (Implementation remains the same as previous fix) ...
        if not isinstance(ordered_indices_raw, list):
            raise ValidationFailure(f"Expected YAML list, got {type(ordered_indices_raw).__name__}.")
        if len(ordered_indices_raw) != num_abstractions:
            raise ValidationFailure(f"Expected {num_abstractions} indices, got {len(ordered_indices_raw)}.")
        ordered_indices: ChapterOrderList = []
        seen_indices: set[int] = set()
        for i, entry in enumerate(ordered_indices_raw):
            idx = self._parse_single_index_entry(entry, i)
            if not (0 <= idx < num_abstractions):
                raise ValidationFailure(f"Invalid index {idx} at pos {i} (0..{num_abstractions - 1}).")
            if idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {idx} at pos {i}.")
            ordered_indices.append(idx)
            seen_indices.add(idx)
        return ordered_indices

    def _build_order_chapters_context(
        self, abstractions: AbstractionsList, relationships: RelationshipsDict, language: str
    ) -> tuple[str, str, str]:
        """Build context string, abstraction listing, and language note for prompt.

        Args:
            abstractions: List of identified abstraction dictionaries.
            relationships: Dictionary of relationship details.
            language: The target language.

        Returns:
            Tuple of (abstraction_listing, context_string, list_language_note).

        """
        abstraction_info: list[str] = [
            f"- {i} # {str(a.get('name', f'Unnamed Abstraction {i}'))}" for i, a in enumerate(abstractions)
        ]
        abstraction_listing = "\n".join(abstraction_info)

        list_lang_note = f" (Names in {language.capitalize()})" if language.lower() != "english" else ""
        summary_note = f" (Summary/labels in {language.capitalize()})" if language.lower() != "english" else ""

        summary_raw = relationships.get("summary", "N/A")
        summary = str(summary_raw if summary_raw is not None else "N/A")

        context_parts: list[str] = [
            f"Project Summary{summary_note}:\n{summary}\n",
            "Relationships (Indices refer to abstractions above):",
        ]

        rel_details = relationships.get("details", [])
        if isinstance(rel_details, list):
            num_abstractions = len(abstractions)
            for rel in rel_details:
                if not isinstance(rel, dict):
                    continue
                from_idx = rel.get("from")
                to_idx = rel.get("to")
                label_raw = rel.get("label", "interacts")
                label = str(label_raw or "interacts")
                if (
                    isinstance(from_idx, int)
                    and 0 <= from_idx < num_abstractions
                    and isinstance(to_idx, int)
                    and 0 <= to_idx < num_abstractions
                ):
                    from_name = str(abstractions[from_idx].get("name", f"Idx {from_idx}"))
                    to_name = str(abstractions[to_idx].get("name", f"Idx {to_idx}"))
                    context_parts.append(f"- From {from_idx} ({from_name}) to {to_idx} ({to_name}): {label}")
                else:
                    logger.warning("Skipping invalid relationship details: %s", rel)
        else:
            logger.warning("Relationship 'details' is not a list, skipping.")

        return abstraction_listing, "\n".join(context_parts), list_lang_note

    def prep(self, shared: SharedState) -> StructurePrepResult:
        """Prepare context for the LLM chapter ordering prompt."""
        self._log_info("Preparing context for chapter ordering...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

        if not abstractions:
            self._log_warning("No abstractions found. Chapter order cannot be determined.")
            return {
                "num_abstractions": 0,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": shared.get("project_name", "N/A"),
                "language": shared.get("language", "english"),
                "abstraction_listing": "",
                "context": "",
                "list_lang_note": "",
            }  # Return necessary keys for exec to handle gracefully

        relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
        project_name: str = self._get_required_shared(shared, "project_name")
        language: str = shared.get("language", "english")

        abstraction_listing, context_str, list_lang_note = self._build_order_chapters_context(
            abstractions, relationships, language
        )

        return {
            "abstraction_listing": abstraction_listing,
            "context": context_str,
            "num_abstractions": len(abstractions),
            "project_name": project_name,
            "list_lang_note": list_lang_note,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }

    def exec(self, prep_res: StructurePrepResult) -> StructureExecResult:
        """Call LLM to determine chapter order and validate the response."""
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        if num_abstractions == 0:
            self._log_warning("Skipping chapter ordering: No abstractions provided.")
            return []

        project_name: str = prep_res["project_name"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info(f"Determining chapter order for '{project_name}' using LLM...")
        # >>> Use ChapterPrompts class <<<
        prompt = ChapterPrompts.format_order_chapters_prompt(
            project_name=project_name,
            abstraction_listing=prep_res["abstraction_listing"],
            context=prep_res["context"],
            num_abstractions=num_abstractions,
            list_lang_note=prep_res["list_lang_note"],
        )
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            self._log_error("LLM call failed during chapter ordering: %s", e, exc=e)
            return []  # Allow flow to continue

        try:
            list_schema = {
                "type": "array",
                "items": {"type": ["integer", "string"]},
                "minItems": num_abstractions,
                "maxItems": num_abstractions,
            }
            ordered_indices_raw = validate_yaml_list(response, list_schema=list_schema)
            ordered_indices = self._parse_and_validate_order(ordered_indices_raw, num_abstractions)
            self._log_info(f"Determined valid chapter order (indices): {ordered_indices}")
            return ordered_indices
        except ValidationFailure as e_val:
            self._log_error("Validation failed processing chapter order: %s", e_val)
            if e_val.raw_output:
                logger.warning("Problematic YAML for chapter order:\n%s", e_val.raw_output[:500])
            return []  # Allow flow to continue
        except (TypeError, ValueError) as e_proc:  # Catch specific unexpected errors
            self._log_error("Unexpected error processing chapter order: %s", e_proc, exc=e_proc)
            return []  # Allow flow to continue

    def post(self, shared: SharedState, prep_res: StructurePrepResult, exec_res: StructureExecResult) -> None:
        """Update the shared state with the determined chapter order."""
        if isinstance(exec_res, list):
            shared["chapter_order"] = exec_res
            self._log_info("Stored chapter order in shared state.")
        else:
            # This should ideally not be reached if exec always returns a list
            self._log_error("Invalid exec result type: %s. Storing empty list.", type(exec_res).__name__)
            shared["chapter_order"] = []


# End of src/sourcelens/nodes/structure.py
