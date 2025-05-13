# src/sourcelens/nodes/write.py

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

# --- Type Aliases specific to this Node ---
WriteChapterPrepItem: TypeAlias = dict[str, Any]
WriteChapterExecResult: TypeAlias = str

# --- Other Type Aliases used within this module ---
FileDataList: TypeAlias = list[tuple[str, str]]
AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]
ChapterOrderList: TypeAlias = list[int]
ChapterMetadata: TypeAlias = dict[str, Any]

# --- Constants ---
ERROR_MESSAGE_PREFIX: Final[str] = "Error generating chapter content:"
DEFAULT_LANGUAGE_CODE: Final[str] = "english"
DEFAULT_PROJECT_NAME: Final[str] = "Unknown Project"


class WriteChapters(BaseBatchNode[WriteChapterPrepItem, WriteChapterExecResult]):
    """Write individual tutorial chapters using an LLM via batch processing.

    The `prep` method prepares a context item for each chapter to be written.
    The `exec` method is then called by the flow engine for each of these items,
    generating the Markdown content for one chapter.
    The `post` method collects all generated chapter contents.
    """

    # __init__ is inherited from BaseBatchNode, which initializes self._logger

    def _prepare_chapter_metadata(
        self: "WriteChapters", abstractions: AbstractionsList, chapter_order: ChapterOrderList
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
                self._log_warning(
                    "Invalid abstraction index %d in chapter order at position %d. Skipping metadata.",
                    abstraction_index,
                    i,
                )
                continue

            chapter_num = i + 1
            abstraction_item = abstractions[abstraction_index]
            chapter_name_raw: Any = abstraction_item.get("name")
            chapter_name = (
                str(chapter_name_raw)
                if isinstance(chapter_name_raw, str) and chapter_name_raw.strip()
                else f"Concept {chapter_num}"
            )
            safe_filename_base = sanitize_filename(chapter_name) or f"chapter-{chapter_num}"
            filename = f"{chapter_num:02d}_{safe_filename_base}.md"

            metadata: ChapterMetadata = {
                "num": chapter_num,
                "name": chapter_name,
                "filename": filename,
                "abstraction_index": abstraction_index,
            }
            chapter_metadata_map[abstraction_index] = metadata
            all_chapters_listing_md.append(f"{chapter_num}. [{chapter_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing_md

    def _prepare_single_chapter_item(  # noqa: PLR0913
        self: "WriteChapters",
        chapter_index_in_order: int,
        abstraction_index: int,
        abstractions: AbstractionsList,
        files_data: FileDataList,
        project_name: str,
        chapter_metadata_map: dict[int, ChapterMetadata],
        chapter_order: ChapterOrderList,
        full_chapter_structure_md: str,
        language: str,
        llm_config: dict[str, Any],
        cache_config: dict[str, Any],
    ) -> WriteChapterPrepItem:
        """Prepare the data item (context) for a single chapter.

        Args:
            chapter_index_in_order: 0-based index in `chapter_order`.
            abstraction_index: Index from the main `abstractions` list.
            abstractions: Full list of abstractions.
            files_data: Full list of (filepath, content) tuples.
            project_name: Name of the project.
            chapter_metadata_map: Map from abstraction_index to `ChapterMetadata`.
            chapter_order: Ordered list of abstraction indices.
            full_chapter_structure_md: Markdown string listing all chapters.
            language: Target language for the chapter.
            llm_config: LLM API configuration.
            cache_config: LLM cache configuration.

        Returns:
            A `WriteChapterPrepItem` dictionary for the `exec` method.

        """
        abstraction_details = abstractions[abstraction_index]
        related_file_indices_raw: Any = abstraction_details.get("files", [])
        related_file_indices: list[int] = (
            [idx for idx in related_file_indices_raw if isinstance(idx, int)]
            if isinstance(related_file_indices_raw, list)
            else []
        )

        related_files_content_map = get_content_for_indices(files_data, related_file_indices)
        file_context_str_parts: list[str] = []
        if related_files_content_map:
            for idx_path, content in related_files_content_map.items():
                path_display = idx_path.split("# ", 1)[1] if "# " in idx_path else idx_path
                path_display = path_display.replace(chr(92), "/")
                file_context_str_parts.append(f"--- File: {path_display} ---\n{content}")
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

        current_chapter_metadata = chapter_metadata_map[abstraction_index]

        prompt_ctx = WriteChapterContext(
            project_name=project_name,
            chapter_num=current_chapter_metadata["num"],
            abstraction_name=current_chapter_metadata["name"],
            abstraction_description=str(abstraction_details.get("description", "N/A")),
            full_chapter_structure=full_chapter_structure_md,
            previous_context_info="Refer to the 'Overall Tutorial Structure' for context.",
            file_context_str=file_context_str,
            language=language,
            prev_chapter_meta=prev_chapter_meta,
            next_chapter_meta=next_chapter_meta,
        )
        return {"prompt_context": prompt_ctx, "llm_config": llm_config, "cache_config": cache_config}

    def prep(self, shared: SLSharedState) -> Iterable[WriteChapterPrepItem]:
        """Prepare an iterable of dictionaries, one for each chapter.

        Args:
            shared: The shared state dictionary.

        Returns:
            An iterable of `WriteChapterPrepItem` dictionaries.

        """
        self._log_info("Preparing data for writing chapters individually...")
        try:
            chapter_order: ChapterOrderList = self._get_required_shared(shared, "chapter_order")
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            files_data: FileDataList = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            language: str = str(shared.get("language", DEFAULT_LANGUAGE_CODE))
        except ValueError:
            self._log_error("WriteChapters.prep: Failed due to missing essential shared data.", exc_info=True)
            return iter([])  # Explicitly return empty iterable

        if not chapter_order or not abstractions:
            self._log_warning("No chapter order or abstractions available. No chapters will be written.")
            return iter([])  # Explicitly return empty iterable

        chapter_metadata_map, all_chapters_listing_md = self._prepare_chapter_metadata(abstractions, chapter_order)
        full_chapter_structure_md: str = "\n".join(all_chapters_listing_md)
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
        # Implicit return of generator is an Iterable

    def exec(self, item: WriteChapterPrepItem) -> WriteChapterExecResult:
        """Generate the Markdown content for a single chapter using the LLM.

        Args:
            item: A `WriteChapterPrepItem` dictionary.

        Returns:
            A string with Markdown content or an error message.

        Raises:
            LlmApiError: Propagated from `call_llm` to allow retries.

        """
        try:
            prompt_context: WriteChapterContext = item["prompt_context"]
            llm_config: dict[str, Any] = item["llm_config"]
            cache_config: dict[str, Any] = item["cache_config"]
        except KeyError as e_key:
            missing_key = str(e_key)
            self._log_error(
                "Missing key '%s' in chapter prep item. Keys: %s", missing_key, list(item.keys()), exc_info=True
            )
            return f"{ERROR_MESSAGE_PREFIX} Internal error: Missing key '{missing_key}' for chapter."

        self._log_info(
            "Writing Chapter %d: '%s' using LLM...", prompt_context.chapter_num, prompt_context.abstraction_name
        )
        try:
            prompt_str = ChapterPrompts.format_write_chapter_prompt(prompt_context)
            chapter_content_raw: str = call_llm(prompt_str, llm_config, cache_config)
            chapter_content: str = str(chapter_content_raw or "").strip()
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
                "Unexpected error during Chapter %d ('%s') exec: %s",
                prompt_context.chapter_num,
                prompt_context.abstraction_name,
                e_unexpected,
                exc_info=True,
            )
            return (
                f"{ERROR_MESSAGE_PREFIX} Unexpected problem generating chapter "
                f"{prompt_context.chapter_num} ('{prompt_context.abstraction_name}'): {e_unexpected!s}"
            )

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
            first_newline = chapter_content.find("\n")
            chapter_content = (
                expected_heading + chapter_content[first_newline:] if first_newline != -1 else expected_heading
            )

        self._log_info("Successfully generated content for Chapter %d.", prompt_context.chapter_num)
        return chapter_content.strip()

    def post(
        self,
        shared: SLSharedState,
        prep_res: Iterable[WriteChapterPrepItem],
        exec_res_list: list[WriteChapterExecResult],
    ) -> None:
        """Update the shared state with the list of generated chapter content.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The iterable of items that were prepared for execution.
            exec_res_list: A list of strings (Markdown content or error messages).

        """
        del prep_res

        chapters_valid_content: list[str] = []
        failed_chapter_count = 0
        for i, chapter_content_or_error in enumerate(exec_res_list):
            if isinstance(chapter_content_or_error, str) and not chapter_content_or_error.startswith(
                ERROR_MESSAGE_PREFIX
            ):
                chapters_valid_content.append(chapter_content_or_error)
            else:
                failed_chapter_count += 1
                # E501 fix: Broke long log message
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


# End of src/sourcelens/nodes/write.py
