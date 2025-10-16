# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Utilities for fetching and processing code from local directories."""

import fnmatch
import logging
import os
from pathlib import Path
from typing import Optional

from typing_extensions import TypeAlias

# --- Safe import of helper from github.py ---
try:
    from .github import _should_include_file  # type: ignore[attr-defined]
except ImportError:
    logger_local_fallback = logging.getLogger(__name__ + ".fallback_filter")
    logger_local_fallback.warning("Could not import _should_include_file from .github, defining basic fallback.")
    PatternsSetFB: TypeAlias = Optional[set[str]]

    def _should_include_file(  # type: ignore[no-redef]
        file_path: str, filename: str, include_patterns: PatternsSetFB, exclude_patterns: PatternsSetFB
    ) -> bool:
        """Provide basic fallback filter if github._should_include_file is unavailable.

        Args:
            file_path: The full path of the file.
            filename: The name of the file.
            include_patterns: Set of glob patterns for files to include.
            exclude_patterns: Set of glob patterns for files/dirs to exclude.

        Returns:
            True if the file should be included, False otherwise.
        """
        file_path_norm = file_path.replace(os.sep, "/")
        if exclude_patterns and any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in exclude_patterns):
            return False
        if (
            include_patterns
            and not any(fnmatch.fnmatchcase(filename, pattern) for pattern in include_patterns)
            and not any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in include_patterns)
        ):
            return False
        return True


logger: logging.Logger = logging.getLogger(__name__)

FilePathContentDict: TypeAlias = dict[str, str]
PatternsSet: TypeAlias = Optional[set[str]]


def _process_local_file(
    abs_filepath: Path,
    max_file_size: Optional[int],
) -> Optional[str]:
    """Read and return content of a single local file if size and readability are valid.

    Args:
        abs_filepath: Absolute path to the file.
        max_file_size: Maximum allowed file size in bytes. If None, no size check.

    Returns:
        The file content as a string if successful, otherwise None.
    """
    if max_file_size is not None:
        try:
            file_size = abs_filepath.stat().st_size
            if file_size > max_file_size:
                logger.info("Skipping '%s': Size %d > limit %d", abs_filepath, file_size, max_file_size)
                return None
        except OSError as e_stat:  # Catches FileNotFoundError, PermissionError for stat
            logger.warning("Could not get size for '%s': %s. Skipping file.", abs_filepath, e_stat)
            return None

    try:
        return abs_filepath.read_text(encoding="utf-8", errors="replace")
    except UnicodeDecodeError as e_decode:  # Specific error for decoding issues
        logger.warning("Unicode decode error reading '%s': %s. Skipping file.", abs_filepath, e_decode)
        return None
    except IOError as e_io:  # Broader I/O errors (includes FileNotFoundError, PermissionError for read)
        logger.warning("Could not read file '%s' due to I/O error: %s. Skipping file.", abs_filepath, e_io)
        return None
    # Removed the general `except Exception` to satisfy BLE001 more strictly.
    # If other unexpected errors occur during read_text, they will now propagate.


def _process_directory_contents(
    current_root_path_str: str,
    dir_names: list[str],
    file_names_in_dir: list[str],
    base_dir_path: Path,
    include_patterns: PatternsSet,
    exclude_patterns: PatternsSet,
    max_file_size: Optional[int],
    *,
    use_relative_paths: bool,
    files_dict: FilePathContentDict,
) -> int:
    """Process files in a directory and prunes subdirectories.

    Modifies `dir_names` in-place for os.walk pruning.
    Updates `files_dict` with content of included files.

    Args:
        current_root_path_str: Current root directory string from os.walk.
        dir_names: List of directory names in current_root_path_str (modified in-place).
        file_names_in_dir: List of file names in current_root_path_str.
        base_dir_path: The absolute, resolved path of the initial crawl directory.
        include_patterns: Glob patterns for files to include.
        exclude_patterns: Glob patterns for files/dirs to exclude.
        max_file_size: Maximum file size in bytes.
        use_relative_paths: Whether to key results with paths relative to `base_dir_path`.
        files_dict: Dictionary to populate with file paths and content.

    Returns:
        Number of files skipped in this directory due to errors or filters.
    """
    current_root_path = Path(current_root_path_str)
    skipped_in_dir = 0
    try:
        path_relative_to_base = current_root_path.relative_to(base_dir_path)
    except ValueError:
        logger.warning(
            "Could not get relative path for root %s to base %s. Skipping directory processing.",
            current_root_path,
            base_dir_path,
        )
        dir_names[:] = []
        return 0

    relative_root_norm = str(path_relative_to_base).replace(os.sep, "/")
    if relative_root_norm == ".":
        relative_root_norm = ""

    if exclude_patterns:
        original_dirs = list(dir_names)
        dir_names[:] = [
            d_name
            for d_name in original_dirs
            if not any(
                fnmatch.fnmatchcase(f"{relative_root_norm}/{d_name}/" if relative_root_norm else f"{d_name}/", pattern)
                for pattern in exclude_patterns
            )
        ]

    for filename in file_names_in_dir:
        abs_filepath = current_root_path / filename
        path_for_filtering_norm = f"{relative_root_norm}/{filename}" if relative_root_norm else filename

        display_path: str
        if use_relative_paths:
            display_path = path_for_filtering_norm
        else:
            display_path = (
                str(abs_filepath.relative_to(Path.cwd())).replace(os.sep, "/")
                if abs_filepath.is_absolute()
                else str(abs_filepath).replace(os.sep, "/")
            )

        if not _should_include_file(path_for_filtering_norm, filename, include_patterns, exclude_patterns):
            continue

        content = _process_local_file(abs_filepath, max_file_size)
        if content is not None:
            files_dict[display_path] = content
        else:
            skipped_in_dir += 1
    return skipped_in_dir


def crawl_local_directory(
    directory: str,
    include_patterns: PatternsSet = None,
    exclude_patterns: PatternsSet = None,
    max_file_size: Optional[int] = None,
    *,
    use_relative_paths: bool = True,
) -> FilePathContentDict:
    """Crawl files recursively in a local directory, applying filters.

    Args:
        directory: Path string to the local directory to crawl.
        include_patterns: Glob patterns for files to include.
        exclude_patterns: Glob patterns for files/dirs to exclude.
        max_file_size: Maximum file size in bytes. Files larger are skipped.
        use_relative_paths: If True, keys in the returned dict are relative to `directory`.

    Returns:
        Dictionary mapping file paths (using '/' separators) to their content.

    Raises:
        ValueError: If `directory` is not a valid directory or cannot be accessed.
    """
    try:
        base_dir_path = Path(directory).resolve(strict=True)
    except FileNotFoundError:
        raise ValueError(f"Specified directory does not exist: '{directory}'") from None
    except OSError as e:
        raise ValueError(f"Could not resolve or access directory path '{directory}': {e!s}") from e

    if not base_dir_path.is_dir():
        raise ValueError(f"Specified path is not a valid directory: '{base_dir_path}'")

    logger.info("Starting local directory crawl: %s", base_dir_path)
    logger.info("Include Patterns: %s, Exclude Patterns: %s", include_patterns, exclude_patterns)
    logger.info("Max File Size: %s, Use Relative Paths: %s", max_file_size, use_relative_paths)

    files_dict: FilePathContentDict = {}
    total_skipped_count = 0

    for root_str, dirs, files_in_dir in os.walk(base_dir_path, topdown=True, onerror=logger.warning):
        skipped_in_current_dir = _process_directory_contents(
            current_root_path_str=root_str,
            dir_names=dirs,
            file_names_in_dir=files_in_dir,
            base_dir_path=base_dir_path,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_file_size=max_file_size,
            use_relative_paths=use_relative_paths,
            files_dict=files_dict,
        )
        total_skipped_count += skipped_in_current_dir

    log_message = f"Local directory crawl complete. Found {len(files_dict)} files matching criteria."
    if total_skipped_count > 0:
        log_message += f" Skipped {total_skipped_count} files/items due to errors, size limits, or filters."
    logger.info(log_message)

    return files_dict


# End of src/sourcelens/utils/local.py
