# src/sourcelens/flow.py

"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using PocketFlow
to generate tutorials from source code, optionally including diagrams.
"""

import logging
from typing import TYPE_CHECKING, Any, TypeAlias

# Use absolute imports for nodes within the sourcelens package
from sourcelens.nodes.analyze import AnalyzeRelationships, IdentifyAbstractions
from sourcelens.nodes.combine import CombineTutorial
from sourcelens.nodes.fetch import FetchCode

# --- Import the new node ---
from sourcelens.nodes.generate_diagrams import GenerateDiagramsNode
from sourcelens.nodes.structure import OrderChapters
from sourcelens.nodes.write import WriteChapters

# Use TYPE_CHECKING block for imports needed only for type hints
if TYPE_CHECKING:
    from pocketflow import Flow

    ConfigDict: TypeAlias = dict[str, Any]

# Type alias defined in main scope
ConfigDict: TypeAlias = dict[str, Any]


def create_tutorial_flow(llm_config: ConfigDict, cache_config: ConfigDict) -> "Flow":
    """Create and configure the codebase tutorial generation flow.

    Instantiates nodes (fetching, analyzing, ordering, diagram generation,
    writing chapters, combining output) and defines their execution order.

    Args:
        llm_config: Processed configuration for the active LLM provider,
                    including retry settings.
        cache_config: Configuration related to LLM response caching.

    Returns:
        An instance of the configured PocketFlow Flow ready for execution.

    Raises:
        ImportError: If the PocketFlow library cannot be imported.

    """
    # --- Node Instantiation ---
    max_retries = llm_config.get("max_retries", 3)
    retry_wait = llm_config.get("retry_wait_seconds", 10)

    # Instantiate nodes, passing retry config to LLM-dependent nodes
    fetch_code = FetchCode()
    identify_abstractions = IdentifyAbstractions(max_retries=max_retries, wait=retry_wait)
    analyze_relationships = AnalyzeRelationships(max_retries=max_retries, wait=retry_wait)
    order_chapters = OrderChapters(max_retries=max_retries, wait=retry_wait)
    # --- Instantiate the new node ---
    generate_diagrams = GenerateDiagramsNode(max_retries=max_retries, wait=retry_wait)
    write_chapters = WriteChapters(max_retries=max_retries, wait=retry_wait)
    combine_tutorial = CombineTutorial(max_retries=max_retries, wait=retry_wait)  # Now calls LLM for flowchart

    # --- Flow Definition ---
    # Define the sequence using the >> operator provided by PocketFlow
    (
        fetch_code
        >> identify_abstractions
        >> analyze_relationships
        >> order_chapters
        >>
        # --- Integrate the new node into the flow ---
        generate_diagrams
        >> write_chapters
        >> combine_tutorial
    )

    # Create the Flow instance
    try:
        from pocketflow import Flow
    except ImportError:
        # Added logger definition for the error case
        logger = logging.getLogger(__name__)
        logger.error("PocketFlow library not found. Flow cannot be created.")
        raise

    # Using type hint assertion for clarity if Flow is available
    flow_instance: Flow = Flow(start=fetch_code)
    return flow_instance


# End of src/sourcelens/flow.py
