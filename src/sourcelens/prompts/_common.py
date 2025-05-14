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


"""Common dataclasses and constants used across different prompt modules."""

from dataclasses import dataclass, field
from typing import Any, Final, Optional  # TypeAlias odstránený z typing

from typing_extensions import TypeAlias  # Použitie typing_extensions

# Type Aliases matching those used in nodes for context clarity
# Používame moderné typy (list namiesto List)
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]  # Spresníme neskôr, ak bude treba
ChapterMetadata: TypeAlias = dict[str, Any]  # keys: num, name, filename, abstraction_index


# --- Constants ---
CODE_BLOCK_MAX_LINES: Final[int] = 20
DEFAULT_RELATIONSHIP_LABEL: Final[str] = "related to"
MAX_FLOWCHART_LABEL_LEN: Final[int] = 30


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
    # repr=False pre veľké štruktúry, aby neboli v logoch priamo z dataclass repr
    abstractions: AbstractionsList = field(default_factory=list, repr=False)
    relationships: RelationshipsDict = field(default_factory=dict, repr=False)


# End of src/sourcelens/prompts/_common.py
