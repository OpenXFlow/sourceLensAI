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

"""Initialize the code analysis prompts sub-package.

This package groups all prompt generation logic specifically tailored for
analyzing source code. It also re-exports common data types and constants
used within these code-specific prompts.
"""

# Import common data types and constants used by code prompts
from ._common import (
    CODE_BLOCK_MAX_LINES,
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,
    ChapterMetadata,
    RelationshipsDict,
    SequenceDiagramContext,
    WriteChapterContext,
)

# Import code-specific prompt generating classes
from .abstraction_prompts import AbstractionPrompts
from .chapter_prompts import ChapterPrompts

# Import and re-export everything from the diagrams sub-package
from .diagrams import (
    INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT,
    format_class_diagram_prompt,
    format_package_diagram_prompt,
    format_relationship_flowchart_prompt,
    format_sequence_diagram_prompt,
    generate_file_structure_mermaid,
)
from .project_review_prompts import ProjectReviewPrompts
from .scenario_prompts import ScenarioPrompts
from .source_index_prompts import SourceIndexPrompts

# Define __all__ to explicitly list all symbols to be exported from this sub-package.
# This makes the imported symbols "used" from Ruff's perspective when this
# sub-package is imported elsewhere (e.g., via 'from .code import *').
__all__: list[str] = [
    # From ._common
    "CODE_BLOCK_MAX_LINES",
    "DEFAULT_RELATIONSHIP_LABEL",
    "MAX_FLOWCHART_LABEL_LEN",
    "AbstractionsList",
    "ChapterMetadata",
    "RelationshipsDict",
    "SequenceDiagramContext",
    "WriteChapterContext",
    # Prompt classes
    "AbstractionPrompts",
    "ChapterPrompts",
    "ProjectReviewPrompts",
    "ScenarioPrompts",
    "SourceIndexPrompts",
    # From .diagrams
    "INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT",
    "format_class_diagram_prompt",
    "format_package_diagram_prompt",
    "format_relationship_flowchart_prompt",
    "format_sequence_diagram_prompt",
    "generate_file_structure_mermaid",
]

# End of src/sourcelens/prompts/code/__init__.py
