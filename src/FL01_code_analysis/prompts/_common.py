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

"""Define common dataclasses and constants SPECIFIC to FL01 Code Analysis prompts.

This module centralizes data structures and constant values that are unique
to the code analysis flow (FL01) and used by its various prompt generation
modules and nodes. General types are imported from `sourcelens.core.common_types`.
"""

from dataclasses import dataclass
from typing import Final, Optional

# Import shared types from the central common_types module
from sourcelens.core.common_types import (
    ChapterMetadata,  # Used by WriteChapterContext
    # SequenceDiagramContext is now imported from common_types by modules needing it
    # CodeAbstractionsList, # No longer needed directly here, SequenceDiagramContext will import it
    # CodeRelationshipsDict, # No longer needed directly here, SequenceDiagramContext will import it
)

# --- Constants specific to Code Analysis Prompts (FL01 only) ---
CODE_BLOCK_MAX_LINES_FOR_CHAPTERS: Final[int] = 20
"""Maximum number of lines for a code block example in generated code chapters."""


# --- Dataclasses for Code Analysis Prompt Contexts (FL01 specific) ---
@dataclass(frozen=True)
class WriteChapterContext:
    """Encapsulate context for the `format_write_chapter_prompt` for code analysis.

    Attributes:
        project_name: Name of the project being documented.
        chapter_num: The sequential number of this chapter.
        abstraction_name: The core concept/abstraction this chapter covers.
        abstraction_description: A description of the abstraction.
        full_chapter_structure: Markdown formatted list of all chapters.
        previous_context_info: Summaries of previously generated chapters.
        file_context_str: String containing relevant code snippets.
        language: Target language for the tutorial chapter.
        prev_chapter_meta: Metadata of the preceding chapter (uses common ChapterMetadata).
        next_chapter_meta: Metadata of the succeeding chapter (uses common ChapterMetadata).
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


# SequenceDiagramContext is now defined in sourcelens.core.common_types
# Modules in FL01 that need SequenceDiagramContext (like n06_generate_diagrams.py
# or prompts/sequence_diagram_prompts.py if it were flow-specific, which it isn't)
# should import it from sourcelens.core.common_types.

__all__ = [
    # Specific constants for FL01
    "CODE_BLOCK_MAX_LINES_FOR_CHAPTERS",
    # Specific dataclasses for FL01 prompt contexts
    "WriteChapterContext",
    # SequenceDiagramContext is no longer defined or re-exported here.
]

# End of src/FL01_code_analysis/prompts/_common.py
