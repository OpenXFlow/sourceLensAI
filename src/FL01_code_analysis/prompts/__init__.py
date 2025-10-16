# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Prompts sub-package for the Code Analysis Flow (FL01_code_analysis).

This package groups all prompt generation logic and related data structures
specifically tailored for analyzing source code. Shared, general-purpose types
and constants should be imported from `sourcelens.core.common_types`.
"""

# Import flow-specific data structures and constants defined within this sub-package.
from ._common import (
    CODE_BLOCK_MAX_LINES_FOR_CHAPTERS,  # Specific to FL01 chapter writing
    # SequenceDiagramContext was moved to sourcelens.core.common_types
    WriteChapterContext,  # Specific context for FL01 chapter writing
)

# Import code-specific prompt generating classes
from .abstraction_prompts import AbstractionPrompts
from .chapter_prompts import ChapterPrompts
from .project_review_prompts import PROJECT_REVIEW_SCHEMA, ProjectReviewPrompts
from .scenario_prompts import ScenarioPrompts
from .source_index_prompts import SourceIndexPrompts

# Diagram-specific prompt formatting functions (like format_class_diagram_prompt, etc.)
# are now centralized in `sourcelens.mermaid_diagrams` and should be imported
# directly from there by nodes that need them (e.g., n06_generate_diagrams.py).

__all__ = [
    # From ._common (specific to FL01 code analysis prompts)
    "CODE_BLOCK_MAX_LINES_FOR_CHAPTERS",
    "WriteChapterContext",
    # Prompt classes for code analysis
    "AbstractionPrompts",
    "ChapterPrompts",
    "ProjectReviewPrompts",
    "PROJECT_REVIEW_SCHEMA",  # Exporting schema alongside the prompt class
    "ScenarioPrompts",
    "SourceIndexPrompts",
    # SequenceDiagramContext is no longer re-exported from here.
    # Modules needing it should import from sourcelens.core.common_types
]
# Note: Types like CodeAbstractionsList, CodeRelationshipsDict, ChapterMetadata,
# DEFAULT_CODE_RELATIONSHIP_LABEL, MAX_CODE_FLOWCHART_LABEL_LEN are now in
# `sourcelens.core.common_types` and should be imported from there by modules
# that directly need them, rather than being re-exported from this `__init__.py`.

# End of src/FL01_code_analysis/prompts/__init__.py
