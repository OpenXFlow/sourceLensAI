"""Node responsible for fetching source code from GitHub or local directories."""
# D200 fix: Reformatted to one line

import logging
from pathlib import Path
from typing import Optional, TypeAlias

# Import specific types for annotations from base_node
from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.utils.github import GithubApiError, crawl_github_repo
from sourcelens.utils.local import crawl_local_directory

# Type Alias
FileData: TypeAlias = list[tuple[str, str]]

logger = logging.getLogger(__name__)

# Specific types for this node's prep/exec results
FetchPrepResult: TypeAlias = bool
FetchExecResult: TypeAlias = None


class FetchCode(BaseNode):
    """Fetch source code files from GitHub or a local directory."""

    def _derive_project_name(self, shared: SharedState) -> str:
        """Derive project name from repo URL or local directory path."""
        project_name: Optional[str] = shared.get("project_name")
        if isinstance(project_name, str) and project_name.strip():
            return project_name.strip()

        repo_url: Optional[str] = shared.get("repo_url")
        local_dir_str: Optional[str] = shared.get("local_dir")
        derived_name: Optional[str] = None

        if repo_url:
            try:
                name_part = repo_url.split('/')[-1]
                derived_name_base = name_part.removesuffix('.git')
                if not derived_name_base: raise ValueError("Empty name from URL.")
                derived_name = derived_name_base
            except (IndexError, ValueError) as e:
                logger.warning("Could not derive project name from repo_url '%s': %s. Using fallback.", repo_url, e)
                derived_name = "unknown_repo"
        elif local_dir_str:
            try:
                # E501 fix: Wrapped long line
                derived_name_base = Path(local_dir_str).resolve(strict=True).name
                derived_name = derived_name_base if derived_name_base else "unknown_dir"
            except (OSError, ValueError) as e:
                 # E501 fix: Wrapped long line
                 logger.warning(
                     "Could not derive project name from local_dir '%s': %s. Using fallback.",
                     local_dir_str, e
                 )
                 derived_name = "unknown_dir"
        else:
            raise ValueError("Missing 'repo_url' or 'local_dir' in shared state.")

        final_name = derived_name if derived_name else "unknown_project"
        shared["project_name"] = final_name
        self._log_info(f"Derived project name: {final_name}")
        return final_name

    def prep(self, shared: SharedState) -> FetchPrepResult:
        """Prepare parameters, fetch files, and update shared state directly."""
        self._log_info("Preparing and fetching code...")
        files_list: FileData = []
        fetch_success = False
        project_name_for_log = shared.get("project_name", "unknown")

        try:
            project_name = self._derive_project_name(shared)
            project_name_for_log = project_name

            repo_url: Optional[str] = shared.get("repo_url")
            local_dir_str: Optional[str] = shared.get("local_dir")
            include_patterns = self._get_required_shared(shared, "include_patterns")
            exclude_patterns = self._get_required_shared(shared, "exclude_patterns")
            max_file_size = self._get_required_shared(shared, "max_file_size")
            use_relative_paths = shared.get("use_relative_paths", True)
            token = shared.get("github_token")

            files_dict: dict[str, str] = {}
            if repo_url:
                self._log_info(f"Crawling GitHub repository: {repo_url}")
                files_dict = crawl_github_repo(
                    repo_url=repo_url, token=token,
                    include_patterns=include_patterns, exclude_patterns=exclude_patterns,
                    max_file_size=max_file_size, use_relative_paths=use_relative_paths
                )
                fetch_success = True
            elif local_dir_str:
                self._log_info(f"Crawling local directory: {local_dir_str}")
                files_dict = crawl_local_directory(
                    directory=local_dir_str, include_patterns=include_patterns,
                    exclude_patterns=exclude_patterns, max_file_size=max_file_size,
                    use_relative_paths=use_relative_paths
                )
                fetch_success = True

            files_list = list(files_dict.items())

        except (OSError, GithubApiError, ValueError, ImportError) as e:
             # E501 fix: Wrapped long log message
             log_msg = (
                 f"File crawling failed for '{project_name_for_log}': {e}. "
                 f"Proceeding with empty file list."
             )
             self._log_error(log_msg)
             files_list = []
             fetch_success = False
        except KeyError as e:
             self._log_error(f"Missing required config key: {e}.", exc=e)
             files_list = []
             fetch_success = False

        finally:
            shared["files"] = files_list
            if fetch_success:
                if not files_list: self._log_warning("Fetch succeeded, but no files found.")
                else: self._log_info(f"Fetched {len(files_list)} files.")
            else: self._log_error("Fetch code operation failed.")

        return fetch_success

    def exec(self, prep_res: FetchPrepResult) -> FetchExecResult:
        """Exec method does nothing as work is done in prep (workaround)."""
        # FBT001 fix: prep_res is bool, handled correctly
        self._log_info(f"Exec step skipped (prep result: {prep_res}).")
        if not prep_res: self._log_warning("Prep step indicated potential failure.")
        return None

    def post(self, shared: SharedState, prep_res: FetchPrepResult, exec_res: FetchExecResult) -> None:
        """Post method logs completion status based on prep result (workaround)."""
        num_files = len(shared.get('files', []))
        status = "successfully" if prep_res else "with errors (check logs)"
        self._log_info(f"FetchCode post step finished {status}. Files in shared: {num_files}")

# End of src/sourcelens/nodes/fetch.py
