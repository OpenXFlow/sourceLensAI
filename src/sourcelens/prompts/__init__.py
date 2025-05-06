# src/sourcelens/prompts/__init__.py

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
