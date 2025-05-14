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

"""Node responsible for fetching source code from GitHub or local directories."""

from pathlib import Path
from typing import Any, Optional, TypedDict

from typing_extensions import TypeAlias

# Import BaseNode and SLSharedState from base_node module
from .base_node import BaseNode, SLSharedState

# Local type aliases for this node's prep/exec results
FetchPrepResult: TypeAlias = bool
"""Type alias for the result of the preparation phase of FetchCode (fetch success status)."""
FetchExecResult: TypeAlias = None
"""Type alias for the result of the execution phase of FetchCode (always None)."""

FileDataListInternal: TypeAlias = list[tuple[str, str]]
"""Type alias for a list of (filepath, content) tuples used internally."""


class _PrepContext(TypedDict):
    """Internal context for prep method sub-functions."""

    project_name: str
    repo_url: Optional[str]
    local_dir_str: Optional[str]
    include_patterns: set[str]
    exclude_patterns: set[str]
    max_file_size: int
    use_relative_paths: bool
    github_token: Optional[str]


class FetchCode(BaseNode[FetchPrepResult, FetchExecResult]):
    """Fetch source code files from GitHub or a local directory.

    This node is responsible for the initial step of acquiring the codebase
    to be analyzed. It can handle both remote GitHub repositories and local
    filesystem directories. It populates the `shared_state` with the fetched
    file data and the derived project name.
    """

    def _derive_project_name(self, shared: SLSharedState) -> str:
        """Derive a project name from repo URL or local directory path.

        Args:
            shared: The shared state dictionary.

        Returns:
            The derived or existing project name.

        Raises:
            ValueError: If project name derivation fails.
        """
        project_name_shared_any: Any = shared.get("project_name")
        project_name_shared: Optional[str] = (
            str(project_name_shared_any) if isinstance(project_name_shared_any, str) else None
        )

        if project_name_shared and project_name_shared.strip():
            self._log_info("Using provided project name: %s", project_name_shared.strip())
            return project_name_shared.strip()

        repo_url_any: Any = shared.get("repo_url")
        local_dir_str_any: Any = shared.get("local_dir")
        repo_url: Optional[str] = str(repo_url_any) if isinstance(repo_url_any, str) else None
        local_dir_str: Optional[str] = str(local_dir_str_any) if isinstance(local_dir_str_any, str) else None

        derived_name: Optional[str] = None
        if repo_url:
            try:
                name_part = repo_url.split("/")[-1]
                derived_name_base = name_part.removesuffix(".git")
                if not derived_name_base:
                    raise ValueError("Empty name derived from URL after stripping .git.")
                derived_name = derived_name_base
            except (IndexError, ValueError) as e:
                self._log_warning("Could not derive project name from repo_url '%s': %s. Using fallback.", repo_url, e)
                derived_name = "unknown_repo"
        elif local_dir_str:
            try:
                resolved_path = Path(local_dir_str).resolve(strict=True)
                derived_name_base = resolved_path.name
                derived_name = derived_name_base if derived_name_base else "unknown_dir"
            except (OSError, ValueError) as e:
                self._log_warning(
                    "Could not derive project name from local_dir '%s': %s. Using fallback.", local_dir_str, e
                )
                derived_name = "unknown_dir"
        else:
            self._log_error("Cannot derive project name: 'repo_url' or 'local_dir' missing and no explicit name.")
            raise ValueError("Missing 'repo_url' or 'local_dir' in shared state to derive project name.")

        final_name: str = derived_name if derived_name else "unknown_project"
        shared["project_name"] = final_name
        self._log_info("Derived project name: %s", final_name)
        return final_name

    def _gather_prep_context(self, shared: SLSharedState, project_name: str) -> _PrepContext:
        """Gather and validate context needed for fetching files.

        Args:
            shared: The shared state dictionary.
            project_name: The derived or provided project name.

        Returns:
            A _PrepContext dictionary.

        Raises:
            TypeError: If max_file_size is not an integer.
        """
        repo_url_any: Any = shared.get("repo_url")
        local_dir_str_any: Any = shared.get("local_dir")
        include_patterns_any: Any = self._get_required_shared(shared, "include_patterns")
        exclude_patterns_any: Any = self._get_required_shared(shared, "exclude_patterns")
        max_file_size_any: Any = self._get_required_shared(shared, "max_file_size")
        use_relative_paths_any: Any = shared.get("use_relative_paths", True)
        github_token_any: Any = shared.get("github_token")

        if not isinstance(max_file_size_any, int):
            # This error should ideally be caught by config validation.
            # Raising TypeError if it's not an int, as downstream code expects int.
            raise TypeError(f"max_file_size must be an int, got {type(max_file_size_any)}")

        context: _PrepContext = {
            "project_name": project_name,
            "repo_url": str(repo_url_any) if isinstance(repo_url_any, str) else None,
            "local_dir_str": str(local_dir_str_any) if isinstance(local_dir_str_any, str) else None,
            "include_patterns": include_patterns_any if isinstance(include_patterns_any, set) else set(),
            "exclude_patterns": exclude_patterns_any if isinstance(exclude_patterns_any, set) else set(),
            "max_file_size": max_file_size_any,  # Already asserted to be int
            "use_relative_paths": bool(use_relative_paths_any),
            "github_token": str(github_token_any) if isinstance(github_token_any, str) else None,
        }
        return context

    def _fetch_files_from_source(self, context: _PrepContext) -> tuple[dict[str, str], bool]:
        """Fetch files based on the provided context (repo or local dir).

        Args:
            context: The _PrepContext dictionary.

        Returns:
            A tuple: (dictionary of fetched files, boolean success status).
        """
        # Lazy import to avoid circular dependencies or issues if utils are not fully ready
        from sourcelens.utils.github import crawl_github_repo
        from sourcelens.utils.local import crawl_local_directory

        files_dict: dict[str, str] = {}
        fetch_successful = False

        if context["repo_url"]:
            self._log_info("Crawling GitHub repository: %s", context["repo_url"])
            # Note: FBT001 for use_relative_paths originates from crawl_github_repo definition
            files_dict = crawl_github_repo(
                repo_url=context["repo_url"],
                token=context["github_token"],
                include_patterns=context["include_patterns"],
                exclude_patterns=context["exclude_patterns"],
                max_file_size=context["max_file_size"],
                use_relative_paths=context["use_relative_paths"],  # FBT001 source
            )
            fetch_successful = True
        elif context["local_dir_str"]:
            self._log_info("Crawling local directory: %s", context["local_dir_str"])
            # Note: FBT001 for use_relative_paths originates from crawl_local_directory definition
            files_dict = crawl_local_directory(
                directory=context["local_dir_str"],
                include_patterns=context["include_patterns"],
                exclude_patterns=context["exclude_patterns"],
                max_file_size=context["max_file_size"],
                use_relative_paths=context["use_relative_paths"],  # FBT001 source
            )
            fetch_successful = True
        else:
            self._log_error("Neither repository URL nor local directory specified for fetching.")
            # fetch_successful remains False
        return files_dict, fetch_successful

    def prep(self, shared: SLSharedState) -> FetchPrepResult:
        """Prepare parameters, fetch files, and update shared state.

        Args:
            shared: The shared state dictionary.

        Returns:
            A boolean indicating fetch attempt success.
        """
        self._log_info("Preparing and fetching code...")
        files_list: FileDataListInternal = []
        fetch_attempt_made_successfully = False
        project_name_for_log: str = str(shared.get("project_name", "unknown_project_initial"))

        # Import moved from _fetch_files_from_source to reduce its statement count slightly.
        from sourcelens.utils.github import GithubApiError

        try:
            project_name = self._derive_project_name(shared)
            project_name_for_log = project_name

            prep_context = self._gather_prep_context(shared, project_name)
            files_dict, fetch_attempt_made_successfully = self._fetch_files_from_source(prep_context)
            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError, TypeError) as e:
            self._log_error(
                "File crawling or context gathering failed for '%s': %s. Proceeding with empty file list.",
                project_name_for_log,
                e,
                exc_info=True,
            )
            files_list = []
            fetch_attempt_made_successfully = False
        except Exception as e:  # noqa: BLE001
            self._log_error("Unexpected error during code fetching: %s", e, exc_info=True)
            files_list = []
            fetch_attempt_made_successfully = False

        shared["files"] = files_list
        if fetch_attempt_made_successfully:
            if not files_list:
                self._log_warning("Fetch operation completed, but no files matched criteria or were found.")
            else:
                self._log_info("Fetched %d files successfully.", len(files_list))
        else:
            self._log_error("Fetch code operation failed critically or found no source to process.")

        return fetch_attempt_made_successfully

    def exec(self, prep_res: FetchPrepResult) -> FetchExecResult:
        """Execute step for FetchCode (no-op).

        Args:
            prep_res: The boolean result from the `prep` method.
        """
        self._log_info("Exec step skipped (prep result: %s).", prep_res)
        if not prep_res:
            self._log_warning("Prep step for FetchCode indicated a failure. No files may have been fetched.")
        # No return value for None type, so no explicit return

    def post(self, shared: SLSharedState, prep_res: FetchPrepResult, exec_res: FetchExecResult) -> None:
        """Finalize the FetchCode node's operation.

        Args:
            shared: The shared state dictionary.
            prep_res: The boolean result from the `prep` method.
            exec_res: The result from the `exec` method (None).
        """
        del exec_res

        files_any: Any = shared.get("files", [])
        num_files: int = len(files_any) if isinstance(files_any, list) else 0
        status_message: str

        if not prep_res:
            status_message = "with critical errors during fetch attempt"
        elif num_files > 0:
            status_message = "successfully"
        else:
            status_message = "with issues or no files found"

        self._log_info("FetchCode post step finished %s. Files in shared state: %d", status_message, num_files)


# End of src/sourcelens/nodes/fetch.py
