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

"""Node responsible for generating Markdown content for individual web content chapters."""

import logging
import time
import warnings
from collections.abc import Iterable
from typing import Any, Final, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseBatchNode, SLSharedContext
from sourcelens.core.common_types import (
    WebContentChunk,
    WebContentChunkList,
    WebContentConceptItem,
    WebContentConceptsList,
)
from sourcelens.utils.helpers import sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

from ..prompts.chapter_prompts import WebChapterPrompts, WriteWebChapterContext

# Type Aliases
WriteWebChapterPreparedItem: TypeAlias = dict[str, Any]
SingleWebChapterExecutionResult: TypeAlias = str
WriteWebChaptersExecutionResultList: TypeAlias = list[SingleWebChapterExecutionResult]

WebChapterOrderList: TypeAlias = list[int]
WebChapterMetadataInternal: TypeAlias = dict[str, Any]


LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_write_web_chaps: logging.Logger = logging.getLogger(__name__)

ERROR_MESSAGE_PREFIX_WEB_CHAP: Final[str] = "Error generating web chapter content:"
DEFAULT_LANGUAGE_CODE_WEB_CHAP: Final[str] = "english"
DEFAULT_PROJECT_NAME_WEB_CHAP: Final[str] = "Web Content Summary"
FILENAME_WEB_CHAPTER_PREFIX_WIDTH: Final[int] = 2
MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT: Final[int] = 3000


class WriteWebChapters(BaseBatchNode[WriteWebChapterPreparedItem, SingleWebChapterExecutionResult]):
    """Write individual web content summary chapters using an LLM via batch processing."""

    def _prepare_web_chapter_metadata(
        self, concepts: WebContentConceptsList, chapter_order: WebChapterOrderList
    ) -> tuple[dict[int, WebChapterMetadataInternal], list[str]]:
        """Prepare metadata for each web chapter.

        Args:
            concepts: List of all identified web concepts.
            chapter_order: List of concept indices specifying chapter order.

        Returns:
            A tuple containing:
                - Dict mapping concept_index to its metadata.
                - Markdown list of all planned chapters.
        """
        chapter_metadata_map: dict[int, WebChapterMetadataInternal] = {}
        all_chapters_listing_md: list[str] = []
        num_concepts = len(concepts)

        for i, concept_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= concept_idx_for_chapter < num_concepts):
                self._log_warning(
                    "Invalid concept_index %d in chapter order at position %d. Skipping metadata.",
                    concept_idx_for_chapter,
                    i,
                )
                continue

            chapter_num = i + 1
            concept_item: WebContentConceptItem = concepts[concept_idx_for_chapter]
            concept_name_raw: Any = concept_item.get("name")
            concept_name: str = (
                str(concept_name_raw).strip()
                if isinstance(concept_name_raw, str) and concept_name_raw.strip()
                else f"Topic {chapter_num}"
            )
            safe_filename_base = sanitize_filename(concept_name) or f"chapter-{chapter_num}"
            filename = f"{chapter_num:0{FILENAME_WEB_CHAPTER_PREFIX_WIDTH}d}_{safe_filename_base}.md"

            metadata: WebChapterMetadataInternal = {
                "num": chapter_num,
                "name": concept_name,
                "filename": filename,
                "concept_index": concept_idx_for_chapter,
            }
            chapter_metadata_map[concept_idx_for_chapter] = metadata
            all_chapters_listing_md.append(f"{chapter_num}. [{concept_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing_md

    def _get_relevant_snippets_for_concept(
        self, concept_item: WebContentConceptItem, web_content_chunks: WebContentChunkList
    ) -> str:
        """Retrieve and concatenate content snippets from relevant chunks for a given concept.

        Args:
            concept_item: The concept for which to get snippets.
                          It should have a 'source_chunk_ids' key.
            web_content_chunks: List of all available WebContentChunk dictionaries.

        Returns:
            A string containing concatenated relevant document snippets,
            or a message if no relevant snippets are found.
        """
        source_chunk_ids_raw: Any = concept_item.get("source_chunk_ids", [])
        source_chunk_ids: list[str] = (
            [str(cid) for cid in source_chunk_ids_raw if isinstance(cid, str)]
            if isinstance(source_chunk_ids_raw, list)
            else []
        )

        if not source_chunk_ids:
            return "No specific source document chunks were linked to this concept during identification."

        content_by_chunk_id: dict[str, str] = {
            str(chunk.get("chunk_id", "")): str(chunk.get("content", ""))
            for chunk in web_content_chunks
            if chunk.get("chunk_id")
        }
        relevant_snippets: list[str] = []

        for chunk_id_key in source_chunk_ids:
            if chunk_id_key in content_by_chunk_id:
                content = content_by_chunk_id[chunk_id_key]
                snippet = content[:MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT]
                if len(content) > MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT:
                    snippet += "..."
                relevant_snippets.append(f"--- Snippet from Chunk ID: {chunk_id_key} ---\n{snippet}\n\n")
            else:
                self._log_warning(
                    "Chunk ID '%s' listed in concept '%s' not found in available web_content_chunks. Snippet skipped.",
                    chunk_id_key,
                    concept_item.get("name", "Unknown Concept"),
                )

        if not relevant_snippets:
            return "Could not retrieve content for any of the source document chunks linked to this concept."
        return "".join(relevant_snippets)

    def _get_context_from_shared(self, shared_context: SLSharedContext) -> dict[str, Any]:
        """Retrieve and validate necessary data from shared_context for pre_execution.

        Args:
            shared_context: The main shared context dictionary.

        Returns:
            A dictionary containing validated data or an error flag.

        Raises:
            ValueError: If essential shared data is missing.
        """
        chapter_order_any: Any = self._get_required_shared(shared_context, "text_chapter_order")
        concepts_any: Any = self._get_required_shared(shared_context, "text_concepts")
        web_chunks_any: Any = self._get_required_shared(shared_context, "web_content_chunks")
        project_name_any: Any = self._get_required_shared(shared_context, "project_name")
        llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
        target_language_any: Any = shared_context.get("language", DEFAULT_LANGUAGE_CODE_WEB_CHAP)

        chapter_order: WebChapterOrderList = (
            cast(WebChapterOrderList, chapter_order_any)
            if isinstance(chapter_order_any, list) and all(isinstance(i, int) for i in chapter_order_any)
            else []
        )
        concepts: WebContentConceptsList = (
            cast(WebContentConceptsList, concepts_any)
            if isinstance(concepts_any, list) and all(isinstance(i, dict) for i in concepts_any)
            else []
        )

        web_chunks: WebContentChunkList = []
        if isinstance(web_chunks_any, list):
            for item in web_chunks_any:
                if isinstance(item, dict) and "chunk_id" in item and "content" in item:
                    web_chunks.append(cast(WebContentChunk, item))
        if len(web_chunks_any or []) != len(web_chunks):
            self._log_warning("Some items in shared_context['web_content_chunks'] were invalid for chapter prep.")

        return {
            "chapter_order": chapter_order,
            "concepts": concepts,
            "web_content_chunks": web_chunks,
            "project_name": str(project_name_any),
            "llm_config": cast(LlmConfigDictTyped, llm_config_any) if isinstance(llm_config_any, dict) else {},
            "cache_config": cast(CacheConfigDictTyped, cache_config_any) if isinstance(cache_config_any, dict) else {},
            "target_language": str(target_language_any),
        }

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WriteWebChapterPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of data items, each for generating one web chapter.

        Args:
            shared_context: The shared context dictionary.

        Yields:
            Dictionaries with context for single chapter generation.
        """
        self._log_info("Preparing data for writing web content chapters individually...")
        try:
            context_data = self._get_context_from_shared(shared_context)
        except ValueError as e_val:
            self._log_error("WriteWebChapters.pre_execution: Failed due to missing shared data: %s", e_val)
            return  # Stop iteration by returning

        chapter_order: WebChapterOrderList = context_data["chapter_order"]
        concepts: WebContentConceptsList = context_data["concepts"]
        web_content_chunks: WebContentChunkList = context_data["web_content_chunks"]

        if not chapter_order or not concepts:
            self._log_warning("No web chapter order or concepts available. No web chapters will be written.")
            return  # Stop iteration

        if not web_content_chunks:  # Check if chunks are available
            self._log_warning(
                "No web content chunks available in shared_context['web_content_chunks']. "
                "Web chapters will lack relevant snippets from source documents."
            )
            # Optionally, could decide to return here if chunks are essential

        chapter_metadata_map, all_chapters_md_list = self._prepare_web_chapter_metadata(concepts, chapter_order)
        full_chapter_structure_md: str = "\n".join(all_chapters_md_list)
        num_concepts = len(concepts)
        num_items_prepared = 0

        for i, concept_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= concept_idx_for_chapter < num_concepts):
                self._log_warning("Skipping web chapter prep: invalid concept_index %d.", concept_idx_for_chapter)
                continue
            if concept_idx_for_chapter not in chapter_metadata_map:
                self._log_error("No metadata for concept_index %d. Skipping web chapter.", concept_idx_for_chapter)
                continue

            current_concept_item = concepts[concept_idx_for_chapter]
            relevant_snippets_str = self._get_relevant_snippets_for_concept(
                current_concept_item,
                web_content_chunks,  # Pass chunks here
            )

            prev_chapter_meta: Optional[WebChapterMetadataInternal] = None
            if i > 0:
                prev_concept_idx = chapter_order[i - 1]
                prev_chapter_meta = chapter_metadata_map.get(prev_concept_idx)

            next_chapter_meta: Optional[WebChapterMetadataInternal] = None
            if i < len(chapter_order) - 1:
                next_concept_idx = chapter_order[i + 1]
                next_chapter_meta = chapter_metadata_map.get(next_concept_idx)

            current_meta = chapter_metadata_map[concept_idx_for_chapter]
            chapter_ctx = WriteWebChapterContext(
                document_collection_name=context_data["project_name"],
                chapter_num=cast(int, current_meta["num"]),
                concept_name=str(current_meta["name"]),
                concept_summary=str(current_concept_item.get("summary", "N/A")),
                full_chapter_structure_md=full_chapter_structure_md,
                relevant_document_snippets=relevant_snippets_str,  # Snippets from chunks
                target_language=context_data["target_language"],
                prev_chapter_meta=prev_chapter_meta,
                next_chapter_meta=next_chapter_meta,
            )
            yield {
                "prompt_context": chapter_ctx,
                "llm_config": context_data["llm_config"],
                "cache_config": context_data["cache_config"],
                "chapter_num_for_log": current_meta["num"],
                "concept_name_for_log": current_meta["name"],
            }
            num_items_prepared += 1
        self._log_info("Prepared %d web chapter items for execution.", num_items_prepared)

    def _call_llm_for_web_chapter_with_retry(
        self,
        prompt_context: WriteWebChapterContext,
        llm_config: LlmConfigDictTyped,
        cache_config: CacheConfigDictTyped,
        chapter_num_log: Any,
        concept_name_log: Any,
    ) -> str:
        """Call LLM for a single web chapter, with internal retry logic.

        Args:
            prompt_context: Context for formatting the chapter prompt.
            llm_config: Configuration for the LLM API.
            cache_config: Configuration for LLM caching.
            chapter_num_log: Chapter number for logging.
            concept_name_log: Concept name for logging.

        Returns:
            Raw string content from LLM or a formatted error message.
        """
        prompt_str = WebChapterPrompts.format_write_web_chapter_prompt(prompt_context)
        last_exception: Optional[LlmApiError] = None

        for attempt in range(self.max_retries):
            try:
                return call_llm(prompt_str, llm_config, cache_config)
            except LlmApiError as e_llm_item:
                last_exception = e_llm_item
                self._log_error(
                    "LLM call failed for Web Chapter %s ('%s'), attempt %d/%d: %s",
                    str(chapter_num_log),
                    str(concept_name_log),
                    attempt + 1,
                    self.max_retries,
                    e_llm_item,
                )
                if attempt == self.max_retries - 1:
                    break
                if self.wait > 0:
                    warnings.warn(
                        f"Node {self.__class__.__name__}, Web Chapter {str(chapter_num_log)} "
                        f"LLM call failed on attempt {attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e_llm_item!s}",
                        UserWarning,
                        stacklevel=2,
                    )
                    time.sleep(self.wait)

        error_msg_prefix_local = ERROR_MESSAGE_PREFIX_WEB_CHAP
        if last_exception:
            return (
                f"{error_msg_prefix_local} LLM API error for web chapter "
                f"{str(chapter_num_log)} ('{str(concept_name_log)}') after {self.max_retries} attempts. "
                f"Last error: {last_exception!s}"
            )
        return (  # Should not be reached if last_exception is always set on failure
            f"{error_msg_prefix_local} Unknown LLM error for web chapter "
            f"{str(chapter_num_log)} ('{str(concept_name_log)}') after {self.max_retries} attempts."
        )

    def _process_single_web_chapter_item(self, item: WriteWebChapterPreparedItem) -> SingleWebChapterExecutionResult:
        """Generate Markdown content for a single web chapter.

        Args:
            item: Dictionary with context for one chapter.

        Returns:
            Markdown content or error message string.
        """
        try:
            prompt_ctx_any: Any = item["prompt_context"]
            llm_cfg_any: Any = item["llm_config"]
            cache_cfg_any: Any = item["cache_config"]
            chap_num_log: Any = item.get("chapter_num_for_log", "Unknown")
            conc_name_log: Any = item.get("concept_name_for_log", "Unknown")

            if not isinstance(prompt_ctx_any, WriteWebChapterContext):
                raise TypeError(f"Expected WriteWebChapterContext, got {type(prompt_ctx_any).__name__}")
            prompt_ctx: WriteWebChapterContext = prompt_ctx_any
            llm_cfg: LlmConfigDictTyped = cast(LlmConfigDictTyped, llm_cfg_any) if isinstance(llm_cfg_any, dict) else {}
            cache_cfg: CacheConfigDictTyped = (
                cast(CacheConfigDictTyped, cache_cfg_any) if isinstance(cache_cfg_any, dict) else {}
            )
        except (KeyError, TypeError) as e_params:
            self._log_error("Invalid structure in web chapter prep item: %s", str(e_params), exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX_WEB_CHAP} Internal error: Invalid prep item structure ({e_params!s})."

        self._log_info(
            "Writing Web Chapter %s: '%s' using LLM (max_retries_per_item=%d)...",
            str(chap_num_log),
            str(conc_name_log),
            self.max_retries,
        )
        raw_content = self._call_llm_for_web_chapter_with_retry(
            prompt_ctx, llm_cfg, cache_cfg, chap_num_log, conc_name_log
        )
        if raw_content.startswith(ERROR_MESSAGE_PREFIX_WEB_CHAP):
            return raw_content

        chapter_content = str(raw_content or "").strip()
        expected_heading = f"# Chapter {prompt_ctx.chapter_num}: {prompt_ctx.concept_name}"
        if not chapter_content:
            self._log_warning(
                "LLM returned empty content for Web Chapter %d ('%s').", prompt_ctx.chapter_num, prompt_ctx.concept_name
            )
            return f"{ERROR_MESSAGE_PREFIX_WEB_CHAP} Empty content for Web Chapter {prompt_ctx.chapter_num}."

        if not chapter_content.startswith(f"# Chapter {prompt_ctx.chapter_num}"):
            self._log_warning(
                "Web Chapter %d ('%s') response missing/incorrect H1. Prepending.",
                prompt_ctx.chapter_num,
                prompt_ctx.concept_name,
            )
            lines = chapter_content.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):
                content_after_h1 = lines[1] if len(lines) > 1 and lines[1].strip() else ""
                chapter_content = expected_heading + ("\n\n" + content_after_h1 if content_after_h1 else "")
            else:
                chapter_content = f"{expected_heading}\n\n{chapter_content}"
        elif not chapter_content.startswith(expected_heading):  # H1 is present but different
            self._log_warning(
                "Web Chapter %d ('%s') H1 differs. Overwriting.", prompt_ctx.chapter_num, prompt_ctx.concept_name
            )
            first_nl_idx = chapter_content.find("\n")
            chapter_content = (
                expected_heading + chapter_content[first_nl_idx:] if first_nl_idx != -1 else expected_heading
            )

        self._log_info("Successfully generated content for Web Chapter %d.", prompt_ctx.chapter_num)
        return chapter_content.strip()

    def execution(self, items_iterable: Iterable[WriteWebChapterPreparedItem]) -> WriteWebChaptersExecutionResultList:
        """Generate Markdown content for each web chapter item in the batch.

        Args:
            items_iterable: Iterable of prepared chapter items.

        Returns:
            List of Markdown strings (chapter content or errors).
        """
        self._log_info("Executing batch generation of web chapters...")
        results: WriteWebChaptersExecutionResultList = []
        item_count = 0
        for item in items_iterable:
            item_count += 1
            chapter_content_or_error = self._process_single_web_chapter_item(item)
            results.append(chapter_content_or_error)
        self._log_info("Finished executing batch of %d web chapter items.", item_count)
        return results

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_items_iterable: Iterable[WriteWebChapterPreparedItem],
        execution_results_list: WriteWebChaptersExecutionResultList,
    ) -> None:
        """Update shared context with generated web chapter content or error messages.

        Args:
            shared_context: The shared context dictionary.
            prepared_items_iterable: Prepared items (unused).
            execution_results_list: Generated chapter contents.
        """
        del prepared_items_iterable
        shared_context["text_chapters"] = execution_results_list
        valid_chapter_count = sum(
            1 for content in execution_results_list if not content.startswith(ERROR_MESSAGE_PREFIX_WEB_CHAP)
        )
        failed_count = len(execution_results_list) - valid_chapter_count
        log_msg = f"Stored {len(execution_results_list)} web chapter strings in shared_context['text_chapters']."
        if failed_count > 0:
            log_msg += f" ({failed_count} web chapters had errors during generation)."
        else:
            log_msg += " All web chapters generated or processed successfully."
        self._log_info(log_msg)


# End of src/FL02_web_crawling/nodes/n05_write_web_chapters.py
