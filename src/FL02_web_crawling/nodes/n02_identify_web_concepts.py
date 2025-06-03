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

"""Node responsible for identifying core concepts from crawled web content using an LLM."""

import logging
from typing import Any, Final, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import (
    WebContentChunk,
    WebContentChunkList,
    WebContentConceptItem,
    WebContentConceptsList,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from ..prompts.concept_prompts import (
    MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS as MAX_CHUNKS_FOR_CONTEXT_PROMPT,
)
from ..prompts.concept_prompts import (
    MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS as MAX_CHUNK_CONTENT_SNIPPET_LEN_PROMPT,
)
from ..prompts.concept_prompts import WebConceptPrompts

IdentifyWebConceptsPreparedInputs: TypeAlias = dict[str, Any]
IdentifyWebConceptsExecutionResult: TypeAlias = WebContentConceptsList

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_concepts: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_CONCEPTS: Final[int] = 500

WEB_CONCEPT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "source_chunk_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "summary", "source_chunk_ids"],
    "additionalProperties": False,
}


class IdentifyWebConcepts(BaseNode[IdentifyWebConceptsPreparedInputs, IdentifyWebConceptsExecutionResult]):
    """Identify core concepts from web content chunks using an LLM.

    This node takes segmented web content (chunks), constructs a prompt
    for an LLM to identify key concepts or topics within these chunks,
    calls the LLM, and then validates and processes the YAML response.
    The identified concepts, linked to their source chunk_ids, are stored
    in the shared context.
    """

    def _prepare_content_for_llm_prompt(self, web_content_chunks: WebContentChunkList) -> tuple[str, str]:
        """Prepare concatenated content snippets and chunk listing for the LLM prompt.

        Args:
            web_content_chunks: List of WebContentChunk dictionaries from SegmentWebContent.

        Returns:
            A tuple containing:
                             - The concatenated content string (from chunks).
                             - The chunk listing string (chunk_id) for the prompt.
        """
        if not web_content_chunks:
            return "No document chunks provided.", "No document chunks available."

        content_context_parts: list[str] = []
        document_listing_parts: list[str] = []

        for i, chunk in enumerate(web_content_chunks):
            chunk_id = str(chunk.get("chunk_id", f"unknown_chunk_{i}"))
            content = str(chunk.get("content", ""))
            title = str(chunk.get("title", "Untitled Chunk"))

            if i < MAX_CHUNKS_FOR_CONTEXT_PROMPT:
                snippet = content[:MAX_CHUNK_CONTENT_SNIPPET_LEN_PROMPT]
                if len(content) > MAX_CHUNK_CONTENT_SNIPPET_LEN_PROMPT:
                    snippet += "..."
                content_context_parts.append(f"--- Chunk ID: {chunk_id} (Title: {title}) ---\n{snippet}\n\n")
            document_listing_parts.append(f"- {chunk_id}")

        if len(web_content_chunks) > MAX_CHUNKS_FOR_CONTEXT_PROMPT:
            omitted_count = len(web_content_chunks) - MAX_CHUNKS_FOR_CONTEXT_PROMPT
            content_context_parts.append(f"... (and {omitted_count} more document chunks not shown in detail) ...")

        full_content_context = "".join(content_context_parts)
        full_document_listing = "\n".join(document_listing_parts)

        return full_content_context, full_document_listing

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyWebConceptsPreparedInputs:
        """Prepare context and parameters for web concept identification LLM prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing context for the `execution` method.
            May include a 'skip': True if prerequisites are not met.
        """
        self._log_info("Preparing context for web concept identification from chunks...")
        try:
            web_chunks_any: Any = self._get_required_shared(shared_context, "web_content_chunks")
            if not isinstance(web_chunks_any, list):
                self._log_warning("'web_content_chunks' in shared_context is not a list. Skipping.")
                return {"skip": True, "reason": "'web_content_chunks' is not a list."}

            web_chunks: WebContentChunkList = []
            for item in web_chunks_any:
                if isinstance(item, dict) and "chunk_id" in item and "content" in item:
                    web_chunks.append(cast(WebContentChunk, item))
                else:
                    self._log_warning("Skipping invalid item in 'web_content_chunks' data: %s", item)

            if not web_chunks:
                self._log_warning("No valid web content chunks found. Skipping concept identification.")
                return {"skip": True, "reason": "No valid web content chunks found."}

            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            language_any: Any = shared_context.get("language", "english")

            project_name: str = str(project_name_any)
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            target_language: str = str(language_any)

        except ValueError as e_val:
            self._log_error("Pre-execution failed due to missing shared data: %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {str(e_val)}"}

        content_context_str, document_listing_str = self._prepare_content_for_llm_prompt(web_chunks)

        prepared_inputs: IdentifyWebConceptsPreparedInputs = {
            "skip": False,
            "document_collection_name": project_name,
            "content_context": content_context_str,
            "document_listing": document_listing_str,
            "target_language": target_language,
            "llm_config": llm_config,
            "cache_config": cache_config,
            "all_chunk_ids": [str(c.get("chunk_id")) for c in web_chunks if c.get("chunk_id")],
        }
        return prepared_inputs

    def _validate_concept_source_ids(self, concept_item: dict[str, Any], all_valid_chunk_ids: list[str]) -> list[str]:
        """Validate that source_chunk_ids in a concept item are valid chunk_ids."""
        validated_ids: list[str] = []
        raw_ids_any: Any = concept_item.get("source_chunk_ids", [])  # Matches schema key
        raw_ids_list = raw_ids_any if isinstance(raw_ids_any, list) else []

        for chunk_id_any in raw_ids_list:
            if isinstance(chunk_id_any, str) and chunk_id_any in all_valid_chunk_ids:
                validated_ids.append(chunk_id_any)
            elif isinstance(chunk_id_any, str):
                self._log_warning(
                    "Concept '%s' references unknown source_chunk_id '%s'. Ignoring this reference.",
                    concept_item.get("name", "Unknown Concept"),
                    chunk_id_any,
                )
            else:
                self._log_warning(
                    "Invalid type for source_chunk_id in concept '%s': %s. Expected string.",
                    concept_item.get("name", "Unknown Concept"),
                    type(chunk_id_any).__name__,
                )
        return validated_ids

    def execution(self, prepared_inputs: IdentifyWebConceptsPreparedInputs) -> IdentifyWebConceptsExecutionResult:
        """Execute LLM call, parse, and validate identified web concepts from chunks.

        Args:
            prepared_inputs: The dictionary returned by `pre_execution`.

        Returns:
            A list of identified and validated web concept dictionaries.
            Returns an empty list if skipped or on failure.
        """
        if prepared_inputs.get("skip", True):
            reason = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web concept identification execution. Reason: %s", reason)
            return []

        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]
        collection_name: str = prepared_inputs["document_collection_name"]
        all_chunk_ids_for_validation: list[str] = prepared_inputs.get("all_chunk_ids", [])
        self._log_info("Identifying web concepts for '%s' from chunks using LLM...", collection_name)

        prompt = WebConceptPrompts.format_identify_web_concepts_prompt(
            document_collection_name=collection_name,
            content_context=prepared_inputs["content_context"],
            document_listing=prepared_inputs["document_listing"],
            target_language=prepared_inputs["target_language"],
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e_llm:
            self._log_error("LLM call failed during web concept identification: %s", e_llm, exc_info=True)
            return []

        raw_concepts_from_yaml: list[Any]
        try:
            raw_concepts_from_yaml = validate_yaml_list(response_text, item_schema=WEB_CONCEPT_ITEM_SCHEMA)
        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for web concepts: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_CONCEPTS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_CONCEPTS:
                    snippet += "..."
                module_logger_web_concepts.warning(
                    "Problematic raw LLM output for web concepts:\n---\n%s\n---", snippet
                )
            return []

        final_validated_concepts: WebContentConceptsList = []
        for raw_concept_dict_any in raw_concepts_from_yaml:
            if not isinstance(raw_concept_dict_any, dict):  # Ensure it's a dict before casting
                self._log_warning("Skipping non-dictionary item from LLM YAML list: %s", raw_concept_dict_any)
                continue
            concept_item = cast(dict[str, Any], raw_concept_dict_any)
            validated_source_ids = self._validate_concept_source_ids(concept_item, all_chunk_ids_for_validation)

            # Ensure name and summary are strings
            name_val = str(concept_item.get("name", "Unnamed Concept"))
            summary_val = str(concept_item.get("summary", "No summary available"))

            processed_concept: WebContentConceptItem = {
                "name": name_val,
                "summary": summary_val,
                "source_chunk_ids": validated_source_ids,
            }
            final_validated_concepts.append(processed_concept)

        if not final_validated_concepts and raw_concepts_from_yaml:
            self._log_warning("LLM parsed YAML, but no valid items remained after item-schema and chunk_id validation.")
        elif not final_validated_concepts:
            self._log_warning("No valid web concepts found in LLM response or after processing.")
        else:
            self._log_info(
                "Successfully processed %d web concepts linked to valid chunks.", len(final_validated_concepts)
            )
        return final_validated_concepts

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: IdentifyWebConceptsPreparedInputs,
        execution_outputs: IdentifyWebConceptsExecutionResult,
    ) -> None:
        """Update the shared context with identified web concepts.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from `pre_execution`.
            execution_outputs: List of web concepts.
        """
        del prepared_inputs
        shared_context["text_concepts"] = execution_outputs
        self._log_info("Stored %d web concepts in shared_context['text_concepts'].", len(execution_outputs))


# End of src/FL02_web_crawling/nodes/n02_identify_web_concepts.py
