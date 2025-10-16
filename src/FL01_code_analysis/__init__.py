# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""FL01_code_analysis: SourceLens Flow for Code Analysis and Tutorial Generation.

This package encapsulates all logic, nodes, and prompts necessary for
analyzing source code from various inputs (local directories, GitHub repositories)
and generating comprehensive tutorials, including textual explanations,
diagrams, and code inventories.

It can be run independently or orchestrated by the main SourceLens application.
"""

# Import the main flow creation function from the flow module within this package.
from .flow import create_code_analysis_flow

__all__ = [
    "create_code_analysis_flow",
]

# End of src/FL01_code_analysis/__init__.py
