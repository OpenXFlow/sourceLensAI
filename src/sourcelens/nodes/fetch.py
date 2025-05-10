# src/sourcelens/nodes/fetch.py

"""Node responsible for fetching source code from GitHub or local directories."""

import logging  # Keep for module-level logger for utilities
from pathlib import Path
from typing import Optional, TypeAlias

from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.utils.github import GithubApiError, crawl_github_repo
from sourcelens.utils.local import crawl_local_directory

# Type Alias
FileData: TypeAlias = list[tuple[str, str]]

# Module-level logger for utility functions if not part of a class instance
module_logger = logging.getLogger(__name__)

# Specific types for this node's prep/exec results
FetchPrepResult: TypeAlias = bool
FetchExecResult: TypeAlias = None


class FetchCode(BaseNode):
    """Fetch source code files from GitHub or a local directory."""

    def _derive_project_name(self, shared: SharedState) -> str:
        """Derive project name from repo URL or local directory path.

        If a project name is already set in shared state, it's used. Otherwise,
        it attempts to derive the name from the repository URL (last part of the path)
        or the local directory name. Fallbacks to 'unknown_project' if derivation fails.
        The derived or existing name is then stored back into the shared state.

        Args:
            shared (SharedState): The shared state dictionary.

        Returns:
            str: The derived or existing project name.

        Raises:
            ValueError: If neither 'repo_url' nor 'local_dir' is present in the
                        shared state when a project name needs to be derived.

        """
        project_name: Optional[str] = shared.get("project_name")
        if isinstance(project_name, str) and project_name.strip():
            self._logger.info("Using provided project name: %s", project_name)  # Use self._logger
            return project_name.strip()

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
                self._logger.warning(  # Use self._logger
                    "Could not derive project name from repo_url '%s': %s. Using fallback.", repo_url, e
                )
                derived_name = "unknown_repo"
        elif local_dir_str:
            try:
                derived_name_base = Path(local_dir_str).resolve(strict=True).name
                derived_name = derived_name_base if derived_name_base else "unknown_dir"
            except (OSError, ValueError) as e:
                self._logger.warning(  # Use self._logger
                    "Could not derive project name from local_dir '%s': %s. Using fallback.", local_dir_str, e
                )
                derived_name = "unknown_dir"
        else:
            # This case should ideally be caught by argparse or earlier validation
            self._logger.error(  # Use self._logger
                "Cannot derive project name: 'repo_url' or 'local_dir' missing."
            )
            raise ValueError("Missing 'repo_url' or 'local_dir' in shared state to derive project name.")

        final_name = derived_name if derived_name else "unknown_project"
        shared["project_name"] = final_name
        self._logger.info(f"Derived project name: {final_name}")  # Use self._logger
        return final_name

    def prep(self, shared: SharedState) -> FetchPrepResult:
        """Prepare parameters, fetch files, and update shared state directly.

        This method orchestrates the code fetching process. It first derives the
        project name if not explicitly provided. Then, based on whether a
        repository URL or a local directory is specified, it calls the
        appropriate crawling utility (`crawl_github_repo` or `crawl_local_directory`).
        The fetched file data (path and content) is stored in the shared state.
        It handles potential errors during fetching and logs the outcome.

        Args:
            shared (SharedState): The shared state dictionary containing initial
                                  parameters like 'repo_url', 'local_dir',
                                  filter patterns, and token. This dictionary
                                  will be updated with 'files' and 'project_name'.

        Returns:
            FetchPrepResult: True if files were fetched (even if zero files were found
                             after filtering), False if a critical error occurred during
                             the fetching process that prevented even an attempt.

        """
        self._logger.info("Preparing and fetching code...")  # Use self._logger
        files_list: FileData = []
        fetch_success = False
        # Use a temporary variable for logging in case derivation fails before assignment
        project_name_for_log = str(shared.get("project_name", "unknown_project_initial"))

        try:
            # Project name is now derived and set in shared_state here
            project_name = self._derive_project_name(shared)
            project_name_for_log = project_name  # Update for subsequent logs

            repo_url: Optional[str] = shared.get("repo_url")
            local_dir_str: Optional[str] = shared.get("local_dir")
            include_patterns = self._get_required_shared(shared, "include_patterns")
            exclude_patterns = self._get_required_shared(shared, "exclude_patterns")
            max_file_size = self._get_required_shared(shared, "max_file_size")
            use_relative_paths = shared.get("use_relative_paths", True)
            token = shared.get("github_token")  # Optional

            files_dict: dict[str, str] = {}
            if repo_url:
                self._logger.info(f"Crawling GitHub repository: {repo_url}")  # Use self._logger
                files_dict = crawl_github_repo(
                    repo_url=repo_url,
                    token=token,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    max_file_size=max_file_size,
                    use_relative_paths=use_relative_paths,
                )
                fetch_success = True  # Indicates crawling attempt was made
            elif local_dir_str:
                self._logger.info(f"Crawling local directory: {local_dir_str}")  # Use self._logger
                files_dict = crawl_local_directory(
                    directory=local_dir_str,
                    include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns,
                    max_file_size=max_file_size,
                    use_relative_paths=use_relative_paths,
                )
                fetch_success = True  # Indicates crawling attempt was made
            else:
                # This case should have been caught by _derive_project_name or argparse
                self._logger.error("Neither repository URL nor local directory specified.")  # Use self._logger
                fetch_success = False

            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError) as e:
            log_msg = f"File crawling failed for '{project_name_for_log}': {e}. Proceeding with empty file list."
            self._logger.error(log_msg, exc_info=True)  # Use self._logger and log traceback
            files_list = []
            fetch_success = False  # Critical error during fetch
        except KeyError as e:  # Should be caught by _get_required_shared
            self._logger.error(f"Missing required config key for fetching: {e}.", exc_info=True)  # Use self._logger
            files_list = []
            fetch_success = False
        except Exception as e:  # Catch any other unexpected error
            self._logger.error(f"Unexpected error during code fetching: {e}", exc_info=True)  # Use self._logger
            files_list = []
            fetch_success = False

        # Update shared state regardless of fetch_success to reflect outcome
        shared["files"] = files_list
        if fetch_success:
            if not files_list:
                self._logger.warning(
                    "Fetch operation completed, but no files matched criteria or were found."
                )  # Use self._logger
            else:
                self._logger.info(f"Fetched {len(files_list)} files successfully.")  # Use self._logger
        else:
            self._logger.error("Fetch code operation failed critically or found no source.")  # Use self._logger

        return fetch_success

    def exec(self, prep_res: FetchPrepResult) -> FetchExecResult:
        """Execute step for FetchCode (no-op as work is done in prep).

        The primary logic of fetching code is performed in the `prep` method to
        make file data available early in the shared state for subsequent nodes.
        This `exec` method is a placeholder to conform to the BaseNode structure.

        Args:
            prep_res (FetchPrepResult): The boolean result from the `prep` method,
                                        indicating if the fetch attempt was made.

        Returns:
            FetchExecResult: Always None, as no execution is performed here.

        """
        self._logger.info(f"Exec step skipped (prep result: {prep_res}).")  # Use self._logger
        if not prep_res:
            self._logger.warning(
                "Prep step for FetchCode indicated a failure. No files may have been fetched."
            )  # Use self._logger
        return None

    def post(self, shared: SharedState, prep_res: FetchPrepResult, exec_res: FetchExecResult) -> None:
        """Finalize the FetchCode node's operation.

        Logs the completion status based on the `prep` phase result and the number
        of files actually stored in the shared state.

        Args:
            shared (SharedState): The shared state dictionary, now containing 'files'.
            prep_res (FetchPrepResult): The boolean result from the `prep` method.
            exec_res (FetchExecResult): The result from the `exec` method (always None).

        """
        num_files = len(shared.get("files", []))
        status_message = "successfully" if prep_res and num_files > 0 else "with issues or no files found"
        if not prep_res:  # If prep itself failed critically
            status_message = "with critical errors during fetch attempt"

        self._logger.info(  # Use self._logger
            f"FetchCode post step finished {status_message}. Files in shared state: {num_files}"
        )


# End of src/sourcelens/nodes/fetch.py
