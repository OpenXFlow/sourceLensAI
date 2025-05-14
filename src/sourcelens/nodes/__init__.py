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
framework to form the complete pipeline.
"""

# Import base classes for node implementation
from .base_node import BaseBatchNode, BaseNode

# Import node classes from their new locations
from .n01_fetch_code import FetchCode
from .n02_identify_abstractions import IdentifyAbstractions
from .n03_analyze_relationships import AnalyzeRelationships
from .n04_order_chapters import OrderChapters
from .n05_identify_scenarios import IdentifyScenariosNode
from .n06_generate_diagrams import GenerateDiagramsNode
from .n07_write_chapters import WriteChapters
from .n08_generate_source_index import GenerateSourceIndexNode
from .n09_combine_tutorial import CombineTutorial

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
    "GenerateSourceIndexNode",
    "WriteChapters",
    "CombineTutorial",
]

# End of src/sourcelens/nodes/__init__.py
