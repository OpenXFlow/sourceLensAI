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

"""Nodes sub-package for the Code Analysis Flow (FL01_code_analysis).

This package groups all processing nodes (pipeline steps) specifically designed
for analyzing source code and generating tutorial components from it.
"""

# Import all node classes from their respective modules within this sub-package.
# These nodes constitute the building blocks of the code analysis pipeline.

from .n01_fetch_code import FetchCode
from .n02_identify_abstractions import IdentifyAbstractions
from .n03_analyze_relationships import AnalyzeRelationships
from .n04_order_chapters import OrderChapters
from .n05_identify_scenarios import IdentifyScenariosNode
from .n06_generate_diagrams import GenerateDiagramsNode
from .n07_write_chapters import WriteChapters
from .n08_generate_source_index import GenerateSourceIndexNode
from .n09_generate_project_review import GenerateProjectReview
from .n10_combine_tutorial import CombineTutorial

# It's good practice to also consider what to export from index_formatters
# if they were to be used directly outside of GenerateSourceIndexNode,
# but for now, they are primarily internal to it.
# from .index_formatters import format_python_index_from_ast, format_index_from_llm

__all__ = [
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
    # If index_formatters were public, they'd be listed here:
    # "format_python_index_from_ast",
    # "format_index_from_llm",
]

# End of src/FL01_code_analysis/nodes/__init__.py
