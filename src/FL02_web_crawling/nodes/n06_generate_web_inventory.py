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
from typing import Any, Final, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseBatchNode, SLSharedContext
from sourcelens.core.common_types import WebContentChunk, WebContentChunkList
from sourcelens.utils.llm_api import LlmApiError, call_llm

from ..prompts.inventory_prompts import (
    MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT,
    WebInventoryPrompts,
)

# Type Aliases for this node
WebInventoryPreparedItem: TypeAlias = dict[str, Any]
SingleChunkSummaryResult: TypeAlias = tuple[str, str]
WebInventoryExecutionResultList: TypeAlias = list[SingleChunkSummaryResult]


LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_inventory: logging.Logger = logging.getLogger(__name__)

ERROR_SUMMARY_PREFIX: Final[str] = "Error summarizing document chunk:"
MIN_PARTS_FOR_CHUNK_ID_DISPLAY: Final[int] = 3  # For len(parts) >= MIN_PARTS_FOR_CHUNK_ID_DISPLAY


class GenerateWebInventory(BaseBatchNode[WebInventoryPreparedItem, SingleChunkSummaryResult]):
    """Generates an inventory of crawled web document chunks, each with an LLM-generated summary."""

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WebInventoryPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of items, each for summarizing one web document chunk.

        Args:
            shared_context: The shared context dictionary.

        Yields:
            Dictionaries with context for summarizing one document chunk.
        """
        self._log_info("Preparing data for web document chunk inventory generation...")
        try:
            current_mode_opts_any: Any = shared_context.get("current_mode_output_options", {})
            current_mode_opts: dict[str, Any] = current_mode_opts_any if isinstance(current_mode_opts_any, dict) else {}

            include_inventory_val: Any = current_mode_opts.get("include_content_inventory")
            include_inventory: bool = include_inventory_val if isinstance(include_inventory_val, bool) else False

            if not include_inventory:
                self._log_info("Web content inventory generation is disabled in output_options. Skipping.")
                yield from []
                return

            web_chunks_any: Any = self._get_required_shared(shared_context, "web_content_chunks")
            if not isinstance(web_chunks_any, list):
                self._log_warning("'web_content_chunks' in shared_context is not a list. Cannot generate inventory.")
                yield from []
                return

            web_chunks: WebContentChunkList = []
            for item_any in web_chunks_any:
                if isinstance(item_any, dict) and "chunk_id" in item_any and "content" in item_any:
                    web_chunks.append(cast(WebContentChunk, item_any))
                else:
                    self._log_warning("Skipping invalid item in 'web_content_chunks' for inventory: %s", item_any)

            if not web_chunks:
                self._log_warning("No valid web content chunks found to generate inventory. Skipping.")
                yield from []
                return

            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            target_language_any: Any = shared_context.get("language", "english")
            project_name_any: Any = shared_context.get("project_name", "Web Content")
            project_name: str = str(project_name_any)

            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            target_language: str = str(target_language_any)

        except ValueError as e_val:
            self._log_error("Pre-execution for Web Inventory failed (missing shared data): %s", e_val)
            yield from []
            return

        num_items_prepared = 0
        for chunk_item in web_chunks:
            chunk_id = str(chunk_item.get("chunk_id", f"unidentified_chunk_{num_items_prepared}"))
            chunk_content = str(chunk_item.get("content", ""))
            chunk_title = str(chunk_item.get("title", "Untitled Chunk"))

            snippet = chunk_content[:MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT]
            yield {
                "chunk_id": chunk_id,
                "chunk_title": chunk_title,
                "chunk_content_snippet": snippet,
                "target_language": target_language,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": project_name,
            }
            num_items_prepared += 1
        self._log_info("Prepared %d web document chunks for inventory summary.", num_items_prepared)

    def _summarize_single_chunk(self, item: WebInventoryPreparedItem) -> SingleChunkSummaryResult:
        """Generate a summary for a single web document chunk using LLM.

        Args:
            item: Context for summarizing one document chunk.

        Returns:
            Tuple of (chunk_id, summary_text_or_error).
        """
        chunk_id: str = item["chunk_id"]
        chunk_title: str = item["chunk_title"]
        self._log_info("Summarizing document chunk: %s (Title: %s)", chunk_id, chunk_title)

        prompt = WebInventoryPrompts.format_summarize_web_document_prompt(
            document_path=f"Chunk: {chunk_id} (from document about: {chunk_title})",
            document_content_snippet=item["chunk_content_snippet"],
            target_language=item["target_language"],
        )
        llm_config: LlmConfigDictTyped = item["llm_config"]
        cache_config: CacheConfigDictTyped = item["cache_config"]

        try:
            summary_text = call_llm(prompt, llm_config, cache_config)
            if not summary_text.strip():
                self._log_warning("LLM returned empty summary for document chunk: %s", chunk_id)
                return chunk_id, f"{ERROR_SUMMARY_PREFIX} LLM returned empty summary."
            return chunk_id, summary_text.strip()
        except LlmApiError as e_llm:
            self._log_error("LLM call failed while summarizing document chunk %s: %s", chunk_id, e_llm)
            return chunk_id, f"{ERROR_SUMMARY_PREFIX} LLM API error: {e_llm!s}"
        except (ValueError, TypeError, AttributeError, KeyError) as e_proc:
            self._log_error("Error processing summary for document chunk %s: %s", chunk_id, e_proc, exc_info=True)
            return chunk_id, f"{ERROR_SUMMARY_PREFIX} Processing error: {e_proc!s}"

    def execution(self, items_iterable: Iterable[WebInventoryPreparedItem]) -> WebInventoryExecutionResultList:
        """Generate summary for each web document chunk in the batch.

        Args:
            items_iterable: Iterable of prepared items.

        Returns:
            List of (chunk_id, summary_or_error) tuples.
        """
        self._log_info("Executing batch summarization for web document chunk inventory...")
        results: WebInventoryExecutionResultList = []
        item_count = 0
        for item in items_iterable:
            item_count += 1
            summary_result = self._summarize_single_chunk(item)
            results.append(summary_result)
        self._log_info("Finished summarizing %d web document chunks for inventory.", item_count)
        return results

    def _format_inventory_markdown(self, project_name: str, summaries: WebInventoryExecutionResultList) -> str:
        """Format the final Markdown content for the web chunk inventory file.

        Args:
            project_name: Name of the project/website.
            summaries: List of (chunk_id, summary) tuples.

        Returns:
            The complete Markdown content for the inventory.
        """
        markdown_lines: list[str] = [f"# Content Chunk Inventory: {project_name}\n"]
        if not summaries:
            markdown_lines.append("\nNo web document chunks were processed or summarized for this inventory.\n")
            return "".join(markdown_lines)

        markdown_lines.append("\n## Document Chunk Summaries\n")
        for chunk_id, summary in sorted(summaries, key=lambda x: x[0]):
            display_name_parts = [chunk_id]
            try:
                parts = chunk_id.split("_")
                # Použitie konštanty MIN_PARTS_FOR_CHUNK_ID_DISPLAY
                if len(parts) >= MIN_PARTS_FOR_CHUNK_ID_DISPLAY:
                    original_file_stem = parts[0]
                    section_title_guess = " ".join(parts[1:-1]).replace("-", " ").title()
                    display_name_parts = [
                        f"Original File Stem: {original_file_stem}",
                        f"Section: {section_title_guess}",
                    ]
            except (IndexError, ValueError, AttributeError):  # Špecifickejšie výnimky
                # Ak sa parsovanie nepodarí, použijeme len chunk_id, nie je potrebné logovať chybu tu
                pass

            markdown_lines.append(f"### Chunk ID: `{chunk_id}`\n")
            if len(display_name_parts) > 1:
                markdown_lines.append(f"**Context:** {', '.join(display_name_parts)}\n")

            if summary.startswith(ERROR_SUMMARY_PREFIX):
                markdown_lines.append(f"> *{summary}*\n")
            else:
                markdown_lines.append(f"{summary}\n")
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
            shared_context: The shared context dictionary.
            prepared_inputs: Prepared items (unused here).
            execution_outputs: List of (chunk_id, summary) tuples.
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

        inventory_markdown = self._format_inventory_markdown(project_name, execution_outputs)
        shared_context["content_inventory_md"] = inventory_markdown
        self._log_info(
            "Stored web content chunk inventory (Markdown format) in shared_context['content_inventory_md']."
        )


# End of src/FL02_web_crawling/nodes/n06_generate_web_inventory.py
