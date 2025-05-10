# src/sourcelens/nodes/write.py

"""Node responsible for generating Markdown content for individual tutorial chapters.

Uses batch processing for efficiency.
"""

import logging
from collections.abc import Iterable
from typing import Any, Final, Optional, TypeAlias

# Use BaseBatchNode which relies on exec_res_list parameter in post
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

module_logger = logging.getLogger(__name__)

# --- Constants ---
CODE_BLOCK_MAX_LINES: Final[int] = 20
ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"


class WriteChapters(BaseBatchNode):
    """Write individual tutorial chapters using an LLM via batch processing."""

    # Removed _chapters_written_this_run initialization from __init__
    # It's better managed within prep/exec if needed across batch items

    def __init__(self, max_retries: int = 0, wait: int = 0) -> None:
        """Initialize the WriteChapters node."""
        super().__init__(max_retries=max_retries, wait=wait)
        # _chapters_written_this_run removed, context is per-item now

    def _prepare_chapter_metadata(
        self, abstractions: AbstractionsList, chapter_order: ChapterOrderList
    ) -> tuple[dict[int, ChapterMetadata], list[str]]:
        """Prepare metadata for each chapter based on abstractions and order."""
        # ... (bez zmeny) ...
        chapter_metadata_map: dict[int, ChapterMetadata] = {}
        all_chapters_listing: list[str] = []
        num_abstractions = len(abstractions)
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                module_logger.warning(
                    "Invalid index %d in chapter order at position %d. Skipping metadata prep.", abstraction_index, i
                )
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
        # Removed previous_chapters_summary as it's complex to manage statefully in batch
    ) -> WriteChapterPrepItem:
        """Prepare the data item (context) for a single chapter to be written."""
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
        # Previous summary context removed for simplicity in batch node
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
            "previous_chapters_summary": "Context from previous chapters is not available in this version.",  # Placeholder
        }

    def prep(self, shared: SharedState) -> Iterable[WriteChapterPrepItem]:
        """Prepare an iterable of dictionaries, one for each chapter to be written."""
        self._logger.info("Preparing data for writing chapters individually...")
        # _chapters_written_this_run removed
        try:
            chapter_order: ChapterOrderList = self._get_required_shared(shared, "chapter_order")
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            files_data: FileData = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            language: str = shared.get("language", "english")
        except ValueError as e:
            self._logger.error("Missing required shared data for WriteChapters.prep: %s", e, exc_info=True)
            return iter([])
        if not chapter_order or not abstractions:
            self._logger.warning("No chapter order or abstractions available. Skipping chapter writing.")
            return iter([])
        chapter_metadata_map, all_chapters_listing_md = self._prepare_chapter_metadata(abstractions, chapter_order)
        full_chapter_structure = "\n".join(all_chapters_listing_md)
        num_abstractions = len(abstractions)
        num_items_prepared = 0
        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                module_logger.warning("Skipping prep for chapter: invalid abstraction index %d.", abstraction_index)
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
            )  # Removed prev summary
            num_items_prepared += 1
        self._logger.info("Prepared %d chapters for writing execution.", num_items_prepared)

    def exec(self, item: WriteChapterPrepItem) -> WriteChapterExecResult:
        """Generate the Markdown content for a single chapter using the LLM."""
        # --- Logika zostáva rovnaká, ale už nepoužíva self._chapters_written_this_run ---
        try:
            project_name = item["project_name"]
            abstraction_details = item["abstraction_details"]
            abstraction_name = str(abstraction_details.get("name", "Unnamed Abstraction"))
            chapter_num = item["chapter_num"]
            llm_config = item["llm_config"]
            cache_config = item["cache_config"]
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
            self._logger.error(
                "Missing key for chapter context in exec: %s. Item keys: %s", e_key, list(item.keys()), exc_info=True
            )
            raise ValueError(f"Missing data for chapter {item.get('chapter_num', 'Unknown')}: {e_key}") from e_key
        self._logger.info("Writing Chapter %d: '%s' using LLM...", chapter_num, abstraction_name)
        try:
            prompt = ChapterPrompts.format_write_chapter_prompt(prompt_context)
            chapter_content_raw = call_llm(prompt, llm_config, cache_config)
            chapter_content = str(chapter_content_raw or "")
        except LlmApiError:
            self._logger.error(
                "LLM call failed for ch %d ('%s'). Awaiting retry or fallback.", chapter_num, abstraction_name
            )
            raise
        except (ValueError, TypeError, KeyError) as e_unexpected:
            self._logger.error("Unexpected error during ch %d exec: %s", chapter_num, e_unexpected, exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX} Unexpected problem generating chapter {chapter_num}: {e_unexpected}"
        expected_heading = f"# Chapter {chapter_num}: {abstraction_name}"
        content_stripped = chapter_content.strip()
        if not content_stripped:
            self._logger.warning("LLM returned empty content for Ch %d ('%s').", chapter_num, abstraction_name)
            return f"{ERROR_MESSAGE_PREFIX} Empty content for Chapter {chapter_num}."
        if not content_stripped.startswith(f"# Chapter {chapter_num}"):
            self._logger.warning(
                "Ch %d ('%s') response missing/incorrect H1. Attempting to fix.", chapter_num, abstraction_name
            )
            lines = content_stripped.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):
                chapter_content = expected_heading + ("\n\n" + lines[1] if len(lines) > 1 and lines[1].strip() else "")
            else:
                chapter_content = f"{expected_heading}\n\n{content_stripped}"
        else:
            chapter_content = content_stripped
        # Removed adding summary to self._chapters_written_this_run
        self._logger.info("Successfully generated content for Chapter %d.", chapter_num)
        return chapter_content

    # --- UPDATED post method ---
    def post(
        self, shared: SharedState, prep_res: Iterable[WriteChapterPrepItem], exec_res_list: list[WriteChapterExecResult]
    ) -> None:
        """Update the shared state with the list of generated chapter content."""
        # Now relies solely on exec_res_list passed by the runner
        chapters_valid_content: list[str] = []
        failed_count = 0
        for i, item_content in enumerate(exec_res_list):
            if isinstance(item_content, str) and not item_content.startswith(ERROR_MESSAGE_PREFIX):
                chapters_valid_content.append(item_content)
            else:
                failed_count += 1
                self._logger.warning(
                    "Chapter at batch index %d failed generation or returned an error. Storing placeholder.", i
                )
                chapters_valid_content.append(
                    f"<!-- {ERROR_MESSAGE_PREFIX} Chapter generation failed. Check logs for details. -->"
                )

        shared["chapters"] = chapters_valid_content
        log_msg = f"Stored {len(chapters_valid_content)} chapter strings in shared state."
        if failed_count > 0:
            log_msg += f" ({failed_count} chapters failed and have placeholders)."
        self._logger.info(log_msg)
        # _chapters_written_this_run removed


# End of src/sourcelens/nodes/write.py
