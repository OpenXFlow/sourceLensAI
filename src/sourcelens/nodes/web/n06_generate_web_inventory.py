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

"""Node responsible for generating an inventory of crawled web documents with summaries."""

import logging
from collections.abc import Iterable
from pathlib import Path
from typing import Any, Final, cast

from typing_extensions import TypeAlias

from sourcelens.nodes.base_node import BaseBatchNode, SLSharedContext
from sourcelens.prompts.web.inventory_prompts import (
    MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT,
    WebInventoryPrompts,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm

# Type Aliases for this node
WebInventoryPreparedItem: TypeAlias = dict[str, Any]
SingleDocumentSummaryResult: TypeAlias = tuple[str, str]
WebInventoryExecutionResultList: TypeAlias = list[SingleDocumentSummaryResult]

FileDataInternal: TypeAlias = tuple[str, str]
FileDataListInternal: TypeAlias = list[FileDataInternal]
LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]
OutputConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_inventory: logging.Logger = logging.getLogger(__name__)

ERROR_SUMMARY_PREFIX: Final[str] = "Error summarizing document:"
EXPECTED_FILE_DATA_TUPLE_LENGTH_INV: Final[int] = 2


class GenerateWebInventory(BaseBatchNode[WebInventoryPreparedItem, SingleDocumentSummaryResult]):
    """Generates an inventory of crawled web documents, each with an LLM-generated summary.

    This node processes each crawled file (Markdown) as an item in a batch.
    For each file, it prompts an LLM to generate a concise summary.
    The final output is a Markdown string containing a list of all documents
    and their summaries.
    """

    def pre_execution(self, shared_context: SLSharedContext) -> Iterable[WebInventoryPreparedItem]:  # type: ignore[override]
        """Prepare an iterable of items, each for summarizing one web document.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Yields:
            WebInventoryPreparedItem: Dictionaries with context for summarizing one document.
                                      If prerequisites are not met or an error occurs,
                                      an empty iterable may be returned.
        """
        self._log_info("Preparing data for web document inventory generation...")
        try:
            config_val: Any = self._get_required_shared(shared_context, "config")
            output_config_val: Any = config_val.get("output", {}) if isinstance(config_val, dict) else {}
            output_config: OutputConfigDictTyped = output_config_val if isinstance(output_config_val, dict) else {}

            if not output_config.get("include_source_index", False):
                self._log_info("Web inventory generation (via 'include_source_index') is disabled. Skipping.")
                yield from []  # Explicitly yield from empty list
                return

            files_data_any: Any = self._get_required_shared(shared_context, "files")
            if not isinstance(files_data_any, list):
                self._log_warning("'files' in shared_context is not a list. Cannot generate inventory.")
                yield from []
                return

            files_data: FileDataListInternal = []
            for item in files_data_any:
                if (
                    isinstance(item, tuple)
                    and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH_INV
                    and isinstance(item[0], str)
                    and isinstance(item[1], str)
                ):
                    files_data.append(cast(FileDataInternal, item))
            if len(files_data_any) != len(files_data):
                self._log_warning("Some items in 'files' were invalid for inventory preparation.")

            if not files_data:
                self._log_warning("No valid crawled files found to generate inventory. Skipping.")
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
        for document_path, document_content in files_data:
            snippet = document_content[:MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT]
            yield {
                "document_path": document_path,
                "document_content_snippet": snippet,
                "target_language": target_language,
                "llm_config": llm_config,
                "cache_config": cache_config,
                "project_name": project_name,
            }
            num_items_prepared += 1
        self._log_info("Prepared %d web documents for inventory summary.", num_items_prepared)

    def _summarize_single_document(self, item: WebInventoryPreparedItem) -> SingleDocumentSummaryResult:
        """Generate a summary for a single web document using LLM.

        Args:
            item (WebInventoryPreparedItem): Context for summarizing one document.

        Returns:
            SingleDocumentSummaryResult: Tuple of (document_path, summary_text_or_error).
        """
        doc_path: str = item["document_path"]
        self._log_info("Summarizing document: %s", doc_path)

        prompt = WebInventoryPrompts.format_summarize_web_document_prompt(
            document_path=doc_path,
            document_content_snippet=item["document_content_snippet"],
            target_language=item["target_language"],
        )
        llm_config: LlmConfigDictTyped = item["llm_config"]
        cache_config: CacheConfigDictTyped = item["cache_config"]

        try:
            summary_text = call_llm(prompt, llm_config, cache_config)
            if not summary_text.strip():
                self._log_warning("LLM returned empty summary for document: %s", doc_path)
                return doc_path, f"{ERROR_SUMMARY_PREFIX} LLM returned empty summary."
            return doc_path, summary_text.strip()
        except LlmApiError as e_llm:
            self._log_error("LLM call failed while summarizing document %s: %s", doc_path, e_llm)
            return doc_path, f"{ERROR_SUMMARY_PREFIX} LLM API error: {e_llm!s}"
        except (ValueError, TypeError, AttributeError, KeyError) as e_proc:
            self._log_error("Error processing summary for document %s: %s", doc_path, e_proc, exc_info=True)
            return doc_path, f"{ERROR_SUMMARY_PREFIX} Processing error: {e_proc!s}"

    def execution(self, items_iterable: Iterable[WebInventoryPreparedItem]) -> WebInventoryExecutionResultList:
        """Generate summary for each web document in the batch.

        Args:
            items_iterable (Iterable[WebInventoryPreparedItem]): Iterable of prepared items.

        Returns:
            WebInventoryExecutionResultList: List of (path, summary_or_error) tuples.
        """
        self._log_info("Executing batch summarization for web document inventory...")
        results: WebInventoryExecutionResultList = []
        item_count = 0
        for item in items_iterable:
            item_count += 1
            summary_result = self._summarize_single_document(item)
            results.append(summary_result)
        self._log_info("Finished summarizing %d web documents for inventory.", item_count)
        return results

    def _format_inventory_markdown(self, project_name: str, summaries: WebInventoryExecutionResultList) -> str:
        """Format the final Markdown content for the web inventory file.

        Args:
            project_name (str): Name of the project/website.
            summaries (WebInventoryExecutionResultList): List of (path, summary) tuples.

        Returns:
            str: The complete Markdown content for the inventory.
        """
        markdown_lines: list[str] = [f"# Content Inventory: {project_name}\n"]
        if not summaries:
            markdown_lines.append("\nNo web documents were processed or summarized for this inventory.\n")
            return "".join(markdown_lines)

        markdown_lines.append("\n## Document Summaries\n")
        for doc_path, summary in sorted(summaries, key=lambda x: x[0]):
            display_name = Path(doc_path).name
            markdown_lines.append(f"### `{display_name}`\n")
            markdown_lines.append(f"**Source Path (relative to crawl output):** `{doc_path}`\n")
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
            shared_context (SLSharedContext): The shared context dictionary.
            prepared_inputs (Iterable[WebInventoryPreparedItem]): Prepared items (unused here).
            execution_outputs (WebInventoryExecutionResultList): List of (path, summary) tuples.
        """
        del prepared_inputs

        project_name_val: Any = shared_context.get("project_name", "Web Content Inventory")
        project_name: str = str(project_name_val)

        if not execution_outputs:
            self._log_warning("No summaries generated for web inventory. Storing empty inventory.")
            shared_context["content_inventory_md"] = f"# Content Inventory: {project_name}\n\nNo content summarized."
            return  # Added return to exit early

        inventory_markdown = self._format_inventory_markdown(project_name, execution_outputs)
        shared_context["content_inventory_md"] = inventory_markdown
        self._log_info("Stored web content inventory (Markdown format) in shared_context['content_inventory_md'].")


# End of src/sourcelens/nodes/web/n06_generate_web_inventory.py
