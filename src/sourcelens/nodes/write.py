# src/sourcelens/nodes/write.py

"""Node responsible for generating Markdown content for individual tutorial chapters.

Uses batch processing for efficiency.
"""

import logging
from collections.abc import Iterable
from typing import Any, Final, Optional, TypeAlias  # Added Final

from sourcelens.nodes.base_node import BaseBatchNode, SharedState
from sourcelens.prompts import ChapterPrompts, WriteChapterContext
from sourcelens.utils.helpers import get_content_for_indices, sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

# --- Type Aliases ---
FileData: TypeAlias = list[tuple[str, str]]
AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]
ChapterOrderList: TypeAlias = list[int]
ChapterContent: TypeAlias = str
ChapterMetadata: TypeAlias = dict[str, Any]
WriteChapterPrepItem: TypeAlias = dict[str, Any]
WriteChapterExecResult: TypeAlias = str  # Can be content or an error message

logger = logging.getLogger(__name__)

# --- Constants ---
# Moved from prompts/_common as it's specific to this node's logic
CODE_BLOCK_MAX_LINES: Final[int] = 20
ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"


class WriteChapters(BaseBatchNode):
    """Write individual tutorial chapters using an LLM via batch processing.

    Prepares data per chapter, calls LLM for Markdown content generation
    for each chapter individually, and collects the results. Handles LLM API
    errors by allowing retries via the underlying flow mechanism.
    """

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the WriteChapters node.

        Args:
            max_retries: Maximum number of retries for LLM calls in exec.
            wait: Wait time in seconds between retries.

        """
        super().__init__(max_retries=max_retries, wait=wait)
        self._chapters_written_this_run: list[ChapterContent] = []

    def _prepare_chapter_metadata(
        self, abstractions: AbstractionsList, chapter_order: ChapterOrderList
    ) -> tuple[dict[int, ChapterMetadata], list[str]]:
        """Prepare metadata for each chapter based on abstractions and order.

        Args:
            abstractions: The list of identified abstraction dictionaries.
            chapter_order: The ordered list of abstraction indices for chapters.

        Returns:
            A tuple containing:
                - A dictionary mapping abstraction index to its ChapterMetadata.
                - A list of formatted Markdown links for all chapters in order.

        """
        # ... (Implementation remains the same) ...
        chapter_metadata_map: dict[int, ChapterMetadata] = {}
        all_chapters_listing: list[str] = []
        num_abstractions = len(abstractions)
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                logger.warning("Invalid index %d in order at pos %d. Skipping.", abstraction_index, i)
                continue
            chapter_num = i + 1
            abs_item = abstractions[abstraction_index]
            chapter_name_raw = abs_item.get("name", f"Concept {chapter_num}")
            chapter_name = str(chapter_name_raw or f"Concept {chapter_num}")
            safe_name = sanitize_filename(chapter_name)
            filename = f"{chapter_num:02d}_{safe_name}.md"
            metadata: ChapterMetadata = {
                "num": chapter_num,
                "name": chapter_name,
                "filename": filename,
                "abstraction_index": abstraction_index,
            }
            chapter_metadata_map[abstraction_index] = metadata
            all_chapters_listing.append(f"{chapter_num}. [{chapter_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing

    def _prepare_single_chapter_item(  # noqa: PLR0913
        self,
        chapter_index_in_order: int,
        abstraction_index: int,
        abstractions: AbstractionsList,
        files_data: FileData,
        project_name: str,
        chapter_metadata_map: dict[int, ChapterMetadata],
        chapter_order: ChapterOrderList,
        full_chapter_structure: str,
        language: str,
        llm_config: dict[str, Any],
        cache_config: dict[str, Any],
    ) -> WriteChapterPrepItem:
        """Prepare the data item for a single chapter to be written."""
        # ... (Implementation remains the same) ...
        abstraction_details = abstractions[abstraction_index]
        related_file_indices_raw = abstraction_details.get("files", [])
        related_file_indices: list[int] = [idx for idx in related_file_indices_raw if isinstance(idx, int)]
        related_files_content_map = get_content_for_indices(files_data, related_file_indices)
        prev_chapter_meta: Optional[ChapterMetadata] = None
        if chapter_index_in_order > 0:
            prev_abs_idx = chapter_order[chapter_index_in_order - 1]
            prev_chapter_meta = chapter_metadata_map.get(prev_abs_idx)
        next_chapter_meta: Optional[ChapterMetadata] = None
        if chapter_index_in_order < len(chapter_order) - 1:
            next_abs_idx = chapter_order[chapter_index_in_order + 1]
            next_chapter_meta = chapter_metadata_map.get(next_abs_idx)
        previous_chapters_summary = "\n\n---\n[Prev Summary]\n---\n\n".join(self._chapters_written_this_run)
        return {
            "chapter_num": chapter_index_in_order + 1,
            "abstraction_index": abstraction_index,
            "abstraction_details": abstraction_details,
            "related_files_content_map": related_files_content_map,
            "project_name": project_name,
            "full_chapter_structure": full_chapter_structure,
            "prev_chapter_meta": prev_chapter_meta,
            "next_chapter_meta": next_chapter_meta,
            "language": language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "previous_chapters_summary": previous_chapters_summary,
        }

    def prep(self, shared: SharedState) -> Iterable[WriteChapterPrepItem]:
        """Prepare an iterable of dictionaries, one for each chapter."""
        # ... (Implementation remains the same) ...
        self._log_info("Preparing data for writing chapters individually...")
        self._chapters_written_this_run = []
        try:
            chapter_order: ChapterOrderList = self._get_required_shared(shared, "chapter_order")
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            files_data: FileData = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            language: str = shared.get("language", "english")
        except ValueError as e:
            self._log_error("Missing required shared data for WriteChapters.prep: %s", e, exc_info=True)
            return iter([])
        if not chapter_order or not abstractions:
            self._log_warning("No chapter order or abstractions available. Skipping chapter writing.")
            return iter([])
        chapter_metadata_map, all_chapters_listing_md = self._prepare_chapter_metadata(abstractions, chapter_order)
        full_chapter_structure = "\n".join(all_chapters_listing_md)
        num_abstractions = len(abstractions)
        num_items_prepared = 0
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                logger.warning("Skipping prep for chapter: invalid abstraction index %d.", abstraction_index)
                continue
            yield self._prepare_single_chapter_item(
                chapter_index_in_order=i,
                abstraction_index=abstraction_index,
                abstractions=abstractions,
                files_data=files_data,
                project_name=project_name,
                chapter_metadata_map=chapter_metadata_map,
                chapter_order=chapter_order,
                full_chapter_structure=full_chapter_structure,
                language=language,
                llm_config=llm_config,
                cache_config=cache_config,
            )
            num_items_prepared += 1
        self._log_info("Prepared %d chapters for writing execution.", num_items_prepared)

    def exec(self, item: WriteChapterPrepItem) -> WriteChapterExecResult:
        """Generate the Markdown content for a single chapter using the LLM.

        Args:
            item: Dictionary with data for this chapter from `prep`.

        Returns:
            String with generated Markdown content, or an error message string
            if a non-API related error occurs.

        Raises:
            LlmApiError: If the underlying LLM API call fails after retries,
                         allowing the flow runner to handle further retries.
            KeyError: If essential keys are missing in `item` for context prep.

        """
        try:
            project_name = item["project_name"]
            abstraction_details = item["abstraction_details"]
            abstraction_name = str(abstraction_details.get("name", "Unnamed Abstraction"))
            chapter_num = item["chapter_num"]
            llm_config = item["llm_config"]  # Needed for call_llm
            cache_config = item["cache_config"]  # Needed for call_llm
            related_files_content_map = item["related_files_content_map"]

            file_context_str = (
                "\n\n".join(
                    f"--- File: {idx_path.split('# ', 1)[1] if '# ' in idx_path else idx_path} ---\n{content}"
                    for idx_path, content in related_files_content_map.items()
                )
                if related_files_content_map
                else "No specific code snippets provided for this chapter."
            )

            prompt_context = WriteChapterContext(
                project_name=project_name,
                chapter_num=chapter_num,
                abstraction_name=abstraction_name,
                abstraction_description=str(abstraction_details.get("description", "N/A")),
                full_chapter_structure=item["full_chapter_structure"],
                previous_context_info=item.get("previous_chapters_summary", "This is the first chapter..."),
                file_context_str=file_context_str,
                language=item["language"],
                prev_chapter_meta=item.get("prev_chapter_meta"),
                next_chapter_meta=item.get("next_chapter_meta"),
            )
        except KeyError as e_key:
            self._log_error("Missing key for chapter context in exec: %s. Item: %s", e_key, item, exc_info=True)
            # Re-raise as this is a programming error, not an LLM error to retry
            raise ValueError(f"Missing data for chapter {item.get('chapter_num', 'Unknown')}: {e_key}") from e_key

        self._log_info("Writing Chapter %d: '%s' using LLM...", chapter_num, abstraction_name)

        try:
            prompt = ChapterPrompts.format_write_chapter_prompt(prompt_context)
            # This call will raise LlmApiError if it fails after its own retries
            chapter_content_raw = call_llm(prompt, llm_config, cache_config)
            chapter_content = str(chapter_content_raw or "")
        except LlmApiError:  # Let LlmApiError propagate for PocketFlow to handle retries
            self._log_error(
                "LLM call failed for ch %d ('%s'). Awaiting retry or fallback.", chapter_num, abstraction_name
            )
            raise  # This is crucial for PocketFlow's retry mechanism
        except (ValueError, TypeError, KeyError) as e_unexpected:  # Catch specific unexpected errors
            self._log_error("Unexpected error during ch %d exec: %s", chapter_num, e_unexpected, exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX} Unexpected problem for chapter {chapter_num}."

        # Basic Content Validation / Cleanup
        expected_heading = f"# Chapter {chapter_num}: {abstraction_name}"
        content_stripped = chapter_content.strip()
        if not content_stripped:
            self._log_warning("LLM returned empty content for Ch %d ('%s').", chapter_num, abstraction_name)
            return f"{ERROR_MESSAGE_PREFIX} Empty content for Chapter {chapter_num}."

        if not content_stripped.startswith(f"# Chapter {chapter_num}"):
            self._log_warning(
                "Ch %d ('%s') response missing/incorrect H1. Attempting to fix.", chapter_num, abstraction_name
            )
            lines = content_stripped.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):
                chapter_content = expected_heading + ("\n\n" + lines[1] if len(lines) > 1 and lines[1].strip() else "")
            else:
                chapter_content = f"{expected_heading}\n\n{content_stripped}"
        else:
            chapter_content = content_stripped  # Use stripped if heading is correct

        summary_max_len = 200
        summary_for_context = f"Chapter {chapter_num} ({abstraction_name}): {chapter_content[:summary_max_len]}"
        if len(chapter_content) > summary_max_len:
            summary_for_context += "..."
        self._chapters_written_this_run.append(summary_for_context)

        self._log_info("Successfully generated content for Chapter %d.", chapter_num)
        return chapter_content

    def post(
        self, shared: SharedState, prep_res: Iterable[WriteChapterPrepItem], exec_res_list: list[WriteChapterExecResult]
    ) -> None:
        """Update the shared state with the list of generated chapter content."""
        # Filter out error messages from exec_res_list before storing
        # This ensures 'chapters' in shared state only contains valid Markdown or empty strings
        chapters_valid_content: list[str] = []
        for i, item_content in enumerate(exec_res_list):
            if isinstance(item_content, str) and not item_content.startswith(ERROR_MESSAGE_PREFIX):
                chapters_valid_content.append(item_content)
            else:
                # Log that a chapter failed and will be empty or have an error placeholder
                # The chapter_order and abstractions list can be used to get the chapter name
                # This requires prep_res to be accessible or chapter details passed differently
                # For simplicity, just log the index for now.
                self._log_warning(
                    "Chapter at batch index %d failed generation or returned an error message. "
                    "It will be stored as empty or with an error marker.",
                    i,
                )
                chapters_valid_content.append(f"<!-- {ERROR_MESSAGE_PREFIX} for this chapter. Check logs. -->")

        shared["chapters"] = chapters_valid_content
        self._log_info(
            "Stored %d chapter content strings in shared state (failed chapters may be empty/placeholders).",
            len(chapters_valid_content),
        )
        self._chapters_written_this_run = []


# End of src/sourcelens/nodes/write.py
