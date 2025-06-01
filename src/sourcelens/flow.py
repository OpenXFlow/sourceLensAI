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
SourceLens flow engine to generate tutorials from source code or to process
web content. For web content, it adapts based on the 'processing_mode'
configured (minimalistic vs. LLM-extended).
"""

import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeAlias

if TYPE_CHECKING:
    from sourcelens.core.flow_engine_sync import Flow as SourceLensFlow
    from sourcelens.nodes.base_node import BaseNode as SourceLensBaseNode
else:
    SourceLensFlow = None
    SourceLensBaseNode = None


from sourcelens.nodes import (
    AnalyzeRelationships,
    AnalyzeWebRelationships,
    CombineTutorial,
    CombineWebSummary,
    FetchCode,
    FetchWebPage,
    GenerateDiagramsNode,
    GenerateProjectReview,
    GenerateSourceIndexNode,
    GenerateWebInventory,
    GenerateWebReview,
    IdentifyAbstractions,
    IdentifyScenariosNode,
    IdentifyWebConcepts,
    OrderChapters,
    OrderWebChapters,
    WriteChapters,
    WriteWebChapters,
)

SharedContextDict: TypeAlias = dict[str, Any]
LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]
CodeAnalysisConfigDict: TypeAlias = dict[str, Any]
WebAnalysisConfigDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)


def _configure_llm_node_params(llm_config: LlmConfigDict) -> tuple[int, int]:
    """Extract LLM retry and wait parameters from the LLM configuration.

    Args:
        llm_config: Configuration dictionary for the LLM provider.
                    Expected keys: 'max_retries', 'retry_wait_seconds'.

    Returns:
        A tuple containing (max_retries, retry_wait_seconds).
    """
    max_r_llm_any: Any = llm_config.get("max_retries", 3)
    r_wait_llm_any: Any = llm_config.get("retry_wait_seconds", 10)
    max_r_llm: int = int(max_r_llm_any) if isinstance(max_r_llm_any, (int, float)) else 3
    r_wait_llm: int = int(r_wait_llm_any) if isinstance(r_wait_llm_any, (int, float)) else 10
    return max_r_llm, r_wait_llm


def _create_code_analysis_flow(
    code_analysis_config: CodeAnalysisConfigDict,
    _common_cache_config: CacheConfigDict,
) -> "SourceLensFlow":
    """Create and configure the pipeline for code analysis and tutorial generation.

    This function sets up a sequence of processing nodes tailored for analyzing
    source code. It initializes each node, including LLM-based nodes with
    appropriate retry and wait parameters derived from the `code_analysis_config`.
    The cache configuration is available in the `initial_context` that nodes will receive.

    Args:
        code_analysis_config: The resolved configuration dictionary specific to
                              code analysis. This includes the LLM settings
                              (provider, model, API keys resolved from env if needed,
                              retries, wait times) and other code-specific options.
        _common_cache_config: The common cache settings from the configuration
                             (e.g., cache file path, whether to use cache).
                             Marked as unused here as nodes get it from shared_context.

    Returns:
        An instance of `SourceLensFlow` representing the configured pipeline
        for code analysis, with `FetchCode` as the starting node.

    Raises:
        RuntimeError: If the core `Flow` component from `sourcelens.core.flow_engine_sync`
                      cannot be imported at runtime.
    """
    del _common_cache_config
    logger.info("Configuring flow for code analysis and tutorial generation.")
    llm_config_code: LlmConfigDict = code_analysis_config.get("llm_config", {})
    max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config_code)
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


def _create_web_analysis_flow(
    web_analysis_config: WebAnalysisConfigDict,
    _common_cache_config: CacheConfigDict,
) -> "SourceLensFlow":
    """Create and configure the pipeline for web content processing.

    This function sets up a sequence of processing nodes for web content.
    If `processing_mode` in `crawler_options` is "llm_extended", it configures
    a full pipeline including LLM-based analysis nodes. If "minimalistic",
    only the `FetchWebPage` node is run. LLM nodes are initialized with
    retry parameters from `web_analysis_config`.

    Args:
        web_analysis_config: The resolved configuration dictionary specific to
                             web analysis. This includes LLM settings, crawler options,
                             and web-specific output options.
        _common_cache_config: The common cache settings (marked as unused).

    Returns:
        An instance of `SourceLensFlow` representing the configured pipeline
        for web content analysis, with `FetchWebPage` as the starting node.

    Raises:
        RuntimeError: If the core `Flow` component from `sourcelens.core.flow_engine_sync`
                      cannot be imported at runtime.
    """
    del _common_cache_config
    crawler_options: dict[str, Any] = web_analysis_config.get("crawler_options", {})
    processing_mode: str = str(crawler_options.get("processing_mode", "minimalistic"))
    logger.info("Configuring flow for web content analysis. Processing mode: '%s'", processing_mode)

    n01_fetch_web = FetchWebPage()
    start_node: "SourceLensBaseNode" = n01_fetch_web
    flow_description_parts: list[str] = [type(n01_fetch_web).__name__]

    if processing_mode == "llm_extended":
        logger.info("Web analysis mode: llm_extended. Configuring full LLM pipeline for web content.")
        llm_config_web: LlmConfigDict = web_analysis_config.get("llm_config", {})
        max_r_llm, r_wait_llm = _configure_llm_node_params(llm_config_web)
        log_msg = "Initializing LLM-based web content analysis nodes with max_retries=%d, retry_wait=%d"
        logger.info(log_msg, max_r_llm, r_wait_llm)

        n02_id_web_concepts = IdentifyWebConcepts(max_retries=max_r_llm, wait=r_wait_llm)
        n03_an_web_rels = AnalyzeWebRelationships(max_retries=max_r_llm, wait=r_wait_llm)
        n04_ord_web_chaps = OrderWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n05_wr_web_chaps = WriteWebChapters(max_retries=max_r_llm, wait=r_wait_llm)
        n06_gen_web_inv = GenerateWebInventory(max_retries=max_r_llm, wait=r_wait_llm)
        n07_gen_web_rev = GenerateWebReview(max_retries=max_r_llm, wait=r_wait_llm)
        n08_comb_web_sum = CombineWebSummary()

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
        flow_description_parts.extend(
            [
                type(n02_id_web_concepts).__name__,
                type(n03_an_web_rels).__name__,
                type(n04_ord_web_chaps).__name__,
                type(n05_wr_web_chaps).__name__,
                type(n06_gen_web_inv).__name__,
                type(n07_gen_web_rev).__name__,
                type(n08_comb_web_sum).__name__,
            ]
        )
    elif processing_mode == "minimalistic":
        logger.info("Web analysis mode: minimalistic. Only FetchWebPage will run.")
    else:
        logger.warning(
            "Unknown web_analysis.crawler_options.processing_mode '%s'. Defaulting to minimalistic.",
            processing_mode,
        )

    logger.info("Flow sequence (web analysis): %s", " -> ".join(flow_description_parts))

    if TYPE_CHECKING:
        from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
    else:
        try:
            from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
        except ImportError as e:
            logger.critical("Failed to import Flow for web analysis: %s", e)
            raise RuntimeError("Core Flow component not importable for web analysis.") from e

    return ActualSourceLensFlow(start=start_node)


def create_tutorial_flow(
    _llm_config_placeholder: LlmConfigDict,
    _cache_config_placeholder: CacheConfigDict,
    initial_context: SharedContextDict,
) -> "SourceLensFlow":
    """Create and configure the appropriate SourceLens processing flow.

    Determines whether to create a code analysis or web analysis flow based on
    input sources specified in `initial_context` and corresponding enabled flags
    in the fully resolved configuration (expected under `initial_context["config"]`).

    Args:
        _llm_config_placeholder: Placeholder; LLM config is now sourced from
                                 `initial_context["config"]["<mode>_analysis"]["llm_config"]`.
        _cache_config_placeholder: Placeholder; Cache config is sourced from
                                   `initial_context["config"]["common"]["cache_settings"]`.
        initial_context: The initial shared context. Must contain the fully resolved
                         application configuration under the key "config".

    Returns:
        An instance of `SourceLensFlow` configured for either code or web analysis.

    Raises:
        ValueError: If the fully resolved configuration is missing from `initial_context`,
                    no valid source type (code or web) is specified, or if the
                    analysis mode for the specified source type is disabled.
    """
    del _llm_config_placeholder, _cache_config_placeholder
    logger.info("Determining appropriate SourceLens processing flow based on context and config...")

    full_resolved_config: dict[str, Any] = initial_context.get("config", {})
    if not full_resolved_config:
        raise ValueError("Critical: Fully resolved configuration is missing from initial_context['config'].")

    common_cfg_val: Any = full_resolved_config.get("common", {})
    common_cfg: dict[str, Any] = common_cfg_val if isinstance(common_cfg_val, dict) else {}
    common_cache_cfg: CacheConfigDict = common_cfg.get("cache_settings", {})

    is_web_source_specified = bool(
        initial_context.get("crawl_url") or initial_context.get("crawl_sitemap") or initial_context.get("crawl_file")
    )
    is_code_source_specified = bool(initial_context.get("repo_url") or initial_context.get("local_dir"))

    code_analysis_cfg_val: Any = full_resolved_config.get("code_analysis", {})
    code_analysis_cfg: CodeAnalysisConfigDict = code_analysis_cfg_val if isinstance(code_analysis_cfg_val, dict) else {}

    web_analysis_cfg_val: Any = full_resolved_config.get("web_analysis", {})
    web_analysis_cfg: WebAnalysisConfigDict = web_analysis_cfg_val if isinstance(web_analysis_cfg_val, dict) else {}

    if is_web_source_specified:
        if web_analysis_cfg.get("enabled", False):
            logger.info("Web source specified and web_analysis is enabled. Creating web analysis flow.")
            return _create_web_analysis_flow(web_analysis_cfg, common_cache_cfg)
        raise ValueError("Web source input provided, but web_analysis mode is disabled in configuration.")
    elif is_code_source_specified:
        if code_analysis_cfg.get("enabled", False):
            logger.info("Code source specified and code_analysis is enabled. Creating code analysis flow.")
            return _create_code_analysis_flow(code_analysis_cfg, common_cache_cfg)
        raise ValueError("Code source input provided, but code_analysis mode is disabled in configuration.")
    else:
        raise ValueError("No valid source (code or web) specified to determine processing flow.")


# End of src/sourcelens/flow.py
