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

from sourcelens.core.common_types import ChapterMetadata

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
        source_code_language_name: The name of the source code's language
                                   (e.g., "Python", "MATLAB") for the LLM's role.
        prev_chapter_meta: Metadata of the preceding chapter.
        next_chapter_meta: Metadata of the succeeding chapter.
    """

    project_name: str
    chapter_num: int
    abstraction_name: str
    abstraction_description: str
    full_chapter_structure: str
    previous_context_info: str
    file_context_str: str
    language: str
    source_code_language_name: str
    prev_chapter_meta: Optional[ChapterMetadata] = None
    next_chapter_meta: Optional[ChapterMetadata] = None


__all__ = [
    "CODE_BLOCK_MAX_LINES_FOR_CHAPTERS",
    "WriteChapterContext",
]

# End of src/FL01_code_analysis/prompts/_common.py
