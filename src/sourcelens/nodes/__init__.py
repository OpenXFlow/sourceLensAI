# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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
from .generate_source_index import GenerateSourceIndexNode  # Added import
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
    "GenerateSourceIndexNode",  # Added new node
    "WriteChapters",
    "CombineTutorial",
]

# End of src/sourcelens/nodes/__init__.py
