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
from typing import Any, Final, Union, cast

from typing_extensions import TypeAlias

# Corrected import path for BaseNode and SLSharedContext
from sourcelens.nodes.base_node import BaseNode, SLSharedContext

# Corrected import path for WebConceptPrompts and its constants
from sourcelens.prompts.web.concept_prompts import (
    MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS,  # Assuming this constant is relevant here
    MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS,  # Assuming this constant is relevant here
    WebConceptPrompts,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# Type Aliases for clarity within this node
WebContentConceptItem: TypeAlias = dict[str, Union[str, list[str]]]
WebContentConceptsList: TypeAlias = list[WebContentConceptItem]
IdentifyWebConceptsPreparedInputs: TypeAlias = dict[str, Any]
IdentifyWebConceptsExecutionResult: TypeAlias = WebContentConceptsList
FileDataInternal: TypeAlias = tuple[str, str]
FileDataListInternal: TypeAlias = list[FileDataInternal]
LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_concepts: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_CONCEPTS: Final[int] = 500
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2

# JSON Schema for validating each item in the list of web concepts from LLM
WEB_CONCEPT_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "name": {"type": "string", "minLength": 1},
        "summary": {"type": "string", "minLength": 1},
        "source_documents": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["name", "summary", "source_documents"],
    "additionalProperties": False,
}


class IdentifyWebConcepts(BaseNode[IdentifyWebConceptsPreparedInputs, IdentifyWebConceptsExecutionResult]):
    """Identify core concepts from web content using an LLM.

    This node takes Markdown content fetched from web pages, constructs a prompt
    for an LLM to identify key concepts or topics, calls the LLM, and then
    validates and processes the YAML response. The identified concepts are
    stored in the shared context.
    """

    def _prepare_content_for_llm_prompt(self, files_data: FileDataListInternal) -> tuple[str, str]:
        """Prepare concatenated content snippets and document listing for the LLM prompt.

        Args:
            files_data (FileDataListInternal): List of (filepath, content) tuples
                                               from `shared_context["files"]`.

        Returns:
            tuple[str, str]: A tuple containing:
                             - The concatenated content string (snippets).
                             - The document listing string for the prompt.
        """
        if not files_data:
            return "No document content provided.", "No documents available."

        content_context_parts: list[str] = []
        document_listing_parts: list[str] = []

        # Use the imported constants from concept_prompts
        for i, (filepath, content) in enumerate(files_data):
            if i < MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS:  # Using imported constant
                snippet = content[:MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS]  # Using imported constant
                if len(content) > MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS:  # Using imported constant
                    snippet += "..."
                content_context_parts.append(f"--- Document: {filepath} ---\n{snippet}\n\n")
            document_listing_parts.append(f"- {filepath}")

        if len(files_data) > MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS:  # Using imported constant
            omitted_count = len(files_data) - MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS  # Using imported constant
            content_context_parts.append(f"... (and {omitted_count} more documents not shown in detail) ...")

        full_content_context = "".join(content_context_parts)
        full_document_listing = "\n".join(document_listing_parts)

        return full_content_context, full_document_listing

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyWebConceptsPreparedInputs:
        """Prepare context and parameters for web concept identification LLM prompt.

        Args:
            shared_context (SLSharedContext): The shared context dictionary.

        Returns:
            IdentifyWebConceptsPreparedInputs: A dictionary containing context for the `execution` method.
                                               May include a 'skip': True if prerequisites are not met.
        """
        self._log_info("Preparing context for web concept identification...")
        try:
            files_data_any: Any = self._get_required_shared(shared_context, "files")
            if not isinstance(files_data_any, list):
                self._log_warning("'files' in shared_context is not a list. Skipping.")
                return {"skip": True, "reason": "'files' is not a list."}

            files_data: FileDataListInternal = []
            for item in files_data_any:
                if (
                    isinstance(item, tuple)
                    and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH
                    and isinstance(item[0], str)
                    and isinstance(item[1], str)
                ):
                    files_data.append(cast(FileDataInternal, item))
                else:
                    self._log_warning("Skipping invalid item in 'files' data: %s", item)

            if not files_data:
                self._log_warning("No valid file data (Markdown content) found in shared_context['files']. Skipping.")
                return {"skip": True, "reason": "No valid Markdown content in shared_context['files']."}

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

        content_context_str, document_listing_str = self._prepare_content_for_llm_prompt(files_data)

        prepared_inputs: IdentifyWebConceptsPreparedInputs = {
            "skip": False,
            "document_collection_name": project_name,
            "content_context": content_context_str,
            "document_listing": document_listing_str,
            "target_language": target_language,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }
        return prepared_inputs

    def execution(self, prepared_inputs: IdentifyWebConceptsPreparedInputs) -> IdentifyWebConceptsExecutionResult:
        """Execute LLM call, parse, and validate identified web concepts.

        Args:
            prepared_inputs (IdentifyWebConceptsPreparedInputs): The dictionary returned by `pre_execution`.

        Returns:
            IdentifyWebConceptsExecutionResult: A list of identified and validated web concept dictionaries.
                                                Returns an empty list if skipped or on failure.
        """
        if prepared_inputs.get("skip", True):
            reason = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web concept identification execution. Reason: %s", reason)
            return []

        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]
        collection_name: str = prepared_inputs["document_collection_name"]
        self._log_info("Identifying web concepts for '%s' using LLM...", collection_name)

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

        validated_concepts: WebContentConceptsList = [
            cast(WebContentConceptItem, item) for item in raw_concepts_from_yaml
        ]

        if not validated_concepts and raw_concepts_from_yaml:
            self._log_warning("LLM parsed YAML, but no valid items remained after item-schema validation.")
        elif not validated_concepts:
            self._log_warning("No valid web concepts found in LLM response or after processing.")
        else:
            self._log_info("Successfully processed %d web concepts.", len(validated_concepts))
        return validated_concepts

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: IdentifyWebConceptsPreparedInputs,
        execution_outputs: IdentifyWebConceptsExecutionResult,
    ) -> None:
        """Update the shared context with identified web concepts.

        Args:
            shared_context (SLSharedContext): The shared context dictionary to update.
            prepared_inputs (IdentifyWebConceptsPreparedInputs): Result from `pre_execution`.
            execution_outputs (IdentifyWebConceptsExecutionResult): List of web concepts.
        """
        del prepared_inputs
        shared_context["text_concepts"] = execution_outputs
        self._log_info("Stored %d web concepts in shared_context['text_concepts'].", len(execution_outputs))


# End of src/sourcelens/nodes/web/n02_identify_web_concepts.py
