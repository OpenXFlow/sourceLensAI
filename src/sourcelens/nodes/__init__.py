# src/sourcelens/nodes/__init__.py

"""Nodes Package for SourceLens Processing Flow.

This package contains the modular processing steps (Nodes) used in the
SourceLens tutorial generation workflow. Each module typically encapsulates
a distinct stage of the process, such as fetching code, analyzing structure,
identifying scenarios, generating content, or combining outputs.

The nodes are designed to be connected in a sequence using a flow execution
framework (like PocketFlow) to form the complete pipeline.
"""

# Import node classes to make them easily accessible via `from sourcelens.nodes import ...`
from .analyze import AnalyzeRelationships, IdentifyAbstractions
from .base_node import BaseBatchNode, BaseNode  # Base classes for node implementation
from .combine import CombineTutorial
from .fetch import FetchCode
from .generate_diagrams import GenerateDiagramsNode

# --- Import the new node ---
from .identify_scenarios import IdentifyScenariosNode
from .structure import OrderChapters
from .write import WriteChapters

# Define __all__ for explicit public interface of the package
# Controls what `from sourcelens.nodes import *` imports
__all__ = [
    "BaseNode",
    "BaseBatchNode",
    "FetchCode",
    "IdentifyAbstractions",
    "AnalyzeRelationships",
    "OrderChapters",
    "IdentifyScenariosNode",
    "GenerateDiagramsNode",
    "WriteChapters",
    "CombineTutorial",
]

# End of src/sourcelens/nodes/__init__.py
