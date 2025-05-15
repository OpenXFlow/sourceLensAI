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

"""General utility functions for the SourceLens application.

Includes helpers for retrieving file content based on indices and sanitizing
strings for use as filenames.
"""

import logging
import re
from collections.abc import Iterable
from typing import Any  # Pridaný Any späť

from typing_extensions import TypeAlias

logger: logging.Logger = logging.getLogger(__name__)

FileDataItem: TypeAlias = tuple[str, str]
FileDataList: TypeAlias = list[FileDataItem]
"""Type alias for a list of (filepath_string, content_string) tuples."""

ContentMap: TypeAlias = dict[str, str]
"""Type alias for a dictionary mapping "index # path" to file content."""

MAX_FILENAME_LEN: int = 60
"""Maximum length for sanitized filenames (excluding extension)."""
INVALID_FILENAME_CHARS_REGEX_PATTERN: str = r'[<>:"/\\|?*\x00-\x1f`#%=~{},\';!@+()\[\]]'
"""Regex pattern for characters to be replaced or removed in filenames."""
INVALID_FILENAME_CHARS_REGEX: re.Pattern[str] = re.compile(INVALID_FILENAME_CHARS_REGEX_PATTERN)


def _validate_and_filter_indices(
    indices_to_filter: Iterable[int], max_allowable_index: int
) -> tuple[set[int], list[int]]:
    """Validate and filter a list of raw indices.

    Converts to integers, checks bounds, and identifies duplicates.

    Args:
        indices_to_filter: An iterable of raw indices (expected to be convertible to int).
        max_allowable_index: The maximum valid index based on data length.

    Returns:
        A tuple containing:
            - A set of valid, unique, in-range integer indices.
            - A list of indices that were out of bounds or invalid (for logging).
    """
    valid_indices_set: set[int] = set()
    invalid_indices_for_log: list[int] = []

    for idx in indices_to_filter:
        if 0 <= idx <= max_allowable_index:
            if idx not in valid_indices_set:
                valid_indices_set.add(idx)
        else:
            invalid_indices_for_log.append(idx)

    return valid_indices_set, invalid_indices_for_log


def _parse_raw_indices(raw_indices: Iterable[Any]) -> set[int]:
    """Parse an iterable of raw indices into a set of integers, logging errors.

    Args:
        raw_indices: An iterable which might contain non-integer values.

    Returns:
        A set of successfully parsed integer indices.
    """
    parsed_integer_indices: set[int] = set()
    for i_val in raw_indices:
        try:
            if isinstance(i_val, int):
                parsed_integer_indices.add(i_val)
            elif isinstance(i_val, float) and i_val.is_integer():
                parsed_integer_indices.add(int(i_val))
            elif isinstance(i_val, str) and i_val.isdigit():
                parsed_integer_indices.add(int(i_val))
            elif i_val is not None:
                logger.debug(
                    "Skipping non-integer or non-convertible index entry: %s (type: %s)", i_val, type(i_val).__name__
                )
        except (ValueError, TypeError):
            logger.debug("Skipping index entry due to conversion error: %s", i_val)
    return parsed_integer_indices


def get_content_for_indices(files_data: FileDataList, indices: Iterable[Any]) -> ContentMap:  # indices is Iterable[Any]
    """Retrieve the file path and content for a specific set of file indices.

    Args:
        files_data: A list of tuples, where each tuple is (path, content).
        indices: An iterable of indices. Non-integer or out-of-range indices
                 in this iterable will be logged and ignored.

    Returns:
        A dictionary where keys are formatted strings "index # path" and
        values are the file content strings. Returns an empty dict if
        files_data is empty or no valid, in-range indices are provided/found.
    """
    content_map: ContentMap = {}
    if not files_data:
        logger.debug("get_content_for_indices called with empty files_data.")
        return content_map

    parsed_int_indices: set[int] = _parse_raw_indices(indices)
    max_index = len(files_data) - 1
    valid_in_range_indices: set[int]
    out_of_bounds_indices: list[int]
    valid_in_range_indices, out_of_bounds_indices = _validate_and_filter_indices(parsed_int_indices, max_index)

    if out_of_bounds_indices:
        logger.warning(
            "Requested indices out of bounds (max: %d): %s. They will be ignored.",
            max_index,
            sorted(out_of_bounds_indices),
        )

    for i, (path, content) in enumerate(files_data):
        if i in valid_in_range_indices:
            normalized_path = path.replace("\\", "/")
            key = f"{i} # {normalized_path}"
            content_str = str(content) if content is not None else ""
            content_map[key] = content_str

    if len(content_map) != len(valid_in_range_indices):
        found_indices_keys = {int(k.split("#", 1)[0].strip()) for k in content_map}
        missing_from_map = valid_in_range_indices - found_indices_keys
        if missing_from_map:
            logger.error(
                "Internal inconsistency: Valid in-range indices %s were not mapped.",
                sorted(missing_from_map),
            )
    return content_map


def sanitize_filename(name: str, *, allow_underscores: bool = True, max_len: int = MAX_FILENAME_LEN) -> str:
    """Sanitize a string to be suitable for use as a filename component.

    Removes/replaces problematic characters, optionally converts underscores,
    converts to lowercase, normalizes spaces/hyphens, and limits length.

    Args:
        name: The input string (e.g., chapter or project name).
        allow_underscores: Keyword-only. If True (default), underscores
                           are preserved. If False, they are replaced with hyphens.
        max_len: Maximum allowed length for the sanitized filename component.

    Returns:
        A sanitized string suitable for use in a filename (excluding extension).
        Returns "unnamed-file" for empty or non-string input, or "sanitized-name"
        if the sanitization process results in an empty or dot-only string.
    """
    if not isinstance(name, str) or not name.strip():
        return "unnamed-file"

    sanitized_name = name.strip()
    sanitized_name = INVALID_FILENAME_CHARS_REGEX.sub("-", sanitized_name)
    sanitized_name = re.sub(r"\s+", "-", sanitized_name)

    if not allow_underscores:
        sanitized_name = sanitized_name.replace("_", "-")
    else:
        sanitized_name = re.sub(r"[-_]+", "-", sanitized_name)

    sanitized_name = re.sub(r"-+", "-", sanitized_name)

    strip_chars = "-"
    if allow_underscores:
        strip_chars += "_"
    sanitized_name = sanitized_name.strip(strip_chars)

    if len(sanitized_name) > max_len:
        cut_pos = sanitized_name.rfind("-", 0, max_len)
        sanitized_name = sanitized_name[:cut_pos] if cut_pos != -1 else sanitized_name[:max_len]
        sanitized_name = sanitized_name.strip(strip_chars)

    if not sanitized_name or all(c == "." for c in sanitized_name):
        return "sanitized-name"

    return sanitized_name.lower()


# End of src/sourcelens/utils/helpers.py
