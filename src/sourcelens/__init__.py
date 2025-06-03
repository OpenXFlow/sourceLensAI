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

"""SourceLens Package.

An AI-powered tool to generate tutorials from codebases or web content
by analyzing source code or web pages and leveraging Large Language Models.
Its primary capabilities include generating code abstractions, documentation chapters,
diagrams, and identifying use case scenarios.
"""

# Define package version.
# This version should be kept in sync with the version in pyproject.toml.
__version__ = "0.2.0"  # Version was 0.1.1, assuming an update.

# It's generally cleaner to let users import directly from submodules
# (e.g., from sourcelens.main import main) rather than re-exporting too much here,
# unless specific functions form the primary public API of the package.
#
# Example of a potential re-export if `main` function was intended as a direct API:
# from .main import main
#
# __all__ = [
# "main",
# "__version__",
# ]

# End of src/sourcelens/__init__.py
