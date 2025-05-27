# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
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

"""Nodes Package for SourceLens Processing Flow.

This package contains the modular processing steps (Nodes) used in the
SourceLens application. It is organized into sub-packages:
- `code`: Nodes for source code analysis and tutorial generation.
- `web`: Nodes for web content fetching and analysis.

The actual base classes (BaseNode, BaseBatchNode) and common type aliases
(SLSharedContext, etc.) are defined in `sourcelens.nodes.base_node` and should
be imported directly from there by individual node implementations.
This __init__.py re-exports them for convenience.
"""

# Import and re-export base classes and common type aliases directly
# This makes them available as sourcelens.nodes.BaseNode etc.
from .base_node import (
    BaseBatchNode as BaseBatchNode,  # Explicit re-export alias
)
from .base_node import (
    BaseNode as BaseNode,  # Explicit re-export alias
)
from .base_node import (
    SLBatchItem as SLBatchItem,
)
from .base_node import (
    SLBatchItemExecutionResult as SLBatchItemExecutionResult,
)
from .base_node import (
    SLExecutionResult as SLExecutionResult,
)
from .base_node import (
    SLPreparedInputs as SLPreparedInputs,
)
from .base_node import (
    SLSharedContext as SLSharedContext,  # Explicit re-export alias
)

# Import and re-export all public symbols from the 'code' sub-package
# This relies on .code.__init__.py having a correctly defined __all__
from .code import *  # noqa: F403

# Import and re-export all public symbols from the 'web' sub-package
# This relies on .web.__init__.py having a correctly defined __all__
from .web import *  # noqa: F403

# Define __all__ for this top-level nodes package.
# It should include the base node classes/types and all re-exported nodes
# from the sub-packages.

_base_exports: list[str] = [
    "BaseNode",
    "BaseBatchNode",
    "SLSharedContext",
    "SLPreparedInputs",
    "SLExecutionResult",
    "SLBatchItem",
    "SLBatchItemExecutionResult",
]

# These lists should ideally mirror the __all__ lists in the respective
# sub-package __init__.py files for clarity, though '*' import handles it.
_code_node_exports: list[str] = [
    "FetchCode",
    "IdentifyAbstractions",
    "AnalyzeRelationships",
    "OrderChapters",
    "IdentifyScenariosNode",
    "GenerateDiagramsNode",
    "WriteChapters",
    "GenerateSourceIndexNode",
    "GenerateProjectReview",
    "CombineTutorial",
]

_web_node_exports: list[str] = [
    "FetchWebPage",
    "IdentifyWebConcepts",
    "AnalyzeWebRelationships",
    "OrderWebChapters",
    "WriteWebChapters",
    "GenerateWebInventory",
    "GenerateWebReview",
    "CombineWebSummary",
]

__all__ = _base_exports + _code_node_exports + _web_node_exports

# End of src/sourcelens/nodes/__init__.py
