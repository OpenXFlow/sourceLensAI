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
from typing import Any, Final, Optional, TypedDict

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext  # ZMENA
from sourcelens.utils.github import GithubApiError, crawl_github_repo
from sourcelens.utils.local import crawl_local_directory

FetchPreparedInputs: TypeAlias = bool
FetchExecutionResult: TypeAlias = None

FileDataListInternal: TypeAlias = list[tuple[str, str]]


class NoFilesFetchedError(Exception):
    """Raised when FetchCode finds no files matching criteria for a critical operation."""


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
    is_file_fetching_critical: bool


CRITICAL_FETCH_MODES: Final[set[str]] = {"code"}  # Modes where finding no files is fatal


class FetchCode(BaseNode[FetchPreparedInputs, FetchExecutionResult]):
    """Fetch source code files from GitHub or a local directory.

    This node is responsible for the initial step of acquiring the codebase
    to be analyzed. It can handle both remote GitHub repositories and local
    filesystem directories. It populates the `shared_context` with the fetched
    file data and the derived project name. If no files are fetched for a
    critical operation (like code analysis), it may raise an error.
    """

    def _derive_project_name_fallback(self, shared_context: SLSharedContext) -> str:
        """Attempt to derive a project name if not already fully resolved in shared_context.

        This method serves as a fallback if `shared_context["project_name"]` is still
        a sentinel like "auto-generated" or missing. The primary name resolution
        should occur in `main.py`.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A derived project name string, or a generic fallback.
        """
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
                self._log_warning("Could not derive project name from repo_url '%s': %s.", repo_url, e)
                derived_name = "unknown_repo_at_node"
        elif local_dir_str:
            try:
                resolved_path = Path(local_dir_str).resolve(strict=False)  # strict=False more robust
                derived_name_base = resolved_path.name
                derived_name = derived_name_base if derived_name_base else "unknown_dir_at_node"
            except (OSError, ValueError) as e:
                self._log_warning("Could not derive project name from local_dir '%s': %s.", local_dir_str, e)
                derived_name = "unknown_dir_at_node"
        return derived_name or "project_name_fallback"

    def _gather_prep_context(self, shared_context: SLSharedContext) -> _PrepContext:
        """Gather and validate context needed for fetching files.

        Args:
            shared_context: The shared context dictionary. Expected to contain all necessary
                            keys like 'project_name', 'include_patterns', etc., which should
                            have been populated by `main.py`.

        Returns:
            A `_PrepContext` dictionary containing validated and typed parameters.

        Raises:
            ValueError: If a required key is missing from `shared_context` or has an invalid value.
            TypeError: If `max_file_size` from `shared_context` is not an integer.
        """
        project_name_val: Any = self._get_required_shared(shared_context, "project_name")
        if not isinstance(project_name_val, str) or not project_name_val.strip():
            # This check implies that project_name should have been resolved by main.py
            # If it's still 'auto-generated' here, derivation within the node might be needed as a fallback.
            project_name_str = self._derive_project_name_fallback(shared_context)
            self._log_warning(
                "Project name was '%s', using node-derived fallback: '%s'", project_name_val, project_name_str
            )
        else:
            project_name_str = project_name_val

        repo_url_any: Any = shared_context.get("repo_url")
        local_dir_str_any: Any = shared_context.get("local_dir")
        include_patterns_any: Any = self._get_required_shared(shared_context, "include_patterns")
        exclude_patterns_any: Any = self._get_required_shared(shared_context, "exclude_patterns")
        max_file_size_any: Any = self._get_required_shared(shared_context, "max_file_size")
        use_relative_paths_any: Any = shared_context.get("use_relative_paths", True)
        github_token_any: Any = shared_context.get("github_token")

        operation_mode_val: Any = shared_context.get("current_operation_mode", "unknown")
        operation_mode: str = str(operation_mode_val)
        is_critical = operation_mode in CRITICAL_FETCH_MODES

        if not isinstance(max_file_size_any, int) or max_file_size_any < 0:
            raise TypeError(f"max_file_size must be a non-negative int, got {max_file_size_any}")

        context: _PrepContext = {
            "project_name": project_name_str,
            "repo_url": str(repo_url_any) if isinstance(repo_url_any, str) else None,
            "local_dir_str": str(local_dir_str_any) if isinstance(local_dir_str_any, str) else None,
            "include_patterns": include_patterns_any if isinstance(include_patterns_any, set) else set(),
            "exclude_patterns": exclude_patterns_any if isinstance(exclude_patterns_any, set) else set(),
            "max_file_size": max_file_size_any,
            "use_relative_paths": bool(use_relative_paths_any),
            "github_token": str(github_token_any) if isinstance(github_token_any, str) else None,
            "is_file_fetching_critical": is_critical,
        }
        return context

    def _fetch_files_from_source(self, context: _PrepContext) -> tuple[dict[str, str], bool]:
        """Fetch files based on the provided context (repo or local dir).

        Delegates to `crawl_github_repo` or `crawl_local_directory` based on
        whether `repo_url` or `local_dir_str` is present in the context.

        Args:
            context: The `_PrepContext` dictionary containing all necessary parameters
                     for fetching, including URLs, paths, patterns, and tokens.

        Returns:
            A tuple:
                - A dictionary mapping file paths (strings) to their content (strings).
                - A boolean indicating if the fetch attempt was made (True) or if
                  no source was specified (False).
        """
        # Lazy imports to avoid circular dependencies or slow startup if utils are heavy

        files_dict: dict[str, str] = {}
        fetch_attempt_made = False

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
            fetch_attempt_made = True
        elif context["local_dir_str"]:
            self._log_info("Crawling local directory: %s", context["local_dir_str"])
            files_dict = crawl_local_directory(
                directory=context["local_dir_str"],
                include_patterns=context["include_patterns"],
                exclude_patterns=context["exclude_patterns"],
                max_file_size=context["max_file_size"],
                use_relative_paths=context["use_relative_paths"],
            )
            fetch_attempt_made = True
        else:
            self._log_error("Neither repository URL nor local directory specified for fetching.")
        return files_dict, fetch_attempt_made

    def pre_execution(self, shared_context: SLSharedContext) -> FetchPreparedInputs:
        """Prepare parameters, fetch files, and update shared context.

        Args:
            shared_context: The shared context dictionary. It is expected to contain
                            'project_name', 'include_patterns', 'exclude_patterns',
                            'max_file_size', 'current_operation_mode', and optionally
                            'repo_url', 'local_dir', 'use_relative_paths', 'github_token'.

        Returns:
            A boolean indicating whether the fetch attempt was made.

        Raises:
            ValueError: If essential pre-requisite data is missing from `shared_context`.
            TypeError: If `max_file_size` from `shared_context` is not a valid integer.
        """
        self._log_info("Preparing and fetching code...")
        files_list: FileDataListInternal = []
        fetch_attempt_made = False
        project_name_for_log: str = str(shared_context.get("project_name", "unknown_project_in_fetch_pre"))

        try:
            # Ensure project_name is valid before proceeding
            project_name_val = self._get_required_shared(shared_context, "project_name")
            if not isinstance(project_name_val, str) or not project_name_val.strip():
                raise ValueError("Project name in shared_context is invalid or empty.")
            project_name_for_log = project_name_val

            prep_context = self._gather_prep_context(shared_context)
            # Update log name if it was derived/validated inside _gather_prep_context
            project_name_for_log = prep_context["project_name"]

            files_dict, fetch_attempt_made = self._fetch_files_from_source(prep_context)
            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError, TypeError) as e:
            self._log_error(
                "File crawling or context gathering failed for '%s': %s. Proceeding with empty file list.",
                project_name_for_log,
                e,
                exc_info=True,
            )
            files_list = []
            fetch_attempt_made = False  # Ensure this is false on any of these errors
        shared_context["files"] = files_list

        if fetch_attempt_made:
            if not files_list:
                self._log_warning("Fetch operation completed, but no files matched criteria or were found.")
            else:
                self._log_info("Fetched %d files successfully.", len(files_list))
        else:
            self._log_error("Fetch code operation did not proceed or failed critically during setup/API call.")

        return fetch_attempt_made

    def execution(self, prepared_inputs: FetchPreparedInputs) -> FetchExecutionResult:
        """Execute the main logic for FetchCode (which is a no-op).

        The core work of fetching files is done in the `pre_execution` phase.
        This method primarily logs the outcome of the preparation.

        Args:
            prepared_inputs: The boolean result from the `pre_execution` method,
                             indicating if the fetch attempt was made.

        Returns:
            None.
        """
        self._log_info("FetchCode execution phase (prep_inputs indicate attempt_made: %s).", prepared_inputs)
        if not prepared_inputs:
            self._log_warning("Pre-execution step for FetchCode indicated a failure. No files may have been fetched.")
        return None

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: FetchPreparedInputs,
        execution_outputs: FetchExecutionResult,
    ) -> None:
        """Finalize the FetchCode node's operation, logging and potentially raising an error.

        If `prepared_inputs` (indicating a successful fetch attempt) is True but no files
        were actually found, and if the current operation mode (e.g., "code")
        deems file fetching critical, this method will raise `NoFilesFetchedError`.
        Otherwise, it logs the outcome.

        Args:
            shared_context: The shared context dictionary. Expected to contain 'files'
                            (list of fetched file data), 'source_config' (for language
                            profile info), 'include_patterns', and
                            'current_operation_mode'.
            prepared_inputs: The boolean result from `pre_execution`, indicating if
                             the fetch attempt was made.
            execution_outputs: The result from `execution` (None).

        Raises:
            NoFilesFetchedError: If `prepared_inputs` is True, no files were found,
                                 and the `current_operation_mode` in `shared_context`
                                 is one of the `CRITICAL_FETCH_MODES`.
        """
        del execution_outputs

        files_any: Any = shared_context.get("files", [])
        num_files: int = len(files_any) if isinstance(files_any, list) else 0
        status_message: str

        current_operation_mode_val: Any = shared_context.get("current_operation_mode", "unknown")
        current_operation_mode: str = str(current_operation_mode_val)
        is_critical_mode = current_operation_mode in CRITICAL_FETCH_MODES

        if not prepared_inputs:
            status_message = "with critical errors during fetch attempt or setup"
            self._log_error(
                "Fetch code operation did not proceed or failed critically. Files in context: %d", num_files
            )
            if is_critical_mode:
                # This error signifies a failure before or during the fetch attempt itself.
                raise NoFilesFetchedError(
                    f"Critical error during file fetching setup/attempt for {current_operation_mode} mode. See logs."
                )
        elif num_files == 0:
            status_message = "but no files matched the configured criteria"
            source_cfg_val: Any = shared_context.get("source_config", {})
            source_cfg: dict[str, Any] = source_cfg_val if isinstance(source_cfg_val, dict) else {}
            profile_id: str = str(source_cfg.get("profile_id", "N/A"))
            lang_name: str = str(source_cfg.get("language_name_for_llm", "N/A"))
            include_patterns_val: Any = shared_context.get("include_patterns", set())
            include_patterns_set: set[str] = include_patterns_val if isinstance(include_patterns_val, set) else set()

            warn_msg_l1 = "No files were found matching the include patterns for the active language profile."
            warn_msg_l2 = f"  Active Profile ID: '{profile_id}' (Language: {lang_name})."
            # Corrected C414: sorted() can take a set directly
            # Corrected E501: Broke down the log message for clarity and length
            sorted_patterns_str = str(sorted(include_patterns_set) if include_patterns_set else ["None"])
            warn_msg_l3_part1 = "  Effective Include Patterns: "
            warn_msg_l3_part2 = sorted_patterns_str

            self._log_warning(warn_msg_l1)
            self._log_warning(warn_msg_l2)
            self._log_warning("%s%s", warn_msg_l3_part1, warn_msg_l3_part2)  # Log as two parts if too long

            if is_critical_mode:
                error_message_parts = [
                    warn_msg_l1,
                    warn_msg_l2,
                    f"{warn_msg_l3_part1}{warn_msg_l3_part2}",
                    "Halting execution as no files were found for critical code analysis.",
                ]
                raise NoFilesFetchedError("\n".join(error_message_parts))
        else:
            status_message = "successfully"

        self._log_info("FetchCode post_execution finished %s. Files in shared context: %d", status_message, num_files)


# End of src/sourcelens/nodes/code/n01_fetch_code.py
