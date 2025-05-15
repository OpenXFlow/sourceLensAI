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

"""Node responsible for generating a source code index/inventory file.

This node acts as a dispatcher to specific formatters based on parser type
and language (e.g., AST for Python, LLM for others).
The output is a Markdown formatted string.
"""

import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional

from typing_extensions import TypeAlias

from sourcelens.nodes.index_formatters import (
    format_index_from_llm,
    format_python_index_from_ast,
)
from sourcelens.prompts.diagrams import generate_file_structure_mermaid
from sourcelens.utils._exceptions import LlmApiError

from .base_node import BaseNode, SLSharedState

if TYPE_CHECKING:
    ConfigDictTyped: TypeAlias = dict[str, Any]
    LlmConfigDictTyped: TypeAlias = dict[str, Any]
    CacheConfigDictTyped: TypeAlias = dict[str, Any]
    SourceConfigDictTyped: TypeAlias = dict[str, Any]
    OutputConfigDictTyped: TypeAlias = dict[str, Any]


SourceIndexPrepResult: TypeAlias = dict[str, Any]
SourceIndexExecResult: TypeAlias = Optional[str]
FileData: TypeAlias = tuple[str, Optional[str]]
FileDataList: TypeAlias = list[FileData]

EXPECTED_FILE_DATA_TUPLE_LENGTH_SRC_IDX: Final[int] = 2
MAX_SUMMARY_DOC_LENGTH: Final[int] = 100
MAX_SUMMARY_DOC_SNIPPET_LEN: Final[int] = MAX_SUMMARY_DOC_LENGTH - 3

logger: logging.Logger = logging.getLogger(__name__)


def _get_summary_doc_from_file_content_for_main_node(content: Optional[str]) -> str:
    """Extract a brief summary from file content (first line heuristic).

    This is a local helper for GenerateSourceIndexNode._format_file_summary_list_main_node.

    Args:
        content: Optional content of the file.

    Returns:
        A string summary or an empty string.
    """
    if not content or not content.strip():
        return ""
    first_line = content.strip().split("\n", 1)[0].strip()
    summary: str
    if (first_line.startswith('"""') and first_line.endswith('"""')) or (
        first_line.startswith("'''") and first_line.endswith("'''")
    ):
        summary = first_line[3:-3].strip()
    elif first_line.startswith("#"):
        summary = first_line[1:].strip()
    else:
        summary = first_line
    return summary[:MAX_SUMMARY_DOC_SNIPPET_LEN] + "..." if len(summary) > MAX_SUMMARY_DOC_LENGTH else summary


class GenerateSourceIndexNode(BaseNode[SourceIndexPrepResult, SourceIndexExecResult]):
    """Generates a Markdown file listing files, classes, and functions by dispatching to formatters."""

    def _format_file_summary_list_main_node(
        self,
        files_data: FileDataList,
    ) -> list[str]:
        """Format a summary list of files for the main index page.

        This summary uses a simple heuristic (first line or __init__ docstring)
        as detailed docstrings are handled by the specific formatters.

        Args:
            files_data: List of (filepath, content) tuples.

        Returns:
            A list of Markdown lines for the file summary section.
        """
        summary_lines: list[str] = ["\n## File Descriptions Summary\n"]
        if not files_data:
            summary_lines.append("No files to summarize.\n")
            return summary_lines

        for path_rel_to_scan_root, file_content_str_opt in files_data:
            file_name_only = Path(path_rel_to_scan_root).name
            doc_to_display: str

            if file_content_str_opt:
                doc_to_display = _get_summary_doc_from_file_content_for_main_node(file_content_str_opt)
            else:
                doc_to_display = "Content not available for summary."

            if file_name_only == "__init__.py" and not doc_to_display.strip():
                parent_name = Path(path_rel_to_scan_root).parent.name
                doc_to_display = (
                    f"Initializes the '{parent_name}' package." if parent_name else "Initializes the package."
                )

            summary_lines.append(f"*   **`{file_name_only}`**: {doc_to_display or 'No description available.'}\n")
        summary_lines.append("\n---\n")
        return summary_lines

    def _format_source_index_content(
        self,
        project_name: str,
        files_data: FileDataList,
        project_scan_root_display: str,
        parser_type: str,
        language: str,
        llm_config: "LlmConfigDictTyped",
        cache_config: "CacheConfigDictTyped",
    ) -> str:
        """Assemble the full source index Markdown content using appropriate formatters."""
        self._log_info("Formatting source index for: '%s' (Parser: %s, Lang: %s)", project_name, parser_type, language)
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}\n"]

        if files_data:
            mermaid_code = generate_file_structure_mermaid(project_scan_root_display, files_data)
            markdown_lines.extend(["\n## File Structure\n", f"```mermaid\n{mermaid_code}\n```\n"])
        else:
            markdown_lines.append("\nNo files found to display structure.\n")

        markdown_lines.extend(self._format_file_summary_list_main_node(files_data))

        detailed_content_str: str = ""
        processed_files_count: int = 0

        if parser_type == "ast" and language == "python":
            self._log_info("Using AST formatter for detailed Python entries.")
            python_files_with_content = [
                fd for fd in files_data if fd[0].endswith((".py", ".pyi")) and fd[1] is not None
            ]
            if python_files_with_content:
                # project_name is passed for potential future use by the formatter, not currently used.
                detailed_content_str = format_python_index_from_ast(
                    project_name, python_files_with_content, project_scan_root_display
                )
                processed_files_count = len(python_files_with_content)
            else:
                self._log_info("No Python files with content found for AST processing.")
        elif parser_type == "llm":
            self._log_info("Using LLM formatter for detailed entries (language: %s).", language)
            detailed_content_str = format_index_from_llm(
                files_data, project_scan_root_display, language, llm_config, cache_config
            )
            processed_files_count = len(files_data)
        else:
            self._log_info("Parser type is '%s'. Generating generic file list for detailed content.", parser_type)
            temp_detailed_lines: list[str] = []
            for i, (path, content_opt) in enumerate(files_data):
                display_path = (Path(project_scan_root_display) / path).as_posix()
                entry_lines: list[str] = ["\n##\n"]
                p = Path(display_path)
                parent = "./" if p.parent.as_posix() == "." else f"{p.parent.as_posix().rstrip('/')}/"
                summary = _get_summary_doc_from_file_content_for_main_node(content_opt)
                entry_lines.extend(
                    [
                        f"###### {i + 1}) {parent}\n",
                        f"#  {p.name}\n",
                        f"\n... {summary}\n" if summary else "\n... (File content summary not available)\n",
                        "---\n",
                    ]
                )
                temp_detailed_lines.extend(entry_lines)
            detailed_content_str = "".join(temp_detailed_lines)
            processed_files_count = len(files_data)

        if detailed_content_str.strip():
            markdown_lines.append("\n## Detailed File Content\n")
            markdown_lines.append(detailed_content_str)
        elif files_data:
            markdown_lines.append("\n## Detailed File Content\n")
            markdown_lines.append("No detailed structural information could be generated for the files.\n")

        if processed_files_count == 0 and files_data:
            # This message might be redundant given the one above.
            pass
        elif not files_data:
            markdown_lines.append("\nNo files found in the source to index.\n")

        self._log_info(
            "Finished source index for '%s'. Detail formatter processed approx %d files. Total length: %d",
            project_name,
            processed_files_count,
            len("".join(markdown_lines)),
        )
        return "".join(markdown_lines)

    def prep(self, shared: SLSharedState) -> SourceIndexPrepResult:
        """Prepare data and configuration for source index generation."""
        self._log_info(">>> GenerateSourceIndexNode.prep: Preparing for source index generation. <<<")
        try:
            files_data_any: Any = self._get_required_shared(shared, "files")
            project_name_any: Any = self._get_required_shared(shared, "project_name")
            config_any: Any = self._get_required_shared(shared, "config")
            source_config_any: Any = self._get_required_shared(shared, "source_config")
            llm_config_any: Any = self._get_required_shared(shared, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared, "cache_config")

            files_data_raw: list[Any] = files_data_any if isinstance(files_data_any, list) else []
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
            config: "ConfigDictTyped" = config_any if isinstance(config_any, dict) else {}
            source_config: "SourceConfigDictTyped" = source_config_any if isinstance(source_config_any, dict) else {}
            llm_config: "LlmConfigDictTyped" = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: "CacheConfigDictTyped" = cache_config_any if isinstance(cache_config_any, dict) else {}

            scan_root_val: Any = shared.get("local_dir_display_root", "./")
            scan_root: str = str(scan_root_val)
            if scan_root and not scan_root.endswith("/"):
                scan_root += "/"
            elif not scan_root:
                scan_root = "./"

            out_cfg_any: Any = config.get("output", {})
            out_cfg: "OutputConfigDictTyped" = out_cfg_any if isinstance(out_cfg_any, dict) else {}
            inc_idx_raw: Any = out_cfg.get("include_source_index")
            inc_idx: bool = inc_idx_raw if isinstance(inc_idx_raw, bool) else False
            if not isinstance(inc_idx_raw, bool) and inc_idx_raw is not None:
                self._log_warning("Config 'output.include_source_index' not boolean, defaulting to False.")

            self._log_info("Prep: include_source_index=%s, scan_root_display='%s'", inc_idx, scan_root)
            if not inc_idx:
                return {"skip": True, "reason": "Disabled via 'output.include_source_index'"}

            lang: str = str(source_config.get("language", "unknown"))
            parser: str = str(source_config.get("source_index_parser", "none"))
            self._log_info("Prep: language=%s, parser_type=%s", lang, parser)

            valid_files: FileDataList = []
            for item in files_data_raw:
                if (
                    isinstance(item, tuple)
                    and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH_SRC_IDX
                    and isinstance(item[0], str)
                    and (isinstance(item[1], str) or item[1] is None)
                ):
                    valid_files.append(item)
                else:
                    self._log_warning("Skipping invalid item in files_data: %s", item)

            return {
                "skip": False,
                "files_data": valid_files,
                "project_name": project_name,
                "language": lang,
                "parser_type": parser,
                "project_scan_root_display": scan_root,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
        except ValueError as e_val:
            self._log_error("Prep failed (missing data): %s", e_val, exc_info=True)
            return {"skip": True, "reason": f"Missing shared data: {e_val!s}"}
        except (OSError, TypeError, KeyError) as e_prep:
            self._log_error("Unexpected prep error: %s", e_prep, exc_info=True)
            return {"skip": True, "reason": f"Unexpected prep error: {type(e_prep).__name__}: {e_prep!s}"}

    def exec(self, prep_res: SourceIndexPrepResult) -> SourceIndexExecResult:
        """Generate the Markdown content for the source index."""
        self._log_info(
            ">>> GenerateSourceIndexNode.exec: Start. Skip flag: %s. Prep_res type: %s <<<",
            prep_res.get("skip") if isinstance(prep_res, dict) else "N/A",
            type(prep_res).__name__,
        )
        if not isinstance(prep_res, dict) or prep_res.get("skip", True):
            reason = prep_res.get("reason", "N/A") if isinstance(prep_res, dict) else "Invalid prep_res"
            self._log_info("Skipping source index exec. Reason: %s", reason)
            return None

        files: FileDataList = prep_res.get("files_data", [])
        name: str = prep_res.get("project_name", "Unknown Project")
        lang: str = prep_res.get("language", "unknown")
        parser: str = prep_res.get("parser_type", "none")
        root_disp: str = prep_res.get("project_scan_root_display", "./")
        llm_cfg: "LlmConfigDictTyped" = prep_res.get("llm_config", {})
        cache_cfg: "CacheConfigDictTyped" = prep_res.get("cache_config", {})

        self._log_info(
            "Calling _format_source_index_content with: name=%s, parser=%s, lang=%s, files_count=%d",
            name,
            parser,
            lang,
            len(files),
        )

        if not files:
            self._log_warning("No files data for index generation, though not skipped.")
            return f"# Code Inventory: {name}\n\nNo files found in source to index.\n"
        try:
            return self._format_source_index_content(name, files, root_disp, parser, lang, llm_cfg, cache_cfg)
        except LlmApiError:
            self._log_error("LlmApiError occurred during source index formatting, re-raising.")
            raise
        except (ValueError, TypeError, KeyError, AttributeError) as e_format:
            self._log_error("Error formatting source index: %s", e_format, exc_info=True)
            return f"# Code Inventory: {name}\n\nError generating source index details: {e_format!s}\n"

    def post(self, shared: SLSharedState, prep_res: SourceIndexPrepResult, exec_res: SourceIndexExecResult) -> None:
        """Store the generated source index content in shared state."""
        self._log_info(">>> GenerateSourceIndexNode.post: Finalizing. <<<")
        if isinstance(prep_res, dict):
            prep_summary = {k: (len(v) if isinstance(v, list) else v) for k, v in prep_res.items() if k != "files_data"}
            if "files_data" in prep_res and isinstance(prep_res["files_data"], list):
                prep_summary["files_data_count"] = len(prep_res["files_data"])
            self._log_info("Post called. prep_res summary: %s", prep_summary)

        shared["source_index_content"] = None
        if isinstance(exec_res, str) and exec_res.strip():
            shared["source_index_content"] = exec_res
            self._log_info("Stored VALID source index content (length: %d).", len(exec_res))
        else:
            self._log_warning("Source index content from exec was None or empty. Not storing.")
        self._log_info(">>> GenerateSourceIndexNode.post: Finished. <<<")


# End of src/sourcelens/nodes/n08_generate_source_index.py
