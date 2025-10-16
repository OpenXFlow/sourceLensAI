# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Defines the main processing flow for Code Analysis.

This module is responsible for instantiating and connecting the various
processing nodes using the SourceLens flow engine to generate tutorials
from source code.
"""

import logging
from typing import Any

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode
from sourcelens.core import Flow as SourceLensFlow

from .nodes import (
    AnalyzeRelationships,
    CombineTutorial,
    FetchCode,
    GenerateDiagramsNode,
    GenerateProjectReview,
    GenerateSourceIndexNode,
    IdentifyAbstractions,
    IdentifyScenariosNode,
    OrderChapters,
    WriteChapters,
)

LlmConfigDict: TypeAlias = dict[str, Any]
SharedContextDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)


def _configure_llm_node_params_for_code_flow(llm_config: LlmConfigDict) -> tuple[int, int]:  # Renamed function
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


def create_code_analysis_flow(initial_context: SharedContextDict) -> SourceLensFlow:  # Renamed function
    """Create and configure the flow for code analysis and tutorial generation.

    Args:
        initial_context: The initial shared context dictionary.

    Returns:
        An instance of `SourceLensFlow` for code analysis.
    """
    logger.info("Configuring flow for FL01_code_analysis.")

    llm_config_for_flow: LlmConfigDict = initial_context.get("llm_config", {})
    if not llm_config_for_flow:
        logger.warning(
            "LLM configuration not found in initial_context['llm_config'] for code analysis flow. "
            "LLM-based nodes might use default retry/wait values or fail."
        )
        llm_config_for_flow = {}

    max_r_llm, r_wait_llm = _configure_llm_node_params_for_code_flow(llm_config_for_flow)  # Use renamed helper
    logger.info(
        "Initializing LLM-based nodes in code analysis flow with max_retries=%d, retry_wait=%d",
        max_r_llm,
        r_wait_llm,
    )

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

    start_node: BaseNode = fetch_code
    (
        start_node
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
    flow_description_parts: list[str] = [
        type(n).__name__
        for n in [
            fetch_code,
            id_abstr,
            an_rels,
            ord_chaps,
            id_scens,
            gen_diags,
            wr_chaps,
            gen_src_idx,
            gen_proj_rev,
            comb_tut,
        ]
    ]
    logger.info("FL01_code_analysis flow sequence: %s", " -> ".join(flow_description_parts))

    return SourceLensFlow(start=start_node)


# End of src/FL01_code_analysis/flow.py
