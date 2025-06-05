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

"""Node responsible for generating an inventory of crawled web document chunks with summaries."""

import logging
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any, Final, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseBatchNode, SLSharedContext
from sourcelens.utils.llm_api import LlmApiError, call_llm

if TYPE_CHECKING:
    from sourcelens.core.common_types import (
        CacheConfigDict,
        LlmConfigDict,
        WebContentChunk,
        WebContentChunkList,
    )

from ..prompts.inventory_prompts import WebInventoryPrompts

WebInventoryPreparedItem: TypeAlias = dict[str, Any]
SingleChunkSummaryResult: TypeAlias = tuple[str, str]
WebInventoryExecutionResultList: TypeAlias = list[SingleChunkSummaryResult]


module_logger_web_inventory: logging.Logger = logging.getLogger(__name__)

ERROR_SUMMARY_PREFIX: Final[str] = "Error summarizing document chunk:"  # Should ideally not be used with fallback
FALLBACK_SNIPPET_MARKER: Final[str] = "(Content snippet due to summarization error)"
FALLBACK_SNIPPET_MAX_WORDS: Final[int] = 70
MIN_PARTS_FOR_CHUNK_ID_DISPLAY: Final[int] = 3


class GenerateWebInventory(BaseBatchNode[WebInventoryPreparedItem, SingleChunkSummaryResult]):
    """Generates an inventory of crawled web document chunks, each with an LLM-generated summary or fallback snippet."""

    def _get_fallback_snippet(self, full_content_snippet: str, max_words: int = FALLBACK_SNIPPET_MAX_WORDS) -> str:
        """Create a fallback snippet from the beginning of the content.

        Args:
            full_content_snippet (str): The full content snippet of the chunk.
            max_words (int): The maximum number of words for the fallback snippet.

        Returns:
            str: A truncated snippet of the content, marked as a fallback.
        """
        if not full_content_snippet:
            return f"{FALLBACK_SNIPPET_MARKER} Original chunk content was empty."
        words: list[str] = full_content_snippet.split()
        if len(words) > max_words:
            snippet: str = " ".join(words[:max_words]) + "..."
        else:
            snippet = full_content_snippet
        return f"{FALLBACK_SNIPPET_MARKER}\n\n> {snippet}"

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WebInventoryPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of items, each for summarizing one web document chunk.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Yields:
            WebInventoryPreparedItem: Dictionaries with context for summarizing one document chunk.
        """
        self._log_info("Preparing data for web document chunk inventory generation...")
        try:
            config_data: dict[str, Any] = cast(dict[str, Any], self._get_required_shared(shared_context, "config"))
            flow_name: str = str(shared_context.get("current_operation_mode", "FL02_web_crawling"))
            flow_config: dict[str, Any] = config_data.get(flow_name, {})
            current_mode_opts: dict[str, Any] = flow_config.get("output_options", {})
            include_inventory: bool = bool(current_mode_opts.get("include_content_inventory", True))

            if not include_inventory:
                self._log_info("Web content inventory generation is disabled in output_options. Skipping.")
                return

            web_chunks_any: Any = self._get_required_shared(shared_context, "web_content_chunks")
            if not isinstance(web_chunks_any, list):
                self._log_warning("'web_content_chunks' in shared_context is not a list. Cannot generate inventory.")
                return

            web_chunks: "WebContentChunkList" = []
            for item_any in web_chunks_any:
                if isinstance(item_any, dict) and "chunk_id" in item_any and "content" in item_any:
                    web_chunks.append(cast("WebContentChunk", item_any))
                else:
                    self._log_warning("Skipping invalid item in 'web_content_chunks' for inventory: %s", item_any)

            if not web_chunks:
                self._log_warning("No valid web content chunks found to generate inventory. Skipping.")
                return

            llm_config: "LlmConfigDict" = cast("LlmConfigDict", self._get_required_shared(shared_context, "llm_config"))  # type: ignore[redundant-cast]
            cache_config: "CacheConfigDict" = cast(
                "CacheConfigDict", self._get_required_shared(shared_context, "cache_config")
            )  # type: ignore[redundant-cast]
            target_language: str = str(shared_context.get("language", "english"))  # This is correctly fetched
            project_name: str = str(shared_context.get("project_name", "Web Content"))

        except ValueError as e_val:
            self._log_error("Pre-execution for Web Inventory failed (missing shared data): %s", e_val)
            return
        except KeyError as e_key:
            self._log_error("Pre-execution for Web Inventory failed (config structure error): %s", e_key)
            return

        num_items_prepared: int = 0
        for chunk_item in web_chunks:
            chunk_id_val: Any = chunk_item.get("chunk_id", f"unidentified_chunk_{num_items_prepared}")
            chunk_id: str = str(chunk_id_val)
            chunk_content_val: Any = chunk_item.get("content", "")
            chunk_content: str = str(chunk_content_val)
            chunk_title_val: Any = chunk_item.get("title", "Untitled Chunk")
            chunk_title: str = str(chunk_title_val)

            snippet_for_prompt: str = chunk_content  # For LLM, it will be truncated by prompt formatter if needed

            yield {
                "chunk_id": chunk_id,
                "chunk_title": chunk_title,
                "chunk_content_snippet": snippet_for_prompt,
                "full_chunk_content_for_fallback": chunk_content,
                "target_language": target_language,  # Pass the fetched language
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": project_name,
            }
            num_items_prepared += 1
        self._log_info("Prepared %d web document chunks for inventory summary.", num_items_prepared)

    def _summarize_single_chunk(self, item: WebInventoryPreparedItem) -> SingleChunkSummaryResult:
        """Generate a summary for a single web document chunk using LLM, with fallback.

        Args:
            item (WebInventoryPreparedItem): Context for summarizing one document chunk.

        Returns:
            SingleChunkSummaryResult: Tuple of (chunk_id, summary_text_or_fallback).
        """
        chunk_id: str = item["chunk_id"]
        chunk_title: str = item["chunk_title"]
        target_language_for_prompt: str = item["target_language"]  # Use the language passed in item
        self._log_info(
            "Summarizing document chunk: %s (Title: %s) in %s", chunk_id, chunk_title, target_language_for_prompt
        )

        prompt: str = WebInventoryPrompts.format_summarize_web_document_prompt(
            document_path=f"Chunk: {chunk_id} (from document section titled: '{chunk_title}')",
            document_content_snippet=item["chunk_content_snippet"],
            target_language=target_language_for_prompt,  # Pass to prompt formatter
        )
        llm_config: "LlmConfigDict" = item["llm_config"]  # type: ignore[redundant-cast]
        cache_config: "CacheConfigDict" = item["cache_config"]  # type: ignore[redundant-cast]

        try:
            summary_text: str = call_llm(prompt, llm_config, cache_config)
            if not summary_text.strip():
                self._log_warning(
                    "LLM returned empty summary for document chunk: %s. Using fallback snippet.", chunk_id
                )
                return chunk_id, self._get_fallback_snippet(item["full_chunk_content_for_fallback"])
            return chunk_id, summary_text.strip()
        except LlmApiError as e_llm:
            self._log_error(
                "LLM call failed while summarizing document chunk %s: %s. Using fallback snippet.",
                chunk_id,
                e_llm.args[0],  # Log only the message part of LlmApiError
            )
            return chunk_id, self._get_fallback_snippet(item["full_chunk_content_for_fallback"])
        except Exception as e_proc:  # Catch any other unexpected error during processing  # noqa: BLE001
            self._log_error(
                "Unexpected error processing summary for document chunk %s: %s. Using fallback snippet.",
                chunk_id,
                e_proc,
                exc_info=True,
            )
            return chunk_id, self._get_fallback_snippet(item["full_chunk_content_for_fallback"])

    def execution(self, items_iterable: Iterable[WebInventoryPreparedItem]) -> WebInventoryExecutionResultList:
        """Generate summary for each web document chunk in the batch.

        Args:
            items_iterable (Iterable[WebInventoryPreparedItem]): Iterable of prepared items.

        Returns:
            WebInventoryExecutionResultList: List of (chunk_id, summary_or_fallback) tuples.
        """
        self._log_info("Executing batch summarization for web document chunk inventory...")
        results: WebInventoryExecutionResultList = []
        item_count: int = 0
        for item in items_iterable:
            item_count += 1
            summary_result: SingleChunkSummaryResult = self._summarize_single_chunk(item)
            results.append(summary_result)
        self._log_info("Finished summarizing %d web document chunks for inventory.", item_count)
        return results

    def _format_inventory_markdown(self, project_name: str, summaries: WebInventoryExecutionResultList) -> str:
        """Format the final Markdown content for the web chunk inventory file.

        Args:
            project_name (str): Name of the project/website.
            summaries (WebInventoryExecutionResultList): List of (chunk_id, summary_or_fallback) tuples.

        Returns:
            str: The complete Markdown content for the inventory.
        """
        markdown_lines: list[str] = [f"# Content Chunk Inventory: {project_name}\n"]
        if not summaries:
            markdown_lines.append("\nNo web document chunks were processed or summarized for this inventory.\n")
            return "".join(markdown_lines)

        markdown_lines.append("\n## Document Chunk Summaries\n")
        for chunk_id, summary_or_fallback in sorted(summaries, key=lambda x_item: x_item[0]):
            display_chunk_context: str
            try:
                parts: list[str] = chunk_id.split("_")
                if len(parts) >= MIN_PARTS_FOR_CHUNK_ID_DISPLAY:
                    original_file_stem: str = parts[0]
                    section_title_guess: str = " ".join(parts[1:-1]).replace("-", " ").title()
                    display_chunk_context = (
                        f"Original File Stem: `{original_file_stem}`, Section: `{section_title_guess}`"
                    )
                else:
                    display_chunk_context = f"Chunk Identifier: `{chunk_id}`"
            except (IndexError, ValueError, AttributeError):
                display_chunk_context = f"Chunk Identifier: `{chunk_id}`"

            markdown_lines.append(f"### {display_chunk_context}\n")

            if FALLBACK_SNIPPET_MARKER in summary_or_fallback:
                markdown_lines.append(f"{summary_or_fallback}\n")
            else:
                markdown_lines.append(f"{summary_or_fallback}\n")
            markdown_lines.append("\n---\n")

        return "".join(markdown_lines)

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: Iterable[WebInventoryPreparedItem],
        execution_outputs: WebInventoryExecutionResultList,
    ) -> None:
        """Format the inventory and store it in shared_context.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.
            prepared_inputs (Iterable[WebInventoryPreparedItem]): Prepared items.
            execution_outputs (WebInventoryExecutionResultList): List of (chunk_id, summary) tuples.
        """
        del prepared_inputs

        project_name_val: Any = shared_context.get("project_name", "Web Content Inventory")
        project_name: str = str(project_name_val)

        if not execution_outputs:
            self._log_warning("No summaries generated for web chunk inventory. Storing empty inventory.")
            shared_context["content_inventory_md"] = (
                f"# Content Chunk Inventory: {project_name}\n\nNo content chunks summarized."
            )
            return

        inventory_markdown: str = self._format_inventory_markdown(project_name, execution_outputs)
        shared_context["content_inventory_md"] = inventory_markdown
        self._log_info(
            "Stored web content chunk inventory (Markdown format) in shared_context['content_inventory_md']."
        )


# End of src/FL02_web_crawling/nodes/n06_generate_web_inventory.py
