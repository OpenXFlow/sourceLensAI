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

"""Handles formatting of prompts for Large Language Models.

This package centralizes all prompt generation logic, organizing prompts
into specific sub-packages based on their purpose:
- `code`: For analyzing source code, including common context datatypes.
- `web`: For analyzing web content.
"""

# Import and re-export all public symbols from the 'code' sub-package.
# This now includes common context datatypes, diagram formatters, and code-specific prompts.
from .code import *  # noqa: F403

# The __all__ list from .code.__init__.py will control what is imported here.
# Import and re-export all public symbols from the 'web' sub-package.
from .web import *  # noqa: F403

# The __all__ list from .web.__init__.py will control what is imported here.


# Define __all__ for this top-level prompts package.
# It should aggregate all relevant exports from its sub-packages.

# These lists should ideally match the __all__ lists in the respective sub-package __init__.py files
# to ensure consistency and avoid importing unintended symbols with '*'.
# For now, we list them explicitly for clarity at this top level.

_common_exports_from_code: list[str] = [
    "CODE_BLOCK_MAX_LINES",
    "DEFAULT_RELATIONSHIP_LABEL",
    "MAX_FLOWCHART_LABEL_LEN",
    "AbstractionsList",
    "ChapterMetadata",
    "RelationshipsDict",
    "SequenceDiagramContext",
    "WriteChapterContext",
]

_code_prompt_exports: list[str] = [
    "AbstractionPrompts",
    "ChapterPrompts",
    "ProjectReviewPrompts",
    "ScenarioPrompts",
    "SourceIndexPrompts",
    "format_class_diagram_prompt",
    "format_package_diagram_prompt",
    "format_relationship_flowchart_prompt",
    "format_sequence_diagram_prompt",
    "generate_file_structure_mermaid",
    "INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT",
]

_web_prompt_exports: list[str] = [
    "WebConceptPrompts",
    "WebRelationshipPrompts",
    # Add future web prompt classes here as they are defined in web.__all__
]

__all__ = _common_exports_from_code + _code_prompt_exports + _web_prompt_exports

# End of src/sourcelens/prompts/__init__.py
