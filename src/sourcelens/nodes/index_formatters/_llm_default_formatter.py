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

"""LLM-based default formatter for source code index."""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional

from typing_extensions import TypeAlias

from sourcelens.prompts import SourceIndexPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_dict

if TYPE_CHECKING:
    LlmConfigDictTyped: TypeAlias = dict[str, Any]
    CacheConfigDictTyped: TypeAlias = dict[str, Any]

FileData: TypeAlias = tuple[str, Optional[str]]
FileDataList: TypeAlias = list[FileData]
ClassAttributeStructure: TypeAlias = dict[str, str]
ClassMethodStructure: TypeAlias = dict[str, str]
ClassStructure: TypeAlias = dict[str, Any]
FunctionStructure: TypeAlias = dict[str, str]
InterfaceStructure: TypeAlias = dict[str, Any]
StructFieldStructure: TypeAlias = dict[str, str]
StructStructure: TypeAlias = dict[str, Any]
EnumStructure: TypeAlias = dict[str, Any]
ModuleStructure: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)

MAX_LLM_RAW_OUTPUT_SNIPPET_LEN: Final[int] = 7000
LLM_FILE_STRUCTURE_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "docstring": {"type": "string"},
        "classes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "docstring": {"type": "string"},
                    "decorators": {"type": "array", "items": {"type": "string"}},
                    "attributes": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                            "required": ["name", "type"],
                        },
                    },
                    "methods": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"signature": {"type": "string"}, "docstring": {"type": "string"}},
                            "required": ["signature"],
                        },
                    },
                },
                "required": ["name"],
            },
        },
        "functions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {"signature": {"type": "string"}, "docstring": {"type": "string"}},
                "required": ["signature"],
            },
        },
        "interfaces": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "docstring": {"type": "string"},
                    "methods": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"signature": {"type": "string"}, "docstring": {"type": "string"}},
                            "required": ["signature"],
                        },
                    },
                },
                "required": ["name"],
            },
        },
        "structs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "docstring": {"type": "string"},
                    "fields": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {"name": {"type": "string"}, "type": {"type": "string"}},
                            "required": ["name", "type"],
                        },
                    },
                },
                "required": ["name"],
            },
        },
        "enums": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "docstring": {"type": "string"},
                    "values": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["name"],
            },
        },
    },
    "additionalProperties": False,
}


def get_structure_from_llm(
    file_path: str,
    file_content: str,
    project_language: str,
    llm_config: "LlmConfigDictTyped",
    cache_config: "CacheConfigDictTyped",
) -> ModuleStructure:
    """Get file structure using LLM for a given file.

    Args:
        file_path: Path of the file.
        file_content: Content of the file.
        project_language: Programming language of the file.
        llm_config: LLM API configuration.
        cache_config: Cache configuration.

    Returns:
        A ModuleStructure dictionary.
    """
    logger.info("Analyzing file via LLM (formatter): %s (Lang: %s)", file_path, project_language)
    prompt = SourceIndexPrompts.format_analyze_file_content_prompt(file_path, file_content, project_language)
    default_error_struct: ModuleStructure = {
        "docstring": "",
        "classes": [],
        "functions": [],
        "interfaces": [],
        "structs": [],
        "enums": [],
        "parsing_error": "LLM analysis failed.",
    }
    try:
        response_text = call_llm(prompt, llm_config, cache_config)
        logger.debug(
            "LLM RAW RESPONSE (formatter) for %s:\n%s",
            file_path,
            response_text[:MAX_LLM_RAW_OUTPUT_SNIPPET_LEN] + "...",
        )
        parsed_yaml: dict[str, Any] = validate_yaml_dict(response_text, LLM_FILE_STRUCTURE_SCHEMA)
        logger.debug(
            "LLM PARSED YAML (formatter) for %s:\n%s", file_path, json.dumps(parsed_yaml, indent=2, ensure_ascii=False)
        )
        final_structure: ModuleStructure = {
            "docstring": parsed_yaml.get("docstring", ""),
            "classes": parsed_yaml.get("classes", []),
            "functions": parsed_yaml.get("functions", []),
            "interfaces": parsed_yaml.get("interfaces", []),
            "structs": parsed_yaml.get("structs", []),
            "enums": parsed_yaml.get("enums", []),
            "parsing_error": None,
        }
        logger.info("LLM analysis (formatter) for %s successful.", file_path)
        return final_structure
    except (LlmApiError, ValidationFailure) as e_val_llm:
        logger.error("LLM analysis/validation (formatter) for %s failed: %s", file_path, e_val_llm, exc_info=False)
        if isinstance(e_val_llm, ValidationFailure) and e_val_llm.raw_output:
            logger.warning(
                "Problematic LLM raw output (formatter) for %s:\n%s",
                file_path,
                e_val_llm.raw_output[:MAX_LLM_RAW_OUTPUT_SNIPPET_LEN],
            )
        default_error_struct["parsing_error"] = f"LLM Error: {type(e_val_llm).__name__}: {str(e_val_llm)[:100]}"
        return default_error_struct
    except Exception as e_unexp:
        logger.error(
            "Unexpected error during LLM file analysis (formatter) for %s: %s", file_path, e_unexp, exc_info=True
        )
        default_error_struct["parsing_error"] = f"Unexpected LLM Error: {type(e_unexp).__name__}: {str(e_unexp)[:100]}"
        return default_error_struct


def _ensure_newline_llm(lines: list[str]) -> None:
    """Ensure the list has a newline character at the end if not empty."""
    if not lines:
        lines.append("\n")
        return
    if lines[-1] and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    elif not lines[-1]:
        lines[-1] = "\n"


def _append_struct_fields_md_llm(lines: list[str], fields: list[StructFieldStructure]) -> None:
    if fields:
        for field in sorted(fields, key=lambda x: x.get("name", "")):
            lines.append(f"    *   `{field.get('name', 'N/A')}: {field.get('type', 'Any')}`\n")
        _ensure_newline_llm(lines)


def _append_enum_values_md_llm(lines: list[str], values: list[str]) -> None:
    if values:
        for enum_val in sorted(values):
            lines.append(f"    *   `{enum_val}`\n")
        _ensure_newline_llm(lines)


def _append_interface_methods_md_llm(lines: list[str], methods: list[ClassMethodStructure]) -> None:
    if methods:
        for method in sorted(methods, key=lambda x: x.get("signature", "")):
            sig, meth_doc = method.get("signature", "N/A"), method.get("docstring", "")
            lines.append(f"    *   **`{sig}`**\n")
            lines.append(f"        ... {meth_doc}\n" if meth_doc else "        ... No method docstring found.\n")
        _ensure_newline_llm(lines)


def _append_generic_item_md_llm(lines: list[str], item_info: dict[str, Any], item_type_name: str) -> None:
    item_name, doc = item_info.get("name", "Unknown"), item_info.get("docstring", "")
    lines.append(f"*   **`{item_name}`**\n")
    lines.append(f"    ... {doc}\n" if doc else "    ... No docstring found.\n")
    if item_type_name == "Structs" and "fields" in item_info:
        _append_struct_fields_md_llm(lines, item_info.get("fields", []))  # Removed self.
    elif item_type_name == "Enums" and "values" in item_info:
        _append_enum_values_md_llm(lines, item_info.get("values", []))  # Removed self.
    elif item_type_name == "Interfaces" and "methods" in item_info:
        _append_interface_methods_md_llm(lines, item_info.get("methods", []))  # Removed self.
    _ensure_newline_llm(lines)


def _append_generic_list_md_llm(lines: list[str], items: list[dict[str, Any]], item_type_name: str) -> None:
    if items:
        logger.debug("Appending generic list for %s (LLM): %s", item_type_name, items)
        if lines and lines[-1].strip() and not lines[-1].endswith("\n\n"):
            lines.append("\n")
        elif lines and not lines[-1].strip():
            _ensure_newline_llm(lines)
        lines.append(f"#### *{item_type_name}:*\n")
        for item_info in sorted(items, key=lambda x: x.get("name", "")):
            _append_generic_item_md_llm(lines, item_info, item_type_name)  # Removed self.
        _ensure_newline_llm(lines)


def _append_module_functions_md_llm(lines: list[str], module_functions: list[FunctionStructure]) -> None:
    if module_functions:
        logger.debug("Formatting %d module functions (LLM)", len(module_functions))
        if lines and lines[-1].strip() and not lines[-1].endswith(("\n\n", "\n")):
            lines.append("\n")
        elif lines and not lines[-1].strip():
            _ensure_newline_llm(lines)
        for func_info in sorted(module_functions, key=lambda x: x.get("signature", "")):
            sig, doc = func_info.get("signature", "Unknown sig"), func_info.get("docstring", "")
            lines.append(f"*   **`{sig}`**\n")
            lines.append(f"    ... {doc}\n" if doc else "    ... No function docstring found.\n")
        _ensure_newline_llm(lines)


def _append_class_attributes_md_llm(lines: list[str], attributes: list[ClassAttributeStructure]) -> None:
    if attributes:
        logger.debug("Appending class attributes (LLM): %s", attributes)
        lines.append("    #### *Attributes / Fields:*\n")
        for attr in sorted(attributes, key=lambda x: x.get("name", "")):
            lines.append(f"    *   **`{attr.get('name', 'N/A')}: {attr.get('type', 'Any')}`**\n")
        _ensure_newline_llm(lines)


def _append_class_methods_md_llm(lines: list[str], methods: list[ClassMethodStructure]) -> None:
    if methods:
        logger.debug("Appending class methods (LLM): %s", methods)
        lines.append("    #### *Methods:*\n")
        for method_info in sorted(methods, key=lambda x: x.get("signature", "")):
            sig, doc = method_info.get("signature", "Unknown sig"), method_info.get("docstring", "")
            lines.append(f"    *   **`{sig}`**\n")
            lines.append(f"        ... {doc}\n" if doc else "        ... No method docstring found.\n")
        _ensure_newline_llm(lines)


def _append_class_md_llm(lines: list[str], class_name: str, class_data: ClassStructure) -> None:
    logger.debug("Appending class MD for %s (LLM): %s", class_name, class_data)
    if lines and lines[-1].strip() and not lines[-1].endswith(("\n\n", "\n")):
        lines.append("\n")
    elif lines and not lines[-1].strip():
        _ensure_newline_llm(lines)
    for decorator_str in class_data.get("decorators", []):
        lines.append(f"**`{decorator_str}`**\n")
    lines.append(f"### **`class {class_name}()`**\n")
    doc = class_data.get("docstring", "")
    lines.append(f"... {doc}\n" if doc else "... No class docstring found.\n")
    _ensure_newline_llm(lines)
    attrs, methods = class_data.get("attributes", []), class_data.get("methods", [])
    if attrs:
        _append_class_attributes_md_llm(lines, attrs)  # Removed self.
    if methods:
        if attrs and lines and lines[-1].strip() and not lines[-1].endswith("\n\n"):
            lines.append("\n")
        elif attrs and not lines[-1].strip():
            _ensure_newline_llm(lines)
        _append_class_methods_md_llm(lines, methods)  # Removed self.
    _ensure_newline_llm(lines)


def _format_file_header_and_docstring_llm(
    lines: list[str], file_display_path: str, structure: ModuleStructure, file_number: int
) -> None:
    lines.append("\n##\n")
    p = Path(file_display_path)
    parent_dir = "./" if p.parent.as_posix() == "." else f"{p.parent.as_posix().rstrip('/')}/"
    lines.extend([f"###### {file_number}) {parent_dir}\n", f"#  {p.name}\n"])
    error, doc = structure.get("parsing_error"), structure.get("docstring", "")
    elements_present = any(
        structure.get(k) for k in ["classes", "functions", "interfaces", "structs", "enums"] if structure.get(k)
    )
    if error:
        lines.append(f"... Error parsing this file: {error}\n")
    elif doc:
        lines.append(f"... {doc}\n")
    elif not elements_present:
        lines.append("... (No parseable elements or module docstring found)\n")
    else:
        lines.append("... No module-level docstring found.\n")
    _ensure_newline_llm(lines)  # Removed self.


def _format_file_entry_llm(file_display_path: str, structure: ModuleStructure, file_number: int) -> list[str]:
    """Format the Markdown entry for a single file using its LLM-parsed structure."""
    logger.debug("Formatting LLM file entry for: %s (File #: %d)", file_display_path, file_number)
    lines_result: list[str] = []
    _format_file_header_and_docstring_llm(lines_result, file_display_path, structure, file_number)  # Removed self.
    _append_generic_list_md_llm(lines_result, structure.get("interfaces", []), "Interfaces")  # Removed self.
    _append_generic_list_md_llm(lines_result, structure.get("structs", []), "Structs")  # Removed self.
    _append_generic_list_md_llm(lines_result, structure.get("enums", []), "Enums")  # Removed self.
    _append_module_functions_md_llm(lines_result, structure.get("functions", []))  # type: ignore[arg-type] # Removed self.

    classes_list: list[ClassStructure] = structure.get("classes", [])  # type: ignore[assignment]
    for class_item in sorted(classes_list, key=lambda x: x.get("name", "")):
        class_name = class_item.get("name")
        if class_name:
            if lines_result and lines_result[-1].strip() and not lines_result[-1].endswith(("\n\n", "\n")):
                lines_result.append("\n")
            elif lines_result and not lines_result[-1].strip():
                _ensure_newline_llm(lines_result)
            _append_class_md_llm(lines_result, class_name, class_item)  # Removed self.

    if lines_result and lines_result[-1].strip() and not lines_result[-1] == "---\n":
        _ensure_newline_llm(lines_result)
    if not lines_result or not lines_result[-1].endswith("---\n"):
        lines_result.append("---\n")
    return lines_result


def format_index_from_llm(
    files_data: FileDataList,
    project_scan_root_display: str,
    project_language: str,
    llm_config: "LlmConfigDictTyped",
    cache_config: "CacheConfigDictTyped",
) -> str:
    """Format the 'Detailed File Content' section of the source index using LLM.

    Args:
        files_data: List of (filepath, content) tuples.
        project_scan_root_display: Display root for paths.
        project_language: The programming language of the project.
        llm_config: Configuration for LLM API calls.
        cache_config: Configuration for LLM caching.

    Returns:
        A string containing the Markdown formatted detailed content section.
    """
    logger.info("Formatting detailed file entries from LLM for language: '%s'", project_language)
    detailed_lines: list[str] = []
    processed_file_count = 0

    for i, (path_from_files_data, content_opt) in enumerate(files_data):
        processed_file_count += 1
        if not isinstance(path_from_files_data, str):
            logger.error("Invalid path type for item at index %d in LLM formatter. Skipping.", i)
            detailed_lines.append(f"\n##\n###### {processed_file_count}) Error: Invalid path\n# N/A\n...\n---\n")
            continue

        file_display_path = (Path(project_scan_root_display) / path_from_files_data).as_posix()
        if content_opt:
            structure = get_structure_from_llm(
                path_from_files_data, content_opt, project_language, llm_config, cache_config
            )
            detailed_lines.extend(_format_file_entry_llm(file_display_path, structure, processed_file_count))
        else:
            logger.debug("File %s has no content, formatting as generic non-content entry.", path_from_files_data)
            lines_for_no_content: list[str] = ["\n##\n"]
            p_no_content = Path(file_display_path)
            parent_no_content = (
                "./" if p_no_content.parent.as_posix() == "." else f"{p_no_content.parent.as_posix().rstrip('/')}/"
            )
            lines_for_no_content.extend(
                [
                    f"###### {processed_file_count}) {parent_no_content}\n",
                    f"#  {p_no_content.name}\n",
                    "\n... (File content not available for LLM analysis)\n",
                    "---\n",
                ]
            )
            detailed_lines.extend(lines_for_no_content)

    if processed_file_count == 0 and files_data:
        detailed_lines.append("\nNo files were processed by LLM for detailed indexing.\n")

    return "".join(detailed_lines)


# End of src/sourcelens/nodes/index_formatters/_llm_default_formatter.py
