# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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

"""Utilities Package for SourceLens.

Contains helper functions and classes used across different parts of the
SourceLens application, such as interacting with external APIs (LLM, GitHub),
handling file operations using pathlib, and performing data validation.
"""

from ._exceptions import LlmApiError
from .github import GithubApiError, crawl_github_repo
from .helpers import get_content_for_indices, sanitize_filename
from .llm_api import call_llm
from .local import crawl_local_directory
from .validation import ValidationFailure, validate_yaml_dict, validate_yaml_list

__all__ = [
    "call_llm",
    "LlmApiError",
    "crawl_github_repo",
    "GithubApiError",
    "crawl_local_directory",
    "get_content_for_indices",
    "sanitize_filename",
    "validate_yaml_list",
    "validate_yaml_dict",
    "ValidationFailure",
]

# End of src/sourcelens/utils/__init__.py
