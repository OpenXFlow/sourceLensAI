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

Includes helpers for retrieving file content based on indices, sanitizing
strings for use as filenames, and YouTube URL utilities.
"""

import logging
import re
from collections.abc import Iterable
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

# Import shared types from the central common_types module
from sourcelens.core.common_types import FilePathContentList

YTDLP_AVAILABLE: bool = False
yt_dlp_module: Optional[Any] = None
YtdlpDownloadError: Optional[type[Exception]] = None
YtdlpExtractorError: Optional[type[Exception]] = None

try:
    import yt_dlp as imported_yt_dlp

    yt_dlp_module = imported_yt_dlp
    if hasattr(yt_dlp_module, "utils"):
        YtdlpDownloadError = getattr(yt_dlp_module.utils, "DownloadError", Exception)
        YtdlpExtractorError = getattr(yt_dlp_module.utils, "ExtractorError", Exception)
    YTDLP_AVAILABLE = True
except ImportError:
    pass  # Handled by functions using it


logger: logging.Logger = logging.getLogger(__name__)

ContentMap: TypeAlias = dict[str, str]
MAX_FILENAME_LEN: int = 60
INVALID_FILENAME_CHARS_REGEX_PATTERN: str = r'[<>:"/\\|?*\x00-\x1f`#%=~{},\';!@+()\[\]]'
INVALID_FILENAME_CHARS_REGEX: re.Pattern[str] = re.compile(INVALID_FILENAME_CHARS_REGEX_PATTERN)

YOUTUBE_URL_PATTERNS_HELPERS: Final[list[re.Pattern[str]]] = [
    re.compile(r"(?:v=|\/|embed\/|watch\?v=|youtu\.be\/)([0-9A-Za-z_-]{11}).*"),
    re.compile(r"shorts\/([0-9A-Za-z_-]{11})"),
]


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

    for idx_val in indices_to_filter:
        if 0 <= idx_val <= max_allowable_index:
            if idx_val not in valid_indices_set:
                valid_indices_set.add(idx_val)
        else:
            invalid_indices_for_log.append(idx_val)

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
            elif i_val is not None:  # pragma: no cover
                logger.debug(
                    "Skipping non-integer or non-convertible index entry: %s (type: %s)", i_val, type(i_val).__name__
                )
        except (ValueError, TypeError):  # pragma: no cover
            logger.debug("Skipping index entry due to conversion error: %s", i_val)
    return parsed_integer_indices


def get_content_for_indices(files_data: FilePathContentList, indices: Iterable[Any]) -> ContentMap:
    """Retrieve the file path and content for a specific set of file indices.

    Args:
        files_data: A list of tuples, where each tuple is (path_string, content_string).
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

    if out_of_bounds_indices:  # pragma: no cover
        logger.warning(
            "Requested indices out of bounds (max: %d): %s. They will be ignored.",
            max_index,
            sorted(out_of_bounds_indices),
        )

    for i, (path, content) in enumerate(files_data):
        if i in valid_in_range_indices:
            normalized_path = path.replace("\\", "/")
            key = f"{i} # {normalized_path}"
            content_map[key] = content

    if len(content_map) != len(valid_in_range_indices):  # pragma: no cover
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
                           are preserved before hyphen normalization. If False,
                           they are replaced with hyphens.
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
        sanitized_name = re.sub(r"[-_]+", "-", sanitized_name)  # Normalize mixed or multiple to single hyphen

    sanitized_name = re.sub(r"-+", "-", sanitized_name)
    strip_chars = "-"
    sanitized_name = sanitized_name.strip(strip_chars)

    if len(sanitized_name) > max_len:
        cut_pos = sanitized_name.rfind("-", 0, max_len)
        sanitized_name = sanitized_name[:cut_pos] if cut_pos != -1 else sanitized_name[:max_len]
        sanitized_name = sanitized_name.strip(strip_chars)

    if not sanitized_name or all(c == "." for c in sanitized_name):  # pragma: no cover
        return "sanitized-name"

    return sanitized_name.lower()


def is_youtube_url(url_string: Optional[str]) -> bool:
    """Check if the given URL string matches known YouTube video URL patterns.

    Args:
        url_string: The URL string to check.

    Returns:
        True if the URL is identified as a YouTube video URL, False otherwise.
    """
    if not url_string or not isinstance(url_string, str):
        return False
    return any(pattern.search(url_string) for pattern in YOUTUBE_URL_PATTERNS_HELPERS)


def get_youtube_video_title_and_id(url_string: str) -> tuple[Optional[str], Optional[str]]:
    """Extract video ID and fetch title for a given YouTube URL using yt-dlp.

    Args:
        url_string: The YouTube URL string.

    Returns:
        A tuple (video_id, video_title). Returns (None, None) if yt-dlp is
        unavailable, URL is not a valid YouTube URL, or if metadata extraction fails.
        If title extraction fails but ID is found, returns (video_id, None).
    """
    if not YTDLP_AVAILABLE or yt_dlp_module is None:  # pragma: no cover
        logger.warning("yt-dlp library not available. Cannot fetch YouTube title and ID.")
        return None, None

    video_id: Optional[str] = None
    for pattern in YOUTUBE_URL_PATTERNS_HELPERS:
        match = pattern.search(url_string)
        if match:
            video_id = match.group(1)
            break

    if not video_id:
        logger.debug("Could not extract YouTube video ID from URL: %s", url_string)
        return None, None

    ydl_opts: dict[str, Any] = {
        "quiet": True,
        "no_warnings": True,
        "skip_download": True,
        "extract_flat": False,
        "noplaylist": True,
    }

    logger.debug("Attempting to fetch YouTube metadata for URL: %s (ID: %s)", url_string, video_id)
    try:
        with yt_dlp_module.YoutubeDL(ydl_opts) as ydl:
            # Ensure error types are defined if yt_dlp_module is not None
            if YtdlpDownloadError is None or YtdlpExtractorError is None:  # pragma: no cover
                raise RuntimeError("yt-dlp error types not initialized correctly.")

            try:
                info_dict: Union[dict[str, Any], None] = ydl.extract_info(url_string, download=False)
            except (YtdlpDownloadError, YtdlpExtractorError) as e_yt_dlp:  # pragma: no cover
                # Catch specific yt-dlp errors during extract_info
                logger.error(
                    "yt-dlp error during metadata extraction for %s (ID: %s): %s", url_string, video_id, e_yt_dlp
                )
                return video_id, None  # Return ID if found, but title fetch failed

            if info_dict:
                actual_id_val: Any = info_dict.get("id")
                title_val: Any = info_dict.get("title")
                actual_id: Optional[str] = str(actual_id_val) if isinstance(actual_id_val, str) else None
                title: Optional[str] = str(title_val) if isinstance(title_val, str) else None

                if actual_id != video_id:  # pragma: no cover
                    logger.warning(
                        "Extracted video ID '%s' differs from regex-parsed ID '%s' for URL %s.",
                        actual_id,
                        video_id,
                        url_string,
                    )
                logger.info("Successfully fetched title '%s' for YouTube ID '%s'", title, actual_id or video_id)
                return actual_id or video_id, title
            else:  # pragma: no cover
                logger.warning("yt-dlp extract_info returned None for URL: %s", url_string)
                return video_id, None  # ID was found by regex, but extract_info failed
    except Exception as e:  # pragma: no cover
        logger.error(
            "Unexpected error fetching YouTube metadata for %s (ID: %s): %s", url_string, video_id, e, exc_info=True
        )
        return video_id, None  # Return ID if found, but general error occurred


# End of src/sourcelens/utils/helpers.py
