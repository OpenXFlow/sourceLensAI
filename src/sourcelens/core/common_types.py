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

"""Define common TypeAliases and constants for data structures used across SourceLens.

This module centralizes fundamental data type definitions and constants
to ensure consistency, reduce redundancy, and help prevent circular imports
across different flows and nodes.
"""

from dataclasses import dataclass, field
from typing import Any, Final, Optional, Union  # Keep Type for now for Optional[Type[Any]]

from typing_extensions import TypeAlias

# --- General Purpose ---
SharedContextDict: TypeAlias = dict[str, Any]
"""The main shared context dictionary passed between nodes."""

ConfigDict: TypeAlias = dict[str, Any]
"""A generic type for configuration dictionaries."""

LlmConfigDict: TypeAlias = dict[str, Any]
"""Configuration dictionary for LLM providers."""

CacheConfigDict: TypeAlias = dict[str, Any]
"""Configuration dictionary for LLM caching."""

# --- Code Analysis Flow (FL01) Specific Data Structures & Constants ---
CodeAbstractionItem: TypeAlias = dict[str, Union[str, list[int], None]]
"""Represents a single code abstraction identified by FL01.

   Expected keys:
       'name' (str): The name of the abstraction.
       'description' (str): A textual description of the abstraction.
       'files' (list[int]): A list of integer indices referring to a list of
                            project files relevant to this abstraction.
"""
CodeAbstractionsList: TypeAlias = list[CodeAbstractionItem]
"""A list of code abstractions from FL01."""

CodeRelationshipDetailItem: TypeAlias = dict[str, Union[int, str]]
"""Represents a single relationship between code abstractions in FL01.

   Expected keys:
       'from' (int): Index of the source abstraction in `CodeAbstractionsList`.
       'to' (int): Index of the target abstraction in `CodeAbstractionsList`.
       'label' (str): A descriptive label for the relationship.
"""
CodeRelationshipsDict: TypeAlias = dict[str, Union[str, list[CodeRelationshipDetailItem]]]
"""Contains relationship summary and details for FL01.

   Expected keys:
       'overall_summary' (str): A textual summary of all relationships.
       'details' (list[CodeRelationshipDetailItem]): A list of specific relationships.
"""

ChapterMetadata: TypeAlias = dict[str, Any]
"""Metadata for a code analysis (FL01) chapter.

   Expected keys:
       'num' (int): The sequential number of the chapter.
       'name' (str): The title of the chapter.
       'filename' (str): The generated filename for the chapter.
       'abstraction_index' (int): The index of the primary code abstraction
                                  this chapter is based on (from `CodeAbstractionsList`).
"""

DEFAULT_CODE_RELATIONSHIP_LABEL: Final[str] = "interacts with"
"""Default label for a relationship between code abstractions if not specified by the LLM."""

MAX_CODE_FLOWCHART_LABEL_LEN: Final[int] = 35
"""Maximum character length for labels on relationship flowchart diagram edges for code analysis."""


# --- Web Content Analysis Flow (FL02) Specific Data Structures & Constants ---
WebContentChunk: TypeAlias = dict[str, Any]
"""Represents a segmented chunk of web content from FL02.

   Expected keys:
       'chunk_id' (str): A unique identifier for the chunk.
       'source_filepath' (str): The original relative path of the crawled document
                                from which this chunk originates.
       'title' (str): The title of the chunk (e.g., from a heading or document title).
       'content' (str): The textual content of the chunk.
       'char_count' (int): The character count of the chunk's content.
   Optional keys:
       'heading_level' (int): The Markdown heading level this chunk originated from, if applicable.
"""
WebContentChunkList: TypeAlias = list[WebContentChunk]
"""A list of web content chunks from FL02."""

WebContentConceptItem: TypeAlias = dict[str, Union[str, list[str]]]
"""Represents a single identified web concept from FL02.

   Expected keys:
       'name' (str): The name of the concept.
       'summary' (str): A textual summary of the concept.
       'source_chunk_ids' (list[str]): A list of `chunk_id` strings from
                                       `WebContentChunkList` relevant to this concept.
"""
WebContentConceptsList: TypeAlias = list[WebContentConceptItem]
"""A list of web content concepts from FL02."""

WebContentRelationshipDetailItem: TypeAlias = dict[str, Union[int, str]]
"""Represents a single relationship between web concepts in FL02.

   Expected keys:
       'from_concept_index' (int): Index of the source concept in `WebContentConceptsList`.
       'to_concept_index' (int): Index of the target concept in `WebContentConceptsList`.
       'label' (str): A descriptive label for the relationship.
"""
WebContentRelationshipDetail: TypeAlias = WebContentRelationshipDetailItem
"""Alias for WebContentRelationshipDetailItem for broader compatibility if used elsewhere."""

WebContentRelationshipsDict: TypeAlias = dict[str, Union[str, list[WebContentRelationshipDetailItem]]]
"""Contains relationship summary and details for web concepts in FL02.

   Expected keys:
       'overall_summary' (str): A textual summary of all web concept relationships.
       'relationships' (list[WebContentRelationshipDetailItem]): A list of specific relationships.
"""

WebChapterMetadata: TypeAlias = dict[str, Any]
"""Metadata for a web content (FL02) chapter.

   Expected keys:
       'num' (int): The sequential number of the chapter.
       'name' (str): The title of the chapter.
       'filename' (str): The generated filename for the chapter.
       'concept_index' (int): The index of the primary web concept
                              this chapter is based on (from `WebContentConceptsList`).
"""

# --- General File/Data Handling ---
FilePathContentTuple: TypeAlias = tuple[str, str]
"""A tuple representing (filepath_string, content_string)."""

FilePathContentList: TypeAlias = list[FilePathContentTuple]
"""A list of (filepath_string, content_string) tuples."""

OptionalFilePathContentTuple: TypeAlias = tuple[str, Optional[str]]
"""A tuple representing (filepath_string, content_string_or_None)."""

OptionalFilePathContentList: TypeAlias = list[OptionalFilePathContentTuple]
"""A list of (filepath_string, content_string_or_None) tuples."""


# --- Context Objects for Prompts (Potentially Shared) ---
@dataclass(frozen=True)
class SequenceDiagramContext:
    """Encapsulate context for sequence diagram generation prompts.

    This context is primarily used for generating sequence diagrams based on
    code analysis abstractions and relationships, but could be generalized
    if web content analysis also requires similar sequence diagrams.

    Attributes:
        project_name: Name of the project or content collection.
        scenario_name: The key name identifying the scenario.
        scenario_description: A textual description of the scenario.
        diagram_format: Target diagram format (e.g., "mermaid").
        abstractions: List of identified abstractions (typically CodeAbstractionsList).
                      This provides the participants for the sequence diagram.
        relationships: Dict of identified relationships (typically CodeRelationshipsDict).
                       This provides context on how participants might interact.
    """

    project_name: str
    scenario_name: str
    scenario_description: str
    diagram_format: str = "mermaid"
    abstractions: CodeAbstractionsList = field(default_factory=list, repr=False)
    relationships: CodeRelationshipsDict = field(default_factory=dict, repr=False)


__all__ = [
    # General
    "SharedContextDict",
    "ConfigDict",
    "LlmConfigDict",
    "CacheConfigDict",
    # Code Analysis (FL01)
    "CodeAbstractionItem",
    "CodeAbstractionsList",
    "CodeRelationshipDetailItem",
    "CodeRelationshipsDict",
    "ChapterMetadata",
    "DEFAULT_CODE_RELATIONSHIP_LABEL",
    "MAX_CODE_FLOWCHART_LABEL_LEN",
    # Web Content (FL02)
    "WebContentChunk",
    "WebContentChunkList",
    "WebContentConceptItem",
    "WebContentConceptsList",
    "WebContentRelationshipDetailItem",
    "WebContentRelationshipDetail",
    "WebContentRelationshipsDict",
    "WebChapterMetadata",
    # File/Data Handling
    "FilePathContentTuple",
    "FilePathContentList",
    "OptionalFilePathContentTuple",
    "OptionalFilePathContentList",
    # Shared Prompt Contexts
    "SequenceDiagramContext",
]

# End of src/sourcelens/core/common_types.py
