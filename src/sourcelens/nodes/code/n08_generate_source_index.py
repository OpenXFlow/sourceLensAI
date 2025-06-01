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

from sourcelens.nodes.base_node import BaseNode, SLSharedContext
from sourcelens.nodes.code.index_formatters import (
    format_index_from_llm,
    format_python_index_from_ast,
)
from sourcelens.prompts.code.diagrams import generate_file_structure_mermaid
from sourcelens.utils._exceptions import LlmApiError

if TYPE_CHECKING:
    ResolvedConfigDict: TypeAlias = dict[str, Any]
    ResolvedLlmConfigDict: TypeAlias = dict[str, Any]
    ResolvedCacheConfigDict: TypeAlias = dict[str, Any]
    ResolvedSourceConfigDict: TypeAlias = dict[str, Any]
    # ResolvedCodeAnalysisOutputOptions: TypeAlias = dict[str, Any] # No longer needed here

SourceIndexPreparedInputs: TypeAlias = dict[str, Any]
SourceIndexExecutionResult: TypeAlias = Optional[str]

FileDataInternal: TypeAlias = tuple[str, Optional[str]]
FileDataListInternal: TypeAlias = list[FileDataInternal]


EXPECTED_FILE_DATA_TUPLE_LENGTH_SRC_IDX: Final[int] = 2
MAX_SUMMARY_DOC_LENGTH: Final[int] = 100
MAX_SUMMARY_DOC_SNIPPET_LEN: Final[int] = MAX_SUMMARY_DOC_LENGTH - 3

logger: logging.Logger = logging.getLogger(__name__)


def _get_summary_doc_from_file_content_for_node(content: Optional[str]) -> str:
    """Extract a brief summary from file content (first line heuristic).

    Args:
        content: The string content of the file, or None.

    Returns:
        A brief summary string, or an empty string if no content or summary found.
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

    if len(summary) > MAX_SUMMARY_DOC_LENGTH:
        return summary[:MAX_SUMMARY_DOC_SNIPPET_LEN] + "..."
    return summary


class GenerateSourceIndexNode(BaseNode[SourceIndexPreparedInputs, SourceIndexExecutionResult]):
    """Generates a Markdown file listing files, classes, and functions by dispatching to formatters."""

    def _format_file_summary_list(
        self,
        files_data: FileDataListInternal,
    ) -> list[str]:
        """Format a summary list of files for the main index page.

        Args:
            files_data: A list of tuples, where each tuple is
                        (relative_path_to_scan_root, optional_content_string).

        Returns:
            A list of strings, where each string is a Markdown formatted line
            for the file summary section.
        """
        summary_lines: list[str] = ["\n## File Descriptions Summary\n"]
        if not files_data:
            summary_lines.append("No files to summarize.\n")
            return summary_lines

        for path_rel_to_scan_root, file_content_str_opt in files_data:
            file_name_only = Path(path_rel_to_scan_root).name
            doc_to_display: str

            if file_content_str_opt:
                doc_to_display = _get_summary_doc_from_file_content_for_node(file_content_str_opt)
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

    def _generate_detailed_content_ast(
        self,
        project_name: str,
        files_data_for_ast: FileDataListInternal,
        project_scan_root_display: str,
    ) -> tuple[str, int]:
        """Generate detailed content using AST formatter for Python files.

        Args:
            project_name: The name of the project.
            files_data_for_ast: List of (filepath, Optional[content]) tuples.
                                The formatter will filter for Python files with content.
            project_scan_root_display: The display root path for file listings.

        Returns:
            A tuple containing:
                - The formatted Markdown string for Python files.
                - The count of Python files actually processed by the AST formatter.
        """
        self._log_info("Using AST formatter for detailed Python entries.")
        python_files_to_process: FileDataListInternal = [
            (p, c) for p, c in files_data_for_ast if p.endswith((".py", ".pyi"))
        ]
        if python_files_to_process:
            content = format_python_index_from_ast(project_name, python_files_to_process, project_scan_root_display)
            return content, len(python_files_to_process)
        self._log_info("No Python files with content found to pass to AST formatter.")
        return "", 0

    def _generate_detailed_content_llm(
        self,
        project_name: str,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        language: str,
        llm_config: "ResolvedLlmConfigDict",
        cache_config: "ResolvedCacheConfigDict",
    ) -> tuple[str, int]:
        """Generate detailed content using LLM formatter.

        Args:
            project_name: The name of the project.
            files_data: List of (filepath, Optional[content]) tuples.
            project_scan_root_display: The display root path for file listings.
            language: The programming language of the project.
            llm_config: Configuration for LLM API calls.
            cache_config: Configuration for LLM caching.

        Returns:
            A tuple containing:
                - The formatted Markdown string from LLM analysis.
                - The count of files passed to the LLM formatter.
        """
        self._log_info("Using LLM formatter for detailed entries (language: %s).", language)
        content = format_index_from_llm(files_data, project_scan_root_display, language, llm_config, cache_config)
        return content, len(files_data)

    def _generate_detailed_content_generic(
        self,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        parser_type: str,
    ) -> tuple[str, int]:
        """Generate a generic file list if no specific parser (AST/LLM) is used.

        Args:
            files_data: List of (filepath, Optional[content]) tuples.
            project_scan_root_display: The display root path for file listings.
            parser_type: The parser type (expected to be "none" here).

        Returns:
            A tuple containing:
                - A Markdown string listing files and their summaries.
                - The count of files processed.
        """
        self._log_info("Parser type is '%s'. Generating generic file list for detailed content.", parser_type)
        temp_detailed_lines: list[str] = []
        for i, (path, content_opt) in enumerate(files_data):
            display_path = (Path(project_scan_root_display) / path).as_posix()
            entry_lines: list[str] = ["\n##\n"]
            p_obj = Path(display_path)
            parent_dir_str = "./" if p_obj.parent.as_posix() == "." else f"{p_obj.parent.as_posix().rstrip('/')}/"
            summary = _get_summary_doc_from_file_content_for_node(content_opt)

            entry_lines.append(f"###### {i + 1}) {parent_dir_str}\n")
            entry_lines.append(f"#  {p_obj.name}\n")
            entry_lines.append(f"\n... {summary}\n" if summary else "\n... (File content summary not available)\n")
            entry_lines.append("---\n")
            temp_detailed_lines.extend(entry_lines)
        return "".join(temp_detailed_lines), len(files_data)

    def _format_source_index_content(
        self,
        project_name: str,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        parser_type: str,
        language: str,
        llm_config: "ResolvedLlmConfigDict",
        cache_config: "ResolvedCacheConfigDict",
    ) -> str:
        """Assemble the full source index Markdown content.

        Args:
            project_name: The name of the project.
            files_data: A list of (filepath, Optional[content]) tuples.
            project_scan_root_display: The display root for paths in the index.
            parser_type: The parser type to use ("ast", "llm", or "none").
            language: The programming language of the project (relevant for AST/LLM).
            llm_config: LLM API configuration.
            cache_config: LLM caching configuration.

        Returns:
            A string containing the complete Markdown content for the source index.
        """
        self._log_info("Formatting source index for: '%s' (Parser: %s, Lang: %s)", project_name, parser_type, language)
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}\n"]

        if files_data:
            mermaid_code = generate_file_structure_mermaid(project_scan_root_display, files_data)
            markdown_lines.extend(["\n## File Structure\n", f"```mermaid\n{mermaid_code}\n```\n"])
        else:
            markdown_lines.append("\nNo files found to display structure.\n")

        markdown_lines.extend(self._format_file_summary_list(files_data))

        detailed_content_str: str = ""
        processed_files_count: int = 0

        if parser_type == "ast" and language.lower() == "python":
            detailed_content_str, processed_files_count = self._generate_detailed_content_ast(
                project_name, files_data, project_scan_root_display
            )
        elif parser_type == "llm":
            detailed_content_str, processed_files_count = self._generate_detailed_content_llm(
                project_name, files_data, project_scan_root_display, language, llm_config, cache_config
            )
        else:
            detailed_content_str, processed_files_count = self._generate_detailed_content_generic(
                files_data, project_scan_root_display, parser_type
            )

        if detailed_content_str.strip():
            markdown_lines.append("\n## Detailed File Content\n")
            markdown_lines.append(detailed_content_str)
        elif files_data:
            markdown_lines.append("\n## Detailed File Content\n")
            markdown_lines.append(
                "No detailed structural information could be generated for the files based on the selected parser.\n"
            )

        if not files_data:
            markdown_lines.append("\nNo files found in the source to index.\n")

        log_msg_parts = [
            f"Finished source index for '{project_name}'.",
            f"Detail formatter ('{parser_type}') processed approx {processed_files_count} files.",
            f"Total Markdown length: {len(''.join(markdown_lines))}",
        ]
        self._log_info(" ".join(log_msg_parts))
        return "".join(markdown_lines)

    def pre_execution(self, shared_context: SLSharedContext) -> SourceIndexPreparedInputs:
        """Prepare data and configuration for source index generation.

        Retrieves necessary data from `shared_context`, including file data,
        project details, and relevant configuration for LLM and caching if needed.
        Determines if source index generation should be skipped based on config.

        Args:
            shared_context: The shared context dictionary. Expected to contain:
                            "files", "project_name", "config" (full resolved config),
                            "source_config" (resolved for code analysis),
                            "llm_config" (resolved for current mode),
                            "cache_config" (common cache settings),
                            "local_dir_display_root",
                            "current_mode_output_options".

        Returns:
            A dictionary containing prepared inputs for the `execution` method.
            If skipping, `{"skip": True, "reason": ...}` is returned.

        Raises:
            ValueError: If essential data is missing or invalid in `shared_context`.
        """
        self._log_info(">>> GenerateSourceIndexNode.pre_execution: Preparing for source index generation. <<<")
        try:
            files_data_any: Any = self._get_required_shared(shared_context, "files")
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            source_config_val: Any = self._get_required_shared(shared_context, "source_config")
            llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")
            # Get output options for the current mode (code analysis)
            current_mode_opts_any: Any = shared_context.get("current_mode_output_options", {})
            current_mode_opts: dict[str, Any] = current_mode_opts_any if isinstance(current_mode_opts_any, dict) else {}

            files_data_raw: list[Any] = files_data_any if isinstance(files_data_any, list) else []
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
            source_config: "ResolvedSourceConfigDict" = source_config_val if isinstance(source_config_val, dict) else {}  # type: ignore[assignment]
            llm_config: "ResolvedLlmConfigDict" = llm_config_val if isinstance(llm_config_val, dict) else {}  # type: ignore[assignment]
            cache_config: "ResolvedCacheConfigDict" = cache_config_val if isinstance(cache_config_val, dict) else {}  # type: ignore[assignment]

            scan_root_val: Any = shared_context.get("local_dir_display_root", "./")
            scan_root: str = str(scan_root_val)
            if scan_root and not scan_root.endswith("/"):
                scan_root += "/"
            elif not scan_root:
                scan_root = "./"

            # Read 'include_source_index' from the mode-specific output options
            include_source_index_val: Any = current_mode_opts.get("include_source_index")
            include_source_index: bool = (
                include_source_index_val if isinstance(include_source_index_val, bool) else False
            )

            log_msg_pre = f"Pre-execution: include_source_index={include_source_index}, scan_root_display='{scan_root}'"
            self._log_info(log_msg_pre)

            if not include_source_index:
                return {
                    "skip": True,
                    "reason": "Source index generation disabled via output_options.include_source_index",
                }

            lang_name: str = str(source_config.get("language_name_for_llm", "unknown"))
            parser: str = str(source_config.get("parser_type", "none"))
            self._log_info("Pre-execution: language_name_for_llm=%s, parser_type=%s", lang_name, parser)

            valid_files_data: FileDataListInternal = []
            for item in files_data_raw:
                if (
                    isinstance(item, tuple)
                    and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH_SRC_IDX
                    and isinstance(item[0], str)
                    and (isinstance(item[1], str) or item[1] is None)
                ):
                    valid_files_data.append(item)
                else:
                    self._log_warning("Skipping invalid item in files_data: %s (type: %s)", item, type(item))

            return {
                "skip": False,
                "files_data": valid_files_data,
                "project_name": project_name,
                "language": lang_name,
                "parser_type": parser,
                "project_scan_root_display": scan_root,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
        except ValueError as e_val:
            self._log_error("Pre-execution failed (missing or invalid shared data): %s", e_val, exc_info=True)
            return {"skip": True, "reason": f"Missing or invalid shared data: {e_val!s}"}
        except (OSError, TypeError, KeyError) as e_prep:
            self._log_error("Unexpected pre-execution error for Source Index: %s", e_prep, exc_info=True)
            return {"skip": True, "reason": f"Unexpected pre_execution error: {type(e_prep).__name__}: {e_prep!s}"}

    def execution(self, prepared_inputs: SourceIndexPreparedInputs) -> SourceIndexExecutionResult:
        """Generate the Markdown content for the source index.

        Args:
            prepared_inputs: A dictionary containing all necessary data and
                             configurations, as prepared by `pre_execution`.

        Returns:
            A string containing the formatted Markdown for the source index,
            or None if execution was skipped or an error occurred.

        Raises:
            LlmApiError: If an LLM API call fails and is not handled internally.
        """
        skip_reason = prepared_inputs.get("reason", "Unknown reason")
        log_msg_exec_l1 = ">>> GenerateSourceIndexNode.execution: Start. "
        log_msg_exec_l2 = (
            f"Skip flag: {prepared_inputs.get('skip')}. Reason: {skip_reason}. "
            f"Prepared_inputs type: {type(prepared_inputs).__name__} <<<"
        )
        self._log_info(log_msg_exec_l1 + log_msg_exec_l2)

        if not isinstance(prepared_inputs, dict) or prepared_inputs.get("skip", True):
            self._log_info("Skipping source index execution. Reason: %s", skip_reason)
            return None

        required_keys = [
            "files_data",
            "project_name",
            "language",
            "parser_type",
            "project_scan_root_display",
            "llm_config",
            "cache_config",
        ]
        for key in required_keys:
            if key not in prepared_inputs:
                self._log_error("Execution error: Missing key '%s' in prepared_inputs.", key)
                project_name_fallback = str(prepared_inputs.get("project_name", "Unknown Project"))
                return f"# Code Inventory: {project_name_fallback}\n\nInternal error: Missing '{key}'.\n"

        files: FileDataListInternal = prepared_inputs["files_data"]  # type: ignore[assignment]
        name: str = prepared_inputs["project_name"]
        lang: str = prepared_inputs["language"]
        parser: str = prepared_inputs["parser_type"]
        root_disp: str = prepared_inputs["project_scan_root_display"]
        llm_cfg: "ResolvedLlmConfigDict" = prepared_inputs["llm_config"]  # type: ignore[assignment]
        cache_cfg: "ResolvedCacheConfigDict" = prepared_inputs["cache_config"]  # type: ignore[assignment]

        log_msg_format = "Calling _format_source_index_content with: name=%s, parser=%s, lang=%s, files_count=%d"
        self._log_info(log_msg_format, name, parser, lang, len(files))

        if not files and (parser == "ast" or parser == "llm"):  # If parser needs files, but none are there
            self._log_warning("No files data available for '%s' parser. Index will be minimal.", parser)
            # Still proceed to _format_source_index_content, which handles empty files_data
            # and can generate headers and the "No files found" message.

        try:
            return self._format_source_index_content(name, files, root_disp, parser, lang, llm_cfg, cache_cfg)
        except LlmApiError:
            self._log_error("LlmApiError occurred during source index formatting, re-raising for flow engine.")
            raise
        except (ValueError, TypeError, KeyError, AttributeError) as e_format:
            self._log_error("Error formatting source index: %s", e_format, exc_info=True)
            return f"# Code Inventory: {name}\n\nError generating source index details: {e_format!s}\n"

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: SourceIndexPreparedInputs,
        execution_outputs: SourceIndexExecutionResult,
    ) -> None:
        """Store the generated source index content in shared context.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: A dictionary of inputs used for the execution phase.
            execution_outputs: The Markdown content of the source index, or None.
        """
        self._log_info(">>> GenerateSourceIndexNode.post_execution: Finalizing. <<<")
        if isinstance(prepared_inputs, dict):
            prep_summary_items = []
            for k_item, v_item in prepared_inputs.items():
                if k_item != "files_data":
                    val_repr = len(v_item) if isinstance(v_item, list) else v_item
                    prep_summary_items.append(f"{k_item}: {val_repr}")
            if "files_data" in prepared_inputs and isinstance(prepared_inputs["files_data"], list):
                prep_summary_items.append(f"files_data_count: {len(prepared_inputs['files_data'])}")
            self._log_info("Post_execution called. Prepared_inputs summary: {%s}", ", ".join(prep_summary_items))

        shared_context["source_index_content"] = None  # Default to None
        if isinstance(execution_outputs, str) and execution_outputs.strip():
            shared_context["source_index_content"] = execution_outputs
            self._log_info("Stored VALID source index content (length: %d).", len(execution_outputs))
        elif execution_outputs is None and isinstance(prepared_inputs, dict) and prepared_inputs.get("skip"):
            self._log_info("Source index generation was skipped. 'source_index_content' remains None.")
        else:
            shared_context["source_index_content"] = execution_outputs  # Store error string or empty
            self._log_warning("Source index content from execution was None, empty, or an error message. Stored as is.")
        self._log_info(">>> GenerateSourceIndexNode.post_execution: Finished. <<<")


# End of src/sourcelens/nodes/code/n08_generate_source_index.py
