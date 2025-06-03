# Copyright (C) 2025 Jozef Darida
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


"""Core Package for SourceLens flow execution engine and base node definitions.

This package contains the fundamental components for defining and running
workflows (Flows) composed of individual processing steps (Nodes).
It provides both synchronous and asynchronous versions of flow engine components,
and the base classes that all SourceLens processing nodes should inherit from.
"""

# Import application-specific base node classes and type aliases first.
# These are intended to be the primary base classes for concrete nodes.
from .base_node import (
    BaseBatchNode,  # This will be the primary BaseBatchNode for application nodes
    BaseNode,  # This will be the primary BaseNode for application nodes
    SLBatchItem,
    SLBatchItemExecutionResult,
    SLExecutionResult,
    SLPreparedInputs,
    SLSharedContext,
)

# The original BaseNode from flow_engine_sync.py is implicitly available
# within this package for flow_engine_sync.Flow etc. to use, but not exported by default.
# Import asynchronous flow engine components
from .flow_engine_async import (
    AsyncBatchFlow,
    AsyncBatchNode,
    AsyncFlow,
    AsyncNode,
    AsyncParallelBatchFlow,
    AsyncParallelBatchNode,
)

# Import synchronous flow engine components
# Note: flow_engine_sync.BaseNode is a different, more primitive base.
# We are prioritizing the BaseNode from .base_node for direct use in applications.
from .flow_engine_sync import (
    BatchFlow,
    Flow,
    Node,  # Parent of our application's BaseNode
)
from .flow_engine_sync import (
    BatchNode as CoreBatchNode,  # Parent of our application's BaseBatchNode, aliased to avoid confusion
    # if 'BatchNode' was also a name used in application directly.
    # If only BaseBatchNode is used, this alias is less critical.
)

__all__ = [
    # Application-specific base nodes and types (from base_node.py)
    "BaseNode",  # Exporting the application-facing BaseNode
    "BaseBatchNode",  # Exporting the application-facing BaseBatchNode
    "SLSharedContext",
    "SLPreparedInputs",
    "SLExecutionResult",
    "SLBatchItem",
    "SLBatchItemExecutionResult",
    # Core Node/BatchNode from flow_engine_sync (parents of our BaseNode/BaseBatchNode)
    "Node",
    "CoreBatchNode",  # Exporting the aliased parent of BaseBatchNode
    # Synchronous flow engine orchestration components (from flow_engine_sync.py)
    "Flow",
    "BatchFlow",
    # Asynchronous flow engine components (from flow_engine_async.py)
    "AsyncNode",
    "AsyncBatchNode",
    "AsyncParallelBatchNode",
    "AsyncFlow",
    "AsyncBatchFlow",
    "AsyncParallelBatchFlow",
]

# End of src/sourcelens/core/__init__.py
