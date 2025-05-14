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
