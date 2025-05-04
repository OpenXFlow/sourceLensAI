# src/sourcelens/nodes/write.py

"""Node responsible for generating the Markdown content for individual.

tutorial chapters using batch processing.
"""

import logging
from collections.abc import Iterable
from typing import Any, Optional, TypeAlias

# Using modern types directly
from sourcelens.nodes.base_node import BaseBatchNode, SharedState

# --- Import prompt formatting function and context dataclass ---
from sourcelens.prompts import WriteChapterContext, format_write_chapter_prompt
from sourcelens.utils.helpers import get_content_for_indices, sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

# --- Type Aliases ---
FileData: TypeAlias = list[tuple[str, str]]
AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]
ChapterOrderList: TypeAlias = list[int]
ChapterContent: TypeAlias = str
ChapterMetadata: TypeAlias = dict[str, Any]  # num, name, filename, abstraction_index
WriteChapterPrepItem: TypeAlias = dict[str, Any]  # Data passed to exec for one chapter
WriteChapterExecResult: TypeAlias = ChapterContent

logger = logging.getLogger(__name__)

# --- Constants ---
# CODE_BLOCK_MAX_LINES is defined and used within prompts.py


class WriteChapters(BaseBatchNode):
    """Write individual tutorial chapters using an LLM via batch processing.

    Prepares data per chapter, calls LLM (using centralized prompt function)
    for Markdown content generation for each chapter individually, and
    collects the results.
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
        # --- Implementation remains the same ---
        chapter_metadata_map: dict[int, ChapterMetadata] = {}
        all_chapters_listing: list[str] = []
        num_abstractions = len(abstractions)
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                logger.warning("Invalid index %d in order at pos %d. Skipping.", abstraction_index, i)
                continue  # noqa E701 E702
            chapter_num = i + 1
            chapter_name_raw = abstractions[abstraction_index].get("name", f"Concept {chapter_num}")
            chapter_name = str(chapter_name_raw or f"Concept {chapter_num}")
            safe_name = sanitize_filename(chapter_name)
            filename = f"{chapter_num:02d}_{safe_name}.md"  # noqa E701
            metadata: ChapterMetadata = {
                "num": chapter_num,
                "name": chapter_name,
                "filename": filename,
                "abstraction_index": abstraction_index,
            }  # noqa E501
            chapter_metadata_map[abstraction_index] = metadata
            all_chapters_listing.append(f"{chapter_num}. [{chapter_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing
        # --- End of unchanged _prepare_chapter_metadata ---

    def prep(self, shared: SharedState) -> Iterable[WriteChapterPrepItem]:
        """Prepare an iterable of dictionaries, one for each chapter to be written.

        Args:
            shared: The shared state dictionary.

        Yields:
            A dictionary (WriteChapterPrepItem) with data for one chapter's prompt.

        Raises:
            ValueError: If required keys are missing from the shared state.

        """
        # --- Implementation remains the same ---
        self._log_info("Preparing data for writing chapters individually...")
        self._chapters_written_this_run = []
        try:
            chapter_order: ChapterOrderList = self._get_required_shared(shared, "chapter_order")
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            files_data: FileData = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            language: str = shared.get("language", "english")  # noqa E701 E702 E501
        except ValueError as e:
            self._log_error("Missing required shared data: %s", e)
            return  # noqa E701 E702
        chapter_metadata_map, all_chapters_listing = self._prepare_chapter_metadata(abstractions, chapter_order)
        full_chapter_structure = "\n".join(all_chapters_listing)
        num_abstractions = len(abstractions)
        num_items_prepared = 0
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                logger.warning("Skipping prep: invalid index %d.", abstraction_index)
                continue  # noqa E701 E702
            abstraction_details = abstractions[abstraction_index]
            related_file_indices_raw = abstraction_details.get("files", [])  # noqa E701
            related_file_indices: list[int] = [idx for idx in related_file_indices_raw if isinstance(idx, int)]
            related_files_content_map = get_content_for_indices(files_data, related_file_indices)
            prev_chapter_meta: Optional[ChapterMetadata] = None
            if i > 0:
                prev_abs_idx = chapter_order[i - 1]
                prev_chapter_meta = chapter_metadata_map.get(prev_abs_idx)  # noqa E701 E702
            next_chapter_meta: Optional[ChapterMetadata] = None
            if i < len(chapter_order) - 1:
                next_abs_idx = chapter_order[i + 1]
                next_chapter_meta = chapter_metadata_map.get(next_abs_idx)  # noqa E701 E702
            previous_chapters_summary = "\n\n---\n[Prev Summary]\n---\n\n".join(self._chapters_written_this_run)
            yield {
                "chapter_num": i + 1,
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
            }  # noqa E501 E701 E702
            num_items_prepared += 1
        self._log_info("Prepared %d chapters for writing execution.", num_items_prepared)
        # --- End of unchanged prep ---

    # --- _format_prompt_for_chapter method removed ---

    def exec(self, item: WriteChapterPrepItem) -> WriteChapterExecResult:
        """Generate the Markdown content for a single chapter using the LLM.

        Prepares context object, calls the centralized prompt formatting function,
        invokes the LLM, validates basic response structure, and accumulates
        context for subsequent calls in the batch.

        Args:
            item: Dictionary with data for this chapter from `prep`.

        Returns:
            String with generated Markdown content, or empty string on failure.

        Raises:
            ValueError: If essential keys are missing in `item`.
            LlmApiError: If the underlying LLM API call fails after retries.

        """
        try:
            # Extract necessary data to build context object and for logging/config
            project_name = item["project_name"]
            abstraction_details = item["abstraction_details"]
            abstraction_name = str(abstraction_details.get("name", "Unnamed"))
            chapter_num = item["chapter_num"]
            llm_config = item["llm_config"]
            cache_config = item["cache_config"]
            related_files_content_map = item["related_files_content_map"]

            file_context_str = (
                "\n\n".join(
                    f"--- File: {idx_path.split('# ', 1)[1] if '# ' in idx_path else idx_path} ---\n{content}"  # noqa E501
                    for idx_path, content in related_files_content_map.items()
                )
                if related_files_content_map
                else "No specific code snippets provided."
            )

            prompt_context = WriteChapterContext(
                project_name=project_name,
                chapter_num=chapter_num,
                abstraction_name=abstraction_name,
                abstraction_description=str(abstraction_details.get("description", "N/A")),
                full_chapter_structure=item["full_chapter_structure"],
                previous_context_info=item.get("previous_chapters_summary", "First chapter."),
                file_context_str=file_context_str,
                language=item["language"],
                prev_chapter_meta=item.get("prev_chapter_meta"),
                next_chapter_meta=item.get("next_chapter_meta"),
            )
        except KeyError as e:
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("Missing key required for chapter context/exec: %s.", e, exc=e)
            return ""

        self._log_info("Writing Chapter %d: '%s' using LLM...", chapter_num, abstraction_name)

        try:
            prompt = format_write_chapter_prompt(prompt_context)
            chapter_content_raw = call_llm(prompt, llm_config, cache_config)
            chapter_content = str(chapter_content_raw or "")
        except LlmApiError as e:
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("LLM call failed for ch %d ('%s'): %s", chapter_num, abstraction_name, e, exc=e)
            raise
        except (ValueError, KeyError) as e:
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("Error preparing context/prompt for ch %d: %s", chapter_num, e, exc=e)
            return ""
        except Exception as e:  # Catch other unexpected errors, more specific above
            # --- FIX: Use exc=e for _log_error ---
            self._log_error("Unexpected error during ch %d exec: %s", chapter_num, e, exc=e)
            return ""

        # --- Basic Content Validation / Cleanup ---
        expected_heading = f"# Chapter {chapter_num}: {abstraction_name}"
        content_stripped = chapter_content.strip()
        if not content_stripped:
            self._log_warning("LLM returned empty content for Ch %d ('%s').", chapter_num, abstraction_name)
            return ""
        if not content_stripped.startswith(f"# Chapter {chapter_num}"):
            self._log_warning("Ch %d ('%s') response missing/incorrect H1. Fixing.", chapter_num, abstraction_name)
            lines = content_stripped.split("\n", 1)
            # Check if first line looks like *any* heading before replacing
            if lines and lines[0].strip().startswith("#"):
                chapter_content = expected_heading + ("\n\n" + lines[1] if len(lines) > 1 and lines[1].strip() else "")
            else:  # Prepend if no heading found
                chapter_content = f"{expected_heading}\n\n{content_stripped}"
        else:
            # Use stripped content if heading is already correct
            chapter_content = content_stripped
        # --- End Validation / Cleanup ---

        summary_for_context = f"Chapter {chapter_num} ({abstraction_name}): {chapter_content[:150]}..."
        self._chapters_written_this_run.append(summary_for_context)

        self._log_info("Successfully generated content for Chapter %d.", chapter_num)
        return chapter_content

    def post(
        self, shared: SharedState, prep_res: Iterable[WriteChapterPrepItem], exec_res_list: list[WriteChapterExecResult]
    ) -> None:
        """Update the shared state with the list of generated chapter content.

        Args:
            shared: The shared state dictionary.
            prep_res: The iterable yielded by `prep` (unused).
            exec_res_list: List of results (strings) from each `exec` call.

        """
        # --- Implementation remains the same ---
        chapters_str_list = [str(item or "") for item in exec_res_list]
        shared["chapters"] = chapters_str_list
        self._log_info("Stored %d chapters content strings in shared state.", len(chapters_str_list))
        self._chapters_written_this_run = []
        # --- End of unchanged post ---


# End of src/sourcelens/nodes/write.py
