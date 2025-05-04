"""Utilities for fetching and processing code from GitHub repositories.

Includes functions for parsing GitHub URLs, crawling repositories via API or Git clone,
filtering files based on patterns and size, and handling potential errors like
rate limits or authentication issues. Uses pathlib and modern Python features.
"""

import base64
import fnmatch
import json
import logging
import os
import tempfile
import time
from pathlib import Path
from typing import Any, Optional, TypeAlias  # Import Any
from urllib.parse import urlparse

try:
    import git  # type: ignore[import-untyped]
    GITPYTHON_AVAILABLE = True
except ImportError:
    git = None # type: ignore[assignment]
    GITPYTHON_AVAILABLE = False

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    requests = None # type: ignore[assignment]
    REQUESTS_AVAILABLE = False


logger = logging.getLogger(__name__)

# Constants
GITHUB_API_BASE = "https://api.github.com"
HTTP_STATUS_OK = 200
HTTP_STATUS_NOT_FOUND = 404
HTTP_STATUS_FORBIDDEN = 403
HTTP_STATUS_UNAUTHORIZED = 401
HTTP_STATUS_TOO_MANY_REQUESTS = 429
DEFAULT_TIMEOUT = 30
GIT_CLONE_DEPTH = 1
BASE64_SIZE_RATIO = 0.75
BASE64_SIZE_BUFFER = 1.1
MIN_SSH_PATH_PARTS = 2
MIN_HTTP_PATH_PARTS = 2
REF_PATH_MIN_PARTS = 3

# Type Aliases
FilePathContentDict: TypeAlias = dict[str, str]
PatternsSet: TypeAlias = Optional[set[str]]
SkippedFileInfo: TypeAlias = tuple[str, int]
HeadersDict: TypeAlias = dict[str, str]

class GithubApiError(Exception):
    """Custom exception for GitHub API or cloning errors."""

    pass

# Helper Functions
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
    """Determine if a file should be included based on patterns."""
    file_path_norm = file_path.replace(os.sep, '/')
    if exclude_patterns and any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in exclude_patterns):
        return False
    if include_patterns:
        matches_include = any(fnmatch.fnmatchcase(filename, pattern) for pattern in include_patterns) or \
                          any(fnmatch.fnmatchcase(file_path_norm, pattern) for pattern in include_patterns)
        if not matches_include:
            return False
    return True

def _try_fetch_download_url(item: dict[str, Any], headers: HeadersDict, display_path: str) -> Optional[str]:
    """Attempt to fetch content using the 'download_url'."""
    _ensure_requests_available()
    if download_url := item.get("download_url"):
        try:
            response = requests.get(download_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            response.raise_for_status()
            try: return response.text
            except UnicodeDecodeError: return response.content.decode('utf-8', errors='replace')
        except requests.exceptions.RequestException as e: logger.warning("Failed download_url fetch for '%s': %s", display_path, e)
    return None

def _try_fetch_inline_base64(item: dict[str, Any], max_file_size: int, display_path: str) -> Optional[str]:
    """Attempt to fetch content from inline 'content' field (base64)."""
    if item.get("encoding") == "base64" and (content_b64 := item.get("content")):
        if not isinstance(content_b64, str): # Ensure content is a string before len()
             logger.warning("Inline base64 content for '%s' is not a string. Skipping.", display_path)
             return None
        try:
            estimated_size = len(content_b64) * BASE64_SIZE_RATIO
            if estimated_size > max_file_size * BASE64_SIZE_BUFFER:
                logger.info("Skipping '%s': Estimated Base64 size %.0f > limit %d", display_path, estimated_size, max_file_size)
                return None
            # Decode base64 content
            decoded_bytes = base64.b64decode(content_b64, validate=True)
            # Decode bytes to string using UTF-8
            return decoded_bytes.decode('utf-8', errors='replace')
        except (base64.binascii.Error, ValueError, UnicodeDecodeError) as e:
            logger.warning("Failed to decode inline base64 for '%s': %s", display_path, e)
    return None

def _try_fetch_blob_api(item: dict[str, Any], headers: HeadersDict, max_file_size: int, display_path: str) -> Optional[str]:
    """Attempt to fetch content using the blob API URL."""
    _ensure_requests_available()
    if blob_url := item.get("url"):
        try:
            logger.debug("Fetching blob API for '%s'", display_path)
            blob_resp = requests.get(blob_url, headers=headers, timeout=DEFAULT_TIMEOUT)
            blob_resp.raise_for_status()
            blob_data = blob_resp.json()
            if blob_data.get("encoding") == "base64" and (blob_content_b64 := blob_data.get("content")):
                if not isinstance(blob_content_b64, str):
                    logger.warning("Blob API base64 content for '%s' not string. Skipping.", display_path)
                    return None
                estimated_size = len(blob_content_b64) * BASE64_SIZE_RATIO
                if estimated_size > max_file_size * BASE64_SIZE_BUFFER:
                    log_msg = (f"Skipping '{display_path}': Estimated blob size {estimated_size:.0f} > limit {max_file_size}")
                    logger.info(log_msg)
                    return None
                try:
                    decoded_bytes = base64.b64decode(blob_content_b64, validate=True)
                    return decoded_bytes.decode('utf-8', errors='replace')
                except (base64.binascii.Error, ValueError, UnicodeDecodeError) as e:
                    logger.warning("Failed decode base64 blob for '%s': %s", display_path, e)
            else:
                log_msg = (f"Blob API content for '{display_path}' unexpected: {blob_data.get('encoding')}")
                logger.warning(log_msg)
        except requests.exceptions.RequestException as e: logger.warning("Failed blob API fetch for '%s': %s", display_path, e)
        except json.JSONDecodeError as e: logger.warning("Failed decode blob API JSON for '%s': %s", display_path, e)
    return None

def _check_content_size(content: str, max_file_size: int, display_path: str) -> Optional[str]:
    """Check decoded content size against the limit."""
    try:
        content_bytes = content.encode('utf-8')
        if len(content_bytes) > max_file_size:
             logger.info("Skipping '%s': Actual size %d > limit %d", display_path, len(content_bytes), max_file_size)
             return None
        return content
    except Exception as e:
        logger.warning("Error encoding content for size check '%s': %s", display_path, e)
        return None

def _fetch_content_via_api(item: dict[str, Any], headers: HeadersDict, max_file_size: int) -> Optional[str]:
    """Fetch and decode content for a single file item from GitHub API response."""
    _ensure_requests_available()
    display_path = item.get("path", "unknown_file")
    content = _try_fetch_download_url(item, headers, display_path)
    if content is not None: return _check_content_size(content, max_file_size, display_path)
    content = _try_fetch_inline_base64(item, max_file_size, display_path)
    if content is not None: return _check_content_size(content, max_file_size, display_path)
    content = _try_fetch_blob_api(item, headers, max_file_size, display_path)
    if content is not None: return _check_content_size(content, max_file_size, display_path)
    logger.warning("Could not determine download method for '%s'.", display_path)
    return None

# Corrected type hint using Any
def _handle_rate_limit(response: Any) -> None: # Expects requests.Response object
    """Handle GitHub API rate limit errors by waiting."""
    reset_timestamp = 0
    try:
        if hasattr(response, 'headers') and isinstance(response.headers, dict):
            reset_timestamp = int(response.headers.get('X-RateLimit-Reset', 0))
        else: logger.warning("Rate limit response missing 'headers'.")
    except (ValueError, TypeError): logger.warning("Could not parse X-RateLimit-Reset header.")
    current_time = time.time()
    wait_time = max(1, min(60, reset_timestamp - current_time)) if reset_timestamp > 0 else 60
    logger.warning("GitHub rate limit exceeded. Waiting for %.0f seconds...", wait_time)
    time.sleep(wait_time)

def _fetch_github_api(
    owner: str, repo: str, specific_path: str, ref: Optional[str], token: Optional[str],
    include_patterns: PatternsSet, exclude_patterns: PatternsSet, max_file_size: int,
    *, use_relative_paths: bool,
) -> FilePathContentDict:
    """Fetch files recursively using the GitHub Contents API (Iterative)."""
    _ensure_requests_available()
    headers: HeadersDict = {"Accept": "application/vnd.github.v3+json"}
    if token: headers["Authorization"] = f"Bearer {token}"
    files: FilePathContentDict = {}; skipped_files: list[SkippedFileInfo] = []
    path_stack: list[str] = [specific_path]

    while path_stack:
        current_path = path_stack.pop()
        api_url = f"{GITHUB_API_BASE}/repos/{owner}/{repo}/contents/{current_path}"
        params = {"ref": ref} if ref else {}
        logger.debug("Fetching GitHub API URL: %s with ref: %s", api_url, ref)
        try:
            response = requests.get(api_url, headers=headers, params=params, timeout=DEFAULT_TIMEOUT)
            if response.status_code in (HTTP_STATUS_FORBIDDEN, HTTP_STATUS_TOO_MANY_REQUESTS) and \
               'rate limit exceeded' in response.text.lower():
                _handle_rate_limit(response); path_stack.append(current_path); continue
            if response.status_code == HTTP_STATUS_NOT_FOUND:
                msg = f"Path '{current_path}' not found in repo '{owner}/{repo}'"
                if ref: msg += f" at ref '{ref}'"
                msg += " (Check path/ref, permissions, token)."
                raise GithubApiError(msg)
            if response.status_code == HTTP_STATUS_UNAUTHORIZED:
                 raise GithubApiError("GitHub API Error 401: Unauthorized. Check token.")
            response.raise_for_status()
        except requests.exceptions.Timeout: raise GithubApiError(f"Timeout fetching {api_url}") from None
        except requests.exceptions.RequestException as e: status = e.response.status_code if e.response else "N/A"; raise GithubApiError(f"Error fetching {current_path} (Status: {status}): {e}") from e
        try:
            contents = response.json()
            if not isinstance(contents, list): contents = [contents]
        except json.JSONDecodeError as e: raise GithubApiError(f"Invalid JSON response from {api_url}") from e

        for item in contents:
            item_path, item_name, item_type = item.get("path"), item.get("name"), item.get("type")
            if not all([item_path, item_name, item_type]): continue
            try:
                base_path_obj = Path(specific_path) if specific_path else Path()
                full_item_path_obj = Path(item_path)
                is_relative_base = ( use_relative_paths and specific_path and (base_path_obj in full_item_path_obj.parents or base_path_obj == full_item_path_obj.parent) )
                display_path = str(full_item_path_obj.relative_to(base_path_obj)) if is_relative_base else item_path
                if display_path == ".": continue
            except (ValueError, TypeError) as path_err: logger.warning("Path error for '%s': %s.", item_path, path_err); display_path = item_path
            display_path_norm = display_path.replace(os.sep, '/')
            if not _should_include_file(display_path_norm, item_name, include_patterns, exclude_patterns): continue

            if item_type == "file":
                file_size = item.get("size", 0)
                if not isinstance(file_size, int) or file_size < 0: file_size = 0
                if file_size > max_file_size: skipped_files.append((display_path_norm, file_size)); continue
                file_content = _fetch_content_via_api(item, headers, max_file_size)
                if file_content is not None: files[display_path_norm] = file_content
            elif item_type == "dir": path_stack.append(item_path)
            elif item_type == "symlink": logger.info("Skipping symlink: '%s'", display_path_norm)
            elif item_type == "submodule": logger.info("Skipping submodule: '%s'", display_path_norm)
            else: logger.warning("Unknown item type '%s': '%s'", item_type, display_path_norm)

    if skipped_files: logger.info("Skipped %d files due to size limits.", len(skipped_files))
    return files

def _process_cloned_file(
    abs_filepath: Path, repo_root: Path, walk_root: Path, include_patterns: PatternsSet,
    exclude_patterns: PatternsSet, max_file_size: int, *, use_relative_paths: bool = True,
) -> Optional[tuple[str, str]]:
    """Process a single file found during git clone walk."""
    filename = abs_filepath.name
    try:
        base_path = walk_root if use_relative_paths else repo_root
        display_path_obj = abs_filepath.relative_to(base_path)
        display_path = str(display_path_obj).replace(os.sep, '/')
    except ValueError: logger.warning("Could not get relative path for %s", abs_filepath); return None
    if not _should_include_file(display_path, filename, include_patterns, exclude_patterns): return None
    try:
        file_size = abs_filepath.stat().st_size
        if file_size > max_file_size: return None
    except OSError as e_size: logger.warning("Could not get size for '%s': %s", display_path, e_size); return None
    try: return display_path, abs_filepath.read_text(encoding="utf-8", errors='replace')
    except OSError as e_read: logger.warning("Failed to read '%s': %s", display_path, e_read); return None
    except Exception as e_other: logger.warning("Unexpected error reading '%s': %s", display_path, e_other); return None

def _clone_and_walk_repo(
    repo_url: str, ref: Optional[str], subdir: Optional[str], include_patterns: PatternsSet,
    exclude_patterns: PatternsSet, max_file_size: int, *, use_relative_paths: bool = True,
) -> FilePathContentDict:
    """Clone a Git repository temporarily and walk the specified path."""
    _ensure_gitpython_available()
    files: FilePathContentDict = {}; skipped_file_count = 0
    with tempfile.TemporaryDirectory() as tmpdir:
        repo_root = Path(tmpdir)
        logger.info("Cloning Git repo '%s' (ref: %s) to '%s'...", repo_url, ref or 'default', repo_root)
        try:
            repo_obj = git.Repo.clone_from(repo_url, repo_root, depth=GIT_CLONE_DEPTH)
            if ref:
                try: repo_obj.git.checkout(ref); logger.info("Checked out ref: %s", ref)
                except git.GitCommandError as e_checkout: stderr = getattr(e_checkout, 'stderr', str(e_checkout)); raise GithubApiError(f"Failed checkout ref '{ref}': {stderr}") from e_checkout
            walk_root = repo_root / subdir if subdir else repo_root
            if not walk_root.is_dir(): raise GithubApiError(f"Subdirectory '{subdir}' not found.")
            logger.info("Walking directory: '%s'", walk_root)
            for item_path in walk_root.rglob('*'):
                if item_path.is_file():
                    result = _process_cloned_file(abs_filepath=item_path, repo_root=repo_root, walk_root=walk_root, include_patterns=include_patterns, exclude_patterns=exclude_patterns, max_file_size=max_file_size, use_relative_paths=use_relative_paths)
                    if result: files[result[0]] = result[1]
                    else: skipped_file_count += 1
        except git.GitCommandError as e_clone:
            stderr = getattr(e_clone, 'stderr', str(e_clone)).lower()
            if 'authentication failed' in stderr or 'could not read' in stderr or 'not found' in stderr: raise GithubApiError(f"Auth failed or repo not found for '{repo_url}'.") from e_clone
            raise GithubApiError(f"Failed clone repo '{repo_url}': {stderr}") from e_clone
        except Exception as e_other: raise GithubApiError(f"Unexpected error during git clone/walk: {e_other}") from e_other
    if skipped_file_count > 0:
        log_msg = (f"Skipped {skipped_file_count} files due to size limits, filters, or read errors during clone walk.")
        logger.info(log_msg)
    return files

def crawl_github_repo(
    repo_url: str, token: Optional[str] = None, max_file_size: int = 1048576,
    include_patterns: PatternsSet = None, exclude_patterns: PatternsSet = None,
    *, use_relative_paths: bool = True, prefer_api: bool = True,
) -> FilePathContentDict:
    """Crawl files from a GitHub repository using API or Git clone."""
    logger.info("Starting GitHub crawl for: %s", repo_url)
    logger.info("Params: max_size=%d, include=%s, exclude=%s, relative=%s, prefer_api=%s, token=%s", max_file_size, include_patterns, exclude_patterns, use_relative_paths, prefer_api, bool(token))
    owner, repo_name, ref, specific_path = None, None, None, ""
    is_ssh = repo_url.startswith("git@"); parsed_url = urlparse(repo_url) # F821 fix: urlparse imported
    try:
        if is_ssh:
            path_part = parsed_url.path
            if ':' in path_part and not path_part.startswith('/'): path_part = path_part.split(':', 1)[1]
            path_parts = path_part.strip('/').removesuffix('.git').split('/')
            if len(path_parts) >= MIN_SSH_PATH_PARTS: owner, repo_name = path_parts[0], path_parts[1]
            else: raise ValueError("Could not parse owner/repo from SSH URL.")
        elif parsed_url.netloc and "github.com" in parsed_url.netloc:
            path_parts = parsed_url.path.strip('/').split('/')
            if len(path_parts) < MIN_HTTP_PATH_PARTS: raise ValueError("Invalid GitHub HTTP URL path.")
            owner, repo_name = path_parts[0], path_parts[1]
            if len(path_parts) > REF_PATH_MIN_PARTS and path_parts[2] in ('tree', 'blob'):
                ref = path_parts[3]; specific_path = "/".join(path_parts[4:])
            elif len(path_parts) > MIN_HTTP_PATH_PARTS: specific_path = "/".join(path_parts[MIN_HTTP_PATH_PARTS:])
        else: raise ValueError("Unsupported repository URL format or host.")
        logger.info("Parsed URL: owner=%s, repo=%s, ref=%s, path='%s'", owner, repo_name, ref, specific_path)
    except (ValueError, IndexError, AttributeError) as e: raise ValueError(f"Could not parse GitHub URL '{repo_url}': {e}") from e

    use_api = prefer_api and not is_ssh
    try:
        if use_api:
            logger.info("Attempting GitHub API fetch..."); return _fetch_github_api(owner=owner, repo=repo_name, specific_path=specific_path, ref=ref, token=token, include_patterns=include_patterns, exclude_patterns=exclude_patterns, max_file_size=max_file_size, use_relative_paths=use_relative_paths)
        logger.info("Attempting Git clone..."); return _clone_and_walk_repo(repo_url=repo_url, ref=ref, subdir=specific_path or None, include_patterns=include_patterns, exclude_patterns=exclude_patterns, max_file_size=max_file_size, use_relative_paths=use_relative_paths)
    except GithubApiError as e_api:
        if use_api:
             logger.warning("API fetch failed: %s. Falling back to Git clone...", e_api)
             try: return _clone_and_walk_repo(repo_url=repo_url, ref=ref, subdir=specific_path or None, include_patterns=include_patterns, exclude_patterns=exclude_patterns, max_file_size=max_file_size, use_relative_paths=use_relative_paths)
             except (GithubApiError, ImportError) as e_clone: logger.error("Git clone fallback failed: %s", e_clone); raise e_clone from e_api
             except Exception as e_clone_other: logger.exception("Unexpected clone fallback error"); raise GithubApiError(f"Unexpected clone fallback error: {e_clone_other}") from e_clone_other
        else: raise e_api
    except ImportError as e: logger.error("Missing library for GitHub op: %s", e); raise
    except Exception as e_unhandled: logger.exception("Unexpected GitHub crawl error"); raise GithubApiError(f"Unexpected crawl error: {e_unhandled}") from e_unhandled

# End of src/sourcelens/utils/github.py
