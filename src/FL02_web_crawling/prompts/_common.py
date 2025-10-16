# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Define common dataclasses and constants SPECIFIC to FL02 Web Crawling prompts.

This module centralizes data structures and constant values that are unique
to the web crawling flow (FL02) and used by its various prompt generation
modules and nodes. General types are imported from `sourcelens.core.common_types`.
"""

from dataclasses import dataclass
from typing import Final, Optional

# Import shared types from the central common_types module
from sourcelens.core.common_types import WebChapterMetadata

# --- Constants specific to Web Crawling Prompts (FL02 only) ---
MAX_SNIPPETS_FOR_WEB_CONCEPT_CONTEXT: Final[int] = 5
"""Max number of chunk snippets to include when identifying web concepts."""


# --- Dataclasses for Web Crawling Prompt Contexts (FL02 specific) ---
@dataclass(frozen=True)
class WriteWebChapterContext:
    """Encapsulate all context needed to format the write web chapter prompt.

    Attributes:
        document_collection_name: Name of the website/document collection.
        chapter_num: The sequential number of this chapter.
        concept_name: The core concept/topic this chapter covers.
        concept_summary: A summary of the concept.
        full_chapter_structure_md: Markdown formatted list of all planned chapters.
        relevant_document_snippets: String containing relevant text snippets
                                    from original web document chunks for this concept.
        target_language: Target language for the chapter content.
        prev_chapter_meta: Metadata of the preceding chapter (uses common WebChapterMetadata).
        next_chapter_meta: Metadata of the succeeding chapter (uses common WebChapterMetadata).
    """

    document_collection_name: str
    chapter_num: int
    concept_name: str
    concept_summary: str
    full_chapter_structure_md: str
    relevant_document_snippets: str
    target_language: str
    prev_chapter_meta: Optional[WebChapterMetadata] = None
    next_chapter_meta: Optional[WebChapterMetadata] = None


# Add WebSequenceDiagramContext if such a concept exists for web flow
# @dataclass(frozen=True)
# class WebSequenceDiagramContext:
# ... (attributes using types from sourcelens.core.common_types if needed)


__all__ = [
    # Specific constants for FL02
    "MAX_SNIPPETS_FOR_WEB_CONCEPT_CONTEXT",
    # Specific dataclasses for FL02 prompt contexts
    "WriteWebChapterContext",
    # "WebSequenceDiagramContext", # if defined
]

# End of src/FL02_web_crawling/prompts/_common.py
