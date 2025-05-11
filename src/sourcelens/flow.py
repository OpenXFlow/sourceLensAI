# src/sourcelens/flow.py

"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using the internal
SourceLens flow engine to generate tutorials from source code. Includes
dynamic scenario identification for sequence diagrams and optional source
code index generation.
"""

import logging
from typing import Any, TypeAlias

# Import Flow class from the integrated flow engine
from sourcelens.core.flow_engine import Flow as SourceLensFlow

# Use absolute imports for nodes within the sourcelens package
from sourcelens.nodes.analyze import AnalyzeRelationships, IdentifyAbstractions
from sourcelens.nodes.combine import CombineTutorial
from sourcelens.nodes.fetch import FetchCode
from sourcelens.nodes.generate_diagrams import GenerateDiagramsNode
from sourcelens.nodes.generate_source_index import GenerateSourceIndexNode
from sourcelens.nodes.identify_scenarios import IdentifyScenariosNode
from sourcelens.nodes.structure import OrderChapters
from sourcelens.nodes.write import WriteChapters

# Type alias for Configuration Dictionary
ConfigDict: TypeAlias = dict[str, Any]

logger = logging.getLogger(__name__)


def create_tutorial_flow(llm_config: ConfigDict, cache_config: ConfigDict) -> SourceLensFlow:  # Return type changed
    """Create and configure the SourceLens tutorial generation flow.

    Instantiates all processing nodes (fetching, analyzing, ordering, scenario
    identification, diagram generation, writing chapters, source index generation,
    combining output), passing necessary configurations. Defines the execution
    sequence of these nodes using the internal SourceLens flow engine.

    Args:
        llm_config: Processed configuration dictionary for the active LLM provider.
        cache_config: Configuration dictionary related to LLM response caching.

    Returns:
        An instance of the configured `SourceLensFlow` ready for execution.

    Raises:
        ImportError: If a required node cannot be imported (though this is less
                     likely with direct imports from the package).

    """
    logger.info("Creating tutorial generation flow...")

    # --- Node Instantiation ---
    max_retries_llm = llm_config.get("max_retries", 3)
    retry_wait_llm = llm_config.get("retry_wait_seconds", 10)
    logger.info("Initializing LLM-based nodes with max_retries=%d, retry_wait=%d", max_retries_llm, retry_wait_llm)

    # Instantiate nodes (Node classes are already based on flow_engine.Node via BaseNode)
    fetch_code = FetchCode()
    identify_abstractions = IdentifyAbstractions(max_retries=max_retries_llm, wait=retry_wait_llm)
    analyze_relationships = AnalyzeRelationships(max_retries=max_retries_llm, wait=retry_wait_llm)
    order_chapters = OrderChapters(max_retries=max_retries_llm, wait=retry_wait_llm)
    identify_scenarios = IdentifyScenariosNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    generate_diagrams = GenerateDiagramsNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    write_chapters = WriteChapters(max_retries=max_retries_llm, wait=retry_wait_llm)
    generate_source_index = GenerateSourceIndexNode(max_retries=1, wait=0)
    logger.info("Initialized GenerateSourceIndexNode with max_retries=1, wait=0.")  # Simpler log
    combine_tutorial = CombineTutorial()

    # --- Flow Definition ---
    # Nodes are chained using the `>>` operator defined in flow_engine.BaseNode
    (
        fetch_code
        >> identify_abstractions
        >> analyze_relationships
        >> order_chapters
        >> identify_scenarios
        >> generate_diagrams
        >> write_chapters
        >> generate_source_index
        >> combine_tutorial
    )
    logger.info(
        "Flow sequence defined: Fetch -> IdentifyAbs -> AnalyzeRel -> OrderChap -> "
        "IdentifyScen -> GenDiag -> WriteChap -> GenSourceIndex -> Combine"
    )

    # --- Flow Creation ---
    # Use the imported SourceLensFlow
    flow_instance: SourceLensFlow = SourceLensFlow(start=fetch_code)
    logger.info("Flow instance created successfully using SourceLensFlow.")

    return flow_instance


# End of src/sourcelens/flow.py
