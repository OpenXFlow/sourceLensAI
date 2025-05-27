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

import time
import warnings
from collections.abc import Iterable
from typing import Any, Final, Optional

from typing_extensions import TypeAlias

from sourcelens.prompts import ChapterPrompts, WriteChapterContext
from sourcelens.utils.helpers import get_content_for_indices, sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

from .base_node import BaseBatchNode, SLSharedContext

WriteChapterPreparedItem: TypeAlias = dict[str, Any]
SingleChapterExecutionResult: TypeAlias = str
WriteChaptersExecutionResultList: TypeAlias = list[SingleChapterExecutionResult]

FileDataOptionalContentInternal: TypeAlias = tuple[str, Optional[str]]
FileDataListOptionalContentInternal: TypeAlias = list[FileDataOptionalContentInternal]
FileDataStrictContentInternal: TypeAlias = tuple[str, str]
FileDataListStrictContentInternal: TypeAlias = list[FileDataStrictContentInternal]

AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
ChapterOrderListInternal: TypeAlias = list[int]
ChapterMetadataInternal: TypeAlias = dict[str, Any]

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]


ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"
DEFAULT_LANGUAGE_CODE: Final[str] = "english"
DEFAULT_PROJECT_NAME: Final[str] = "Unknown Project"
FILENAME_CHAPTER_PREFIX_WIDTH: Final[int] = 2


class WriteChapters(BaseBatchNode[WriteChapterPreparedItem, SingleChapterExecutionResult]):
    """Write individual tutorial chapters using an LLM via batch processing.

    The `pre_execution` method prepares an iterable of items, each representing
    the context for a single chapter. The `execution` method iterates through
    these items, calling an LLM for each to generate chapter content.
    This node implements per-item retry logic for LLM calls internally.
    """

    def _prepare_chapter_metadata(
        self, abstractions: AbstractionsListInternal, chapter_order: ChapterOrderListInternal
    ) -> tuple[dict[int, ChapterMetadataInternal], list[str]]:
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
                  `ChapterMetadataInternal` (name, number, filename).
                - A list of Markdown-formatted strings, each representing a link
                  to a chapter in the planned tutorial structure.
        """
        chapter_metadata_map: dict[int, ChapterMetadataInternal] = {}
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
            abstraction_item: AbstractionItemInternal = abstractions[abstraction_index]
            chapter_name_raw_any: Any = abstraction_item.get("name")
            chapter_name: str = (
                str(chapter_name_raw_any)
                if isinstance(chapter_name_raw_any, str) and chapter_name_raw_any.strip()
                else f"Concept {chapter_num}"
            )
            safe_filename_base = sanitize_filename(chapter_name) or f"chapter-{chapter_num}"
            filename = f"{chapter_num:0{FILENAME_CHAPTER_PREFIX_WIDTH}d}_{safe_filename_base}.md"

            metadata: ChapterMetadataInternal = {
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
        abstractions: AbstractionsListInternal,
        files_data: FileDataListOptionalContentInternal,
        project_name: str,
        chapter_metadata_map: dict[int, ChapterMetadataInternal],
        chapter_order: ChapterOrderListInternal,
        full_chapter_structure_md: str,
        language: str,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
    ) -> WriteChapterPreparedItem:
        """Prepare the data item (context) for generating a single chapter.

        This involves gathering the specific abstraction details, relevant code snippets,
        and contextual information about neighboring chapters.

        Args:
            chapter_index_in_order: 0-based index of the current chapter in the `chapter_order` list.
            abstraction_index: The index of the core abstraction for this chapter from the main `abstractions` list.
            abstractions: The full list of identified abstractions.
            files_data: The full list of (filepath, Optional[content]) tuples for the project.
            project_name: The name of the project.
            chapter_metadata_map: A map from abstraction_index to `ChapterMetadataInternal`.
            chapter_order: The ordered list of abstraction indices representing chapter sequence.
            full_chapter_structure_md: A Markdown string listing all planned chapters (for context).
            language: The target language for the chapter content.
            llm_config: Configuration for the LLM API.
            cache_config: Configuration for LLM caching.

        Returns:
            A dictionary (`WriteChapterPreparedItem`) containing all necessary context
            for the `_process_single_chapter_item` method to generate one chapter.
        """
        abstraction_details: AbstractionItemInternal = abstractions[abstraction_index]
        related_file_indices_any: Any = abstraction_details.get("files", [])
        related_file_indices: list[int] = (
            [idx for idx in related_file_indices_any if isinstance(idx, int)]
            if isinstance(related_file_indices_any, list)
            else []
        )

        files_data_for_context: FileDataListStrictContentInternal = []
        for path, content in files_data:
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

        prev_chapter_meta: Optional[ChapterMetadataInternal] = None
        if chapter_index_in_order > 0:
            prev_abs_idx = chapter_order[chapter_index_in_order - 1]
            prev_chapter_meta = chapter_metadata_map.get(prev_abs_idx)

        next_chapter_meta: Optional[ChapterMetadataInternal] = None
        if chapter_index_in_order < len(chapter_order) - 1:
            next_abs_idx = chapter_order[chapter_index_in_order + 1]
            next_chapter_meta = chapter_metadata_map.get(next_abs_idx)

        current_chapter_metadata: ChapterMetadataInternal = chapter_metadata_map[abstraction_index]
        current_chapter_name: str = str(current_chapter_metadata.get("name", "Unknown Chapter"))
        current_chapter_num_any: Any = current_chapter_metadata.get("num", chapter_index_in_order + 1)
        current_chapter_num: int = (
            int(current_chapter_num_any)
            if isinstance(current_chapter_num_any, (int, float)) and float(current_chapter_num_any).is_integer()
            else (chapter_index_in_order + 1)
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
            prev_chapter_meta=prev_chapter_meta,  # type: ignore[arg-type]
            next_chapter_meta=next_chapter_meta,  # type: ignore[arg-type]
        )
        prepared_item: WriteChapterPreparedItem = {
            "prompt_context": prompt_ctx,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "chapter_num_for_log": current_chapter_num,
            "abstraction_name_for_log": current_chapter_name,
        }
        return prepared_item

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WriteChapterPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of data items, each for generating one chapter.

        This method retrieves necessary data (abstractions, chapter order, file contents,
        configurations) from the `shared_context`. It then constructs metadata for
        each chapter (like name, number, filename) and assembles a `WriteChapterContext`
        object for each. These context objects, along with LLM configurations,
        are yielded one by one for batch processing by the `execution` method.

        Args:
            shared_context: The shared context dictionary containing data from
                            previous pipeline nodes.

        Yields:
            `WriteChapterPreparedItem` dictionaries, each containing all necessary
            information and context to generate a single tutorial chapter.
            If prerequisites (like chapter order or abstractions) are missing,
            it may yield no items.
        """
        self._log_info("Preparing data for writing chapters individually...")
        try:
            chapter_order_any: Any = self._get_required_shared(shared_context, "chapter_order")
            abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
            files_data_any: Any = self._get_required_shared(shared_context, "files")
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            language_any: Any = shared_context.get("language", DEFAULT_LANGUAGE_CODE)

            chapter_order: ChapterOrderListInternal = chapter_order_any if isinstance(chapter_order_any, list) else []
            abstractions: AbstractionsListInternal = abstractions_any if isinstance(abstractions_any, list) else []
            files_data: FileDataListOptionalContentInternal = files_data_any if isinstance(files_data_any, list) else []
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else DEFAULT_PROJECT_NAME
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            language: str = str(language_any) if isinstance(language_any, str) else DEFAULT_LANGUAGE_CODE

        except ValueError:
            self._log_error("WriteChapters.pre_execution: Failed due to missing essential shared data.", exc_info=True)
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

    def _call_llm_for_chapter_with_retry(
        self,
        prompt_context: WriteChapterContext,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
        chapter_num_log: Any,
        abstraction_name_log: Any,
    ) -> str:
        """Call LLM for a single chapter, with internal retry logic using node's settings.

        This method attempts to call the LLM up to `self.max_retries` times,
        waiting `self.wait` seconds between attempts if an `LlmApiError` occurs.

        Args:
            prompt_context: The context for formatting the chapter prompt.
            llm_config: Configuration for the LLM API.
            cache_config: Configuration for LLM caching.
            chapter_num_log: The chapter number, for logging purposes.
            abstraction_name_log: The abstraction name, for logging purposes.

        Returns:
            The raw string content from the LLM if successful, or a formatted
            error message string if all retry attempts fail.
        """
        prompt_str = ChapterPrompts.format_write_chapter_prompt(prompt_context)
        last_exception: Optional[LlmApiError] = None

        for attempt in range(self.max_retries):  # self.max_retries from CoreNode
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
                if attempt == self.max_retries - 1:  # Last attempt
                    break
                if self.wait > 0:  # self.wait from CoreNode
                    warn_msg_l1 = (
                        f"Node {self.__class__.__name__}, Chapter {str(chapter_num_log)} "
                        f"LLM call failed on attempt {attempt + 1}/{self.max_retries}."
                    )
                    warn_msg_l2 = f" Retrying after {self.wait}s. Error: {e_llm_item!s}"
                    warnings.warn(warn_msg_l1 + warn_msg_l2, UserWarning, stacklevel=2)
                    time.sleep(self.wait)
        # If all retries failed
        if last_exception:
            return (
                f"{ERROR_MESSAGE_PREFIX} LLM API error for chapter "
                f"{str(chapter_num_log)} ('{str(abstraction_name_log)}') after {self.max_retries} attempts. "
                f"Last error: {last_exception!s}"
            )
        # Fallback if loop completes without LlmApiError but no success (should be rare)
        return (
            f"{ERROR_MESSAGE_PREFIX} Unknown LLM error for chapter "
            f"{str(chapter_num_log)} ('{str(abstraction_name_log)}') after {self.max_retries} attempts."
        )

    def _process_single_chapter_item(self, item: WriteChapterPreparedItem) -> SingleChapterExecutionResult:
        """Generate Markdown content for a single chapter.

        This method extracts necessary parameters from the prepared `item`,
        calls the LLM (with retry logic handled by `_call_llm_for_chapter_with_retry`),
        and formats the LLM's response, ensuring a correct H1 heading.

        Args:
            item: A `WriteChapterPreparedItem` dictionary containing all context
                  and configurations for generating one chapter.

        Returns:
            A string, either the formatted Markdown content of the chapter or
            an error message string if generation failed.
        """
        try:
            prompt_context_any: Any = item["prompt_context"]
            llm_config_any: Any = item["llm_config"]
            cache_config_any: Any = item["cache_config"]
            chapter_num_log: Any = item.get("chapter_num_for_log", "Unknown")
            abstraction_name_log: Any = item.get("abstraction_name_for_log", "Unknown")

            if not isinstance(prompt_context_any, WriteChapterContext):
                raise TypeError(f"Expected WriteChapterContext, got {type(prompt_context_any).__name__}")
            prompt_context: WriteChapterContext = prompt_context_any
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}

        except (KeyError, TypeError) as e_params:
            self._log_error("Invalid structure in chapter prep item. Error: %s", str(e_params), exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX} Internal error: Invalid prep item structure ({e_params!s})."

        self._log_info(
            "Writing Chapter %s: '%s' using LLM (max_retries_per_item=%d)...",
            str(chapter_num_log),
            str(abstraction_name_log),
            self.max_retries,  # Using inherited max_retries for per-item logic
        )

        raw_llm_content = self._call_llm_for_chapter_with_retry(
            prompt_context, llm_config, cache_config, chapter_num_log, abstraction_name_log
        )

        if raw_llm_content.startswith(ERROR_MESSAGE_PREFIX):  # Error already formatted by retry helper
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

        # Ensure correct H1 heading
        if not chapter_content.startswith(f"# Chapter {prompt_context.chapter_num}"):
            self._log_warning(
                "Chapter %d ('%s') response missing/incorrect H1. Attempting to prepend.",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            lines = chapter_content.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):  # If another H1 exists, replace it
                content_after_h1 = lines[1] if len(lines) > 1 and lines[1].strip() else ""
                chapter_content = expected_heading + ("\n\n" + content_after_h1 if content_after_h1 else "")
            else:  # No H1, prepend ours
                chapter_content = f"{expected_heading}\n\n{chapter_content}"
        elif not chapter_content.startswith(expected_heading):  # H1 exists but differs
            self._log_warning(
                "Chapter %d ('%s') H1 differs from expected. Overwriting.",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
            )
            first_newline_idx = chapter_content.find("\n")
            chapter_content = (
                expected_heading + chapter_content[first_newline_idx:] if first_newline_idx != -1 else expected_heading
            )

        self._log_info("Successfully generated content for Chapter %d.", prompt_context.chapter_num)
        return chapter_content.strip()

    def execution(  # type: ignore[override]
        self, items_iterable: Iterable[WriteChapterPreparedItem]
    ) -> WriteChaptersExecutionResultList:
        """Generate Markdown content for each chapter item in the batch.

        This method iterates through the `WriteChapterPreparedItem` objects yielded
        by `pre_execution`. For each item, it calls `_process_single_chapter_item`
        to generate the chapter content, which includes internal retry logic for
        LLM calls. The results (chapter content strings or error messages) are
        collected into a list.

        The retry mechanism inherited from the parent `Node` class applies to this
        `execution` method as a whole. If this method itself were to raise a
        recoverable exception (which is unlikely given current `_process_single_chapter_item`
        error handling), the entire batch processing would be retried.

        Args:
            items_iterable: An iterable of `WriteChapterPreparedItem` dictionaries,
                            each containing context for one chapter.

        Returns:
            A list of strings, where each string is either the successfully
            generated Markdown content for a chapter or a formatted error
            message if generation for that specific chapter failed after retries.
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

    def post_execution(  # type: ignore[override]
        self,
        shared_context: SLSharedContext,
        prepared_items_iterable: Iterable[WriteChapterPreparedItem],
        execution_results_list: WriteChaptersExecutionResultList,
    ) -> None:
        """Update the shared context with the list of generated chapter content or error messages.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_items_iterable: The iterable of items that were prepared (unused here).
            execution_results_list: A list of strings, where each string is either
                                    the Markdown content for a chapter or an error
                                    message if generation for that chapter failed.
        """
        del prepared_items_iterable  # Mark as unused

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


# End of src/sourcelens/nodes/n07_write_chapters.py
