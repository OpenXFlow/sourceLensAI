"""General utility functions for the SourceLens application.

Includes helpers for retrieving file content based on indices and sanitizing
strings for use as filenames.
"""

import logging
import re
from collections.abc import Iterable  # Use collections.abc for generic types
from typing import TypeAlias

logger = logging.getLogger(__name__)

# Type alias for file data (using modern syntax)
FileData: TypeAlias = list[tuple[str, str]]
ContentMap: TypeAlias = dict[str, str] # For "index # path" -> content mapping


def get_content_for_indices(files_data: FileData, indices: Iterable[int]) -> ContentMap:
    """Retrieve the file path and content for a specific set of file indices.

    Args:
        files_data: A list of tuples, where each tuple is (path, content).
                    Typically sourced from shared['files'].
        indices: An iterable of integer indices corresponding to the files_data list.

    Returns:
        A dictionary where keys are formatted strings "index # path" and
        values are the file content strings. Returns an empty dict if
        files_data is empty or no valid indices are provided/found.

    """
    content_map: ContentMap = {}
    if not files_data:
        # Log if called with empty data, but proceed returning empty map
        logger.debug("get_content_for_indices called with empty files_data.")
        return content_map

    # Use a set for efficient lookup and handle potential duplicates/non-int types
    try:
        valid_indices_set: set[int] = {int(i) for i in indices}
    except (ValueError, TypeError):
        logger.warning("Could not convert all provided indices to integers. Using only valid integers.")
        valid_indices_set = {int(i) for i in indices if isinstance(i, int) or (isinstance(i, str) and i.isdigit())}

    max_index = len(files_data) - 1

    # Filter out invalid indices (out of bounds) and log them
    indices_in_range: set[int] = set()
    invalid_indices: list[int] = []
    for idx in valid_indices_set:
        if 0 <= idx <= max_index:
            indices_in_range.add(idx)
        else:
            invalid_indices.append(idx)

    if invalid_indices:
        logger.warning(
            "Requested indices out of bounds (max: %d): %s. They will be ignored.",
            max_index, sorted(invalid_indices) # C414 fix: removed list()
        )

    # Iterate through files_data once and populate the map for valid indices
    for i, (path, content) in enumerate(files_data):
        if i in indices_in_range:
            key = f"{i} # {path}"
            # Ensure content is string, handle potential None or other types
            content_str = str(content) if content is not None else ""
            content_map[key] = content_str
            # Optional: remove found index to track inconsistencies later
            # indices_in_range.remove(i)

    # Log if the number of found items doesn't match the number of valid indices
    if len(content_map) != len(indices_in_range):
         # This usually indicates a logic error if it happens
         found_indices_keys = {int(k.split('#', 1)[0].strip()) for k in content_map}
         missing_valid_indices = indices_in_range - found_indices_keys
         if missing_valid_indices:
             # C414 fix: removed list()
             logger.error(
                 "Internal inconsistency: Valid in-range indices %s were not found during files_data iteration.",
                 sorted(missing_valid_indices)
             )

    return content_map


def sanitize_filename(name: str, *, allow_underscores: bool = True) -> str:
    """Sanitize a string to be suitable for use as a filename component.

    Removes/replaces problematic characters, optionally converts underscores,
    converts to lowercase, and limits length.

    Args:
        name: The input string (e.g., chapter or project name).
        allow_underscores: Keyword-only argument. If True (default), underscores
                           are preserved. If False, they are replaced with hyphens.

    Returns:
        A sanitized string suitable for use in a filename (excluding extension).

    """
    if not isinstance(name, str) or not name:
        return "unnamed-file"

    sanitized_name = name.strip()
    # Replace problematic characters with a hyphen
    sanitized_name = re.sub(r'[<>:"/\\|?*\x00-\x1f\s]+', '-', sanitized_name)
    if not allow_underscores:
        sanitized_name = sanitized_name.replace("_", "-")
    # Collapse multiple consecutive hyphens
    sanitized_name = re.sub(r'-+', '-', sanitized_name)
    sanitized_name = sanitized_name.strip('-') # Remove leading/trailing hyphens

    # Limit overall length
    max_len = 100
    if len(sanitized_name) > max_len:
        sanitized_name = sanitized_name[:max_len].strip('-')

    # Ensure filename is not empty after sanitization
    if not sanitized_name:
        return "sanitized-name"

    return sanitized_name.lower()


# End of src/sourcelens/utils/helpers.py
