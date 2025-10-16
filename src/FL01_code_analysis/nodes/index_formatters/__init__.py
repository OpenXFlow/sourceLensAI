# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Formatters for generating the source code index content.

This package contains modules responsible for parsing source files (either via
AST for Python or using an LLM for various languages) and formatting
the extracted structural information into a Markdown representation for the
code inventory.
"""

from ._ast_python_formatter import format_python_index_from_ast
from ._llm_default_formatter import format_index_from_llm

__all__: list[str] = [
    "format_python_index_from_ast",
    "format_index_from_llm",
]

# End of src/sourcelens/nodes/index_formatters/__init__.py
