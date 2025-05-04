# src/sourcelens/nodes/structure.py

"""Node responsible for determining the logical order of tutorial chapters.

Based on identified code abstractions and their relationships using an LLM.
"""

import logging
from typing import Any, TypeAlias, Union

# Import base class and types
from sourcelens.nodes.base_node import BaseNode, SharedState

# --- Import prompt formatting function ---
from sourcelens.prompts import format_order_chapters_prompt

# Import LLM call utility and potential errors
from sourcelens.utils.llm_api import LlmApiError, call_llm

# Import validation utilities
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ChapterOrderList: TypeAlias = list[int]  # Represents the result of this node
# Refining Any for raw entry type
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

    # --- _format_prompt method removed ---

    # --- Helper Methods for Parsing (Revised Type Hint) ---
    def _parse_single_index_entry(
        self,
        entry: RawIndexEntry,  # Use refined type hint
        position: int,
    ) -> int:  # Return non-optional, raise ValidationFailure on error
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
                # Handle "idx # path" format first
                stripped_entry = entry.strip()
                if "#" in stripped_entry:
                    try:
                        return int(stripped_entry.split("#", 1)[0].strip())
                    except (ValueError, IndexError):
                        # Fall through if '#' parsing fails
                        pass
                # Try parsing as plain integer string
                try:
                    return int(stripped_entry)
                except ValueError as e_val:
                    # Raise specific error if string cannot be parsed as int
                    raise ValidationFailure(
                        f"String entry '{entry}' at pos {position} is not a valid integer index."
                    ) from e_val
            if isinstance(entry, float):
                # Allow conversion only if it represents a whole number
                if entry.is_integer():
                    return int(entry)
                raise ValidationFailure(f"Float entry '{entry}' at pos {position} is not a whole number.")

            # Handle other unexpected types explicitly
            raise ValidationFailure(f"Unexpected entry type '{type(entry).__name__}' at pos {position}: '{entry}'.")

        except (ValueError, TypeError) as e:
            # Catch potential errors during int() conversion for float/other
            raise ValidationFailure(f"Could not parse index from entry at pos {position}: '{entry}'. Error: {e}") from e

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
        if not isinstance(ordered_indices_raw, list):
            raise ValidationFailure(f"Expected YAML list, got {type(ordered_indices_raw).__name__}.")

        if len(ordered_indices_raw) != num_abstractions:
            # Check length early
            raise ValidationFailure(f"Expected {num_abstractions} indices, got {len(ordered_indices_raw)}.")

        ordered_indices: ChapterOrderList = []
        seen_indices: set[int] = set()

        for i, entry in enumerate(ordered_indices_raw):
            idx = self._parse_single_index_entry(entry, i)  # Raises ValidationFailure on error

            # Validate bounds and uniqueness
            if not (0 <= idx < num_abstractions):
                raise ValidationFailure(f"Invalid index {idx} at pos {i} (must be 0..{num_abstractions - 1}).")
            if idx in seen_indices:
                raise ValidationFailure(f"Duplicate index {idx} found at pos {i}.")

            ordered_indices.append(idx)
            seen_indices.add(idx)

        # Note: Check for missing indices is implicitly covered by length check + duplicate check
        return ordered_indices

    # --- End Helper Methods ---

    # --- Abstract Method Implementations ---

    def prep(self, shared: SharedState) -> StructurePrepResult:
        """Prepare context for the LLM chapter ordering prompt.

        Args:
            shared: The shared state dictionary.

        Returns:
            A dictionary containing context data needed for the `exec` step.

        Raises:
            ValueError: If required keys are missing from the shared state.

        """
        # --- Implementation remains the same ---
        self._log_info("Preparing context for chapter ordering...")
        abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
        relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
        project_name: str = self._get_required_shared(shared, "project_name")
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        language: str = shared.get("language", "english")  # noqa E701 E702 E501
        num_abstractions = len(abstractions)
        if num_abstractions == 0:
            self._log_warning("No abstractions found.")
            return {"num_abstractions": 0}
        abstraction_info_for_prompt: list[str] = [
            f"- {i} # {str(a.get('name', f'Unnamed {i}'))}" for i, a in enumerate(abstractions)
        ]
        abstraction_listing = "\n".join(abstraction_info_for_prompt)  # noqa E701 E702
        list_lang_note = ""
        summary_note = ""  # noqa E701
        if language.lower() != "english":
            lang_cap = language.capitalize()
            list_lang_note = f" (Names in {lang_cap})"
            summary_note = f" (Summary/labels in {lang_cap})"  # noqa E701 E702 E501
        summary_raw = relationships.get("summary", "N/A")
        summary = str(summary_raw if summary_raw is not None else "N/A")  # noqa E701 E702
        context_parts: list[str] = [
            f"Project Summary{summary_note}:\n{summary}\n",
            "Relationships (Indices refer to abstractions above):",
        ]  # noqa E501
        rel_details = relationships.get("details", [])
        if isinstance(rel_details, list):
            for rel in rel_details:
                if not isinstance(rel, dict):
                    continue
                from_idx = rel.get("from")
                to_idx = rel.get("to")
                label_raw = rel.get("label", "interacts")
                label = str(label_raw or "interacts")  # noqa E701 E702
                if (
                    isinstance(from_idx, int)
                    and 0 <= from_idx < num_abstractions
                    and isinstance(to_idx, int)
                    and 0 <= to_idx < num_abstractions
                ):  # noqa E501
                    from_name = str(abstractions[from_idx].get("name", f"Idx {from_idx}"))
                    to_name = str(abstractions[to_idx].get("name", f"Idx {to_idx}"))  # noqa E701 E702
                    context_parts.append(f"- From {from_idx} ({from_name}) to {to_idx} ({to_name}): {label}")
                else:
                    logger.warning("Skipping invalid relationship: %s", rel)  # noqa E701
        else:
            logger.warning("Relationship 'details' is not a list.")
        context = "\n".join(context_parts)
        return {
            "abstraction_listing": abstraction_listing,
            "context": context,
            "num_abstractions": num_abstractions,
            "project_name": project_name,
            "list_lang_note": list_lang_note,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }  # noqa E501
        # --- End of unchanged prep ---

    def exec(self, prep_res: StructurePrepResult) -> StructureExecResult:
        """Call the LLM to determine chapter order and validate the response.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            An ordered list of abstraction indices (ChapterOrderList).

        Raises:
            LlmApiError: If the LLM API call fails after retries.
            ValidationFailure: If the LLM response fails validation.

        """
        num_abstractions: int = prep_res.get("num_abstractions", 0)
        if num_abstractions == 0:
            return []

        # Extract needed info
        project_name: str = prep_res["project_name"]
        abstraction_listing: str = prep_res["abstraction_listing"]
        context: str = prep_res["context"]
        list_lang_note: str = prep_res["list_lang_note"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info(f"Determining chapter order for '{project_name}' using LLM...")

        # --- Use imported prompt function ---
        prompt = format_order_chapters_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing,
            context=context,
            num_abstractions=num_abstractions,
            list_lang_note=list_lang_note,
        )
        # --- End prompt function usage ---

        response: str
        try:
            response = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("LLM call failed during chapter ordering: %s", e, exc=e)
            raise

        try:
            list_schema = {
                "type": "array",
                "items": {"type": ["integer", "string"]},
                "minItems": num_abstractions,
                "maxItems": num_abstractions,
            }
            ordered_indices_raw = validate_yaml_list(raw_llm_output=response, list_schema=list_schema)
            ordered_indices = self._parse_and_validate_order(ordered_indices_raw, num_abstractions)
            self._log_info(f"Determined valid chapter order (indices): {ordered_indices}")
            return ordered_indices
        except ValidationFailure as e:
            self._log_error("Validation failed processing chapter order: %s", e)  # Log message only
            raise
        except Exception as e:
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("Unexpected error processing chapter order: %s", e, exc=e)
            raise ValidationFailure(f"Unexpected processing error: {e}") from e

    def post(self, shared: SharedState, prep_res: StructurePrepResult, exec_res: StructureExecResult) -> None:
        """Update the shared state with the determined chapter order.

        Args:
            shared: The shared state dictionary.
            prep_res: The dictionary returned by `prep` (unused here).
            exec_res: The ordered list of indices returned by `exec`.

        """
        # --- Implementation remains the same ---
        if isinstance(exec_res, list):
            shared["chapter_order"] = exec_res
            self._log_info("Stored chapter order in shared state.")
        else:
            log_msg = f"Invalid result type from exec: {type(exec_res).__name__}. Expected list. Order not stored."
            self._log_error(log_msg)
            shared["chapter_order"] = []
        # --- End of unchanged post ---


# End of src/sourcelens/nodes/structure.py
