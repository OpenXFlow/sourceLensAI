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

"""Defines the main processing flow for Web Content Analysis.

This module orchestrates nodes for fetching, processing, and analyzing web content.
For YouTube URLs:
  - `FetchYouTubeContent` extracts metadata and raw transcript text.
  - `TranslateYouTubeTranscript` translates and/or reformats the transcript using LLM.
  - `CombineWebSummary` creates a 'pg_{sanitized_title}.md' from metadata and saves transcripts.
  - In 'llm_extended' mode, description and the final transcript are segmented for LLM processing.
For general web URLs:
  - `FetchWebPage` crawls content.
  - Subsequent LLM nodes process this content in 'llm_extended' mode.
"""

import logging
import re
from typing import Any, Final, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.config_loader import DEFAULT_WEB_PROCESSING_MODE
from sourcelens.core import Flow as SourceLensFlow
from sourcelens.core.common_types import SharedContextDict
from sourcelens.core.flow_engine_sync import Node as CoreEngineNode

from .nodes import (
    AnalyzeWebRelationships,
    CombineWebSummary,
    FetchWebPage,
    FetchYouTubeContent,
    GenerateWebInventory,
    GenerateWebReview,
    IdentifyWebConcepts,
    OrderWebChapters,
    SegmentWebContent,
    TranslateYouTubeTranscript,
    WriteWebChapters,
)

LlmConfigDict: TypeAlias = dict[str, Any]
PipelineNodeType: TypeAlias = CoreEngineNode[SharedContextDict, Any, Any]


logger: logging.Logger = logging.getLogger(__name__)

YOUTUBE_URL_PATTERNS_IN_FLOW: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?:v=|\/|embed\/|watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11}).*"),
    re.compile(r"shorts\/([0-9A-Za-z_-]{11})"),
]


def _is_youtube_url_in_flow(url: Optional[str]) -> bool:
    """Check if the given URL is a YouTube video URL.

    Args:
        url: The URL string to check.

    Returns:
        True if the URL matches known YouTube video patterns, False otherwise.
    """
    if not url:
        return False
    return any(pattern.search(url) for pattern in YOUTUBE_URL_PATTERNS_IN_FLOW)


def _configure_llm_node_params(llm_config: LlmConfigDict) -> tuple[int, int]:
    """Extract LLM retry and wait parameters from the LLM configuration.

    Args:
        llm_config: Configuration dictionary for the LLM provider.

    Returns:
        A tuple containing (max_retries, retry_wait_seconds).
    """
    max_r_llm_any: Any = llm_config.get("max_retries", 3)
    r_wait_llm_any: Any = llm_config.get("retry_wait_seconds", 10)
    max_r_llm: int = int(max_r_llm_any) if isinstance(max_r_llm_any, (int, float)) else 3
    r_wait_llm: int = int(r_wait_llm_any) if isinstance(r_wait_llm_any, (int, float)) else 10
    return max_r_llm, r_wait_llm


def _build_llm_extended_pipeline_core(
    current_node_tracker: PipelineNodeType,
    initial_context: SharedContextDict,
    flow_description_parts: list[str],
) -> tuple[PipelineNodeType, list[str]]:
    """Build the core LLM-dependent part of the web crawling pipeline.

    Appends LLM processing nodes (segmentation, concepts, relationships, chapters,
    inventory, review) to the `current_node_tracker`.

    Args:
        current_node_tracker: The node to chain LLM processing from.
        initial_context: The shared context for retrieving LLM config.
        flow_description_parts: List of node names for logging.

    Returns:
        A tuple: (new_last_node, updated_flow_description_parts).
    """
    llm_config_for_flow: LlmConfigDict = cast(dict, initial_context.get("llm_config", {}))
    if not llm_config_for_flow:  # pragma: no cover
        logger.warning("LLM config missing for llm_extended mode. Using defaults.")
        llm_config_for_flow = {}

    max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config_for_flow)
    logger.info("Initializing LLM-based web nodes with max_retries=%d, retry_wait=%d", max_r_llm, r_wait_llm)

    llm_nodes_sequence: list[PipelineNodeType] = [
        cast(PipelineNodeType, SegmentWebContent()),
        cast(PipelineNodeType, IdentifyWebConcepts(max_retries=max_r_llm, wait=r_wait_llm)),
        cast(PipelineNodeType, AnalyzeWebRelationships(max_retries=max_r_llm, wait=r_wait_llm)),
        cast(PipelineNodeType, OrderWebChapters(max_retries=max_r_llm, wait=r_wait_llm)),
        cast(PipelineNodeType, WriteWebChapters(max_retries=max_r_llm, wait=r_wait_llm)),
        cast(PipelineNodeType, GenerateWebInventory(max_retries=max_r_llm, wait=r_wait_llm)),
        cast(PipelineNodeType, GenerateWebReview(max_retries=max_r_llm, wait=r_wait_llm)),
    ]

    temp_chain_tracker: PipelineNodeType = current_node_tracker
    for node_to_add in llm_nodes_sequence:
        temp_chain_tracker = cast(PipelineNodeType, temp_chain_tracker >> node_to_add)
        flow_description_parts.append(type(node_to_add).__name__)

    return temp_chain_tracker, flow_description_parts


def _build_youtube_pipeline(
    initial_context: SharedContextDict, processing_mode: str, max_r_llm: int, r_wait_llm: int
) -> tuple[PipelineNodeType, list[str]]:
    """Build the pipeline for YouTube URL processing.

    Args:
        initial_context: The initial shared context.
        processing_mode: The current processing mode ("minimalistic" or "llm_extended").
        max_r_llm: Max retries for LLM nodes.
        r_wait_llm: Wait time for LLM node retries.

    Returns:
        A tuple: (start_node, flow_description_parts).
    """
    flow_description_parts: list[str] = []
    fetch_yt_node: PipelineNodeType = cast(PipelineNodeType, FetchYouTubeContent())
    start_node = fetch_yt_node
    current_node_tracker = start_node
    flow_description_parts.append(type(fetch_yt_node).__name__)

    translate_node = cast(PipelineNodeType, TranslateYouTubeTranscript(max_retries=max_r_llm, wait=r_wait_llm))
    current_node_tracker = cast(PipelineNodeType, current_node_tracker >> translate_node)
    flow_description_parts.append(type(translate_node).__name__)
    logger.info("Added TranslateYouTubeTranscript for YouTube URL.")

    if processing_mode == "llm_extended":
        logger.info("YouTube URL: Configuring LLM pipeline after translation.")
        current_node_tracker, flow_description_parts = _build_llm_extended_pipeline_core(
            current_node_tracker, initial_context, flow_description_parts
        )

    combine_node_yt: PipelineNodeType = cast(PipelineNodeType, CombineWebSummary())
    current_node_tracker = cast(PipelineNodeType, current_node_tracker >> combine_node_yt)
    flow_description_parts.append(type(combine_node_yt).__name__)
    logger.info("Added CombineWebSummary for final YouTube URL processing.")
    return start_node, flow_description_parts


def _build_general_web_pipeline(
    initial_context: SharedContextDict, processing_mode: str, primary_input_url: Optional[str]
) -> tuple[PipelineNodeType, list[str]]:
    """Build the pipeline for general web URL or file processing.

    Args:
        initial_context: The initial shared context.
        processing_mode: The current processing mode.
        primary_input_url: The primary URL or file path being processed.

    Returns:
        A tuple: (start_node, flow_description_parts).
    """
    flow_description_parts: list[str] = []
    logger.info("General Web URL/File ('%s'). Initializing FetchWebPage node.", primary_input_url)
    fetch_page_node_instance: PipelineNodeType = cast(PipelineNodeType, FetchWebPage())
    start_node = fetch_page_node_instance
    current_node_tracker = start_node
    flow_description_parts.append(type(fetch_page_node_instance).__name__)

    if processing_mode == "llm_extended":
        logger.info("General Web URL: Configuring LLM pipeline.")
        current_node_tracker, flow_description_parts = _build_llm_extended_pipeline_core(
            current_node_tracker, initial_context, flow_description_parts
        )
        combine_node_web: PipelineNodeType = cast(PipelineNodeType, CombineWebSummary())
        current_node_tracker = cast(PipelineNodeType, current_node_tracker >> combine_node_web)
        flow_description_parts.append(type(combine_node_web).__name__)
    elif processing_mode == "minimalistic":
        logger.info("General Web URL: Minimalistic mode. Flow ends after FetchWebPage.")
    else:  # pragma: no cover
        logger.warning("Unknown processing_mode '%s'. Defaulting to FetchWebPage only.", processing_mode)
    return start_node, flow_description_parts


def create_web_crawling_flow(initial_context: SharedContextDict) -> SourceLensFlow:
    """Create and configure the flow for web content processing.

    Args:
        initial_context: The initial shared context dictionary.

    Returns:
        An instance of `SourceLensFlow` for web content analysis.
    """
    logger.info("Configuring flow for FL02_web_crawling.")

    # Prefer processing_mode directly from initial_context if set by CLI,
    # otherwise fallback to the value within initial_context["config"].
    processing_mode_from_context: Optional[Any] = initial_context.get("processing_mode")
    processing_mode: str

    if isinstance(processing_mode_from_context, str):
        processing_mode = processing_mode_from_context
        logger.debug("Using 'processing_mode' directly from initial_context: '%s'", processing_mode)
    else:
        resolved_config_val: Any = initial_context.get("config", {})
        resolved_config: dict[str, Any] = cast(dict, resolved_config_val)
        web_flow_settings: dict[str, Any] = resolved_config.get("FL02_web_crawling", {})
        crawler_options: dict[str, Any] = web_flow_settings.get("crawler_options", {})
        processing_mode = str(crawler_options.get("processing_mode", DEFAULT_WEB_PROCESSING_MODE))
        logger.debug("Using 'processing_mode' from config within initial_context: '%s'", processing_mode)

    logger.info("Web analysis processing mode determined for flow.py: '%s'", processing_mode)

    primary_input_url: Optional[str] = None
    if initial_context.get("crawl_url"):
        primary_input_url = cast(Optional[str], initial_context.get("crawl_url"))
    elif initial_context.get("crawl_file"):
        primary_input_url = cast(Optional[str], initial_context.get("crawl_file"))

    is_yt_url: bool = _is_youtube_url_in_flow(primary_input_url)

    start_node: PipelineNodeType
    flow_description_parts: list[str]
    llm_config_for_flow: LlmConfigDict = cast(dict, initial_context.get("llm_config", {}))
    max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config_for_flow)

    if is_yt_url:
        start_node, flow_description_parts = _build_youtube_pipeline(
            initial_context, processing_mode, max_r_llm, r_wait_llm
        )
    else:
        start_node, flow_description_parts = _build_general_web_pipeline(
            initial_context, processing_mode, primary_input_url
        )

    logger.info("FL02_web_crawling final flow sequence: %s", " -> ".join(flow_description_parts))
    return SourceLensFlow(start=start_node)


# End of src/FL02_web_crawling/flow.py
