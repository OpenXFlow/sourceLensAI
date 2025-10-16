# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Node responsible for analyzing relationships between identified web concepts using an LLM."""

import logging
from typing import Any, Final, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import (
    WebContentConceptItem,
    WebContentConceptsList,
    WebContentRelationshipDetail,
    WebContentRelationshipsDict,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_dict

from ..prompts.relationship_prompts import WebRelationshipPrompts

AnalyzeWebRelationshipsPreparedInputs: TypeAlias = dict[str, Any]
AnalyzeWebRelationshipsExecutionResult: TypeAlias = WebContentRelationshipsDict

LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]

module_logger_web_rels: logging.Logger = logging.getLogger(__name__)

MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_RELS: Final[int] = 500
DEFAULT_REL_ERROR_SUMMARY: Final[str] = "Error during web content relationship analysis."
MAX_RELATIONSHIP_LABEL_LEN_NODE: Final[int] = 100

WEB_RELATIONSHIP_ITEM_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "from_concept_index": {"type": "integer", "minimum": 0},
        "to_concept_index": {"type": "integer", "minimum": 0},
        "label": {"type": "string", "minLength": 1, "maxLength": MAX_RELATIONSHIP_LABEL_LEN_NODE},
    },
    "required": ["from_concept_index", "to_concept_index", "label"],
    "additionalProperties": False,
}
WEB_RELATIONSHIPS_DICT_SCHEMA: dict[str, Any] = {
    "type": "object",
    "properties": {
        "overall_summary": {"type": "string", "minLength": 1},
        "relationships": {"type": "array", "items": WEB_RELATIONSHIP_ITEM_SCHEMA},
    },
    "required": ["overall_summary", "relationships"],
    "additionalProperties": False,
}


class AnalyzeWebRelationships(BaseNode[AnalyzeWebRelationshipsPreparedInputs, AnalyzeWebRelationshipsExecutionResult]):
    """Analyze relationships between identified web content concepts using an LLM.

    This node uses previously identified web concepts (derived from chunks)
    to prompt an LLM for a summary of their interactions and a list of specific
    relationships.
    """

    def _build_concepts_listing_for_prompt(self, concepts: WebContentConceptsList) -> str:
        """Build a string listing concepts and their summaries for the LLM prompt.

        Args:
            concepts: List of identified web concept dictionaries.
                      Each dict should have 'name' and 'summary'.
                      'source_chunk_ids' can be used for richer context if needed in future.

        Returns:
            A formatted string listing concepts with indices and summaries.
        """
        if not concepts:
            return "No concepts available for relationship analysis."

        listing_parts: list[str] = []
        for i, concept_item in enumerate(concepts):
            name = str(concept_item.get("name", f"Unnamed Concept {i}"))
            summary_val = concept_item.get("summary", "No summary available.")
            summary = str(summary_val) if isinstance(summary_val, str) else "Summary not available as string."
            # Optionally, include info about source_chunk_ids if helpful for LLM context on relationships
            # chunk_ids_list = concept_item.get("source_chunk_ids", [])
            # chunk_info = f" (Sources: {len(chunk_ids_list)} chunks)" if chunk_ids_list else ""
            # listing_parts.append(f"{i}. {name}{chunk_info} - Summary: {summary}")
            listing_parts.append(f"{i}. {name} - Summary: {summary}")
        return "\n".join(listing_parts)

    def pre_execution(self, shared_context: SLSharedContext) -> AnalyzeWebRelationshipsPreparedInputs:
        """Prepare context for the web relationship analysis LLM prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary for the `execution` method,
            or includes 'skip': True if prerequisites fail.
        """
        self._log_info("Preparing context for web content relationship analysis...")
        try:
            text_concepts_any: Any = self._get_required_shared(shared_context, "text_concepts")
            if not isinstance(text_concepts_any, list):
                self._log_warning("'text_concepts' in shared_context is not a list. Skipping.")
                return {"skip": True, "reason": "'text_concepts' is not a list."}

            text_concepts: WebContentConceptsList = []
            for item_any in text_concepts_any:
                # Ensure concepts have the expected structure for _build_concepts_listing_for_prompt
                if isinstance(item_any, dict) and "name" in item_any and "summary" in item_any:
                    # Ensure source_chunk_ids is a list of strings if present, or default to empty list
                    source_ids_raw = item_any.get("source_chunk_ids", [])
                    source_ids_list = (
                        [str(sid) for sid in source_ids_raw if isinstance(sid, str)]
                        if isinstance(source_ids_raw, list)
                        else []
                    )
                    item_any["source_chunk_ids"] = source_ids_list  # Ensure it's in the concept item
                    text_concepts.append(cast(WebContentConceptItem, item_any))
                else:
                    self._log_warning("Skipping invalid concept item in 'text_concepts': %s", item_any)

            if not text_concepts:
                self._log_warning("No valid web concepts found in shared_context['text_concepts']. Skipping.")
                return {"skip": True, "reason": "No valid web concepts in shared_context['text_concepts']."}

            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            target_language_any: Any = shared_context.get("language", "english")

            project_name: str = str(project_name_any)
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            target_language: str = str(target_language_any)

        except ValueError as e_val:
            self._log_error("Pre-execution for web relationships failed (missing shared data): %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {str(e_val)}"}

        concepts_listing_str = self._build_concepts_listing_for_prompt(text_concepts)

        prepared_inputs: AnalyzeWebRelationshipsPreparedInputs = {
            "skip": False,
            "document_collection_name": project_name,
            "concepts_listing_with_summaries": concepts_listing_str,  # Based on new chunk-derived concepts
            "num_concepts": len(text_concepts),
            "target_language": target_language,
            "llm_config": llm_config,
            "cache_config": cache_config,
        }
        return prepared_inputs

    def _parse_and_validate_llm_relationships(
        self, relationships_data_yaml: dict[str, Any], num_concepts: int
    ) -> WebContentRelationshipsDict:
        """Parse and validate relationship details from the LLM's YAML response.

        Args:
            relationships_data_yaml: The validated dictionary from LLM.
            num_concepts: Total number of concepts for index validation.

        Returns:
            Processed and validated relationship data.
        """
        overall_summary_raw: Any = relationships_data_yaml.get("overall_summary", "")
        overall_summary: str = str(overall_summary_raw).strip() if overall_summary_raw else DEFAULT_REL_ERROR_SUMMARY

        raw_rels_list_any: Any = relationships_data_yaml.get("relationships", [])
        raw_rels_list: list[Any] = raw_rels_list_any if isinstance(raw_rels_list_any, list) else []

        validated_details: list[WebContentRelationshipDetail] = []
        for rel_item_any in raw_rels_list:
            if not isinstance(rel_item_any, dict):
                module_logger_web_rels.warning("Skipping non-dictionary item in relationships list: %s", rel_item_any)
                continue
            rel_item: dict[str, Any] = rel_item_any
            from_idx = cast(int, rel_item.get("from_concept_index"))
            to_idx = cast(int, rel_item.get("to_concept_index"))
            label = cast(str, rel_item.get("label"))

            if not (0 <= from_idx < num_concepts and 0 <= to_idx < num_concepts):
                module_logger_web_rels.warning(
                    "Relationship item has out-of-bounds index(es): from=%d, to=%d (num_concepts=%d). Skipping: %s",
                    from_idx,
                    to_idx,
                    num_concepts,
                    rel_item,
                )
                continue
            validated_details.append(
                {
                    "from_concept_index": from_idx,  # Ensure keys match WebContentRelationshipDetail
                    "to_concept_index": to_idx,
                    "label": label,
                }
            )
        return {"overall_summary": overall_summary, "relationships": validated_details}

    def execution(
        self, prepared_inputs: AnalyzeWebRelationshipsPreparedInputs
    ) -> AnalyzeWebRelationshipsExecutionResult:
        """Execute LLM call to analyze web concept relationships, parse, and validate.

        Args:
            prepared_inputs: From `pre_execution`.

        Returns:
            Dict with 'overall_summary' and 'relationships'.
            Returns a default error structure on failure.
        """
        default_error_output: AnalyzeWebRelationshipsExecutionResult = {
            "overall_summary": DEFAULT_REL_ERROR_SUMMARY,
            "relationships": [],
        }
        if prepared_inputs.get("skip", True):
            reason = str(prepared_inputs.get("reason", "N/A"))
            self._log_info("Skipping web relationship analysis execution. Reason: %s", reason)
            default_error_output["overall_summary"] = f"Skipped: {reason}"
            return default_error_output

        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]
        collection_name: str = prepared_inputs["document_collection_name"]
        num_concepts: int = prepared_inputs["num_concepts"]

        self._log_info("Analyzing relationships for %d web concepts in '%s'...", num_concepts, collection_name)
        if num_concepts == 0:
            self._log_warning("No concepts to analyze relationships for.")
            default_error_output["overall_summary"] = "No concepts provided for analysis."
            return default_error_output

        prompt = WebRelationshipPrompts.format_analyze_web_relationships_prompt(
            document_collection_name=collection_name,
            concepts_listing_with_summaries=prepared_inputs["concepts_listing_with_summaries"],
            num_concepts=num_concepts,
            target_language=prepared_inputs["target_language"],
        )
        response_text: str
        try:
            response_text = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e_llm:
            self._log_error("LLM call failed during web relationship analysis: %s", e_llm, exc_info=True)
            return default_error_output

        try:
            validated_yaml_data = validate_yaml_dict(response_text, WEB_RELATIONSHIPS_DICT_SCHEMA)
            processed_relationships = self._parse_and_validate_llm_relationships(validated_yaml_data, num_concepts)
            self._log_info(
                "Successfully processed web relationships: %d details.",
                len(processed_relationships.get("relationships", [])),
            )
            return processed_relationships

        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for web relationships: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_RELS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_WEB_RELS:
                    snippet += "..."
                module_logger_web_rels.warning(
                    "Problematic raw LLM output for web relationships:\n---\n%s\n---", snippet
                )
            return default_error_output

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: AnalyzeWebRelationshipsPreparedInputs,
        execution_outputs: AnalyzeWebRelationshipsExecutionResult,
    ) -> None:
        """Update the shared context with analyzed web concept relationships.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from `pre_execution`.
            execution_outputs: Dict of relationships.
        """
        del prepared_inputs
        shared_context["text_relationships"] = execution_outputs
        summary_snippet = str(execution_outputs.get("overall_summary", ""))[:70]
        details_count = len(cast(list, execution_outputs.get("relationships", [])))
        self._log_info(
            "Stored web relationships in shared_context['text_relationships']. "
            "Summary snippet: '%s...', Details count: %d",
            summary_snippet,
            details_count,
        )


# End of src/FL02_web_crawling/nodes/n03_analyze_web_relationships.py
