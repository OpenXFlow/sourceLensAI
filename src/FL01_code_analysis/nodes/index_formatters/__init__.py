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
