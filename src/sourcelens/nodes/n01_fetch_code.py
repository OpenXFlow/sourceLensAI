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

"""Node responsible for fetching source code from GitHub or local directories."""

from pathlib import Path
from typing import Any, Optional, TypedDict

from typing_extensions import TypeAlias

from .base_node import BaseNode, SLSharedContext  # Updated import and type name

# Using new type naming convention
FetchPreparedInputs: TypeAlias = bool
"""Type alias for the result of the pre-execution phase of FetchCode."""
FetchExecutionResult: TypeAlias = None  # No specific result from main execution
"""Type alias for the result of the execution phase of FetchCode."""

FileDataListInternal: TypeAlias = list[tuple[str, str]]
"""Type alias for a list of (filepath, content) tuples used internally."""


class _PrepContext(TypedDict):
    """Internal context for pre_execution method sub-functions."""

    project_name: str
    repo_url: Optional[str]
    local_dir_str: Optional[str]
    include_patterns: set[str]
    exclude_patterns: set[str]
    max_file_size: int
    use_relative_paths: bool
    github_token: Optional[str]


class FetchCode(BaseNode[FetchPreparedInputs, FetchExecutionResult]):
    """Fetch source code files from GitHub or a local directory.

    This node is responsible for the initial step of acquiring the codebase
    to be analyzed. It can handle both remote GitHub repositories and local
    filesystem directories. It populates the `shared_context` with the fetched
    file data and the derived project name.
    """

    def _derive_project_name(self, shared_context: SLSharedContext) -> str:
        """Derive a project name from repo URL or local directory path.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            The derived or existing project name.

        Raises:
            ValueError: If project name derivation fails.
        """
        project_name_shared_any: Any = shared_context.get("project_name")
        project_name_shared: Optional[str] = (
            str(project_name_shared_any) if isinstance(project_name_shared_any, str) else None
        )

        if project_name_shared and project_name_shared.strip():
            self._log_info("Using provided project name: %s", project_name_shared.strip())
            return project_name_shared.strip()

        repo_url_any: Any = shared_context.get("repo_url")
        local_dir_str_any: Any = shared_context.get("local_dir")
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
            raise ValueError("Missing 'repo_url' or 'local_dir' in shared context to derive project name.")

        final_name: str = derived_name if derived_name else "unknown_project"
        shared_context["project_name"] = final_name
        self._log_info("Derived project name: %s", final_name)
        return final_name

    def _gather_prep_context(self, shared_context: SLSharedContext, project_name: str) -> _PrepContext:
        """Gather and validate context needed for fetching files.

        Args:
            shared_context: The shared context dictionary.
            project_name: The derived or provided project name.

        Returns:
            A _PrepContext dictionary.

        Raises:
            TypeError: If max_file_size is not an integer.
        """
        repo_url_any: Any = shared_context.get("repo_url")
        local_dir_str_any: Any = shared_context.get("local_dir")
        include_patterns_any: Any = self._get_required_shared(shared_context, "include_patterns")
        exclude_patterns_any: Any = self._get_required_shared(shared_context, "exclude_patterns")
        max_file_size_any: Any = self._get_required_shared(shared_context, "max_file_size")
        use_relative_paths_any: Any = shared_context.get("use_relative_paths", True)
        github_token_any: Any = shared_context.get("github_token")

        if not isinstance(max_file_size_any, int):
            raise TypeError(f"max_file_size must be an int, got {type(max_file_size_any)}")

        context: _PrepContext = {
            "project_name": project_name,
            "repo_url": str(repo_url_any) if isinstance(repo_url_any, str) else None,
            "local_dir_str": str(local_dir_str_any) if isinstance(local_dir_str_any, str) else None,
            "include_patterns": include_patterns_any if isinstance(include_patterns_any, set) else set(),
            "exclude_patterns": exclude_patterns_any if isinstance(exclude_patterns_any, set) else set(),
            "max_file_size": max_file_size_any,
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
        from sourcelens.utils.github import crawl_github_repo
        from sourcelens.utils.local import crawl_local_directory

        files_dict: dict[str, str] = {}
        fetch_successful = False

        if context["repo_url"]:
            self._log_info("Crawling GitHub repository: %s", context["repo_url"])
            files_dict = crawl_github_repo(
                repo_url=context["repo_url"],
                token=context["github_token"],
                include_patterns=context["include_patterns"],
                exclude_patterns=context["exclude_patterns"],
                max_file_size=context["max_file_size"],
                use_relative_paths=context["use_relative_paths"],
            )
            fetch_successful = True
        elif context["local_dir_str"]:
            self._log_info("Crawling local directory: %s", context["local_dir_str"])
            files_dict = crawl_local_directory(
                directory=context["local_dir_str"],
                include_patterns=context["include_patterns"],
                exclude_patterns=context["exclude_patterns"],
                max_file_size=context["max_file_size"],
                use_relative_paths=context["use_relative_paths"],
            )
            fetch_successful = True
        else:
            self._log_error("Neither repository URL nor local directory specified for fetching.")
            # fetch_successful remains False
        return files_dict, fetch_successful

    def pre_execution(self, shared_context: SLSharedContext) -> FetchPreparedInputs:
        """Prepare parameters, fetch files, and update shared context.

        This phase involves deriving the project name, gathering necessary
        configurations, and then fetching the source code files either from
        a GitHub repository or a local directory. The list of fetched files
        (path and content) is stored in the `shared_context`.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A boolean indicating whether the fetch attempt was made and considered
            successful (even if no files were ultimately matched or found).
            Returns False if a critical error prevented the fetch attempt.
        """
        self._log_info("Preparing and fetching code...")
        files_list: FileDataListInternal = []
        fetch_attempt_made_successfully = False
        project_name_for_log: str = str(shared_context.get("project_name", "unknown_project_initial"))

        from sourcelens.utils.github import GithubApiError  # Lazy import for GithubApiError

        try:
            project_name = self._derive_project_name(shared_context)
            project_name_for_log = project_name

            prep_context = self._gather_prep_context(shared_context, project_name)
            files_dict, fetch_attempt_made_successfully = self._fetch_files_from_source(prep_context)
            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError, TypeError) as e:
            self._log_error(
                "File crawling or context gathering failed for '%s': %s. Proceeding with empty file list.",
                project_name_for_log,
                e,
                exc_info=True,
            )
            files_list = []  # Ensure files_list is empty on error
            fetch_attempt_made_successfully = False  # Mark as failed
        # Removed broad Exception catch as per BLE001, specific errors are handled.

        shared_context["files"] = files_list
        if fetch_attempt_made_successfully:
            if not files_list:
                self._log_warning("Fetch operation completed, but no files matched criteria or were found.")
            else:
                self._log_info("Fetched %d files successfully.", len(files_list))
        else:
            self._log_error("Fetch code operation failed critically or found no source to process.")

        return fetch_attempt_made_successfully

    def execution(self, prepared_inputs: FetchPreparedInputs) -> FetchExecutionResult:
        """Execute the main logic for FetchCode (which is a no-op).

        The core work of fetching files is done in the `pre_execution` phase.
        This method primarily logs the outcome of the preparation.

        Args:
            prepared_inputs: The boolean result from the `pre_execution` method,
                             indicating if the fetch attempt was made.

        Returns:
            None, as this node's main work is preparatory.
        """
        self._log_info("FetchCode execution phase (prep result: %s).", prepared_inputs)
        if not prepared_inputs:
            self._log_warning("Pre-execution step for FetchCode indicated a failure. No files may have been fetched.")
        return None

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: FetchPreparedInputs,
        execution_outputs: FetchExecutionResult,
    ) -> None:
        """Finalize the FetchCode node's operation by logging the outcome.

        Args:
            shared_context: The shared context dictionary.
            prepared_inputs: The boolean result from the `pre_execution` method.
            execution_outputs: The result from the `execution` method (None).
        """
        del execution_outputs  # Unused

        files_any: Any = shared_context.get("files", [])
        num_files: int = len(files_any) if isinstance(files_any, list) else 0
        status_message: str

        if not prepared_inputs:  # If pre_execution itself failed (e.g. couldn't make attempt)
            status_message = "with critical errors during fetch attempt"
        elif num_files > 0:
            status_message = "successfully"
        else:  # pre_execution was "successful" in making an attempt, but no files found
            status_message = "with issues or no files found"

        self._log_info("FetchCode post_execution finished %s. Files in shared context: %d", status_message, num_files)


# End of src/sourcelens/nodes/n01_fetch_code.py
