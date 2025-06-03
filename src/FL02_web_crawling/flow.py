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

This module is responsible for instantiating and connecting the various
processing nodes using the SourceLens flow engine to fetch, process, and
analyze web content.
"""

import logging
from typing import Any, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode  # Using BaseNode from sourcelens.core.base_node
from sourcelens.core import Flow as SourceLensFlow

from .nodes import (
    AnalyzeWebRelationships,
    CombineWebSummary,
    FetchWebPage,
    GenerateWebInventory,
    GenerateWebReview,
    IdentifyWebConcepts,
    OrderWebChapters,
    SegmentWebContent,
    WriteWebChapters,
)

LlmConfigDict: TypeAlias = dict[str, Any]
SharedContextDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)


def _configure_llm_node_params_for_web_flow(llm_config: LlmConfigDict) -> tuple[int, int]:
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


def create_web_crawling_flow(initial_context: SharedContextDict) -> SourceLensFlow:
    """Create and configure the flow for web content processing.

    Args:
        initial_context: The initial shared context dictionary.

    Returns:
        An instance of `SourceLensFlow` for web content analysis.
    """
    logger.info("Configuring flow for FL02_web_crawling.")

    resolved_flow_config: dict[str, Any] = initial_context.get("config", {})
    web_flow_specific_settings: dict[str, Any] = resolved_flow_config.get("FL02_web_crawling", {})

    crawler_options_val: Any = web_flow_specific_settings.get("crawler_options", {})
    crawler_options: dict[str, Any] = crawler_options_val if isinstance(crawler_options_val, dict) else {}
    processing_mode: str = str(crawler_options.get("processing_mode", "minimalistic"))

    logger.info("Web analysis processing mode from resolved flow config: '%s'", processing_mode)

    n01_fetch_web = FetchWebPage()
    # Explicitly type start_node and current_node_tracker as our application's BaseNode
    start_node: BaseNode[Any, Any] = n01_fetch_web
    current_node_tracker: BaseNode[Any, Any] = start_node
    flow_description_parts: list[str] = [type(n01_fetch_web).__name__]

    if processing_mode == "llm_extended":
        logger.info("Configuring full LLM pipeline for web content (llm_extended mode).")
        llm_config_for_flow: LlmConfigDict = initial_context.get("llm_config", {})
        if not llm_config_for_flow:
            logger.warning("LLM configuration missing for web llm_extended mode. Using defaults for LLM nodes.")
            llm_config_for_flow = {}

        max_r_llm, r_wait_llm = _configure_llm_node_params_for_web_flow(llm_config_for_flow)
        log_msg_llm = "Initializing LLM-based web nodes in flow with max_retries=%d, retry_wait=%d"
        logger.info(log_msg_llm, max_r_llm, r_wait_llm)

        # Add the new SegmentWebContent node
        n01b_segment_content = SegmentWebContent()  # Retries usually not needed for this node
        # Cast to the type expected by current_node_tracker
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n01b_segment_content)
        flow_description_parts.append(type(n01b_segment_content).__name__)

        # Identify concepts (now from chunks)
        n02_id_web_concepts = IdentifyWebConcepts(max_retries=max_r_llm, wait=r_wait_llm)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n02_id_web_concepts)
        flow_description_parts.append(type(n02_id_web_concepts).__name__)

        # Remainder of the pipeline
        n03_an_web_rels = AnalyzeWebRelationships(max_retries=max_r_llm, wait=r_wait_llm)
        n04_ord_web_chaps = OrderWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n05_wr_web_chaps = WriteWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n06_gen_web_inv = GenerateWebInventory(max_retries=max_r_llm, wait=r_wait_llm)
        n07_gen_web_rev = GenerateWebReview(max_retries=max_r_llm, wait=r_wait_llm)
        n08_comb_web_sum = CombineWebSummary()

        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n03_an_web_rels)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n04_ord_web_chaps)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n05_wr_web_chaps)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n06_gen_web_inv)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n07_gen_web_rev)
        current_node_tracker = cast(BaseNode[Any, Any], current_node_tracker >> n08_comb_web_sum)

        flow_description_parts.extend(
            [
                type(n).__name__
                for n in [
                    n03_an_web_rels,  # n02 already added
                    n04_ord_web_chaps,
                    n05_wr_web_chaps,
                    n06_gen_web_inv,
                    n07_gen_web_rev,
                    n08_comb_web_sum,
                ]
            ]
        )
    elif processing_mode == "minimalistic":
        logger.info("Web analysis mode: minimalistic. Flow will only run FetchWebPage.")
    else:
        logger.warning(
            "Unknown processing_mode '%s' in web_analysis config. Defaulting to minimalistic flow.",
            processing_mode,
        )

    logger.info("FL02_web_crawling flow sequence: %s", " -> ".join(flow_description_parts))
    # start_node is correctly typed as BaseNode[Any,Any]
    return SourceLensFlow(start=start_node)


# End of src/FL02_web_crawling/flow.py
