# src/sourcelens/nodes/fetch.py

"""Node responsible for fetching source code from GitHub or local directories."""

# import logging # F401: Removed unused import
from pathlib import Path
from typing import Optional, TypeAlias

from .base_node import BaseNode, SharedState

# Local type aliases for this node's prep/exec results
FetchPrepResult: TypeAlias = bool
"""Type alias for the result of the preparation phase of FetchCode (fetch success status)."""
FetchExecResult: TypeAlias = None
"""Type alias for the result of the execution phase of FetchCode (always None)."""

FileDataList: TypeAlias = list[tuple[str, str]]
"""Type alias for a list of (filepath, content) tuples."""


class FetchCode(BaseNode[FetchPrepResult, FetchExecResult]):
    """Fetch source code files from GitHub or a local directory.

    This node is responsible for the initial step of acquiring the codebase
    to be analyzed. It can handle both remote GitHub repositories and local
    filesystem directories. It populates the `shared_state` with the fetched
    file data and the derived project name.
    """

    def _derive_project_name(self, shared: SharedState) -> str:
        """Derive a project name from repo URL or local directory path.

        If a project name is already set in `shared_state` (e.g., from command-line
        arguments), it's used directly. Otherwise, this method attempts to derive
        the name from the repository URL (typically the last part of the path,
        stripping ".git") or from the name of the local directory being processed.
        If derivation fails or no source is provided, it defaults to "unknown_project".
        The determined project name is stored back into `shared["project_name"]`.

        Args:
            shared: The shared state dictionary. Expected to contain 'repo_url'
                    or 'local_dir' if 'project_name' is not already set.

        Returns:
            The derived or existing project name.

        Raises:
            ValueError: If neither 'repo_url' nor 'local_dir' is present in the
                        shared state when a project name needs to be derived and
                        'project_name' is not already set.

        """
        project_name_shared: Optional[str] = shared.get("project_name")
        if isinstance(project_name_shared, str) and project_name_shared.strip():
            self._log_info("Using provided project name: %s", project_name_shared)
            return project_name_shared.strip()

        repo_url: Optional[str] = shared.get("repo_url")
        local_dir_str: Optional[str] = shared.get("local_dir")
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

    def prep(self, shared: SharedState) -> FetchPrepResult:
        """Prepare parameters, fetch files, and update shared state.

        This method orchestrates the code fetching process. It first derives the
        project name. Then, based on 'repo_url' or 'local_dir' in `shared_state`,
        it calls the appropriate crawling utility. Fetched file data (path and content)
        is stored in `shared['files']`.

        Args:
            shared: The shared state dictionary. It is updated with 'files'
                    (a `FileDataList`) and 'project_name' (a string).

        Returns:
            A boolean indicating whether the fetching attempt was made and
            was not critically interrupted (True), or if a critical error
            occurred preventing even an attempt (False). Note that True
            is returned even if zero files are found after filtering.

        """
        self._log_info("Preparing and fetching code...")
        files_list: FileDataList = []
        fetch_attempt_made_successfully = False
        project_name_for_log: str = str(shared.get("project_name", "unknown_project_initial"))

        from sourcelens.utils.github import GithubApiError, crawl_github_repo
        from sourcelens.utils.local import crawl_local_directory

        try:
            project_name = self._derive_project_name(shared)
            project_name_for_log = project_name

            repo_url: Optional[str] = shared.get("repo_url")
            local_dir_str: Optional[str] = shared.get("local_dir")

            include_patterns: set[str] = self._get_required_shared(shared, "include_patterns")
            exclude_patterns: set[str] = self._get_required_shared(shared, "exclude_patterns")
            max_file_size: int = self._get_required_shared(shared, "max_file_size")

            use_relative_paths: bool = shared.get("use_relative_paths", True)
            github_token: Optional[str] = shared.get("github_token")

            files_dict: dict[str, str] = {}
            if repo_url:
                self._log_info("Crawling GitHub repository: %s", repo_url)
                files_dict = crawl_github_repo(
                    repo_url=repo_url,
                    token=github_token,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    max_file_size=max_file_size,
                    use_relative_paths=use_relative_paths,
                )
                fetch_attempt_made_successfully = True
            elif local_dir_str:
                self._log_info("Crawling local directory: %s", local_dir_str)
                files_dict = crawl_local_directory(
                    directory=local_dir_str,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    max_file_size=max_file_size,
                    use_relative_paths=use_relative_paths,
                )
                fetch_attempt_made_successfully = True
            else:
                self._log_error("Neither repository URL nor local directory specified for fetching.")
                fetch_attempt_made_successfully = False

            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError) as e:
            self._log_error(
                "File crawling failed for '%s': %s. Proceeding with empty file list.",
                project_name_for_log,
                e,
                exc_info=True,
            )
            files_list = []
            fetch_attempt_made_successfully = False
        except Exception as e:  # noqa: BLE001 - Catch-all for unexpected errors during complex I/O
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
        """Execute step for FetchCode (no-op as work is done in prep).

        Args:
            prep_res: The boolean result from the `prep` method.

        Returns:
            Always None.

        """
        self._log_info("Exec step skipped (prep result: %s).", prep_res)
        if not prep_res:
            self._log_warning("Prep step for FetchCode indicated a failure. No files may have been fetched.")
        return None

    def post(self, shared: SharedState, prep_res: FetchPrepResult, exec_res: FetchExecResult) -> None:
        """Finalize the FetchCode node's operation.

        Args:
            shared: The shared state dictionary.
            prep_res: The boolean result from the `prep` method.
            exec_res: The result from the `exec` method (None).

        """
        num_files = len(shared.get("files", []))
        status_message: str
        if not prep_res:
            status_message = "with critical errors during fetch attempt"
        elif num_files > 0:
            status_message = "successfully"
        else:
            status_message = "with issues or no files found"

        self._log_info("FetchCode post step finished %s. Files in shared state: %d", status_message, num_files)


# End of src/sourcelens/nodes/fetch.py
