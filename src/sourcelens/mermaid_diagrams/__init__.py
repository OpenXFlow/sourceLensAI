# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Mermaid Diagrams Generation Utilities for SourceLens.

This package centralizes all logic related to generating Mermaid diagram
markup, both through LLM-powered prompt formatting and direct algorithmic
generation. It provides functions to create various diagram types like
sequence, class, package, and flowchart diagrams, along with common
guidelines for ensuring valid and useful Mermaid output.
"""

# Import using the exact filenames provided by the user
from ._common_guidelines import INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT
from .class_diagram_prompts import format_class_diagram_prompt
from .file_structure_diagram import generate_file_structure_mermaid
from .package_diagram_prompts import format_package_diagram_prompt
from .relationship_flowchart_prompts import format_relationship_flowchart_prompt
from .sequence_diagram_prompts import format_sequence_diagram_prompt

__all__ = [
    "format_sequence_diagram_prompt",
    "format_class_diagram_prompt",
    "format_package_diagram_prompt",
    "format_relationship_flowchart_prompt",
    "generate_file_structure_mermaid",
    "INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT",
]

# End of src/sourcelens/mermaid_diagrams/__init__.py
