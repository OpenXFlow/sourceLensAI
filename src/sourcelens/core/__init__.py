# src/sourcelens/core/__init__.py

"""Core Package for SourceLens flow execution engine.

This package contains the fundamental components for defining and running
workflows (Flows) composed of individual processing steps (Nodes).
It provides both synchronous and asynchronous versions of these components.
The engine is based on a PocketFlow-like architecture.
"""

# Import synchronous components to be part of the public API of 'sourcelens.core'
# Import asynchronous components to be part of the public API of 'sourcelens.core'
from .flow_engine_async import (
    AsyncBatchFlow,
    AsyncBatchNode,
    AsyncFlow,
    AsyncNode,
    AsyncParallelBatchFlow,
    AsyncParallelBatchNode,
)
from .flow_engine_sync import (
    BaseNode,
    BatchFlow,
    BatchNode,
    Flow,
    Node,
    # _ConditionalTransition, # Typically not for public API
)

__all__ = [
    # Synchronous components
    "BaseNode",
    "Node",
    "BatchNode",
    "Flow",
    "BatchFlow",
    # Asynchronous components
    "AsyncNode",
    "AsyncBatchNode",
    "AsyncParallelBatchNode",
    "AsyncFlow",
    "AsyncBatchFlow",
    "AsyncParallelBatchFlow",
]
# Note on _ConditionalTransition: It's an internal mechanism for the '-' operator
# on BaseNode and is not typically instantiated directly by users.
# Thus, it's intentionally omitted from __all__.

# End of src/sourcelens/core/__init__.py
