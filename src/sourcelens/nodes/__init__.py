# src/sourcelens/nodes/__init__.py

"""Nodes Package for SourceLens Flow.

This package contains the different processing steps (Nodes) used in the
tutorial generation workflow. Each module typically groups related nodes
or represents a significant stage in the process.
"""

# Import node classes to make them easily accessible from sourcelens.nodes
from .analyze import AnalyzeRelationships, IdentifyAbstractions
from .base_node import BaseBatchNode, BaseNode
from .combine import CombineTutorial
from .fetch import FetchCode

# --- Import the new node ---
from .generate_diagrams import GenerateDiagramsNode
from .structure import OrderChapters
from .write import WriteChapters

__all__ = [
    "BaseNode",
    "BaseBatchNode",
    "FetchCode",
    "IdentifyAbstractions",
    "AnalyzeRelationships",
    "OrderChapters",
    "WriteChapters",
    "GenerateDiagramsNode",  # --- Add the new node to __all__ ---
    "CombineTutorial",
]

# End of src/sourcelens/nodes/__init__.py
