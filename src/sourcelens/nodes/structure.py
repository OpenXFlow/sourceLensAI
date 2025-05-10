# src/sourcelens/nodes/structure.py

"""Node responsible for determining the logical order of tutorial chapters.

Based on identified code abstractions and their relationships using an LLM.
"""

import contextlib
import logging
from typing import Any, TypeAlias, Union

# BaseNode now relies on exec_res parameter in post
from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import ChapterPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ChapterOrderList: TypeAlias = list[int]
RawIndexEntry: TypeAlias = Union[str, int, float, None]

# Module-level logger for utility functions if not part of a class instance
module_logger = logging.getLogger(__name__)

# Specific types for this node's prep/exec results
StructurePrepResult: TypeAlias = dict[str, Any]
StructureExecResult: TypeAlias = ChapterOrderList


class OrderChapters(BaseNode):
    """Determine the optimal chapter order for the tutorial using an LLM.

    This node takes the list of identified code abstractions and their analyzed
    relationships as input. It then constructs a prompt for an LLM, asking it
    to suggest a logical and pedagogical sequence for these abstractions, which
    will form the basis of the tutorial's chapter order. The LLM's response,
    expected as a YAML list of abstraction indices, is validated for correctness
    (e.g., all indices present, no duplicates, within bounds). The successfully
    ordered list of indices is stored in the shared state.
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

        Ensures the list contains the correct number of unique indices,
        all within the valid range [0, num_abstractions - 1].

        Args:
            ordered_indices_raw: The raw list parsed from YAML.
            num_abstractions: The expected number of chapters/abstractions.

        Returns:
            A validated list of integer indices representing the chapter order.

        Raises:
            ValidationFailure: If list structure, parsing, indices, or uniqueness fail.

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
            idx = self._parse_single_index_entry(entry, i)
            if not (0 <= idx < num_abstractions):
                raise ValidationFailure(
                    f"Invalid index {idx} at pos {i} for chapter order. Must be between 0 and {num_abstractions - 1}."
                )
            if idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {idx} found at position {i} in chapter order.")
            ordered_indices.append(idx)
            seen_indices.add(idx)
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
                - abstraction_listing (str): Formatted list of "Index # Name".
                - context_string (str): Formatted project summary and relationships.
                - list_lang_note (str): Language hint for the abstraction list.

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
                    module_logger.warning("Skipping invalid relationship details: %s", rel)
        else:
            module_logger.warning("Relationship 'details' is not a list, skipping relationship processing.")

        return abstraction_listing, "\n".join(context_parts), list_lang_note

    def prep(self, shared: SharedState) -> StructurePrepResult:
        """Prepare context for the LLM chapter ordering prompt."""
        self._logger.info("Preparing context for chapter ordering...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

        if not abstractions:
            self._logger.warning("No abstractions found. Chapter order cannot be determined.")
            return {
                "num_abstractions": 0,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": shared.get("project_name", "N/A"),
                "language": shared.get("language", "english"),
                "abstraction_listing": "",
                "context": "",
                "list_lang_note": "",
            }

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
            self._logger.warning("Skipping chapter ordering: No abstractions provided.")
            return []

        project_name: str = prep_res["project_name"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._logger.info(f"Determining chapter order for '{project_name}' using LLM...")
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
            self._logger.error("LLM call failed during chapter ordering: %s", e, exc_info=True)
            return []

        try:
            list_schema = {
                "type": "array",
                "items": {"type": ["integer", "string"]},
                "minItems": num_abstractions,
                "maxItems": num_abstractions,
            }
            ordered_indices_raw = validate_yaml_list(response, list_schema=list_schema)
            ordered_indices = self._parse_and_validate_order(ordered_indices_raw, num_abstractions)
            self._logger.info(f"Determined valid chapter order (indices): {ordered_indices}")
            return ordered_indices
        except ValidationFailure as e_val:
            self._logger.error("Validation failed processing chapter order: %s", e_val)
            if e_val.raw_output:
                module_logger.warning("Problematic YAML for chapter order:\n%s", e_val.raw_output[:500])
            return []
        except (TypeError, ValueError) as e_proc:
            self._logger.error("Unexpected error processing chapter order: %s", e_proc, exc_info=True)
            return []

    # --- UPDATED post method ---
    def post(self, shared: SharedState, prep_res: StructurePrepResult, exec_res: StructureExecResult) -> None:
        """Update the shared state with the determined chapter order.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The result from the `prep` method (unused in this specific `post`).
            exec_res: The list of ordered chapter indices from `exec`, passed by
                      the flow runner.

        """
        if isinstance(exec_res, list):
            shared["chapter_order"] = exec_res
            self._logger.info("Stored chapter order in shared state.")
        else:
            self._logger.error(
                "Invalid exec_res type for chapter order: %s. Storing empty list.", type(exec_res).__name__
            )
            shared["chapter_order"] = []


# End of src/sourcelens/nodes/structure.py
