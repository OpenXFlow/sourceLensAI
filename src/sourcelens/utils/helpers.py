# src/sourcelens/utils/helpers.py

"""General utility functions for the SourceLens application.

Includes helpers for retrieving file content based on indices and sanitizing
strings for use as filenames.
"""

import logging
import re
from collections.abc import Iterable
from typing import TypeAlias

logger = logging.getLogger(__name__)

# Type alias for file data (using modern syntax)
FileData: TypeAlias = list[tuple[str, str]]
ContentMap: TypeAlias = dict[str, str]  # For "index # path" -> content mapping

# --- Constants ---
# Maximum length for sanitized filenames (excluding extension)
MAX_FILENAME_LEN = 60
# Characters to be replaced or removed in filenames
INVALID_FILENAME_CHARS_REGEX = r'[<>:"/\\|?*\x00-\x1f`#%=~{},\';!@+()\[\]]'  # Added more chars


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
        logger.debug("get_content_for_indices called with empty files_data.")
        return content_map

    try:
        valid_indices_set: set[int] = {
            int(i) for i in indices if isinstance(i, (int, float)) or (isinstance(i, str) and i.isdigit())
        }
    except (ValueError, TypeError) as e:
        logger.warning("Could not convert all provided indices to integers. Error: %s. Using only valid integers.", e)
        # Fallback conversion, attempting to ignore problematic entries
        valid_indices_set = set()
        for i in indices:
            try:
                if isinstance(i, int):
                    valid_indices_set.add(i)
                elif isinstance(i, float) and i.is_integer() or isinstance(i, str) and i.isdigit():
                    valid_indices_set.add(int(i))
            except (ValueError, TypeError):
                logger.debug("Skipping non-integer index entry: %s", i)

    max_index = len(files_data) - 1
    indices_in_range: set[int] = set()
    invalid_indices: list[int] = []

    for idx in valid_indices_set:
        if 0 <= idx <= max_index:
            indices_in_range.add(idx)
        else:
            invalid_indices.append(idx)

    if invalid_indices:
        logger.warning(
            "Requested indices out of bounds (max: %d): %s. They will be ignored.", max_index, sorted(invalid_indices)
        )

    for i, (path, content) in enumerate(files_data):
        if i in indices_in_range:
            normalized_path = path.replace("\\", "/")  # Ensure consistent path separators
            key = f"{i} # {normalized_path}"
            content_str = str(content) if content is not None else ""
            content_map[key] = content_str

    if len(content_map) != len(indices_in_range):
        found_indices_keys = {int(k.split("#", 1)[0].strip()) for k in content_map}
        missing_valid_indices = indices_in_range - found_indices_keys
        if missing_valid_indices:
            logger.error(
                "Internal inconsistency: Valid in-range indices %s were not found during files_data iteration.",
                sorted(missing_valid_indices),
            )

    return content_map


def sanitize_filename(name: str, *, allow_underscores: bool = True, max_len: int = MAX_FILENAME_LEN) -> str:
    """Sanitize a string to be suitable for use as a filename component.

    Removes/replaces problematic characters, optionally converts underscores,
    converts to lowercase, normalizes spaces/hyphens, and limits length.

    Args:
        name: The input string (e.g., chapter or project name).
        allow_underscores: Keyword-only argument. If True (default), underscores
                           are preserved. If False, they are replaced with hyphens.
        max_len: Maximum allowed length for the sanitized filename component.

    Returns:
        A sanitized string suitable for use in a filename (excluding extension).

    """
    if not isinstance(name, str) or not name.strip():
        return "unnamed-file"  # Return default for empty or non-string input

    sanitized_name = name.strip()

    # Replace specific problematic characters with a hyphen
    sanitized_name = re.sub(INVALID_FILENAME_CHARS_REGEX, "-", sanitized_name)

    # Replace whitespace sequences with a single hyphen
    sanitized_name = re.sub(r"\s+", "-", sanitized_name)

    # Handle underscores based on the flag
    if not allow_underscores:
        sanitized_name = sanitized_name.replace("_", "-")
    else:
        # If underscores are allowed, ensure they aren't mixed with hyphens where not intended
        # (e.g., replace hyphen-underscore or underscore-hyphen sequences)
        sanitized_name = re.sub(r"[-_]+", "-", sanitized_name)  # Treat consecutive mix as hyphen

    # Collapse multiple consecutive hyphens into one
    sanitized_name = re.sub(r"-+", "-", sanitized_name)

    # Remove leading/trailing hyphens and underscores (if allowed)
    strip_chars = "-"
    if allow_underscores:
        strip_chars += "_"
    sanitized_name = sanitized_name.strip(strip_chars)

    # Limit overall length intelligently (try to cut at hyphen)
    if len(sanitized_name) > max_len:
        cut_pos = sanitized_name.rfind("-", 0, max_len)  # Find last hyphen within limit
        sanitized_name = sanitized_name[:cut_pos] if cut_pos != -1 else sanitized_name[:max_len]
        # Strip again in case truncation created leading/trailing hyphens
        sanitized_name = sanitized_name.strip(strip_chars)

    # Ensure filename is not empty or just dots after sanitization
    if not sanitized_name or sanitized_name == "." * len(sanitized_name):
        return "sanitized-name"  # Fallback if everything was stripped

    return sanitized_name.lower()


# End of src/sourcelens/utils/helpers.py
