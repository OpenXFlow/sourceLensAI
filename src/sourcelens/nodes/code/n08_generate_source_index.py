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
    ConfigDictInternal: TypeAlias = dict[str, Any]
    LlmConfigDictInternal: TypeAlias = dict[str, Any]
    CacheConfigDictInternal: TypeAlias = dict[str, Any]
    SourceConfigDictInternal: TypeAlias = dict[str, Any]
    OutputConfigDictInternal: TypeAlias = dict[str, Any]

SourceIndexPreparedInputs: TypeAlias = dict[str, Any]
SourceIndexExecutionResult: TypeAlias = Optional[str]

FileDataInternal: TypeAlias = tuple[str, Optional[str]]
FileDataListInternal: TypeAlias = list[FileDataInternal]


EXPECTED_FILE_DATA_TUPLE_LENGTH_SRC_IDX: Final[int] = 2
MAX_SUMMARY_DOC_LENGTH: Final[int] = 100
MAX_SUMMARY_DOC_SNIPPET_LEN: Final[int] = MAX_SUMMARY_DOC_LENGTH - 3

logger: logging.Logger = logging.getLogger(__name__)


def _get_summary_doc_from_file_content_for_node(content: Optional[str]) -> str:
    """Extract a brief summary from file content (first line heuristic)."""
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
        """Format a summary list of files for the main index page."""
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
        files_data_for_ast: FileDataListInternal,  # Changed: expects list[tuple[str, Optional[str]]]
        project_scan_root_display: str,
    ) -> tuple[str, int]:
        """Generate detailed content using AST formatter for Python files."""
        self._log_info("Using AST formatter for detailed Python entries.")
        # AST formatter should ideally handle None content by skipping or erroring.
        # We pass all .py/.pyi files, even if some might have None content theoretically.
        python_files_to_process: FileDataListInternal = [
            (p, c) for p, c in files_data_for_ast if p.endswith((".py", ".pyi"))
        ]
        if python_files_to_process:
            # The `format_python_index_from_ast` must be robust enough to handle
            # Optional[str] for content, or we assume it filters/errors internally
            # if content is None (which it should for AST parsing).
            content = format_python_index_from_ast(project_name, python_files_to_process, project_scan_root_display)
            return content, len(python_files_to_process)
        self._log_info("No Python files found to pass to AST formatter.")
        return "", 0

    def _generate_detailed_content_llm(
        self,
        project_name: str,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        language: str,
        llm_config: "LlmConfigDictInternal",
        cache_config: "CacheConfigDictInternal",
    ) -> tuple[str, int]:
        """Generate detailed content using LLM formatter."""
        self._log_info("Using LLM formatter for detailed entries (language: %s).", language)
        content = format_index_from_llm(files_data, project_scan_root_display, language, llm_config, cache_config)
        return content, len(files_data)

    def _generate_detailed_content_generic(
        self,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        parser_type: str,
    ) -> tuple[str, int]:
        """Generate generic file list if no specific parser is used."""
        self._log_info("Parser type is '%s'. Generating generic file list for detailed content.", parser_type)
        temp_detailed_lines: list[str] = []
        for i, (path, content_opt) in enumerate(files_data):
            display_path = (Path(project_scan_root_display) / path).as_posix()
            entry_lines: list[str] = ["\n##\n"]
            p_obj = Path(display_path)
            parent_dir_str = "./" if p_obj.parent.as_posix() == "." else f"{p_obj.parent.as_posix().rstrip('/')}/"
            summary = _get_summary_doc_from_file_content_for_node(content_opt)
            entry_lines.extend(
                [
                    f"###### {i + 1}) {parent_dir_str}\n",
                    f"#  {p_obj.name}\n",
                    f"\n... {summary}\n" if summary else "\n... (File content summary not available)\n",
                    "---\n",
                ]
            )
            temp_detailed_lines.extend(entry_lines)
        return "".join(temp_detailed_lines), len(files_data)

    def _format_source_index_content(
        self,
        project_name: str,
        files_data: FileDataListInternal,
        project_scan_root_display: str,
        parser_type: str,
        language: str,
        llm_config: "LlmConfigDictInternal",
        cache_config: "CacheConfigDictInternal",
    ) -> str:
        """Assemble the full source index Markdown content."""
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

        if parser_type == "ast" and language == "python":
            # Pass the original files_data (list[tuple[str, Optional[str]]])
            # The _generate_detailed_content_ast method will filter for .py/.pyi
            # and format_python_index_from_ast MUST handle Optional[str] for content
            # (ideally by skipping files where content is None, as AST needs content).
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
            markdown_lines.append("No detailed structural information could be generated for the files.\n")

        if not files_data:
            markdown_lines.append("\nNo files found in the source to index.\n")

        log_msg = "Finished source index for '%s'. Detail formatter processed approx %d files. Total length: %d"
        self._log_info(log_msg, project_name, processed_files_count, len("".join(markdown_lines)))
        return "".join(markdown_lines)

    def pre_execution(self, shared_context: SLSharedContext) -> SourceIndexPreparedInputs:
        """Prepare data and configuration for source index generation."""
        self._log_info(">>> GenerateSourceIndexNode.pre_execution: Preparing for source index generation. <<<")
        try:
            files_data_any: Any = self._get_required_shared(shared_context, "files")
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            config_any: Any = self._get_required_shared(shared_context, "config")
            source_config_any: Any = self._get_required_shared(shared_context, "source_config")
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")

            files_data_raw: list[Any] = files_data_any if isinstance(files_data_any, list) else []
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
            config: "ConfigDictInternal" = config_any if isinstance(config_any, dict) else {}
            source_config: "SourceConfigDictInternal" = source_config_any if isinstance(source_config_any, dict) else {}
            llm_config: "LlmConfigDictInternal" = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config: "CacheConfigDictInternal" = cache_config_any if isinstance(cache_config_any, dict) else {}

            scan_root_val: Any = shared_context.get("local_dir_display_root", "./")
            scan_root: str = str(scan_root_val)
            if scan_root and not scan_root.endswith("/"):
                scan_root += "/"
            elif not scan_root:
                scan_root = "./"

            out_cfg_any: Any = config.get("output", {})
            out_cfg: "OutputConfigDictInternal" = out_cfg_any if isinstance(out_cfg_any, dict) else {}
            inc_idx_raw: Any = out_cfg.get("include_source_index")
            inc_idx: bool = inc_idx_raw if isinstance(inc_idx_raw, bool) else False
            if not isinstance(inc_idx_raw, bool) and inc_idx_raw is not None:
                self._log_warning("Config 'output.include_source_index' not boolean, defaulting to False.")

            self._log_info("Pre-execution: include_source_index=%s, scan_root_display='%s'", inc_idx, scan_root)
            if not inc_idx:
                return {"skip": True, "reason": "Disabled via 'output.include_source_index'"}

            lang: str = str(source_config.get("language", "unknown"))
            parser: str = str(source_config.get("source_index_parser", "none"))
            self._log_info("Pre-execution: language=%s, parser_type=%s", lang, parser)

            valid_files: FileDataListInternal = []
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
            self._log_error("Pre-execution failed (missing data): %s", e_val, exc_info=True)
            return {"skip": True, "reason": f"Missing shared data: {e_val!s}"}
        except (OSError, TypeError, KeyError) as e_prep:
            self._log_error("Unexpected pre-execution error: %s", e_prep, exc_info=True)
            return {"skip": True, "reason": f"Unexpected pre_execution error: {type(e_prep).__name__}: {e_prep!s}"}

    def execution(self, prepared_inputs: SourceIndexPreparedInputs) -> SourceIndexExecutionResult:
        """Generate the Markdown content for the source index."""
        log_msg_exec_l1 = ">>> GenerateSourceIndexNode.execution: Start. "
        log_msg_exec_l2 = (
            f"Skip flag: {prepared_inputs.get('skip') if isinstance(prepared_inputs, dict) else 'N/A'}. "
            f"Prepared_inputs type: {type(prepared_inputs).__name__} <<<"
        )
        self._log_info(log_msg_exec_l1 + log_msg_exec_l2)

        if not isinstance(prepared_inputs, dict) or prepared_inputs.get("skip", True):
            reason_val = prepared_inputs.get("reason", "N/A") if isinstance(prepared_inputs, dict) else "Invalid prep"
            self._log_info("Skipping source index execution. Reason: %s", str(reason_val))
            return None

        files: FileDataListInternal = prepared_inputs.get("files_data", [])  # type: ignore[assignment]
        name: str = prepared_inputs.get("project_name", "Unknown Project")
        lang: str = prepared_inputs.get("language", "unknown")
        parser: str = prepared_inputs.get("parser_type", "none")
        root_disp: str = prepared_inputs.get("project_scan_root_display", "./")
        llm_cfg: "LlmConfigDictInternal" = prepared_inputs.get("llm_config", {})  # type: ignore[assignment]
        cache_cfg: "CacheConfigDictInternal" = prepared_inputs.get("cache_config", {})  # type: ignore[assignment]

        log_msg_format = "Calling _format_source_index_content with: name=%s, parser=%s, lang=%s, files_count=%d"
        self._log_info(log_msg_format, name, parser, lang, len(files))

        if not files:
            self._log_warning("No files data for index generation, though not skipped in pre_execution.")
            return f"# Code Inventory: {name}\n\nNo files found in source to index.\n"
        try:
            return self._format_source_index_content(name, files, root_disp, parser, lang, llm_cfg, cache_cfg)
        except LlmApiError:
            self._log_error("LlmApiError occurred during source index formatting, re-raising.")
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
        """Store the generated source index content in shared context."""
        self._log_info(">>> GenerateSourceIndexNode.post_execution: Finalizing. <<<")
        if isinstance(prepared_inputs, dict):
            prep_summary_items = []
            for k_item, v_item in prepared_inputs.items():
                if k_item != "files_data":
                    val_repr = len(v_item) if isinstance(v_item, list) else v_item
                    prep_summary_items.append(f"{k_item}: {val_repr}")
            if "files_data" in prepared_inputs and isinstance(prepared_inputs["files_data"], list):
                prep_summary_items.append(f"files_data_count: {len(prepared_inputs['files_data'])}")
            self._log_info("Post_execution called. prepared_inputs summary: {%s}", ", ".join(prep_summary_items))

        shared_context["source_index_content"] = None
        if isinstance(execution_outputs, str) and execution_outputs.strip():
            shared_context["source_index_content"] = execution_outputs
            self._log_info("Stored VALID source index content (length: %d).", len(execution_outputs))
        else:
            self._log_warning("Source index content from execution was None or empty. Not storing valid content.")
        self._log_info(">>> GenerateSourceIndexNode.post_execution: Finished. <<<")


# End of src/sourcelens/nodes/n08_generate_source_index.py
