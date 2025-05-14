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


"""Handles formatting of prompts for Large Language Models.

This package centralizes all prompt generation logic, organizing prompts
into specific classes based on their purpose (e.g., abstractions,
relationships, chapter writing, diagram generation). It also provides
common data classes used as context for these prompts.

Key exports:
    - AbstractionPrompts: Class for formatting prompts related to identifying
      and analyzing code abstractions and their relationships.
    - ChapterPrompts: Class for formatting prompts related to ordering and
      writing tutorial chapters.
    - DiagramPrompts: Class for formatting prompts related to generating
      various architectural diagrams.
    - ScenarioPrompts: Class for formatting prompts related to identifying
      interaction scenarios.
    - WriteChapterContext: Dataclass for chapter writing context.
    - SequenceDiagramContext: Dataclass for sequence diagram context.
    - Relevant constants for prompt generation.
"""

# Import common dataclasses and constants first
from ._common import (
    CODE_BLOCK_MAX_LINES,
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,  # Re-exporting for convenience if needed by nodes directly
    ChapterMetadata,  # Re-exporting
    RelationshipsDict,  # Re-exporting
    SequenceDiagramContext,
    WriteChapterContext,
)

# Import prompt-generating classes
from .abstraction_prompts import AbstractionPrompts
from .chapter_prompts import ChapterPrompts
from .diagram_prompts import DiagramPrompts
from .scenario_prompts import ScenarioPrompts

__all__ = [
    # Dataclasses
    "WriteChapterContext",
    "SequenceDiagramContext",
    # Type Aliases (can be useful for external type hinting)
    "AbstractionsList",
    "RelationshipsDict",
    "ChapterMetadata",
    # Constants
    "CODE_BLOCK_MAX_LINES",
    "DEFAULT_RELATIONSHIP_LABEL",
    "MAX_FLOWCHART_LABEL_LEN",
    # Prompt Classes
    "AbstractionPrompts",
    "ChapterPrompts",
    "DiagramPrompts",
    "ScenarioPrompts",
]

# End of src/sourcelens/prompts/__init__.py
