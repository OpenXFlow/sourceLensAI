# src/sourcelens/flow.py

"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using a flow execution library
(like PocketFlow) to generate tutorials from source code. Includes dynamic scenario
identification for sequence diagrams and optional source code index generation.
"""

import logging
from typing import TYPE_CHECKING, Any, TypeAlias

# Use absolute imports for nodes within the sourcelens package
from sourcelens.nodes.analyze import AnalyzeRelationships, IdentifyAbstractions
from sourcelens.nodes.combine import CombineTutorial
from sourcelens.nodes.fetch import FetchCode
from sourcelens.nodes.generate_diagrams import GenerateDiagramsNode

# --- Import the new node ---
from sourcelens.nodes.generate_source_index import GenerateSourceIndexNode
from sourcelens.nodes.identify_scenarios import IdentifyScenariosNode
from sourcelens.nodes.structure import OrderChapters
from sourcelens.nodes.write import WriteChapters

# Use TYPE_CHECKING block for imports needed only for type hints
if TYPE_CHECKING:
    try:
        from pocketflow import Flow  # type: ignore[import-untyped] # PGH003 for untyped 3rd party
    except ImportError:
        Flow = Any  # type: ignore[misc, assignment]

# Type alias for Configuration Dictionary
ConfigDict: TypeAlias = dict[str, Any]

logger = logging.getLogger(__name__)


def create_tutorial_flow(llm_config: ConfigDict, cache_config: ConfigDict) -> "Flow":
    """Create and configure the SourceLens tutorial generation flow.

    Instantiates all processing nodes (fetching, analyzing, ordering, scenario
    identification, diagram generation, writing chapters, source index generation,
    combining output), passing necessary configurations. Defines the execution
    sequence of these nodes.

    Args:
        llm_config: Processed configuration dictionary for the active LLM provider.
        cache_config: Configuration dictionary related to LLM response caching.

    Returns:
        An instance of the configured Flow (e.g., `pocketflow.Flow`) ready for execution.

    Raises:
        ImportError: If the required flow execution library (e.g., PocketFlow)
                     cannot be imported.

    """
    logger.info("Creating tutorial generation flow...")

    # --- Node Instantiation ---
    max_retries_llm = llm_config.get("max_retries", 3)
    retry_wait_llm = llm_config.get("retry_wait_seconds", 10)
    logger.info("Initializing LLM-based nodes with max_retries=%d, retry_wait=%d", max_retries_llm, retry_wait_llm)

    # Instantiate nodes
    fetch_code = FetchCode()  # No LLM retries needed for its core logic
    identify_abstractions = IdentifyAbstractions(max_retries=max_retries_llm, wait=retry_wait_llm)
    analyze_relationships = AnalyzeRelationships(max_retries=max_retries_llm, wait=retry_wait_llm)
    order_chapters = OrderChapters(max_retries=max_retries_llm, wait=retry_wait_llm)
    identify_scenarios = IdentifyScenariosNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    generate_diagrams = GenerateDiagramsNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    write_chapters = WriteChapters(max_retries=max_retries_llm, wait=retry_wait_llm)

    # GenerateSourceIndexNode does not call LLM, so retries are for potential
    # internal errors if any were to be handled by PocketFlow's retry mechanism.
    # Setting max_retries to 1 ensures its exec() method is called once.
    generate_source_index = GenerateSourceIndexNode(max_retries=1, wait=0)
    logger.info("Initialized GenerateSourceIndexNode with max_retries=1, wait=0 to ensure exec call.")

    combine_tutorial = CombineTutorial()  # No LLM retries needed for its core logic

    # --- Flow Definition ---
    # Fetch -> Identify Abstractions -> Analyze Relationships -> Order Chapters
    # -> Identify Scenarios -> Generate Diagrams -> Write Chapters
    # -> Generate Source Index -> Combine
    (
        fetch_code
        >> identify_abstractions
        >> analyze_relationships
        >> order_chapters
        >> identify_scenarios
        >> generate_diagrams
        >> write_chapters
        # --- Add new node before combine ---
        >> generate_source_index
        >> combine_tutorial
    )
    logger.info(
        "Flow sequence defined: Fetch -> IdentifyAbs -> AnalyzeRel -> OrderChap -> "
        "IdentifyScen -> GenDiag -> WriteChap -> GenSourceIndex -> Combine"
    )

    # --- Flow Creation ---
    try:
        # Replace 'pocketflow' if using a different library
        from pocketflow import Flow as PocketFlowRunner  # Alias to avoid confusion
    except ImportError as e:
        logger.error("Flow execution library (e.g., PocketFlow) not found. Cannot create flow.")
        raise ImportError("PocketFlow library is required to create the execution flow.") from e

    flow_instance: PocketFlowRunner = PocketFlowRunner(start=fetch_code)
    logger.info("Flow instance created successfully.")

    return flow_instance


# End of src/sourcelens/flow.py
