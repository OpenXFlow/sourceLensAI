# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Node responsible for generating Markdown content for individual web content chapters."""

import logging
import time
import warnings
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Final, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseBatchNode, SLSharedContext
from sourcelens.utils.helpers import sanitize_filename
from sourcelens.utils.llm_api import LlmApiError, call_llm

if TYPE_CHECKING:
    from sourcelens.core.common_types import (
        CacheConfigDict,
        LlmConfigDict,
        WebChapterMetadata,
        WebContentChunk,
        WebContentChunkList,
        WebContentConceptItem,
        WebContentConceptsList,
    )

    from ..prompts._common import WriteWebChapterContext  # Relative import for flow-specific type


# Import prompt related classes from the correct location for this flow
from ..prompts.chapter_prompts import WebChapterPrompts

# Type Aliases
WriteWebChapterPreparedItem: TypeAlias = dict[str, Any]
SingleWebChapterExecutionResult: TypeAlias = str  # Markdown content or error string
WriteWebChaptersExecutionResultList: TypeAlias = list[SingleWebChapterExecutionResult]

WebChapterOrderList: TypeAlias = list[int]  # List of concept indices
WebChapterMetadataInternal: TypeAlias = dict[str, Any]  # Internal representation for this node


module_logger_write_web_chaps: logging.Logger = logging.getLogger(__name__)

ERROR_MESSAGE_PREFIX_WEB_CHAP: Final[str] = "Error generating web chapter content:"
DEFAULT_LANGUAGE_CODE_WEB_CHAP: Final[str] = "english"
DEFAULT_PROJECT_NAME_WEB_CHAP: Final[str] = "Web Content Summary"
FILENAME_WEB_CHAPTER_PREFIX_WIDTH: Final[int] = 2  # e.g., 01_, 02_
MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT: Final[int] = 3000  # Max chars for aggregated chunk snippets
MAX_AGGREGATED_SNIPPETS_FOR_PROMPT: Final[int] = 5  # Max number of chunks to aggregate for one chapter prompt


class WriteWebChapters(BaseBatchNode[WriteWebChapterPreparedItem, SingleWebChapterExecutionResult]):
    """Write individual web content summary chapters using an LLM via batch processing.

    This node iterates through an ordered list of concepts (derived from web content chunks).
    For each concept, it gathers relevant content from the source chunks, formats a
    detailed prompt, and calls an LLM to generate the Markdown content for that chapter.
    The generated chapters aim to be specific, detailed, and practically useful,
    extracting facts, examples, and explanations from the provided chunk snippets.
    """

    def _prepare_web_chapter_metadata(
        self, concepts: "WebContentConceptsList", chapter_order: WebChapterOrderList
    ) -> tuple[dict[int, WebChapterMetadataInternal], list[str]]:
        """Prepare metadata for each web chapter based on concepts and their order.

        Args:
            concepts (WebContentConceptsList): List of all identified web concepts.
            chapter_order (WebChapterOrderList): List of concept indices specifying chapter order.

        Returns:
            tuple[dict[int, WebChapterMetadataInternal], list[str]]:
                - A dictionary mapping concept_index to its metadata (chapter number, name, filename).
                - A Markdown formatted list of all planned chapter titles and their filenames for context.
        """
        chapter_metadata_map: dict[int, WebChapterMetadataInternal] = {}
        all_chapters_listing_md: list[str] = []
        num_concepts_available: int = len(concepts)

        for i, concept_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= concept_idx_for_chapter < num_concepts_available):
                self._log_warning(
                    "Invalid concept_index %d in chapter order at position %d (max index %d). Skipping metadata.",
                    concept_idx_for_chapter,
                    i,
                    num_concepts_available - 1,
                )
                continue

            chapter_num: int = i + 1  # Human-readable chapter number
            concept_item: "WebContentConceptItem" = concepts[concept_idx_for_chapter]
            concept_name_raw: Any = concept_item.get("name")
            concept_name: str = (
                str(concept_name_raw).strip()
                if isinstance(concept_name_raw, str) and concept_name_raw.strip()
                else f"Topic {chapter_num}"
            )
            safe_filename_base: str = sanitize_filename(concept_name, max_len=40) or f"chapter-{chapter_num}"
            filename: str = f"{chapter_num:0{FILENAME_WEB_CHAPTER_PREFIX_WIDTH}d}_{safe_filename_base}.md"

            metadata: WebChapterMetadataInternal = {
                "num": chapter_num,
                "name": concept_name,
                "filename": filename,
                "concept_index": concept_idx_for_chapter,  # Link back to the concept
            }
            chapter_metadata_map[concept_idx_for_chapter] = metadata
            all_chapters_listing_md.append(f"{chapter_num}. [{concept_name}]({filename})")
        return chapter_metadata_map, all_chapters_listing_md

    def _get_relevant_snippets_for_concept(
        self, concept_item: "WebContentConceptItem", web_content_chunks: "WebContentChunkList"
    ) -> str:
        """Retrieve and concatenate content snippets from relevant chunks for a given concept.

        Args:
            concept_item (WebContentConceptItem): The concept for which to get snippets.
                                                  It must have a 'source_chunk_ids' key.
            web_content_chunks (WebContentChunkList): List of all available WebContentChunk dictionaries.

        Returns:
            str: A string containing concatenated relevant document snippets,
                 limited by `MAX_AGGREGATED_SNIPPETS_FOR_PROMPT` and `MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT`.
                 Returns a message if no relevant snippets are found or chunks are missing.
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
            if chunk.get("chunk_id")  # Ensure chunk_id exists
        }
        relevant_snippets_list: list[str] = []
        total_chars_aggregated: int = 0
        num_snippets_aggregated: int = 0

        for chunk_id_key in source_chunk_ids:
            if num_snippets_aggregated >= MAX_AGGREGATED_SNIPPETS_FOR_PROMPT:
                self._log_debug(
                    "Reached max aggregated snippets (%d) for concept '%s'. Truncating context.",
                    MAX_AGGREGATED_SNIPPETS_FOR_PROMPT,
                    concept_item.get("name", "Unknown Concept"),
                )
                break

            if chunk_id_key in content_by_chunk_id:
                chunk_content: str = content_by_chunk_id[chunk_id_key]
                chars_to_add: int = len(chunk_content)
                if (total_chars_aggregated + chars_to_add) > MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT:
                    remaining_char_budget: int = MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT - total_chars_aggregated
                    snippet_part: str = chunk_content[:remaining_char_budget] + "..."
                    relevant_snippets_list.append(
                        f"--- Snippet from Chunk ID: {chunk_id_key} (truncated) ---\n{snippet_part}\n\n"
                    )
                    total_chars_aggregated += len(snippet_part)  # Approximately
                    num_snippets_aggregated += 1
                    self._log_debug(
                        "Reached max char length (%d) for aggregated snippets. Truncated chunk '%s'.",
                        MAX_SNIPPET_LEN_FOR_CHAPTER_PROMPT,
                        chunk_id_key,
                    )
                    break  # Stop adding more snippets
                else:
                    relevant_snippets_list.append(f"--- Snippet from Chunk ID: {chunk_id_key} ---\n{chunk_content}\n\n")
                    total_chars_aggregated += chars_to_add
                    num_snippets_aggregated += 1
            else:
                self._log_warning(
                    "Chunk ID '%s' listed in concept '%s' not found in available web_content_chunks. Snippet skipped.",
                    chunk_id_key,
                    concept_item.get("name", "Unknown Concept"),
                )

        if not relevant_snippets_list:
            return "Could not retrieve content for any of the source document chunks linked to this concept."
        return "".join(relevant_snippets_list)

    def _get_context_from_shared(self, shared_context: SLSharedContext) -> dict[str, Any]:
        """Retrieve and validate necessary data from shared_context for pre_execution.

        Args:
            shared_context (SLSharedContext): The main shared context dictionary.

        Returns:
            dict[str, Any]: A dictionary containing validated data or an error flag.

        Raises:
            ValueError: If essential shared data is missing or of an invalid type.
        """

        # Helper to safely cast or raise ValueError
        def _cast_or_raise(val: Any, expected_type: type, name: str) -> Any:
            if not isinstance(val, expected_type):
                raise ValueError(f"'{name}' in shared_context is not of type {expected_type.__name__}.")
            return val

        chapter_order: WebChapterOrderList = _cast_or_raise(
            self._get_required_shared(shared_context, "text_chapter_order"), list, "text_chapter_order"
        )
        concepts: "WebContentConceptsList" = _cast_or_raise(
            self._get_required_shared(shared_context, "text_concepts"), list, "text_concepts"
        )
        web_chunks_raw: list[Any] = _cast_or_raise(
            self._get_required_shared(shared_context, "web_content_chunks"), list, "web_content_chunks"
        )

        # Validate items within lists
        if not all(isinstance(i, int) for i in chapter_order):
            raise ValueError("'text_chapter_order' must be a list of integers.")
        if not all(
            isinstance(i, dict) and "name" in i and "source_chunk_ids" in i for i in concepts
        ):  # Check structure
            raise ValueError("'text_concepts' must be a list of dicts with 'name' and 'source_chunk_ids'.")

        web_chunks_validated: "WebContentChunkList" = []
        for item in web_chunks_raw:
            if isinstance(item, dict) and "chunk_id" in item and "content" in item:
                web_chunks_validated.append(cast("WebContentChunk", item))
            else:
                self._log_warning("Invalid item in shared_context['web_content_chunks'] skipped: %s", str(item)[:100])
        if len(web_chunks_raw) != len(web_chunks_validated):
            self._log_warning("Some items in shared_context['web_content_chunks'] were invalid and filtered out.")

        return {
            "chapter_order": chapter_order,
            "concepts": concepts,
            "web_content_chunks": web_chunks_validated,
            "project_name": str(self._get_required_shared(shared_context, "project_name")),
            "llm_config": cast("LlmConfigDict", self._get_required_shared(shared_context, "llm_config")),
            "cache_config": cast("CacheConfigDict", self._get_required_shared(shared_context, "cache_config")),
            "target_language": str(shared_context.get("language", DEFAULT_LANGUAGE_CODE_WEB_CHAP)),
        }

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WriteWebChapterPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of data items, each for generating one web chapter.

        This method orchestrates the setup for each chapter to be written. It retrieves
        concepts, their order, and relevant chunk content. It then formats the context
        needed for the LLM prompt for each chapter.

        Args:
            shared_context (SLSharedContext): The shared context dictionary containing all necessary
                                              data from previous nodes (concepts, order, chunks).

        Yields:
            WriteWebChapterPreparedItem: Dictionaries, each containing the full context
                                         (prompt_context, llm_config, etc.) required for
                                         generating a single web chapter. If prerequisites are not met
                                         (e.g., no concepts or chapter order), yields nothing.
        """
        self._log_info("Preparing data for writing web content chapters individually...")
        try:
            context_data: dict[str, Any] = self._get_context_from_shared(shared_context)
        except ValueError as e_val:
            self._log_error("WriteWebChapters.pre_execution: Failed due to missing or invalid shared data: %s", e_val)
            return  # Stop iteration by returning

        chapter_order: WebChapterOrderList = context_data["chapter_order"]
        concepts: "WebContentConceptsList" = context_data["concepts"]
        web_content_chunks: "WebContentChunkList" = context_data["web_content_chunks"]

        if not chapter_order or not concepts:
            self._log_warning("No web chapter order or concepts available. No web chapters will be written.")
            return

        if not web_content_chunks:
            self._log_warning(
                "No web content chunks available in shared_context['web_content_chunks']. "
                "Web chapters will lack relevant snippets from source documents. Proceeding with empty snippets."
            )
            # Proceeding, but snippets will be empty or a note.

        chapter_metadata_map: dict[int, WebChapterMetadataInternal]
        all_chapters_md_list: list[str]
        chapter_metadata_map, all_chapters_md_list = self._prepare_web_chapter_metadata(concepts, chapter_order)
        full_chapter_structure_md: str = "\n".join(all_chapters_md_list)
        num_concepts: int = len(concepts)
        num_items_prepared: int = 0

        for i, concept_idx_for_chapter in enumerate(chapter_order):
            if not (0 <= concept_idx_for_chapter < num_concepts):
                self._log_warning("Skipping web chapter prep: invalid concept_index %d.", concept_idx_for_chapter)
                continue
            if concept_idx_for_chapter not in chapter_metadata_map:
                self._log_error("No metadata for concept_index %d. Skipping web chapter.", concept_idx_for_chapter)
                continue

            current_concept_item: "WebContentConceptItem" = concepts[concept_idx_for_chapter]
            relevant_snippets_str: str = self._get_relevant_snippets_for_concept(
                current_concept_item, web_content_chunks
            )

            prev_chapter_meta_internal: Optional[WebChapterMetadataInternal] = None
            if i > 0:
                prev_concept_idx: int = chapter_order[i - 1]
                prev_chapter_meta_internal = chapter_metadata_map.get(prev_concept_idx)

            next_chapter_meta_internal: Optional[WebChapterMetadataInternal] = None
            if i < len(chapter_order) - 1:
                next_concept_idx: int = chapter_order[i + 1]
                next_chapter_meta_internal = chapter_metadata_map.get(next_concept_idx)

            current_meta: WebChapterMetadataInternal = chapter_metadata_map[concept_idx_for_chapter]
            # Construct WebChapterContext using data from WebChapterMetadataInternal
            # This now uses the flow-specific _common.WriteWebChapterContext
            from ..prompts._common import WriteWebChapterContext as FlowWriteWebChapterContext

            chapter_ctx: "FlowWriteWebChapterContext" = FlowWriteWebChapterContext(
                document_collection_name=context_data["project_name"],
                chapter_num=cast(int, current_meta["num"]),
                concept_name=str(current_meta["name"]),
                concept_summary=str(current_concept_item.get("summary", "N/A")),
                full_chapter_structure_md=full_chapter_structure_md,
                relevant_document_snippets=relevant_snippets_str,
                target_language=context_data["target_language"],
                prev_chapter_meta=cast(
                    Optional["WebChapterMetadata"], prev_chapter_meta_internal
                ),  # Cast to common type
                next_chapter_meta=cast(
                    Optional["WebChapterMetadata"], next_chapter_meta_internal
                ),  # Cast to common type
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
        prompt_context: "WriteWebChapterContext",  # Type from prompts._common
        llm_config: "LlmConfigDict",
        cache_config: "CacheConfigDict",
        chapter_num_log: Any,
        concept_name_log: Any,
    ) -> str:
        """Call LLM for a single web chapter, with internal retry logic.

        Args:
            prompt_context (WriteWebChapterContext): Context for formatting the chapter prompt.
            llm_config (LlmConfigDict): Configuration for the LLM API.
            cache_config (CacheConfigDict): Configuration for LLM caching.
            chapter_num_log (Any): Chapter number for logging.
            concept_name_log (Any): Concept name for logging.

        Returns:
            str: Raw string content from LLM or a formatted error message if all retries fail.
        """
        prompt_str: str = WebChapterPrompts.format_write_web_chapter_prompt(prompt_context)
        last_exception: Optional[LlmApiError] = None

        for attempt in range(self.max_retries):  # self.max_retries from BaseBatchNode
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
                if attempt == self.max_retries - 1:  # Last attempt
                    break
                if self.wait > 0:  # self.wait from BaseBatchNode
                    warnings.warn(
                        f"Node {self.__class__.__name__}, Web Chapter {str(chapter_num_log)} "
                        f"LLM call failed on attempt {attempt + 1}/{self.max_retries}. "
                        f"Retrying after {self.wait}s. Error: {e_llm_item!s}",
                        UserWarning,
                        stacklevel=2,
                    )
                    time.sleep(self.wait)
            # Removed broad except Exception to be more specific with LlmApiError

        # If loop finishes due to exhausting retries
        error_msg_prefix_local: str = ERROR_MESSAGE_PREFIX_WEB_CHAP
        if last_exception:
            return (
                f"{error_msg_prefix_local} LLM API error for web chapter "
                f"{str(chapter_num_log)} ('{str(concept_name_log)}') after {self.max_retries} attempts. "
                f"Last error: {last_exception!s}"
            )
        # This case should ideally not be reached if LlmApiError is always raised on failure
        return (
            f"{error_msg_prefix_local} Unknown LLM error for web chapter "
            f"{str(chapter_num_log)} ('{str(concept_name_log)}') after {self.max_retries} attempts."
        )

    def _process_single_web_chapter_item(self, item: WriteWebChapterPreparedItem) -> SingleWebChapterExecutionResult:
        """Generate Markdown content for a single web chapter based on the prepared item.

        This method handles the LLM call for one chapter and basic formatting of the response.

        Args:
            item (WriteWebChapterPreparedItem): A dictionary containing all necessary context
                                                for generating one chapter, including the
                                                `prompt_context`, `llm_config`, and `cache_config`.

        Returns:
            SingleWebChapterExecutionResult: A string containing the generated Markdown content
                                             for the chapter, or an error message string if
                                             generation failed.
        """
        try:
            # Type hinting for prompt_context should use the flow-specific one
            from ..prompts._common import WriteWebChapterContext as FlowWriteWebChapterContext

            prompt_ctx_any: Any = item["prompt_context"]
            llm_cfg_any: Any = item["llm_config"]
            cache_cfg_any: Any = item["cache_config"]
            chap_num_log: Any = item.get("chapter_num_for_log", "Unknown")
            conc_name_log: Any = item.get("concept_name_for_log", "Unknown")

            if not isinstance(prompt_ctx_any, FlowWriteWebChapterContext):
                raise TypeError(f"Expected FlowWriteWebChapterContext, got {type(prompt_ctx_any).__name__}")

            prompt_ctx: "FlowWriteWebChapterContext" = prompt_ctx_any
            llm_cfg: "LlmConfigDict" = cast("LlmConfigDict", llm_cfg_any)  # type: ignore[redundant-cast]
            cache_cfg: "CacheConfigDict" = cast("CacheConfigDict", cache_cfg_any)  # type: ignore[redundant-cast]
        except (KeyError, TypeError) as e_params:
            self._log_error("Invalid structure in web chapter prep item: %s", str(e_params), exc_info=True)
            return f"{ERROR_MESSAGE_PREFIX_WEB_CHAP} Internal error: Invalid prep item structure ({e_params!s})."

        self._log_info(
            "Writing Web Chapter %s: '%s' using LLM (node max_retries_per_item=%d)...",
            str(chap_num_log),
            str(conc_name_log),
            self.max_retries,  # This refers to the node's max_retries for this item's processing
        )
        raw_content: str = self._call_llm_for_web_chapter_with_retry(
            prompt_ctx, llm_cfg, cache_cfg, chap_num_log, conc_name_log
        )
        if raw_content.startswith(ERROR_MESSAGE_PREFIX_WEB_CHAP):
            return raw_content  # Propagate error message

        chapter_content: str = str(raw_content or "").strip()
        expected_heading: str = f"# Chapter {prompt_ctx.chapter_num}: {prompt_ctx.concept_name}"

        if not chapter_content:  # LLM returned empty string after successful call
            self._log_warning(
                "LLM returned empty content for Web Chapter %d ('%s').", prompt_ctx.chapter_num, prompt_ctx.concept_name
            )
            return f"{ERROR_MESSAGE_PREFIX_WEB_CHAP} Empty content for Web Chapter {prompt_ctx.chapter_num}."

        # Ensure H1 heading is correct as per prompt instructions
        if not chapter_content.startswith(f"# Chapter {prompt_ctx.chapter_num}"):
            self._log_warning(
                "Web Chapter %d ('%s') response missing or has incorrect H1. Prepending/Correcting.",
                prompt_ctx.chapter_num,
                prompt_ctx.concept_name,
            )
            lines: list[str] = chapter_content.split("\n", 1)
            if lines and lines[0].strip().startswith("#"):  # If there's an H1, but it's wrong
                content_after_h1: str = lines[1] if len(lines) > 1 and lines[1].strip() else ""
                chapter_content = expected_heading + ("\n\n" + content_after_h1 if content_after_h1 else "")
            else:  # No H1 at all
                chapter_content = f"{expected_heading}\n\n{chapter_content}"
        elif not chapter_content.startswith(expected_heading):  # H1 is present but differs from expected
            self._log_warning(
                "Web Chapter %d ('%s') H1 differs from expected. Overwriting.",
                prompt_ctx.chapter_num,
                prompt_ctx.concept_name,
            )
            first_nl_idx: int = chapter_content.find("\n")
            chapter_content = (
                expected_heading + chapter_content[first_nl_idx:] if first_nl_idx != -1 else expected_heading
            )

        self._log_info(
            "Successfully generated content for Web Chapter %d ('%s').", prompt_ctx.chapter_num, prompt_ctx.concept_name
        )
        return chapter_content.strip()

    def execution(self, items_iterable: Iterable[WriteWebChapterPreparedItem]) -> WriteWebChaptersExecutionResultList:
        """Generate Markdown content for each web chapter item in the batch.

        Iterates through the prepared chapter items, calls the LLM for each,
        and collects the generated Markdown content or error messages.

        Args:
            items_iterable (Iterable[WriteWebChapterPreparedItem]): An iterable of dictionaries,
                                                                    each prepared by `pre_execution`
                                                                    for a single chapter.

        Returns:
            WriteWebChaptersExecutionResultList: A list of strings, where each string is
                                                 either the Markdown content of a generated
                                                 chapter or an error message if generation failed.
        """
        self._log_info("Executing batch generation of web chapters...")
        results: WriteWebChaptersExecutionResultList = []
        item_count: int = 0
        for item in items_iterable:
            item_count += 1
            chapter_content_or_error: str = self._process_single_web_chapter_item(item)
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
            shared_context (SLSharedContext): The shared context dictionary to update.
            prepared_items_iterable (Iterable[WriteWebChapterPreparedItem]): The iterable of
                                                                            prepared items (unused).
            execution_results_list (WriteWebChaptersExecutionResultList): List of generated chapter
                                                                          Markdown contents or error strings.
        """
        del prepared_items_iterable  # Mark as unused
        shared_context["text_chapters"] = execution_results_list
        valid_chapter_count: int = sum(
            1 for content in execution_results_list if not content.startswith(ERROR_MESSAGE_PREFIX_WEB_CHAP)
        )
        failed_count: int = len(execution_results_list) - valid_chapter_count
        log_msg: str = f"Stored {len(execution_results_list)} web chapter strings in shared_context['text_chapters']."
        if failed_count > 0:
            log_msg += f" ({failed_count} web chapters had errors during generation)."
        else:
            log_msg += " All web chapters generated or processed successfully."
        self._log_info(log_msg)


# End of src/FL02_web_crawling/nodes/n05_write_web_chapters.py
