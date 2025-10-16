# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

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
