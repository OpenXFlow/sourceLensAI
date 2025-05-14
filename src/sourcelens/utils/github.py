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

"""Utilities for fetching and processing code from GitHub repositories.

Includes functions for parsing GitHub URLs, crawling repositories via API or Git clone,
filtering files based on patterns and size, and handling potential errors like
rate limits or authentication issues. Uses pathlib and modern Python features.
"""

import base64
import binascii
import fnmatch
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, Union
from urllib.parse import urlparse

from typing_extensions import TypeAlias

try:
    import git  # type: ignore[import-untyped]

    GITPYTHON_AVAILABLE = True
except ImportError:
    git = None  # type: ignore[assignment]
    GITPYTHON_AVAILABLE = False

try:
    import requests

    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None  # type: ignore[assignment]
    REQUESTS_AVAILABLE = False


logger: logging.Logger = logging.getLogger(__name__)

# Constants
GITHUB_API_BASE: str = "https://api.github.com"
HTTP_STATUS_NOT_FOUND: int = 404
HTTP_STATUS_FORBIDDEN: int = 403
HTTP_STATUS_UNAUTHORIZED: int = 401
HTTP_STATUS_TOO_MANY_REQUESTS: int = 429
DEFAULT_TIMEOUT: int = 30
GIT_CLONE_DEPTH: int = 1
BASE64_SIZE_RATIO: float = 0.75
BASE64_SIZE_BUFFER: float = 1.1
MIN_SSH_PATH_PARTS: int = 2
MIN_HTTP_PATH_PARTS: int = 2
REF_PATH_MIN_PARTS: int = 3

# Type Aliases
FilePathContentDict: TypeAlias = dict[str, str]
PatternsSet: TypeAlias = Optional[set[str]]
SkippedFileInfo: TypeAlias = tuple[str, int]
HeadersDict: TypeAlias = dict[str, str]
GitHubApiItem: TypeAlias = dict[str, Any]
GitHubApiContents: TypeAlias = list[GitHubApiItem]
ParsedGitHubUrl: TypeAlias = tuple[Optional[str], Optional[str], Optional[str], str]


class GithubApiError(Exception):
    """Custom exception for GitHub API or cloning errors."""

    def __init__(self, message: str, status_code: Optional[int] = None) -> None:
        """Initialize GithubApiError.

        Args:
            message: The error message.
            status_code: Optional HTTP status code associated with the error.
        """
        self.status_code = status_code
        status_str = f" (Status: {status_code})" if status_code else ""
        super().__init__(f"{message}{status_str}")


def _ensure_requests_available() -> None:
    """Raise ImportError if requests library is not available."""
    if not REQUESTS_AVAILABLE or requests is None:
        raise ImportError("The 'requests' library is required for GitHub API operations.")


def _ensure_gitpython_available() -> None:
    """Raise ImportError if GitPython library is not available."""
    if not GITPYTHON_AVAILABLE or git is None:
        raise ImportError("The 'GitPython' library is required for Git clone operations.")


def _should_include_file(
    file_path: str, filename: str, include_patterns: PatternsSet, exclude_patterns: PatternsSet
) -> bool:
    """Determine if a file should be included based on patterns.

    Args:
        file_path: The full path of the file relative to the scan root.
        filename: The name of the file.
        include_patterns: Set of glob patterns for files to include.
        exclude_patterns: Set of glob patterns for files/dirs to exclude.

    Returns:
        True if the file should be included, False otherwise.
    """
    file_path_norm = file_path.replace(os.sep, "/")
    if exclude_patterns and any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in exclude_patterns):
        return False
    if include_patterns:
        matches_include = any(fnmatch.fnmatchcase(filename, pattern) for pattern in include_patterns) or any(
            fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in include_patterns
        )
        if not matches_include:
            return False
    return True


def _try_fetch_download_url(item: GitHubApiItem, headers: HeadersDict, display_path: str) -> Optional[str]:
    """Attempt to fetch content using the 'download_url' from a GitHub API item.

    Args:
        item: Dictionary representing a file item from GitHub API, expected to have a 'download_url'.
        headers: HTTP headers for the request.
        display_path: Path of the item used for logging purposes.

    Returns:
        File content as a string if successfully fetched, otherwise None.
    """
    _ensure_requests_available()
    assert requests is not None
    download_url_any: Any = item.get("download_url")
    if isinstance(download_url_any, str) and download_url_any:
        download_url: str = download_url_any
        try:
            response = requests.get(download_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            try:
                return response.text
            except UnicodeDecodeError:
                return response.content.decode("utf-8", errors="replace")
        except requests.exceptions.RequestException as e:
            logger.warning("Failed download_url fetch for '%s': %s", display_path, e)
    return None


def _try_fetch_inline_base64(item: GitHubApiItem, max_file_size: int, display_path: str) -> Optional[str]:
    """Attempt to fetch content from an inline base64 encoded 'content' field of a GitHub API item.

    Checks estimated decoded size before attempting to decode.

    Args:
        item: Dictionary representing a file item from GitHub API.
        max_file_size: Maximum allowed file size in bytes for the decoded content.
        display_path: Path of the item used for logging purposes.

    Returns:
        Decoded file content as a string if successful and within size limits, otherwise None.
    """
    if item.get("encoding") == "base64":
        content_b64_any: Any = item.get("content")
        if not isinstance(content_b64_any, str):
            logger.warning("Inline base64 content for '%s' is not a string. Skipping.", display_path)
            return None
        content_b64: str = content_b64_any
        try:
            estimated_decoded_size = len(content_b64) * BASE64_SIZE_RATIO
            if estimated_decoded_size > max_file_size * BASE64_SIZE_BUFFER:
                logger.info(
                    "Skipping '%s': Estimated Base64 size %.0f is too large (limit %d).",
                    display_path,
                    estimated_decoded_size,
                    max_file_size,
                )
                return None
            decoded_bytes = base64.b64decode(content_b64, validate=True)
            return decoded_bytes.decode("utf-8", errors="replace")
        except (binascii.Error, ValueError, UnicodeDecodeError) as e:
            logger.warning("Failed to decode inline base64 for '%s': %s", display_path, e)
    return None


def _try_fetch_blob_api(
    item: GitHubApiItem, headers: HeadersDict, max_file_size: int, display_path: str
) -> Optional[str]:
    """Attempt to fetch content using the blob API URL from a GitHub API item.

    This is typically a fallback if 'download_url' or inline content is not available/suitable.
    Checks estimated decoded size from base64 content if present.

    Args:
        item: Dictionary representing a file item from GitHub API, expected to have a 'url' key.
        headers: HTTP headers for the request.
        max_file_size: Maximum allowed file size in bytes for the decoded content.
        display_path: Path of the item used for logging purposes.

    Returns:
        Decoded file content as a string if successful and within size limits, otherwise None.
    """
    _ensure_requests_available()
    assert requests is not None
    blob_url_any: Any = item.get("url")
    if isinstance(blob_url_any, str) and blob_url_any:
        blob_url: str = blob_url_any
        try:
            logger.debug("Fetching blob API for '%s' from URL: %s", display_path, blob_url)
            blob_resp = requests.get(blob_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            blob_resp.raise_for_status()
            blob_data: dict[str, Any] = blob_resp.json()

            if blob_data.get("encoding") == "base64":
                blob_content_b64_any: Any = blob_data.get("content")
                if not isinstance(blob_content_b64_any, str):
                    logger.warning("Blob API base64 content for '%s' not string. Skipping.", display_path)
                    return None
                blob_content_b64: str = blob_content_b64_any

                estimated_decoded_size = len(blob_content_b64) * BASE64_SIZE_RATIO
                if estimated_decoded_size > max_file_size * BASE64_SIZE_BUFFER:
                    logger.info(
                        "Skipping '%s': Estimated blob API size %.0f > limit %d",
                        display_path,
                        estimated_decoded_size,
                        max_file_size,
                    )
                    return None
                try:
                    decoded_bytes = base64.b64decode(blob_content_b64, validate=True)
                    return decoded_bytes.decode("utf-8", errors="replace")
                except (binascii.Error, ValueError, UnicodeDecodeError) as e_decode:
                    logger.warning("Failed to decode base64 blob for '%s': %s", display_path, e_decode)
            else:
                logger.warning(
                    "Blob API content for '%s' has unexpected encoding: %s", display_path, blob_data.get("encoding")
                )
        except requests.exceptions.RequestException as e_req:
            logger.warning("Failed blob API fetch for '%s': %s", display_path, e_req)
        except json.JSONDecodeError as e_json:
            logger.warning("Failed to decode blob API JSON for '%s': %s", display_path, e_json)
    return None


def _check_content_size(content: str, max_file_size: int, display_path: str) -> Optional[str]:
    """Check if the size of the decoded content string exceeds the maximum file size.

    Args:
        content: The decoded file content as a string.
        max_file_size: Maximum allowed file size in bytes.
        display_path: Path of the file, used for logging purposes.

    Returns:
        The original content string if its UTF-8 byte size is within the limit,
        otherwise None.
    """
    try:
        content_bytes = content.encode("utf-8")
        if len(content_bytes) > max_file_size:
            logger.info("Skipping '%s': Actual size %d > limit %d", display_path, len(content_bytes), max_file_size)
            return None
        return content
    except UnicodeEncodeError as e:
        logger.warning("Error encoding content for size check '%s': %s. Skipping.", display_path, e)
        return None


def _fetch_content_via_api(item: GitHubApiItem, headers: HeadersDict, max_file_size: int) -> Optional[str]:
    """Fetch and decode content for a single file item from GitHub API response.

    Tries fetching via 'download_url', then from inline base64 'content',
    and finally via the blob API URL specified in 'url'. Performs size checks.

    Args:
        item: Dictionary representing a file item from the GitHub API.
        headers: HTTP headers to use for API requests.
        max_file_size: Maximum allowed file size in bytes.

    Returns:
        The file content as a string if successfully fetched and within size limits,
        otherwise None.
    """
    display_path = str(item.get("path", "unknown_file"))

    content = _try_fetch_download_url(item, headers, display_path)
    if content is not None:
        return _check_content_size(content, max_file_size, display_path)

    content = _try_fetch_inline_base64(item, max_file_size, display_path)
    if content is not None:
        return _check_content_size(content, max_file_size, display_path)

    content = _try_fetch_blob_api(item, headers, max_file_size, display_path)
    if content is not None:
        return _check_content_size(content, max_file_size, display_path)

    logger.warning("Could not determine valid download method for file '%s'.", display_path)
    return None


def _handle_rate_limit(response: Any) -> None:
    """Handle GitHub API rate limit errors by waiting until the reset time.

    Args:
        response: The `requests.Response` object that indicated a rate limit.
    """
    reset_timestamp: int = 0
    try:
        if hasattr(response, "headers") and hasattr(response.headers, "get"):
            reset_timestamp_str = response.headers.get("X-RateLimit-Reset", "0")
            reset_timestamp = int(reset_timestamp_str)
        else:
            logger.warning("Rate limit response missing or has invalid 'headers' attribute.")
    except (ValueError, TypeError) as e_parse_header:
        logger.warning("Could not parse X-RateLimit-Reset header: %s", e_parse_header)

    current_time = int(time.time())
    wait_time = max(1, min(60, (reset_timestamp - current_time))) if reset_timestamp > current_time else 60
    logger.warning("GitHub API rate limit exceeded. Waiting for %d seconds...", wait_time)
    time.sleep(wait_time)


def _process_api_item(  # noqa: C901, PLR0912
    item: GitHubApiItem,
    specific_path: str,
    headers: HeadersDict,
    include_patterns: PatternsSet,
    exclude_patterns: PatternsSet,
    max_file_size: int,
    *,
    use_relative_paths: bool,
    files: FilePathContentDict,
    skipped_files_info: list[SkippedFileInfo],
    path_stack: list[str],
) -> None:
    """Process a single item (file or directory) from the GitHub API contents response.

    If it's a file, it's fetched (if filters pass). If it's a directory, it's added to the stack.

    Args:
        item: The GitHub API item dictionary.
        specific_path: The initial specific path requested in the repository, used as a base for relative paths.
        headers: HTTP headers for API requests.
        include_patterns: Glob patterns for including files.
        exclude_patterns: Glob patterns for excluding files/directories.
        max_file_size: Maximum allowed file size in bytes.
        use_relative_paths: If True, keys in the `files` dict will be relative to `specific_path`.
        files: Dictionary to populate with successfully fetched file paths and content.
        skipped_files_info: List to record files skipped due to size.
        path_stack: Stack (list) for directories to be processed.
    """
    item_api_path: Optional[str] = item.get("path")
    item_name: Optional[str] = item.get("name")
    item_type: Optional[str] = item.get("type")

    if not (item_api_path and item_name and item_type):
        logger.warning("Skipping item with missing path, name, or type: %s", item)
        return

    display_path_str: str
    base_path_for_relative = Path(specific_path.strip("/")) if specific_path else Path()

    if use_relative_paths:
        try:
            if item_api_path == specific_path.strip("/"):  # Item is the specific_path itself (likely a file)
                display_path_str = Path(item_api_path).name
            else:
                display_path_str = str(Path(item_api_path).relative_to(base_path_for_relative))
        except ValueError:  # item_api_path is not under specific_path, use full path
            display_path_str = item_api_path
    else:
        display_path_str = item_api_path

    if display_path_str == ".":  # Avoids issues if specific_path was the item itself
        return

    display_path_norm = display_path_str.replace(os.sep, "/")

    # Filtering should ideally use item_api_path for consistency,
    # as display_path_norm might be relative.
    if not _should_include_file(item_api_path, item_name, include_patterns, exclude_patterns):
        return

    if item_type == "file":
        file_size_any: Any = item.get("size", 0)
        file_size: int = file_size_any if isinstance(file_size_any, int) and file_size_any >= 0 else 0

        if file_size > max_file_size:
            skipped_files_info.append((display_path_norm, file_size))
            return  # Do not attempt to fetch if API reports size > max_file_size
        file_content = _fetch_content_via_api(item, headers, max_file_size)
        if file_content is not None:
            files[display_path_norm] = file_content
    elif item_type == "dir":
        path_stack.append(item_api_path)  # Add full API path of the directory to stack
    elif item_type == "symlink":
        logger.info("Skipping symlink: '%s'", display_path_norm)
    elif item_type == "submodule":
        logger.info("Skipping submodule: '%s'", display_path_norm)
    else:
        logger.warning("Unknown item type '%s' for path '%s'", item_type, display_path_norm)


def _fetch_github_api_contents(
    api_url: str, headers: HeadersDict, ref: Optional[str]
) -> Union[GitHubApiContents, GitHubApiItem]:
    """Fetch contents from a given GitHub API URL.

    Handles common HTTP errors and rate limiting.

    Args:
        api_url: The full API URL to fetch.
        headers: HTTP headers for the request.
        ref: Optional Git reference (branch, tag, commit).

    Returns:
        The JSON response from the API (either a list of items or a single item).

    Raises:
        GithubApiError: If the API request fails or returns an unexpected error,
                        including specific status codes for common issues.
    """
    assert requests is not None
    params = {"ref": ref} if ref else {}
    logger.debug("Fetching GitHub API URL: %s with ref: %s", api_url, ref or "default")
    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
        if response.status_code == HTTP_STATUS_TOO_MANY_REQUESTS or (
            response.status_code == HTTP_STATUS_FORBIDDEN and "rate limit exceeded" in response.text.lower()
        ):
            _handle_rate_limit(response)  # This function blocks and waits
            # After waiting, the original request should be retried by the caller.
            raise GithubApiError(f"Rate limit hit for {api_url}, retry suggested.", status_code=response.status_code)

        response.raise_for_status()  # Raises HTTPError for other 4xx/5xx
        return response.json()  # type: ignore[no-any-return] # requests.Response.json() returns Any
    except requests.exceptions.Timeout:
        raise GithubApiError(f"Timeout fetching GitHub API URL: {api_url}") from None
    except requests.exceptions.HTTPError as e_http:
        status_code = e_http.response.status_code
        if status_code == HTTP_STATUS_NOT_FOUND:
            msg = f"Path not found via API: {api_url}" + (f" at ref '{ref}'" if ref else "")
            raise GithubApiError(msg, status_code=status_code) from e_http
        if status_code == HTTP_STATUS_UNAUTHORIZED:
            raise GithubApiError(
                "GitHub API Error 401: Unauthorized. Check token.", status_code=status_code
            ) from e_http
        raise GithubApiError(
            f"HTTP error fetching '{api_url}' (Status: {status_code}): {e_http!s}", status_code=status_code
        ) from e_http
    except requests.exceptions.RequestException as e_req:  # Other requests-related errors
        raise GithubApiError(f"Request error fetching '{api_url}': {e_req!s}") from e_req
    except json.JSONDecodeError as e_json_decode:
        raise GithubApiError(f"Invalid JSON response from GitHub API URL: {api_url}") from e_json_decode


def _fetch_github_api(
    owner: str,
    repo: str,
    specific_path: str,
    ref: Optional[str],
    token: Optional[str],
    include_patterns: PatternsSet,
    exclude_patterns: PatternsSet,
    max_file_size: int,
    *,
    use_relative_paths: bool,
) -> FilePathContentDict:
    """Fetch files recursively using the GitHub Contents API by iteratively processing a path stack.

    Args:
        owner: The owner of the GitHub repository.
        repo: The name of the GitHub repository.
        specific_path: The initial path within the repository to start crawling (can be empty for root).
        ref: The Git reference (branch, tag, or commit SHA) to use.
        token: Optional GitHub API token for authentication.
        include_patterns: A set of glob patterns for files/paths to include.
        exclude_patterns: A set of glob patterns for files/paths to exclude.
        max_file_size: Maximum file size in bytes.
        use_relative_paths: If True, keys in the returned dictionary are relative to `specific_path`.

    Returns:
        A dictionary mapping file paths to their content.

    Raises:
        GithubApiError: If a critical API error occurs (e.g., 401 Unauthorized, 404 Not Found for initial path).
        ImportError: If 'requests' library is not available.
    """
    _ensure_requests_available()
    headers: HeadersDict = {"Accept": "application/vnd.github.v3+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    files: FilePathContentDict = {}
    skipped_files_info: list[SkippedFileInfo] = []
    path_stack: list[str] = [specific_path.strip("/")]  # Normalize initial path

    while path_stack:
        current_api_path = path_stack.pop()
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{current_api_path}"
        try:
            contents_response = _fetch_github_api_contents(api_url, headers, ref)
            items_to_process: GitHubApiContents = (
                contents_response if isinstance(contents_response, list) else [contents_response]
            )
            for item in items_to_process:
                _process_api_item(
                    item,
                    specific_path,
                    headers,
                    include_patterns,
                    exclude_patterns,
                    max_file_size,
                    use_relative_paths=use_relative_paths,
                    files=files,
                    skipped_files_info=skipped_files_info,
                    path_stack=path_stack,
                )
        except GithubApiError as e:
            # If rate limit was hit, _fetch_github_api_contents waited and re-raised.
            # Re-add to stack to try again after the wait.
            if e.status_code == HTTP_STATUS_TOO_MANY_REQUESTS or (
                e.status_code == HTTP_STATUS_FORBIDDEN and e.args and "rate limit" in str(e.args[0]).lower()
            ):
                logger.info("Rate limit encountered for '%s', re-adding to stack after wait.", current_api_path)
                path_stack.append(current_api_path)
                continue  # Allow main loop to continue, will try this path later
            logger.error("API Error processing path '%s': %s", current_api_path, e)
            if e.status_code in (
                HTTP_STATUS_UNAUTHORIZED,
                HTTP_STATUS_NOT_FOUND,
            ) and current_api_path == specific_path.strip("/"):
                # If the initial specific_path is not found or unauthorized, it's a critical error.
                raise
            # For other errors on sub-paths, log and continue with other paths in the stack.
        except Exception as e_generic:
            logger.error("Unexpected error processing API path '%s': %s", current_api_path, e_generic, exc_info=True)

    if skipped_files_info:
        logger.info("Skipped %d files due to size limits via API.", len(skipped_files_info))
    return files


def _process_cloned_file(
    abs_filepath: Path,
    repo_root: Path,
    walk_base_path: Path,
    include_patterns: PatternsSet,
    exclude_patterns: PatternsSet,
    max_file_size: int,
    *,
    use_relative_paths: bool,
) -> Optional[tuple[str, str]]:
    """Process a single file found during a Git clone directory walk.

    Checks filters, size, and reads content.

    Args:
        abs_filepath: Absolute path to the file.
        repo_root: Absolute path to the root of the cloned repository.
        walk_base_path: The path from which `os.walk` started (repo_root or a subdirectory).
        include_patterns: Glob patterns for files to include.
        exclude_patterns: Glob patterns for files/dirs to exclude.
        max_file_size: Maximum file size in bytes.
        use_relative_paths: If True, the returned path is relative to `walk_base_path`.
                            Otherwise, it's relative to `repo_root`.

    Returns:
        A tuple (display_path, content) if the file is included and readable,
        otherwise None.
    """
    filename = abs_filepath.name
    try:
        # Path for filtering is always relative to the actual root of the scanned portion
        path_for_filtering: Path = abs_filepath.relative_to(walk_base_path)
    except ValueError:
        logger.warning("Could not make '%s' relative to walk base '%s'. Skipping.", abs_filepath, walk_base_path)
        return None
    path_for_filtering_norm: str = str(path_for_filtering).replace(os.sep, "/")

    display_path_obj: Path
    if use_relative_paths:
        display_path_obj = path_for_filtering  # Relative to where the crawl started
    else:  # Relative to the absolute repo root
        try:
            display_path_obj = abs_filepath.relative_to(repo_root)
        except ValueError:
            logger.warning("Could not make '%s' relative to repo root '%s'. Using absolute.", abs_filepath, repo_root)
            display_path_obj = abs_filepath  # Fallback, less ideal
    display_path: str = str(display_path_obj).replace(os.sep, "/")

    if not _should_include_file(path_for_filtering_norm, filename, include_patterns, exclude_patterns):
        return None
    try:
        file_size = abs_filepath.stat().st_size
        if file_size > max_file_size:
            # Skipped files are counted in the calling function
            return None
    except OSError as e_size:
        logger.warning("Could not get size for '%s': %s. Skipping.", display_path, e_size)
        return None
    try:
        return display_path, abs_filepath.read_text(encoding="utf-8", errors="replace")
    except OSError as e_read:
        logger.warning("Failed to read '%s': %s. Skipping.", display_path, e_read)
        return None
    except UnicodeDecodeError as e_decode:
        logger.warning("Unicode decode error reading '%s': %s. Skipping.", display_path, e_decode)
        return None


def _perform_git_clone_and_checkout(repo_url: str, ref: Optional[str], target_dir: Path) -> None:
    """Perform git clone and checkout operations.

    Args:
        repo_url: URL of the repository to clone.
        ref: Optional Git reference (branch, tag, commit SHA) to checkout.
        target_dir: The local directory path where the repository will be cloned.

    Raises:
        GithubApiError: If cloning or checkout fails.
        ImportError: If GitPython is not available.
    """
    _ensure_gitpython_available()
    assert git is not None
    logger.info("Cloning Git repo '%s' (ref: %s) to '%s'...", repo_url, ref or "default", target_dir)
    try:
        repo_obj = git.Repo.clone_from(repo_url, str(target_dir), depth=GIT_CLONE_DEPTH)
        if ref:
            try:
                repo_obj.git.checkout(ref)
                logger.info("Checked out ref: %s", ref)
            except git.GitCommandError as e_checkout:
                stderr_val = getattr(e_checkout, "stderr", str(e_checkout))
                raise GithubApiError(f"Failed checkout ref '{ref}': {stderr_val}") from e_checkout
    except git.GitCommandError as e_clone:
        stderr_val = getattr(e_clone, "stderr", str(e_clone)).lower()
        if "authentication failed" in stderr_val or "could not read" in stderr_val or "not found" in stderr_val:
            raise GithubApiError(f"Auth failed or repo not found for '{repo_url}'. Details: {stderr_val}") from e_clone
        raise GithubApiError(f"Failed clone repo '{repo_url}': {stderr_val}") from e_clone


def _clone_and_walk_repo(
    repo_url: str,
    ref: Optional[str],
    subdir_in_repo: Optional[str],
    include_patterns: PatternsSet,
    exclude_patterns: PatternsSet,
    max_file_size: int,
    *,
    use_relative_paths: bool,
) -> FilePathContentDict:
    """Clone a Git repository temporarily and walk the specified subdirectory (or root).

    Args:
        repo_url: URL of the repository.
        ref: Optional Git reference to checkout.
        subdir_in_repo: Optional subdirectory within the repo to crawl. If None, crawls from repo root.
        include_patterns: Patterns for files to include.
        exclude_patterns: Patterns for files/dirs to exclude.
        max_file_size: Maximum file size.
        use_relative_paths: If True, keys in the result are relative to `subdir_in_repo`
                            (or repo root if `subdir_in_repo` is None).

    Returns:
        A dictionary mapping file paths to their content.

    Raises:
        GithubApiError: For errors during cloning, checkout, or walking the directory.
        ImportError: If GitPython is not available.
    """
    files: FilePathContentDict = {}
    skipped_file_count = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root_abs = Path(tmpdir)
        try:
            _perform_git_clone_and_checkout(repo_url, ref, repo_root_abs)
            walk_start_abs_path = repo_root_abs / subdir_in_repo if subdir_in_repo else repo_root_abs

            if not walk_start_abs_path.is_dir():
                err_msg = f"Subdirectory '{subdir_in_repo}' not found in cloned repo at '{walk_start_abs_path}'."
                raise GithubApiError(err_msg)
            logger.info("Walking directory: '%s'", walk_start_abs_path)

            for current_os_walk_root, _dirs, dir_files in os.walk(walk_start_abs_path):
                current_os_walk_root_path = Path(current_os_walk_root)
                for filename in dir_files:
                    abs_filepath = current_os_walk_root_path / filename
                    if abs_filepath.is_file():
                        result = _process_cloned_file(
                            abs_filepath=abs_filepath,
                            repo_root=repo_root_abs,
                            walk_base_path=walk_start_abs_path,
                            include_patterns=include_patterns,
                            exclude_patterns=exclude_patterns,
                            max_file_size=max_file_size,
                            use_relative_paths=use_relative_paths,
                        )
                        if result:
                            files[result[0]] = result[1]
                        else:
                            skipped_file_count += 1
        except GithubApiError:  # Re-raise specific errors from clone/checkout
            raise
        except OSError as e_os:  # Catch OS errors during temp dir operations or os.walk
            raise GithubApiError(f"OS error during git clone/walk: {e_os!s}") from e_os
        except Exception as e_other:  # Broad catch for truly unexpected errors
            logger.error("Unexpected error during Git clone and walk: %s", e_other, exc_info=True)
            raise GithubApiError(f"Unexpected error during git clone/walk: {e_other!s}") from e_other

    if skipped_file_count > 0:
        logger.info(
            "Skipped %d files due to size limits, filters, or read errors during clone walk.", skipped_file_count
        )
    return files


def _parse_github_url_http(parsed_url: Any, path_components: list[str]) -> ParsedGitHubUrl:
    """Parse HTTP/HTTPS GitHub URLs.

    Args:
        parsed_url: The result of urllib.parse.urlparse.
        path_components: List of path components from the URL.

    Returns:
        A tuple (owner, repo_name, ref, specific_path).

    Raises:
        ValueError: If the URL is malformed.
    """
    owner: Optional[str] = None
    repo_name: Optional[str] = None
    ref: Optional[str] = None
    specific_path: str = ""

    if len(path_components) < MIN_HTTP_PATH_PARTS:
        raise ValueError("Invalid GitHub HTTP URL path: missing owner/repo.")
    owner, repo_name_with_git = path_components[0], path_components[1]
    if not repo_name_with_git:  # Check if it's an empty string
        raise ValueError("Repository name part is empty in URL.")
    repo_name = repo_name_with_git.removesuffix(".git")

    if len(path_components) > REF_PATH_MIN_PARTS and path_components[2] in ("tree", "blob"):
        ref = path_components[3]
        specific_path = "/".join(path_components[4:])
    elif len(path_components) > MIN_HTTP_PATH_PARTS:
        specific_path = "/".join(path_components[MIN_HTTP_PATH_PARTS:])
    return owner, repo_name, ref, specific_path


def _parse_github_url_ssh(parsed_url: Any) -> ParsedGitHubUrl:
    """Parse SSH GitHub URLs.

    Args:
        parsed_url: The result of urllib.parse.urlparse.

    Returns:
        A tuple (owner, repo_name, ref, specific_path).

    Raises:
        ValueError: If the URL is malformed.
    """
    owner: Optional[str] = None
    repo_name: Optional[str] = None
    specific_path: str = ""

    path_part_raw: Optional[str] = parsed_url.path
    if not path_part_raw:
        raise ValueError("SSH URL path component is missing.")
    path_part: str = path_part_raw

    if ":" in path_part and not path_part.startswith("/"):
        path_part = path_part.split(":", 1)[1]

    path_components = path_part.strip("/").split("/")

    if len(path_components) >= MIN_SSH_PATH_PARTS:
        owner = path_components[0]
        repo_name_with_git_ssh = path_components[1]
        if not repo_name_with_git_ssh:
            raise ValueError("Repository name part is empty in SSH URL.")
        repo_name = repo_name_with_git_ssh.removesuffix(".git")

        if len(path_components) > MIN_SSH_PATH_PARTS:
            specific_path = "/".join(path_components[MIN_SSH_PATH_PARTS:])
    else:
        raise ValueError("Could not parse owner/repo from SSH URL.")
    return owner, repo_name, None, specific_path


def _parse_github_url(repo_url: str) -> ParsedGitHubUrl:
    """Parse GitHub URL into owner, repo_name, ref, and specific_path.

    Args:
        repo_url: The GitHub repository URL.

    Returns:
        A tuple containing owner, repository name, ref (branch/tag/commit),
        and specific path within the repository.

    Raises:
        ValueError: If the URL cannot be parsed or is unsupported.
    """
    parsed_url = urlparse(repo_url)
    owner: Optional[str] = None
    repo_name: Optional[str] = None
    ref: Optional[str] = None
    specific_path: str = ""

    try:
        if repo_url.startswith("git@"):
            owner, repo_name, ref, specific_path = _parse_github_url_ssh(parsed_url)
        elif parsed_url.netloc and "github.com" in parsed_url.netloc.lower():
            path_components_str: Optional[str] = parsed_url.path
            if not path_components_str:
                raise ValueError("HTTP URL path component is missing.")
            path_components: list[str] = path_components_str.strip("/").split("/")
            owner, repo_name, ref, specific_path = _parse_github_url_http(parsed_url, path_components)
        else:
            raise ValueError("Unsupported repository URL format or non-GitHub host.")

        if not owner or not repo_name:
            raise ValueError("Failed to extract owner and repository name after parsing attempt.")
        return owner, repo_name, ref, specific_path
    except (ValueError, IndexError, AttributeError) as e_parse_url:
        raise ValueError(f"Could not parse GitHub URL '{repo_url}': {e_parse_url!s}") from e_parse_url


def crawl_github_repo(
    repo_url: str,
    token: Optional[str] = None,
    max_file_size: int = 1048576,
    include_patterns: PatternsSet = None,
    exclude_patterns: PatternsSet = None,
    *,
    use_relative_paths: bool = True,
    prefer_api: bool = True,
) -> FilePathContentDict:
    """Crawl files from a GitHub repository using API or Git clone.

    Args:
        repo_url: URL of the GitHub repository.
        token: Optional GitHub API token for private repos or higher rate limits.
        max_file_size: Maximum file size in bytes to fetch.
        include_patterns: Glob patterns for files/paths to include.
        exclude_patterns: Glob patterns for files/paths to exclude.
        use_relative_paths: If True, file paths in the result dict are relative
                            to the `specific_path` identified in the URL (or repo root).
                            If False (relevant for clone), paths are relative to the cloned repo root.
        prefer_api: If True (default), attempts to use GitHub API first. Falls back
                    to Git clone if API fails. If False, or if URL is SSH, uses Git clone.

    Returns:
        A dictionary mapping file paths to their string content.

    Raises:
        ValueError: If the repository URL is invalid.
        GithubApiError: For errors during API fetching or Git cloning.
        ImportError: If required libraries (requests, GitPython) are not installed.
    """
    logger.info("Starting GitHub crawl for: %s", repo_url)
    log_args = (
        f"Params: max_size={max_file_size}, include={include_patterns}, "
        f"exclude={exclude_patterns}, relative={use_relative_paths}, "
        f"prefer_api={prefer_api}, token_present={bool(token)}"
    )
    logger.info(log_args)

    owner, repo_name, ref, specific_path = _parse_github_url(repo_url)
    logger.info("Parsed URL: owner=%s, repo=%s, ref=%s, path_in_repo='%s'", owner, repo_name, ref, specific_path)

    assert owner is not None, "Owner should be parsed by _parse_github_url"
    assert repo_name is not None, "Repo name should be parsed by _parse_github_url"

    is_ssh = repo_url.startswith("git@")
    use_api_method = prefer_api and not is_ssh

    if use_api_method:
        try:
            logger.info("Attempting GitHub API fetch for '%s/%s'...", owner, repo_name)
            return _fetch_github_api(
                owner=owner,
                repo=repo_name,
                specific_path=specific_path,
                ref=ref,
                token=token,
                include_patterns=include_patterns,
                exclude_patterns=exclude_patterns,
                max_file_size=max_file_size,
                use_relative_paths=use_relative_paths,
            )
        except GithubApiError as e_api:
            logger.warning("GitHub API fetch failed: %s. Falling back to Git clone if applicable.", e_api)
        except ImportError as e_imp_api:  # e.g. requests not installed
            logger.error("Missing library for GitHub API operation: %s. Trying Git clone if applicable.", e_imp_api)
        # If API fails for any reason, code execution will proceed to clone attempt below.

    # Attempt Git clone if API was not used, or if API failed
    if not GITPYTHON_AVAILABLE:  # Check moved here so API can be attempted even if GitPython is missing
        logger.error("GitPython not available, cannot perform Git clone.")
        # If API was preferred and failed, and GitPython is also missing, then raise.
        # If API was not preferred, this is the first point of failure.
        raise ImportError("GitPython is required for clone operations but is not installed.")

    logger.info("Attempting Git clone for '%s'...", repo_url)
    try:
        return _clone_and_walk_repo(
            repo_url=repo_url,
            ref=ref,
            subdir_in_repo=specific_path or None,
            include_patterns=include_patterns,
            exclude_patterns=exclude_patterns,
            max_file_size=max_file_size,
            use_relative_paths=use_relative_paths,
        )
    except (GithubApiError, ImportError) as e_clone:
        logger.error("Git clone operation failed: %s", e_clone)
        raise
    except OSError as e_os:
        logger.exception("OS error during Git clone operation.")
        raise GithubApiError(f"OS error during Git clone: {e_os!s}") from e_os
    except Exception as e_unhandled_clone:
        logger.exception("Unexpected error during Git clone operation.")
        raise GithubApiError(f"Unexpected Git clone error: {e_unhandled_clone!s}") from e_unhandled_clone


# End of src/sourcelens/utils/github.py
