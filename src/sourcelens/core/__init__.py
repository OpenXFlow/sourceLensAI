# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.


"""Core Package for SourceLens flow execution engine and base node definitions.

This package contains the fundamental components for defining and running
workflows (Flows) composed of individual processing steps (Nodes).
It provides both synchronous and asynchronous versions of flow engine components,
and the base classes that all SourceLens processing nodes should inherit from.
It also centralizes common type definitions used across the application.
"""

# Import application-specific base node classes and type aliases first.
# These are intended to be the primary base classes for concrete nodes.
from .base_node import (
    BaseBatchNode,
    BaseNode,
    SLBatchItem,
    SLBatchItemExecutionResult,
    SLExecutionResult,
    SLPreparedInputs,
    SLSharedContext,
)

# Import common_types which are used across various modules including core.
from .common_types import (
    CacheConfigDict,
    ChapterMetadata,
    CodeAbstractionItem,
    CodeAbstractionsList,
    CodeRelationshipDetailItem,
    CodeRelationshipsDict,
    ConfigDict,
    FilePathContentList,
    FilePathContentTuple,
    LlmConfigDict,
    OptionalFilePathContentList,
    OptionalFilePathContentTuple,
    SequenceDiagramContext,
    SharedContextDict,  # Re-exporting from common_types for convenience if used directly from core
    WebChapterMetadata,
    WebContentChunk,
    WebContentChunkList,
    WebContentConceptItem,
    WebContentConceptsList,
    WebContentRelationshipDetail,
    WebContentRelationshipDetailItem,
    WebContentRelationshipsDict,
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
    BatchNode as CoreBatchNode,  # Parent of our application's BaseBatchNode
)

__all__ = [
    # Application-specific base nodes and types (from base_node.py)
    "BaseNode",
    "BaseBatchNode",
    "SLSharedContext",
    "SLPreparedInputs",
    "SLExecutionResult",
    "SLBatchItem",
    "SLBatchItemExecutionResult",
    # Core Node/BatchNode from flow_engine_sync (parents of our BaseNode/BaseBatchNode)
    "Node",  # The very base node from which sourcelens.core.BaseNode inherits
    "CoreBatchNode",  # The very base batch node
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
    # Common Type Aliases from common_types.py
    "SharedContextDict",  # Also SLSharedContext, but SharedContextDict is more generic
    "ConfigDict",
    "LlmConfigDict",
    "CacheConfigDict",
    "CodeAbstractionItem",
    "CodeAbstractionsList",
    "CodeRelationshipDetailItem",
    "CodeRelationshipsDict",
    "ChapterMetadata",
    "WebContentChunk",
    "WebContentChunkList",
    "WebContentConceptItem",
    "WebContentConceptsList",
    "WebContentRelationshipDetailItem",
    "WebContentRelationshipDetail",
    "WebContentRelationshipsDict",
    "WebChapterMetadata",
    "FilePathContentTuple",
    "FilePathContentList",
    "OptionalFilePathContentTuple",
    "OptionalFilePathContentList",
    "SequenceDiagramContext",
]

# End of src/sourcelens/core/__init__.py
