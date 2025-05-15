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

"""Node responsible for generating Markdown content for individual tutorial chapters.

This node operates in a batch mode, where each item in the batch corresponds
to a chapter to be written. It uses an LLM to generate the content for each
chapter based on its corresponding abstraction, context from other chapters,
and relevant code snippets.
"""

from collections.abc import Iterable
from typing import Any, Final, Optional

from typing_extensions import TypeAlias

from sourcelens.prompts import ChapterPrompts, WriteChapterContext
from sourcelens.utils.helpers import get_content_for_indices, sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

from .base_node import BaseBatchNode, SLSharedState

WriteChapterPrepItem: TypeAlias = dict[str, Any]
"""Type alias for the data item prepared for a single chapter's generation."""
_SingleChapterExecResult: TypeAlias = str
"""Internal type alias for the execution result of processing one chapter item."""

WriteChaptersExecResult: TypeAlias = list[_SingleChapterExecResult]
"""Type alias for the execution result of the entire batch."""

FileDataOptionalContent: TypeAlias = tuple[str, Optional[str]]
FileDataListOptionalContent: TypeAlias = list[FileDataOptionalContent]
"""Represents file data where content might be None if read failed."""

FileDataStrictContent: TypeAlias = tuple[str, str]
FileDataListStrictContent: TypeAlias = list[FileDataStrictContent]


AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]

ChapterOrderList: TypeAlias = list[int]
ChapterMetadata: TypeAlias = dict[str, Any]

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]


ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"
DEFAULT_LANGUAGE_CODE: Final[str] = "english"
DEFAULT_PROJECT_NAME: Final[str] = "Unknown Project"
FILENAME_CHAPTER_PREFIX_WIDTH: Final[int] = 2


class WriteChapters(BaseBatchNode[WriteChapterPrepItem, _SingleChapterExecResult]):
    """Write individual tutorial chapters using an LLM via batch processing."""

    def _prepare_chapter_metadata(
        self, abstractions: AbstractionsList, chapter_order: ChapterOrderList
    ) -> tuple[dict[int, ChapterMetadata], list[str]]:
        """Prepare metadata for each chapter based on abstractions and order.

        Args:
            abstractions: The list of all identified abstractions.
            chapter_order: A list of integer indices specifying the order.

        Returns:
            A tuple containing:
                - A dictionary mapping abstraction_index to `ChapterMetadata`.
                - A list of Markdown-formatted chapter links.
        """
        chapter_metadata_map: dict[int, ChapterMetadata] = {}
        all_chapters_listing_md: list[str] = []
        num_abstractions = len(abstractions)

        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                self._log_warning(  # Correct: using inherited logger helper
                    "Invalid abstraction index %d in chapter order at position %d. Skipping metadata.",
                    abstraction_index,
                    i,
                )
                continue

            chapter_num = i + 1
            abstraction_item: AbstractionItem = abstractions[abstraction_index]
            chapter_name_raw_any: Any = abstraction_item.get("name")
            chapter_name: str = (
                str(chapter_name_raw_any)
                if isinstance(chapter_name_raw_any, str) and chapter_name_raw_any.strip()
                else f"Concept {chapter_num}"
            )
            safe_filename_base = sanitize_filename(chapter_name) or f"chapter-{chapter_num}"
            filename = f"{chapter_num:0{FILENAME_CHAPTER_PREFIX_WIDTH}d}_{safe_filename_base}.md"

            metadata: ChapterMetadata = {
                "num": chapter_num,
                "name": chapter_name,
                "filename": filename,
                "abstraction_index": abstraction_index,
            }
            chapter_metadata_map[abstraction_index] = metadata
            all_chapters_listing_md.append(f"{chapter_num}. [{chapter_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing_md

    def _prepare_single_chapter_item(
        self,
        chapter_index_in_order: int,
        abstraction_index: int,
        abstractions: AbstractionsList,
        files_data: FileDataListOptionalContent,
        project_name: str,
        chapter_metadata_map: dict[int, ChapterMetadata],
        chapter_order: ChapterOrderList,
        full_chapter_structure_md: str,
        language: str,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
    ) -> WriteChapterPrepItem:
        """Prepare the data item (context) for a single chapter.

        Args:
            chapter_index_in_order: 0-based index in `chapter_order`.
            abstraction_index: Index from the main `abstractions` list.
            abstractions: Full list of abstractions.
            files_data: Full list of (filepath, Optional[content]) tuples.
            project_name: Name of the project.
            chapter_metadata_map: Map from abstraction_index to `ChapterMetadata`.
            chapter_order: Ordered list of abstraction indices.
            full_chapter_structure_md: Markdown string listing all chapters.
            language: Target language for the chapter.
            llm_config: LLM API configuration.
            cache_config: LLM cache configuration.

        Returns:
            A `WriteChapterPrepItem` dictionary for the `exec_item` method.
        """
        abstraction_details: AbstractionItem = abstractions[abstraction_index]
        related_file_indices_any: Any = abstraction_details.get("files", [])
        related_file_indices: list[int] = (
            [idx for idx in related_file_indices_any if isinstance(idx, int)]
            if isinstance(related_file_indices_any, list)
            else []
        )

        files_data_for_context: FileDataListStrictContent = []
        for path, content in files_data:
            if content is not None:
                files_data_for_context.append((path, content))
            else:
                # Use self._logger directly or the inherited helper _log_info, _log_warning etc.
                self._logger.debug("Skipping file '%s' for chapter context as its content is None.", path)

        related_files_content_map = get_content_for_indices(files_data_for_context, related_file_indices)
        file_context_str_parts: list[str] = []
        if related_files_content_map:
            for idx_path, content_val in related_files_content_map.items():
                path_display = idx_path.split("# ", 1)[1] if "# " in idx_path else idx_path
                path_display = path_display.replace("\\", "/")
                file_context_str_parts.append(f"--- File: {path_display} ---\n{content_val}")
            file_context_str = "\n\n".join(file_context_str_parts)
        else:
            file_context_str = "No specific code snippets provided for this chapter's core abstraction."

        prev_chapter_meta: Optional[ChapterMetadata] = None
        if chapter_index_in_order > 0:
            prev_abs_idx = chapter_order[chapter_index_in_order - 1]
            prev_chapter_meta = chapter_metadata_map.get(prev_abs_idx)

        next_chapter_meta: Optional[ChapterMetadata] = None
        if chapter_index_in_order < len(chapter_order) - 1:
            next_abs_idx = chapter_order[chapter_index_in_order + 1]
            next_chapter_meta = chapter_metadata_map.get(next_abs_idx)

        current_chapter_metadata: ChapterMetadata = chapter_metadata_map[abstraction_index]
        current_chapter_name: str = str(current_chapter_metadata.get("name", "Unknown Chapter"))
        current_chapter_num_any: Any = current_chapter_metadata.get("num", chapter_index_in_order + 1)
        current_chapter_num: int = (
            current_chapter_num_any if isinstance(current_chapter_num_any, int) else (chapter_index_in_order + 1)
        )

        prompt_ctx = WriteChapterContext(
            project_name=project_name,
            chapter_num=current_chapter_num,
            abstraction_name=current_chapter_name,
            abstraction_description=str(abstraction_details.get("description", "N/A")),
            full_chapter_structure=full_chapter_structure_md,
            previous_context_info="Refer to the 'Overall Tutorial Structure' for context.",
            file_context_str=file_context_str,
            language=language,
            prev_chapter_meta=prev_chapter_meta,
            next_chapter_meta=next_chapter_meta,
        )
        prep_item: WriteChapterPrepItem = {
            "prompt_context": prompt_ctx,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }
        return prep_item

    def prep(self, shared: SLSharedState) -> Iterable[WriteChapterPrepItem]:
        """Prepare an iterable of dictionaries, one for each chapter.

        Args:
            shared: The shared state dictionary.

        Returns:
            An iterable of `WriteChapterPrepItem` dictionaries. Yields items.
        """
        self._log_info("Preparing data for writing chapters individually...")
        try:
            chapter_order_any: Any = self._get_required_shared(shared, "chapter_order")
            abstractions_any: Any = self._get_required_shared(shared, "abstractions")
            files_data_any: Any = self._get_required_shared(shared, "files")
            project_name_any: Any = self._get_required_shared(shared, "project_name")
            llm_config_any: Any = self._get_required_shared(shared, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared, "cache_config")
            language_any: Any = shared.get("language", DEFAULT_LANGUAGE_CODE)

            chapter_order: ChapterOrderList = chapter_order_any if isinstance(chapter_order_any, list) else []
            abstractions: AbstractionsList = abstractions_any if isinstance(abstractions_any, list) else []
            files_data: FileDataListOptionalContent = files_data_any if isinstance(files_data_any, list) else []
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else DEFAULT_PROJECT_NAME
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            language: str = str(language_any) if isinstance(language_any, str) else DEFAULT_LANGUAGE_CODE

        except ValueError:
            self._log_error("WriteChapters.prep: Failed due to missing essential shared data.", exc_info=True)
            return

        if not chapter_order or not abstractions:
            self._log_warning("No chapter order or abstractions available. No chapters will be written.")
            return

        chapter_metadata_map, all_chapters_listing_md_list = self._prepare_chapter_metadata(abstractions, chapter_order)
        full_chapter_structure_md: str = "\n".join(all_chapters_listing_md_list)
        num_abstractions = len(abstractions)
        num_items_prepared = 0

        for i, abstraction_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= abstraction_idx_for_chapter < num_abstractions):
                self._log_warning(
                    "Skipping prep for chapter item: invalid abstraction_index %d at order position %d.",
                    abstraction_idx_for_chapter,
                    i,
                )
                continue
            if abstraction_idx_for_chapter not in chapter_metadata_map:
                self._log_error(
                    "Critical: No metadata for abstraction_index %d when preparing chapter. Skipping.",
                    abstraction_idx_for_chapter,
                )
                continue

            yield self._prepare_single_chapter_item(
                chapter_index_in_order=i,
                abstraction_index=abstraction_idx_for_chapter,
                abstractions=abstractions,
                files_data=files_data,
                project_name=project_name,
                chapter_metadata_map=chapter_metadata_map,
                chapter_order=chapter_order,
                full_chapter_structure_md=full_chapter_structure_md,
                language=language,
                llm_config=llm_config,
                cache_config=cache_config,
            )
            num_items_prepared += 1
        self._log_info("Prepared %d chapter items for execution.", num_items_prepared)

    def _extract_and_validate_item_params(
        self, item: WriteChapterPrepItem
    ) -> tuple[WriteChapterContext, LlmConfigDictTyped, CacheConfigDictTyped]:
        """Extract and validate parameters from a single chapter prep item.

        Args:
            item: The `WriteChapterPrepItem` dictionary.

        Returns:
            A tuple containing (prompt_context, llm_config, cache_config).

        Raises:
            KeyError: If essential keys are missing.
            TypeError: If `prompt_context` is not of type `WriteChapterContext`
                       or if llm_config/cache_config are not dictionaries.
        """
        prompt_context_any: Any = item["prompt_context"]
        if not isinstance(prompt_context_any, WriteChapterContext):
            raise TypeError(f"Expected WriteChapterContext, got {type(prompt_context_any).__name__}")
        prompt_context: WriteChapterContext = prompt_context_any

        llm_config_any: Any = item["llm_config"]
        if not isinstance(llm_config_any, dict):
            raise TypeError(f"Expected dict for llm_config, got {type(llm_config_any).__name__}")
        llm_config: LlmConfigDictTyped = llm_config_any

        cache_config_any: Any = item["cache_config"]
        if not isinstance(cache_config_any, dict):
            raise TypeError(f"Expected dict for cache_config, got {type(cache_config_any).__name__}")
        cache_config: CacheConfigDictTyped = cache_config_any

        return prompt_context, llm_config, cache_config

    def _call_llm_for_chapter(
        self,
        prompt_context: WriteChapterContext,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
    ) -> str:
        """Call the LLM to generate content for a single chapter.

        Args:
            prompt_context: The context for the chapter prompt.
            llm_config: LLM API configuration.
            cache_config: LLM cache configuration.

        Returns:
            The raw string content from the LLM.

        Raises:
            LlmApiError: If the LLM call fails.
        """
        prompt_str = ChapterPrompts.format_write_chapter_prompt(prompt_context)
        return call_llm(prompt_str, llm_config, cache_config)

    def _format_llm_response(self, raw_content: str, prompt_context: WriteChapterContext) -> _SingleChapterExecResult:
        """Format the LLM's raw response, ensuring correct H1 heading.

        Args:
            raw_content: The raw string content from the LLM.
            prompt_context: The context used for generating this chapter.

        Returns:
            Formatted chapter content string or an error message string.
        """
        chapter_content = str(raw_content or "").strip()
        expected_heading = f"# Chapter {prompt_context.chapter_num}: {prompt_context.abstraction_name}"

        if not chapter_content:
            self._log_warning(
                "LLM returned empty content for Chapter %d ('%s').",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            return f"{ERROR_MESSAGE_PREFIX} Empty content for Chapter {prompt_context.chapter_num}."

        if not chapter_content.startswith(f"# Chapter {prompt_context.chapter_num}"):
            self._log_warning(
                "Chapter %d ('%s') response missing/incorrect H1. Attempting to prepend.",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            lines = chapter_content.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):
                chapter_content = expected_heading + ("\n\n" + lines[1] if len(lines) > 1 and lines[1].strip() else "")
            else:
                chapter_content = f"{expected_heading}\n\n{chapter_content}"
        elif not chapter_content.startswith(expected_heading):
            self._log_warning(
                "Chapter %d ('%s') H1 differs from expected. Overwriting.",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            first_newline_idx = chapter_content.find("\n")
            chapter_content = (
                expected_heading + chapter_content[first_newline_idx:] if first_newline_idx != -1 else expected_heading
            )
        return chapter_content.strip()

    def exec_item(self, item: WriteChapterPrepItem) -> _SingleChapterExecResult:
        """Generate the Markdown content for a single chapter using the LLM.

        Args:
            item: A `WriteChapterPrepItem` dictionary.

        Returns:
            A string with Markdown content or an error message.

        Raises:
            LlmApiError: Propagated from `call_llm` to allow retries.
        """
        try:
            prompt_context, llm_config, cache_config = self._extract_and_validate_item_params(item)
        except (KeyError, TypeError) as e_params:
            self._log_error("Invalid structure in chapter prep item. Error: %s", str(e_params), exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX} Internal error: Invalid prep item structure ({e_params!s})."

        self._log_info(
            "Writing Chapter %d: '%s' using LLM...", prompt_context.chapter_num, prompt_context.abstraction_name
        )
        try:
            raw_llm_content = self._call_llm_for_chapter(prompt_context, llm_config, cache_config)
            formatted_content = self._format_llm_response(raw_llm_content, prompt_context)
            self._log_info("Successfully generated content for Chapter %d.", prompt_context.chapter_num)
            return formatted_content
        except LlmApiError:
            self._log_error(
                "LLM call failed for Chapter %d ('%s'). Awaiting retry or fallback by flow engine.",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
                exc_info=True,
            )
            raise
        except Exception as e_unexpected:  # noqa: BLE001
            self._log_error(
                "Unexpected error during Chapter %d ('%s') exec_item: %s",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
                e_unexpected,
                exc_info=True,
            )
            return (
                f"{ERROR_MESSAGE_PREFIX} Unexpected problem generating chapter "
                f"{prompt_context.chapter_num} ('{prompt_context.abstraction_name}'): {e_unexpected!s}"
            )

    def post(
        self,
        shared: SLSharedState,
        prep_res: Iterable[WriteChapterPrepItem],
        exec_res_list: WriteChaptersExecResult,
    ) -> None:
        """Update the shared state with the list of generated chapter content.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable of items that were prepared for execution.
            exec_res_list: A list of strings (Markdown content or error messages for each item).
        """
        del prep_res

        chapters_valid_content: list[str] = []
        failed_chapter_count = 0
        for i, chapter_content_or_error in enumerate(exec_res_list):
            if not chapter_content_or_error.startswith(ERROR_MESSAGE_PREFIX):
                chapters_valid_content.append(chapter_content_or_error)
            else:
                failed_chapter_count += 1
                log_message_part1 = "Chapter generation for batch item %d failed or returned "
                log_message_part2 = "an error message: %s. Storing placeholder."
                self._log_warning(
                    log_message_part1 + log_message_part2,
                    i,
                    chapter_content_or_error,
                )
                chapters_valid_content.append(
                    f"<!-- {ERROR_MESSAGE_PREFIX} Chapter generation failed for item index {i}. "
                    "Check application logs for details. -->"
                )

        shared["chapters"] = chapters_valid_content
        log_msg = f"Stored {len(chapters_valid_content)} chapter strings in shared state."
        if failed_chapter_count > 0:
            log_msg += f" ({failed_chapter_count} chapters had errors and are placeholders)."
        self._log_info(log_msg)


# End of src/sourcelens/nodes/n07_write_chapters.py
