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
and relevant code snippets. It now includes per-item retry logic for LLM calls.
"""

import re
import time
import warnings
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Any, Final, Optional

from typing_extensions import TypeAlias

from sourcelens.core import BaseBatchNode, SLSharedContext
from sourcelens.core.common_types import (
    ChapterMetadata,
    CodeAbstractionsList,
    FilePathContentList,
    OptionalFilePathContentList,
)
from sourcelens.utils.helpers import get_content_for_indices, sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

from ..prompts._common import WriteChapterContext
from ..prompts.chapter_prompts import ChapterPrompts

WriteChapterPreparedItem: TypeAlias = dict[str, Any]
SingleChapterExecutionResult: TypeAlias = str
WriteChaptersExecutionResultList: TypeAlias = list[SingleChapterExecutionResult]

ChapterOrderListInternal: TypeAlias = list[int]

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]


ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"
DEFAULT_LANGUAGE_CODE: Final[str] = "english"
DEFAULT_SOURCE_CODE_LANGUAGE_NAME: Final[str] = "general"
DEFAULT_PROJECT_NAME: Final[str] = "Unknown Project"
FILENAME_CHAPTER_PREFIX_WIDTH: Final[int] = 2


@dataclass(frozen=True)
class _ChapterPreparationContext:
    """Internal dataclass to hold context for preparing a single chapter item."""

    abstractions: CodeAbstractionsList
    files_data: OptionalFilePathContentList
    project_name: str
    chapter_metadata_map: dict[int, ChapterMetadata]
    chapter_order: ChapterOrderListInternal
    full_chapter_structure_md: str
    language: str
    source_code_language_name: str
    llm_config: LlmConfigDictTyped
    cache_config: CacheConfigDictTyped


class WriteChapters(BaseBatchNode[WriteChapterPreparedItem, SingleChapterExecutionResult]):
    """Write individual tutorial chapters using an LLM via batch processing.

    The `pre_execution` method prepares an iterable of items, each representing
    the context for a single chapter. The `execution` method iterates through
    these items, calling an LLM for each to generate chapter content.
    This node implements per-item retry logic for LLM calls internally.
    """

    def _prepare_chapter_metadata(
        self, abstractions: CodeAbstractionsList, chapter_order: ChapterOrderListInternal
    ) -> tuple[dict[int, ChapterMetadata], list[str]]:
        """Prepare metadata for each chapter based on abstractions and order.

        Generates filenames, chapter numbers, and a markdown list of all chapters
        for inclusion in prompts.

        Args:
            abstractions: The list of all identified abstractions for the project.
            chapter_order: A list of integer indices specifying the pedagogical
                           order of chapters, corresponding to indices in `abstractions`.

        Returns:
            A tuple containing:
                - A dictionary mapping original abstraction_index to its
                  `ChapterMetadata`.
                - A list of Markdown-formatted strings, each representing a link
                  to a chapter in the planned tutorial structure.
        """
        chapter_metadata_map: dict[int, ChapterMetadata] = {}
        all_chapters_listing_md: list[str] = []
        num_abstractions = len(abstractions)

        for i, abstraction_index in enumerate(chapter_order):
            if not (0 <= abstraction_index < num_abstractions):
                self._log_warning(
                    "Invalid abstraction index %d in chapter order at position %d. Skipping metadata.",
                    abstraction_index,
                    i,
                )
                continue

            chapter_num = i + 1
            abstraction_item: dict[str, Any] = abstractions[abstraction_index]
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
        prep_context: _ChapterPreparationContext,
    ) -> WriteChapterPreparedItem:
        """Prepare the data item (context) for generating a single chapter.

        Args:
            chapter_index_in_order: 0-based index of the current chapter.
            abstraction_index: The index of the core abstraction for this chapter.
            prep_context: A dataclass containing all shared preparation data.

        Returns:
            A dictionary (`WriteChapterPreparedItem`) with context for one chapter.
        """
        abstraction_details: dict[str, Any] = prep_context.abstractions[abstraction_index]
        related_file_indices_any: Any = abstraction_details.get("files", [])
        related_file_indices: list[int] = (
            [idx for idx in related_file_indices_any if isinstance(idx, int)]
            if isinstance(related_file_indices_any, list)
            else []
        )

        files_data_for_context: FilePathContentList = []
        for path, content in prep_context.files_data:
            if content is not None:
                files_data_for_context.append((path, content))
            else:
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
            prev_abs_idx = prep_context.chapter_order[chapter_index_in_order - 1]
            prev_chapter_meta = prep_context.chapter_metadata_map.get(prev_abs_idx)

        next_chapter_meta: Optional[ChapterMetadata] = None
        if chapter_index_in_order < len(prep_context.chapter_order) - 1:
            next_abs_idx = prep_context.chapter_order[chapter_index_in_order + 1]
            next_chapter_meta = prep_context.chapter_metadata_map.get(next_abs_idx)

        current_chapter_metadata: ChapterMetadata = prep_context.chapter_metadata_map[abstraction_index]
        current_chapter_name: str = str(current_chapter_metadata.get("name", "Unknown Chapter"))
        current_chapter_num = int(current_chapter_metadata.get("num", chapter_index_in_order + 1))

        prompt_ctx = WriteChapterContext(
            project_name=prep_context.project_name,
            chapter_num=current_chapter_num,
            abstraction_name=current_chapter_name,
            abstraction_description=str(abstraction_details.get("description", "N/A")),
            full_chapter_structure=prep_context.full_chapter_structure_md,
            previous_context_info="Refer to the 'Overall Tutorial Structure' for context.",
            file_context_str=file_context_str,
            language=prep_context.language,
            source_code_language_name=prep_context.source_code_language_name,
            prev_chapter_meta=prev_chapter_meta,
            next_chapter_meta=next_chapter_meta,
        )
        prepared_item: WriteChapterPreparedItem = {
            "prompt_context": prompt_ctx,
            "llm_config": prep_context.llm_config,
            "cache_config": prep_context.cache_config,
            "chapter_num_for_log": current_chapter_num,
            "abstraction_name_for_log": current_chapter_name,
        }
        return prepared_item

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WriteChapterPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of data items, each for generating one chapter.

        Args:
            shared_context: The shared context dictionary.

        Yields:
            `WriteChapterPreparedItem` dictionaries for each chapter.
        """
        self._log_info("Preparing data for writing chapters individually...")
        try:
            chapter_order: ChapterOrderListInternal = self._get_required_shared(shared_context, "chapter_order")
            abstractions: CodeAbstractionsList = self._get_required_shared(shared_context, "abstractions")
            source_config: dict[str, Any] = self._get_required_shared(shared_context, "source_config")

        except ValueError:
            self._log_error("WriteChapters.pre_execution: Failed due to missing essential shared data.", exc_info=True)
            return

        if not chapter_order or not abstractions:
            self._log_warning("No chapter order or abstractions available. No chapters will be written.")
            return

        chapter_metadata_map, all_chapters_md_list = self._prepare_chapter_metadata(abstractions, chapter_order)

        prep_context = _ChapterPreparationContext(
            abstractions=abstractions,
            files_data=self._get_required_shared(shared_context, "files"),
            project_name=self._get_required_shared(shared_context, "project_name"),
            chapter_metadata_map=chapter_metadata_map,
            chapter_order=chapter_order,
            full_chapter_structure_md="\n".join(all_chapters_md_list),
            language=str(shared_context.get("language", DEFAULT_LANGUAGE_CODE)),
            source_code_language_name=str(
                source_config.get("language_name_for_llm", DEFAULT_SOURCE_CODE_LANGUAGE_NAME)
            ),
            llm_config=self._get_required_shared(shared_context, "llm_config"),
            cache_config=self._get_required_shared(shared_context, "cache_config"),
        )

        num_items_prepared = 0
        for i, abstraction_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= abstraction_idx_for_chapter < len(abstractions)):
                continue
            if abstraction_idx_for_chapter not in chapter_metadata_map:
                continue

            yield self._prepare_single_chapter_item(i, abstraction_idx_for_chapter, prep_context)
            num_items_prepared += 1
        self._log_info("Prepared %d chapter items for execution.", num_items_prepared)

    def _call_llm_for_chapter_with_retry(
        self,
        prompt_context: WriteChapterContext,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
        chapter_num_log: Any,
        abstraction_name_log: Any,
    ) -> str:
        """Call LLM for a single chapter, with internal retry logic.

        Args:
            prompt_context: The context for formatting the chapter prompt.
            llm_config: Configuration for the LLM API.
            cache_config: Configuration for LLM caching.
            chapter_num_log: The chapter number, for logging purposes.
            abstraction_name_log: The abstraction name, for logging purposes.

        Returns:
            The raw string content from the LLM or an error message.
        """
        prompt_str = ChapterPrompts.format_write_chapter_prompt(prompt_context)
        last_exception: Optional[LlmApiError] = None

        for attempt in range(self.max_retries):
            try:
                return call_llm(prompt_str, llm_config, cache_config)
            except LlmApiError as e_llm_item:
                last_exception = e_llm_item
                self._log_error(
                    "LLM call failed for Chapter %s ('%s'), attempt %d/%d: %s",
                    str(chapter_num_log),
                    str(abstraction_name_log),
                    attempt + 1,
                    self.max_retries,
                    e_llm_item,
                )
                if attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warn_msg = (
                        f"Node {self.__class__.__name__}, Chapter {str(chapter_num_log)} "
                        f"LLM call failed on attempt {attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e_llm_item!s}"
                    )
                    warnings.warn(warn_msg, UserWarning, stacklevel=2)
                    time.sleep(self.wait)

        err_msg_prefix = f"{ERROR_MESSAGE_PREFIX} LLM API error for chapter "
        err_details = (
            f"{str(chapter_num_log)} ('{str(abstraction_name_log)}') after {self.max_retries} attempts. "
            f"Last error: {last_exception!s}"
        )
        return err_msg_prefix + err_details if last_exception else f"{err_msg_prefix}Unknown LLM error."

    def _process_single_chapter_item(self, item: WriteChapterPreparedItem) -> SingleChapterExecutionResult:
        """Generate Markdown content for a single chapter.

        Args:
            item: A dictionary containing context for generating one chapter.

        Returns:
            A string with the chapter's Markdown content or an error message.
        """
        try:
            prompt_context: WriteChapterContext = item["prompt_context"]
            llm_config: LlmConfigDictTyped = item["llm_config"]
            cache_config: CacheConfigDictTyped = item["cache_config"]
            chapter_num_log: Any = item.get("chapter_num_for_log", "Unknown")
            abstraction_name_log: Any = item.get("abstraction_name_for_log", "Unknown")
        except (KeyError, TypeError) as e_params:
            self._log_error("Invalid structure in chapter prep item: %s", str(e_params), exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX} Internal error: Invalid prep item structure ({e_params!s})."

        self._log_info(
            "Writing Chapter %s: '%s' using LLM (max_retries_per_item=%d)...",
            str(chapter_num_log),
            str(abstraction_name_log),
            self.max_retries,
        )

        raw_llm_content = self._call_llm_for_chapter_with_retry(
            prompt_context, llm_config, cache_config, chapter_num_log, abstraction_name_log
        )

        if raw_llm_content.startswith(ERROR_MESSAGE_PREFIX):
            return raw_llm_content

        chapter_content = str(raw_llm_content or "").strip()
        expected_heading = f"# Chapter {prompt_context.chapter_num}: {prompt_context.abstraction_name}"

        if not chapter_content:
            self._log_warning(
                "LLM returned empty content for Chapter %d ('%s').",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            return f"{ERROR_MESSAGE_PREFIX} Empty content for Chapter {prompt_context.chapter_num}."

        updated_content, num_replacements = re.subn(
            r"^\s*#\s+.*", expected_heading, chapter_content, count=1, flags=re.MULTILINE
        )
        if num_replacements == 0:
            self._log_warning(
                "Chapter %d did not start with H1. Prepending correct heading.", prompt_context.chapter_num
            )
            chapter_content = f"{expected_heading}\n\n{chapter_content}"
        else:
            chapter_content = updated_content

        self._log_info("Successfully generated content for Chapter %d.", prompt_context.chapter_num)
        return chapter_content.strip()

    def execution(self, items_iterable: Iterable[WriteChapterPreparedItem]) -> WriteChaptersExecutionResultList:
        """Generate Markdown content for each chapter item in the batch.

        Args:
            items_iterable: An iterable of `WriteChapterPreparedItem` dictionaries.

        Returns:
            A list of strings, each being the content for a chapter or an error message.
        """
        self._log_info("Executing batch generation of chapters...")
        results: WriteChaptersExecutionResultList = []
        item_count = 0
        for item in items_iterable:
            item_count += 1
            chapter_content_or_error = self._process_single_chapter_item(item)
            results.append(chapter_content_or_error)

        self._log_info("Finished executing batch of %d chapter items.", item_count)
        return results

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_items_iterable: Iterable[WriteChapterPreparedItem],
        execution_results_list: WriteChaptersExecutionResultList,
    ) -> None:
        """Update the shared context with the list of generated chapter content.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_items_iterable: The iterable of items that were prepared.
            execution_results_list: A list of strings with chapter content or errors.
        """
        del prepared_items_iterable

        shared_context["chapters"] = execution_results_list
        valid_chapter_count = sum(
            1 for content in execution_results_list if not content.startswith(ERROR_MESSAGE_PREFIX)
        )
        failed_chapter_count = len(execution_results_list) - valid_chapter_count

        log_msg = f"Stored {len(execution_results_list)} chapter strings in shared context."
        if failed_chapter_count > 0:
            log_msg += f" ({failed_chapter_count} chapters had errors during generation)."
        else:
            log_msg += " All chapters generated or processed successfully."
        self._log_info(log_msg)


# End of src/FL01_code_analysis/nodes/n07_write_chapters.py
