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

"""Initialize the code analysis nodes sub-package.

This package groups all processing nodes specifically designed for
analyzing source code.
"""

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

# Note: index_formatters are typically used internally by GenerateSourceIndexNode,
# so they are not usually part of the public API of this package unless needed elsewhere.
# If they are needed, they should be imported and added to __all__.
# from .index_formatters import format_python_index_from_ast, format_index_from_llm

__all__: list[str] = [
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

# End of src/sourcelens/nodes/code/__init__.py
