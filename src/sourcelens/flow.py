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

"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using the internal
SourceLens flow engine to generate tutorials from source code or to fetch
web content. For web content fetching, it can operate in a minimalistic
mode (save files only) or an extended mode (save files and perform LLM-based
analysis of the web content).
"""

import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from sourcelens.core.flow_engine_sync import Flow as SourceLensFlow
    from sourcelens.nodes import BaseNode as SourceLensBaseNode  # Assuming nodes.__init__ exports BaseNode
else:
    SourceLensFlow: Any = None
    SourceLensBaseNode: Any = None


from sourcelens.nodes import (
    # Code Analysis Nodes
    AnalyzeRelationships,
    AnalyzeWebRelationships,  # n03
    CombineTutorial,
    CombineWebSummary,  # n08
    FetchCode,
    # Web Content Analysis Nodes (using new n0x_ prefix)
    FetchWebPage,
    GenerateDiagramsNode,
    GenerateProjectReview,
    GenerateSourceIndexNode,
    GenerateWebInventory,  # n06
    GenerateWebReview,  # n07
    IdentifyAbstractions,
    IdentifyScenariosNode,
    IdentifyWebConcepts,
    OrderChapters,
    OrderWebChapters,  # n04
    WriteChapters,
    WriteWebChapters,  # n05
)

SharedContextDict: TypeAlias = dict[str, Any]
LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)


def _configure_llm_node_params(llm_config: LlmConfigDict) -> tuple[int, int]:
    """Extract LLM retry and wait parameters from the configuration.

    Args:
        llm_config (LlmConfigDict): Configuration dictionary for the LLM provider.

    Returns:
        tuple[int, int]: A tuple containing (max_retries, retry_wait_seconds).
    """
    max_r_llm_any: Any = llm_config.get("max_retries", 3)
    r_wait_llm_any: Any = llm_config.get("retry_wait_seconds", 10)
    max_r_llm: int = int(max_r_llm_any) if isinstance(max_r_llm_any, (int, float)) else 3
    r_wait_llm: int = int(r_wait_llm_any) if isinstance(r_wait_llm_any, (int, float)) else 10
    return max_r_llm, r_wait_llm


def _create_code_analysis_flow(
    llm_config: LlmConfigDict,
    cache_config: CacheConfigDict,
) -> "SourceLensFlow":
    """Create and configure the pipeline for code analysis and tutorial generation.

    Args:
        llm_config (LlmConfigDict): Configuration for the LLM provider.
        cache_config (CacheConfigDict): Configuration for LLM caching.

    Returns:
        SourceLensFlow: An instance of the configured `SourceLensFlow` for code analysis.

    Raises:
        RuntimeError: If the core Flow component cannot be imported.
    """
    del cache_config
    logger.info("Configuring flow for code analysis and tutorial generation.")
    max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config)
    logger.info("Initializing LLM-based code analysis nodes with max_retries=%d, retry_wait=%d", max_r_llm, r_wait_llm)

    fetch_code = FetchCode()
    id_abstr = IdentifyAbstractions(max_retries=max_r_llm, wait=r_wait_llm)
    an_rels = AnalyzeRelationships(max_retries=max_r_llm, wait=r_wait_llm)
    ord_chaps = OrderChapters(max_retries=max_r_llm, wait=r_wait_llm)
    id_scens = IdentifyScenariosNode(max_retries=max_r_llm, wait=r_wait_llm)
    gen_diags = GenerateDiagramsNode(max_retries=max_r_llm, wait=r_wait_llm)
    wr_chaps = WriteChapters(max_retries=max_r_llm, wait=r_wait_llm)
    gen_src_idx = GenerateSourceIndexNode(max_retries=1, wait=0)
    gen_proj_rev = GenerateProjectReview(max_retries=max_r_llm, wait=r_wait_llm)
    comb_tut = CombineTutorial()

    (
        fetch_code
        >> id_abstr
        >> an_rels
        >> ord_chaps
        >> id_scens
        >> gen_diags
        >> wr_chaps
        >> gen_src_idx
        >> gen_proj_rev
        >> comb_tut
    )

    flow_description = (
        "Flow sequence (code analysis): FetchCode -> IdentifyAbstractions -> AnalyzeRelationships -> "
        "OrderChapters -> IdentifyScenariosNode -> GenerateDiagramsNode -> "
        "WriteChapters -> GenerateSourceIndexNode -> GenerateProjectReview -> CombineTutorial"
    )
    logger.info(flow_description)

    if TYPE_CHECKING:
        from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
    else:
        try:
            from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
        except ImportError as e:
            logger.critical("Failed to import Flow for code analysis: %s", e)
            raise RuntimeError("Core Flow component not importable for code analysis.") from e

    return ActualSourceLensFlow(start=fetch_code)


def _create_web_content_flow(
    llm_config: LlmConfigDict,
    cache_config: CacheConfigDict,
    initial_context: SharedContextDict,
) -> "SourceLensFlow":
    """Create and configure the pipeline for web content processing.

    Args:
        llm_config (LlmConfigDict): Configuration for the LLM provider.
        cache_config (CacheConfigDict): Configuration for LLM caching.
        initial_context (SharedContextDict): The initial shared context.

    Returns:
        SourceLensFlow: An instance of the configured `SourceLensFlow` for web content.

    Raises:
        RuntimeError: If the core Flow component cannot be imported.
    """
    del cache_config
    config_data_val: Any = initial_context.get("config", {})
    config_data: dict[str, Any] = config_data_val if isinstance(config_data_val, dict) else {}
    web_opts_val: Any = config_data.get("web_crawler_options", {})
    web_opts: dict[str, Any] = web_opts_val if isinstance(web_opts_val, dict) else {}
    processing_mode: str = str(web_opts.get("processing_mode", "minimalistic"))
    logger.info("Web crawl operation. Processing mode: '%s'", processing_mode)

    n01_fetch_web = FetchWebPage()  # Node n01 (was n20)
    start_node: "SourceLensBaseNode" = n01_fetch_web
    flow_description: str

    if processing_mode == "minimalistic":
        logger.info("Configuring flow for minimalist web content fetching (FetchWebPage only).")
        flow_description = f"Flow sequence (minimal web crawl): {type(n01_fetch_web).__name__}"
    elif processing_mode == "llm_extended":
        logger.info("Configuring flow for LLM-extended web content processing.")
        max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config)
        logger.info(
            "Initializing LLM-based web content analysis nodes with max_retries=%d, retry_wait=%d",
            max_r_llm,
            r_wait_llm,
        )

        n02_id_web_concepts = IdentifyWebConcepts(max_retries=max_r_llm, wait=r_wait_llm)
        n03_an_web_rels = AnalyzeWebRelationships(max_retries=max_r_llm, wait=r_wait_llm)
        n04_ord_web_chaps = OrderWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n05_wr_web_chaps = WriteWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n06_gen_web_inv = GenerateWebInventory(max_retries=max_r_llm, wait=r_wait_llm)  # LLM for summaries
        n07_gen_web_rev = GenerateWebReview(max_retries=max_r_llm, wait=r_wait_llm)
        n08_comb_web_sum = CombineWebSummary()  # No LLM, just combines

        (
            n01_fetch_web
            >> n02_id_web_concepts
            >> n03_an_web_rels
            >> n04_ord_web_chaps
            >> n05_wr_web_chaps
            >> n06_gen_web_inv
            >> n07_gen_web_rev
            >> n08_comb_web_sum
        )

        flow_description = (
            f"Flow sequence (extended web crawl): {type(n01_fetch_web).__name__} -> "
            f"{type(n02_id_web_concepts).__name__} -> {type(n03_an_web_rels).__name__} -> "
            f"{type(n04_ord_web_chaps).__name__} -> {type(n05_wr_web_chaps).__name__} -> "
            f"{type(n06_gen_web_inv).__name__} -> {type(n07_gen_web_rev).__name__} -> "
            f"{type(n08_comb_web_sum).__name__}"
        )
    else:
        logger.warning(
            "Unknown web_crawler_options.processing_mode '%s'. Defaulting to minimalistic.",
            processing_mode,
        )
        flow_description = f"Flow sequence (defaulted minimal web crawl): {type(n01_fetch_web).__name__}"

    logger.info(flow_description)

    if TYPE_CHECKING:
        from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
    else:
        try:
            from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
        except ImportError as e:
            logger.critical("Failed to import Flow for web content: %s", e)
            raise RuntimeError("Core Flow component not importable for web content.") from e

    return ActualSourceLensFlow(start=start_node)


def create_tutorial_flow(
    llm_config: LlmConfigDict,
    cache_config: CacheConfigDict,
    initial_context: SharedContextDict,
) -> "SourceLensFlow":
    """Create and configure the appropriate SourceLens processing flow.

    Dispatches to a specific flow creation function based on the operation type
    indicated in the `initial_context` (web crawl vs. code analysis).

    Args:
        llm_config (LlmConfigDict): Processed configuration for the active LLM provider.
        cache_config (CacheConfigDict): Configuration related to LLM response caching.
        initial_context (SharedContextDict): The initial shared context.

    Returns:
        SourceLensFlow: An instance of the configured `SourceLensFlow`.
    """
    logger.info("Determining appropriate SourceLens processing flow...")

    is_web_crawl_op = bool(
        initial_context.get("crawl_url") or initial_context.get("crawl_sitemap") or initial_context.get("crawl_file")
    )

    if is_web_crawl_op:
        return _create_web_content_flow(llm_config, cache_config, initial_context)
    # else
    return _create_code_analysis_flow(llm_config, cache_config)


# End of src/sourcelens/flow.py
