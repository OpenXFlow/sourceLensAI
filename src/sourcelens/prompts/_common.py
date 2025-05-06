# src/sourcelens/prompts/_common.py

"""Common dataclasses and constants used across different prompt modules."""

from dataclasses import dataclass, field
from typing import Any, Final, Optional, TypeAlias

# Type Aliases matching those used in nodes for context clarity
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ChapterMetadata: TypeAlias = dict[str, Any]  # keys: num, name, filename, abstraction_index


# --- Constants ---
CODE_BLOCK_MAX_LINES: Final[int] = 20
DEFAULT_RELATIONSHIP_LABEL: Final[str] = "related to"
MAX_FLOWCHART_LABEL_LEN: Final[int] = 30
# MAX_FILES_FOR_STRUCTURE_CONTEXT is used in generate_diagrams.py, keep it there or move here if widely used


# --- Dataclasses for Prompt Context ---


@dataclass(frozen=True)
class WriteChapterContext:
    """Encapsulate all context needed to format the write chapter prompt.

    Attributes:
        project_name: Name of the project being documented.
        chapter_num: The sequential number of this chapter.
        abstraction_name: The core concept/abstraction this chapter covers.
        abstraction_description: A description of the abstraction.
        full_chapter_structure: Markdown formatted list of all chapters.
        previous_context_info: Summaries of previously generated chapters.
        file_context_str: String containing relevant code snippets.
        language: Target language for the tutorial chapter.
        prev_chapter_meta: Metadata of the preceding chapter, if any.
        next_chapter_meta: Metadata of the succeeding chapter, if any.

    """

    project_name: str
    chapter_num: int
    abstraction_name: str
    abstraction_description: str
    full_chapter_structure: str
    previous_context_info: str
    file_context_str: str
    language: str
    prev_chapter_meta: Optional[ChapterMetadata] = None
    next_chapter_meta: Optional[ChapterMetadata] = None


@dataclass(frozen=True)
class SequenceDiagramContext:
    """Encapsulate context needed for sequence diagram generation prompt.

    Attributes:
        project_name: Name of the project.
        scenario_name: The key name identifying the scenario.
        scenario_description: A textual description of the scenario.
        diagram_format: Target diagram format (currently 'mermaid').
        abstractions: List of identified abstractions (for potential future use).
        relationships: Dict of identified relationships (for potential future use).

    """

    project_name: str
    scenario_name: str
    scenario_description: str
    diagram_format: str = "mermaid"
    abstractions: AbstractionsList = field(default_factory=list, repr=False)
    relationships: RelationshipsDict = field(default_factory=dict, repr=False)


# End of src/sourcelens/prompts/_common.py
