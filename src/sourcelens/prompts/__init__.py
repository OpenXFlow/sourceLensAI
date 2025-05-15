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
into specific classes or modules based on their purpose (e.g., abstractions,
relationships, chapter writing, diagram generation, source index). It also provides
common data classes used as context for these prompts.

Key exports:
    - AbstractionPrompts: Class for formatting prompts related to identifying
      and analyzing code abstractions and their relationships.
    - ChapterPrompts: Class for formatting prompts related to ordering and
      writing tutorial chapters.
    - ScenarioPrompts: Class for formatting prompts related to identifying
      interaction scenarios.
    - SourceIndexPrompts: Class for formatting prompts related to LLM-based
      source code analysis for indexing.
    - Individual diagram prompt formatters from the `diagrams` sub-package.
    - WriteChapterContext: Dataclass for chapter writing context.
    - SequenceDiagramContext: Dataclass for sequence diagram context.
    - Relevant constants for prompt generation.
"""

# Import common dataclasses and constants first
from sourcelens.prompts._common import (
    CODE_BLOCK_MAX_LINES,
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,
    ChapterMetadata,
    RelationshipsDict,
    SequenceDiagramContext,
    WriteChapterContext,
)

# Import prompt-generating classes/modules
from sourcelens.prompts.abstraction_prompts import AbstractionPrompts
from sourcelens.prompts.chapter_prompts import ChapterPrompts
from sourcelens.prompts.diagrams import (
    INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT,  # Added this as it's exported by diagrams/__init__
    format_class_diagram_prompt,
    format_package_diagram_prompt,
    format_relationship_flowchart_prompt,
    format_sequence_diagram_prompt,
    generate_file_structure_mermaid,  # Added this as it's exported by diagrams/__init__
)
from sourcelens.prompts.scenario_prompts import ScenarioPrompts
from sourcelens.prompts.source_index_prompts import SourceIndexPrompts

__all__: list[str] = [
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
    "INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT",  # Added to __all__
    # Prompt Classes/Functions
    "AbstractionPrompts",
    "ChapterPrompts",
    "ScenarioPrompts",
    "SourceIndexPrompts",  # Added to __all__
    "format_class_diagram_prompt",
    "format_package_diagram_prompt",
    "format_relationship_flowchart_prompt",
    "format_sequence_diagram_prompt",
    "generate_file_structure_mermaid",  # Added to __all__
]

# End of src/sourcelens/prompts/__init__.py
