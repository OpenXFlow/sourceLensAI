# src/sourcelens/flow.py

"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using a flow execution library
(like PocketFlow) to generate tutorials from source code. Includes dynamic scenario
identification for sequence diagrams.
"""

import logging
from typing import TYPE_CHECKING, Any, TypeAlias

# Use absolute imports for nodes within the sourcelens package
from sourcelens.nodes.analyze import AnalyzeRelationships, IdentifyAbstractions
from sourcelens.nodes.combine import CombineTutorial
from sourcelens.nodes.fetch import FetchCode
from sourcelens.nodes.generate_diagrams import GenerateDiagramsNode

# --- Import the new node ---
from sourcelens.nodes.identify_scenarios import IdentifyScenariosNode
from sourcelens.nodes.structure import OrderChapters
from sourcelens.nodes.write import WriteChapters

# Use TYPE_CHECKING block for imports needed only for type hints
# Replace 'pocketflow.Flow' with your actual flow execution library if different
if TYPE_CHECKING:
    try:
        from pocketflow import Flow
    except ImportError:
        Flow = Any  # type: ignore[misc, assignment]

# Type alias for Configuration Dictionary
ConfigDict: TypeAlias = dict[str, Any]

logger = logging.getLogger(__name__)


def create_tutorial_flow(llm_config: ConfigDict, cache_config: ConfigDict) -> "Flow":
    """Create and configure the SourceLens tutorial generation flow.

    Instantiates all processing nodes (fetching, analyzing, ordering, scenario
    identification, diagram generation, writing chapters, combining output),
    passing necessary configurations. Defines the execution sequence of these nodes.

    Args:
        llm_config: Processed configuration dictionary for the active LLM provider.
        cache_config: Configuration dictionary related to LLM response caching.

    Returns:
        An instance of the configured Flow (e.g., `pocketflow.Flow`) ready for execution.

    Raises:
        ImportError: If the required flow execution library (e.g., PocketFlow)
                     cannot be imported.

    """
    logger.info("Creating tutorial generation flow with dynamic scenario identification...")

    # --- Node Instantiation ---
    max_retries = llm_config.get("max_retries", 3)
    retry_wait = llm_config.get("retry_wait_seconds", 10)
    logger.debug("Initializing LLM nodes with max_retries=%d, retry_wait=%d", max_retries, retry_wait)

    # Instantiate nodes
    fetch_code = FetchCode()
    identify_abstractions = IdentifyAbstractions(max_retries=max_retries, wait=retry_wait)
    analyze_relationships = AnalyzeRelationships(max_retries=max_retries, wait=retry_wait)
    order_chapters = OrderChapters(max_retries=max_retries, wait=retry_wait)
    # --- Instantiate the new node ---
    identify_scenarios = IdentifyScenariosNode(max_retries=max_retries, wait=retry_wait)
    generate_diagrams = GenerateDiagramsNode(max_retries=max_retries, wait=retry_wait)
    write_chapters = WriteChapters(max_retries=max_retries, wait=retry_wait)
    combine_tutorial = CombineTutorial()

    # --- Flow Definition ---
    # Fetch -> Identify Abstractions -> Analyze Relationships -> Order Chapters
    # -> Identify Scenarios -> Generate Diagrams -> Write Chapters -> Combine
    (
        fetch_code
        >> identify_abstractions
        >> analyze_relationships
        >> order_chapters
        # --- Add new node to identify scenarios before generating diagrams ---
        >> identify_scenarios
        >> generate_diagrams  # GenerateDiagramsNode now uses identified scenarios
        >> write_chapters
        >> combine_tutorial
    )
    logger.info(
        "Flow sequence defined: Fetch -> IdentifyAbs -> AnalyzeRel -> OrderChap -> IdentifyScen -> GenDiag -> WriteChap -> Combine"
    )

    # --- Flow Creation ---
    try:
        # Replace 'pocketflow' if using a different library
        from pocketflow import Flow
    except ImportError as e:
        logger.error("Flow execution library (e.g., PocketFlow) not found. Cannot create flow.")
        raise ImportError("PocketFlow library is required to create the execution flow.") from e

    flow_instance: Flow = Flow(start=fetch_code)
    logger.info("Flow instance created successfully.")

    return flow_instance


# End of src/sourcelens/flow.py
