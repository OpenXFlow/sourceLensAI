"""Utilities for fetching and processing code from local directories."""

import fnmatch
import logging
import os  # Keep os for path manipulations like relpath, normcase if needed
from pathlib import Path  # Use pathlib for path operations
from typing import Optional, TypeAlias  # Use TypeAlias

# --- Safe import of helper from github.py ---
try:
    # Import the specific function needed
    from .github import _should_include_file
except ImportError:
    logger_local = logging.getLogger(__name__)
    logger_local.warning("Could not import _should_include_file from .github, defining basic fallback.")
    PatternsSetFB: TypeAlias = Optional[set[str]]
    # PGH003: Specific ignore for known redefinition in fallback case
    def _should_include_file( # type: ignore[no-redef]
        file_path: str, filename: str, include_patterns: PatternsSetFB, exclude_patterns: PatternsSetFB
    ) -> bool:
        """Basic fallback filter function (case-sensitive)."""
        # D401: Docstring fixed to imperative mood (already done)
        file_path_norm = file_path.replace(os.sep, '/')
        if exclude_patterns and any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in exclude_patterns):
            return False
        # SIM102 fix: Combine nested if conditions
        if include_patterns and \
           not any(fnmatch.fnmatchcase(filename, pattern) for pattern in include_patterns) and \
           not any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in include_patterns):
            return False
        return True

logger = logging.getLogger(__name__)

# Type Aliases
FilePathContentDict: TypeAlias = dict[str, str]
PatternsSet: TypeAlias = Optional[set[str]]

def _process_local_file(
    abs_filepath: Path,
    relative_filepath_norm: str, # Path relative to root, normalized
    max_file_size: Optional[int],
) -> Optional[str]:
    """Read and return content of a single local file if size is valid."""
    # Check file size
    if max_file_size is not None:
        try:
            if abs_filepath.stat().st_size > max_file_size:
                # Log info moved to the main loop for consolidated skipped count
                # logger.info("Skipping '%s': Size %d > limit %d", display_path, file_size, max_file_size)
                return None # Skip file if too large
        except OSError as e_stat:
            # Log error if file size cannot be obtained
            logger.warning("Could not get size for '%s': %s. Skipping file.", abs_filepath, e_stat)
            return None

    # Read file content
    try:
        # Use pathlib's read_text for simplicity and correct encoding handling
        return abs_filepath.read_text(encoding='utf-8', errors='replace')
    except OSError as e_read:
        logger.warning("Could not read file '%s': %s. Skipping file.", abs_filepath, e_read)
        return None
    except Exception as e_other: # Catch other potential errors like decoding
        # BLE001 fix: Catching broader Exception, but logging it specifically
        logger.warning("An unexpected error occurred reading '%s': %s. Skipping file.", abs_filepath, e_other)
        return None

def crawl_local_directory(
    directory: str,
    include_patterns: PatternsSet = None,
    exclude_patterns: PatternsSet = None,
    max_file_size: Optional[int] = None,
    *, # Make use_relative_paths keyword-only
    use_relative_paths: bool = True,
) -> FilePathContentDict:
    """Crawl files recursively in a local directory, applying filters.

    Uses `os.walk` for efficient directory traversal and pruning, and `pathlib`
    for path operations. Filters files based on include/exclude patterns
    (case-sensitive) and maximum file size. Handles potential OS errors.

    Args:
        directory: Path string to the local directory to crawl.
        include_patterns: Glob patterns for files to include.
        exclude_patterns: Glob patterns for files/dirs to exclude.
        max_file_size: Maximum file size in bytes. Files larger are skipped.
        use_relative_paths: If True (default), keys in the returned dict are
                            relative to the input `directory`'s resolved path.
                            If False, keys remain relative to the resolved root.

    Returns:
        Dictionary mapping file paths (using '/' separators) to their content.

    Raises:
        ValueError: If the specified directory does not exist, is not a directory,
                    or cannot be resolved.

    """
    # C901, PLR0912, PLR0915: Complexity reduced by extracting file processing logic.
    dir_path = Path(directory)
    if not dir_path.is_dir():
        raise ValueError(f"Specified path is not a valid directory: '{directory}'")

    try:
        resolved_dir_path = dir_path.resolve(strict=True)
    except OSError as e:
         raise ValueError(f"Could not resolve or access directory path '{directory}': {e}") from e

    logger.info("Starting local directory crawl: %s", resolved_dir_path)
    logger.info("Include Patterns: %s, Exclude Patterns: %s", include_patterns, exclude_patterns)
    logger.info("Max File Size: %s, Use Relative Paths: %s", max_file_size, use_relative_paths)

    files_dict: FilePathContentDict = {}
    skipped_count = 0

    # Use os.walk for efficient directory pruning
    for root, dirs, files in os.walk(resolved_dir_path, topdown=True, onerror=logger.warning):
        current_root_path = Path(root)
        try:
            relative_root_path = current_root_path.relative_to(resolved_dir_path)
        except ValueError:
             logger.warning("Could not get relative path for root %s. Skipping.", current_root_path)
             continue

        relative_root_norm = str(relative_root_path).replace(os.sep, '/')
        # Handle root case where relative path is '.'
        if relative_root_norm == '.': relative_root_norm = ''

        # --- Directory Pruning ---
        if exclude_patterns:
            original_dirs = list(dirs)
            dirs[:] = [
                d for d in original_dirs
                # Check if the normalized relative directory path matches any exclude pattern
                if not any(
                    # Ensure trailing slash for directory matching
                    fnmatch.fnmatchcase(f"{relative_root_norm}/{d}/" if relative_root_norm else f"{d}/", pattern)
                    for pattern in exclude_patterns
                )
            ]

        # --- Process Files ---
        for filename in files:
            abs_filepath = current_root_path / filename
            # Normalized path relative to resolved root (used for filtering)
            relative_filepath_norm = f"{relative_root_norm}/{filename}" if relative_root_norm else filename

            # Determine display path based on flag (key in the result dict)
            # Currently, both relative and non-relative use path relative to resolved root.
            # If strict relativity to *input* `directory` is needed for use_relative_paths=True,
            # calculate relative_to(dir_path.resolve()) here instead.
            display_path = relative_filepath_norm

            # Filter based on include/exclude patterns
            if not _should_include_file(relative_filepath_norm, filename, include_patterns, exclude_patterns):
                continue

            # Process (check size & read) the file
            content = _process_local_file(abs_filepath, relative_filepath_norm, max_file_size)

            if content is not None:
                files_dict[display_path] = content
            else:
                # Increment skipped count if processing failed or file skipped by size
                skipped_count += 1

    # Consolidate logging message
    log_message = f"Local directory crawl complete. Found {len(files_dict)} files matching criteria."
    if skipped_count > 0:
        # Wrapped log message for E501
        log_message += (
            f" Skipped {skipped_count} files/items due to errors, size limits, or filters."
        )
    logger.info(log_message)

    return files_dict

# End of src/sourcelens/utils/local.py
