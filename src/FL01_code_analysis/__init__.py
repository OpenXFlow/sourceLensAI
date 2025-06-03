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
