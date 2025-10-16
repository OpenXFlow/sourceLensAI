# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""AST-based formatter for Python source code index."""

import ast
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

# Type Aliases
FileData: TypeAlias = tuple[str, Optional[str]]
FileDataList: TypeAlias = list[FileData]
ClassAttributeStructure: TypeAlias = dict[str, str]
ClassMethodStructure: TypeAlias = dict[str, str]
ClassStructure: TypeAlias = dict[str, Any]
FunctionStructure: TypeAlias = dict[str, str]
ModuleStructure: TypeAlias = dict[str, Any]
DocstringParentNode: TypeAlias = Union[ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef]

logger: logging.Logger = logging.getLogger(__name__)  # Logger pre tento modul

MAX_SUMMARY_DOC_LENGTH: Final[int] = 100
MAX_SUMMARY_DOC_SNIPPET_LEN: Final[int] = MAX_SUMMARY_DOC_LENGTH - 3


class PythonCodeVisitor(ast.NodeVisitor):
    """An AST visitor to extract classes, methods, and functions from Python code."""

    module_doc: Optional[str]
    classes: dict[str, ClassStructure]
    functions: list[FunctionStructure]
    _current_class_name: Optional[str]
    _source_code_lines: list[str]

    def __init__(self) -> None:
        """Initialize the visitor, resetting its internal state."""
        super().__init__()
        self.module_doc = None
        self.classes = defaultdict(lambda: {"doc": "", "decorators": [], "attributes": [], "methods": []})
        self.functions = []
        self._current_class_name = None
        self._source_code_lines = []
        logger.debug("PythonCodeVisitor initialized for AST formatting.")

    def _get_first_line_of_docstring(self, node: DocstringParentNode) -> str:
        """Extract the first line of a docstring from an AST node."""
        raw_docstring: Optional[str] = ast.get_docstring(node, clean=False)
        if raw_docstring:
            stripped_doc = raw_docstring.strip()
            if (stripped_doc.startswith('"""') and stripped_doc.endswith('"""')) or (
                stripped_doc.startswith("'''") and stripped_doc.endswith("'''")
            ):
                docstring_content = stripped_doc[3:-3].strip()
            elif (stripped_doc.startswith('"') and stripped_doc.endswith('"')) or (
                stripped_doc.startswith("'") and stripped_doc.endswith("'")
            ):
                docstring_content = stripped_doc[1:-1].strip()
            else:
                docstring_content = stripped_doc

            if not docstring_content:
                # logger.debug("Node %s raw_docstring '%s' resulted in empty content after stripping quotes.", type(node).__name__, raw_docstring)
                return ""

            first_line = docstring_content.lstrip().split("\n", 1)[0].strip()
            # logger.debug("Node %s, docstring first line: '%s'", type(node).__name__, first_line)
            if len(first_line) > MAX_SUMMARY_DOC_LENGTH:
                return first_line[:MAX_SUMMARY_DOC_SNIPPET_LEN] + "..."
            return first_line
        # logger.debug("Node %s has no raw_docstring.", type(node).__name__)
        return ""

    def _is_forward_ref_candidate(self, name: str) -> bool:
        """Heuristically determine if a name is a candidate for forward reference quoting."""
        known_basic_types_or_keywords: set[str] = {
            "list",
            "dict",
            "str",
            "int",
            "bool",
            "float",
            "tuple",
            "set",
            "Any",
            "Optional",
            "Union",
            "Callable",
            "None",
            "NoneType",
            "Type",
            "TypeVar",
            "Generic",
            "Final",
            "Literal",
            "Iterable",
            "Mapping",
            "Sequence",
            "Self",
            "ClassVar",
        }
        if name in known_basic_types_or_keywords or name.islower() or name.startswith("_"):
            return False
        return name[0].isupper() and name.replace("_", "").isalnum() and "." not in name

    def _parse_annotation_segment(self, segment: str, *, is_self_arg: bool) -> str:
        """Parse an annotation string obtained from ast.get_source_segment."""
        cleaned_segment = segment.strip()
        if is_self_arg and self._current_class_name and cleaned_segment == self._current_class_name:
            return f'"{cleaned_segment}"'

        generic_match = re.fullmatch(r"(\w+)\[(['\"]?)(.+?)(['\"]?)\]", cleaned_segment)
        if generic_match:
            base_type, _q1, inner_types_str, _q2 = generic_match.groups()
            inner_params = [p.strip() for p in inner_types_str.split(",")]
            formatted_inner_params: list[str] = [
                f'"{p.strip("'\" ")}"' if self._is_forward_ref_candidate(p.strip("'\" ")) else p.strip("'\" ")
                for p in inner_params
            ]
            return f"{base_type}[{', '.join(formatted_inner_params)}]"

        if (cleaned_segment.startswith('"') and cleaned_segment.endswith('"')) or (
            cleaned_segment.startswith("'") and cleaned_segment.endswith("'")
        ):
            inner_content = cleaned_segment[1:-1]
            if "[" in inner_content and "]" in inner_content:
                return self._parse_annotation_segment(inner_content, is_self_arg=False)
            return f'"{inner_content}"'
        if self._is_forward_ref_candidate(cleaned_segment):
            return f'"{cleaned_segment}"'
        return cleaned_segment

    def _parse_node_based_annotation(self, node: ast.expr, *, is_self_arg: bool) -> str:
        """Parse an annotation based on the AST node type (fallback)."""
        if isinstance(node, ast.Name):
            name_id = node.id
            if name_id == "None":
                return "None"
            is_candidate = (
                is_self_arg and self._current_class_name and name_id == self._current_class_name
            ) or self._is_forward_ref_candidate(name_id)
            return f'"{name_id}"' if is_candidate else name_id
        if isinstance(node, ast.Constant) and node.value is None:
            return "None"
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return self._parse_annotation_segment(node.value, is_self_arg=False)
        if isinstance(node, ast.Subscript):
            value_str = self._get_annotation_str(node.value, is_self_arg=False)
            slice_val = node.slice
            slice_elts_str: list[str]
            if isinstance(slice_val, ast.Tuple):
                slice_elts_str = [self._get_annotation_str(elt, is_self_arg=False) for elt in slice_val.elts]
            else:
                slice_elts_str = [self._get_annotation_str(slice_val, is_self_arg=False)]
            return f"{value_str}[{', '.join(slice_elts_str)}]"
        logger.debug("Returning 'Any' for unparseable AST annotation node type: %s", type(node).__name__)
        return "Any"

    def _get_annotation_str(self, node: Optional[ast.expr], *, is_self_arg: bool = False) -> str:
        """Attempt to get the source string for a type annotation node."""
        if node is None:
            return ""
        if self._source_code_lines and hasattr(node, "lineno") and hasattr(node, "end_lineno"):
            try:
                full_source_code = "".join(self._source_code_lines)
                segment = ast.get_source_segment(full_source_code, node)
                if segment:
                    return self._parse_annotation_segment(segment, is_self_arg=is_self_arg)
            except (AttributeError, TypeError, ValueError, IndexError) as e_segment:
                logger.debug(
                    "Failed to get source segment for annotation (line %s): %s. Fallback.",
                    getattr(node, "lineno", "N/A"),
                    str(e_segment),
                )
        return self._parse_node_based_annotation(node, is_self_arg=is_self_arg)

    def _format_single_arg(self, arg_node: ast.arg, *, has_default: bool, is_self_or_cls: bool) -> str:
        """Format a single argument node."""
        anno_str = self._get_annotation_str(arg_node.annotation, is_self_arg=is_self_or_cls)
        arg_repr = f"{arg_node.arg}: {anno_str}" if anno_str else arg_node.arg
        return f"{arg_repr} = ..." if has_default else arg_repr

    def _format_arguments(self, args_node: ast.arguments) -> str:
        """Format function arguments."""
        args_list: list[str] = []
        num_regular_args = len(args_node.args)
        for arg in args_node.posonlyargs:
            args_list.append(self._format_single_arg(arg, has_default=False, is_self_or_cls=False))
        if args_node.posonlyargs:
            args_list.append("/")
        for i, arg in enumerate(args_node.args):
            is_first = i == 0 and not args_node.posonlyargs
            is_self_or_cls = arg.arg in {"self", "cls"} and is_first and self._current_class_name is not None
            has_default = (num_regular_args - 1 - i) < len(args_node.defaults)
            args_list.append(self._format_single_arg(arg, has_default=has_default, is_self_or_cls=is_self_or_cls))
        if args_node.vararg:
            anno = self._get_annotation_str(args_node.vararg.annotation)
            args_list.append(f"*{args_node.vararg.arg}{f': {anno}' if anno else ''}")
        if args_node.kwonlyargs:
            if not args_node.vararg and (args_node.posonlyargs or args_node.args or not args_list):
                args_list.append("*")
            for i, arg_kwonly in enumerate(args_node.kwonlyargs):
                has_default_kw = args_node.kw_defaults[i] is not None
                args_list.append(self._format_single_arg(arg_kwonly, has_default=has_default_kw, is_self_or_cls=False))
        if args_node.kwarg:
            anno = self._get_annotation_str(args_node.kwarg.annotation)
            args_list.append(f"**{args_node.kwarg.arg}{f': {anno}' if anno else ''}")
        return ", ".join(filter(None, args_list))

    def _format_return_annotation(self, returns_node: Optional[ast.expr]) -> str:
        """Format the return type annotation."""
        anno_str = self._get_annotation_str(returns_node, is_self_arg=False)
        return f" -> {anno_str}" if anno_str else ""

    def _get_decorator_name_str(self, decorator_func_node: ast.expr) -> str:
        """Return the name part of a decorator."""
        if isinstance(decorator_func_node, ast.Name):
            return decorator_func_node.id
        if isinstance(decorator_func_node, ast.Attribute):
            return f"{self._get_decorator_name_str(decorator_func_node.value)}.{decorator_func_node.attr}"
        try:
            if self._source_code_lines and hasattr(decorator_func_node, "lineno"):
                segment = ast.get_source_segment("".join(self._source_code_lines), decorator_func_node)
                if segment:
                    return segment.strip()
        except (TypeError, ValueError, IndexError, AttributeError) as e:
            logger.debug("Could not get source segment for decorator name string: %s", str(e))
        return "..."

    def _get_decorator_str(self, decorator_node: ast.expr) -> str:
        """Convert a decorator AST node to string."""
        try:
            if self._source_code_lines and hasattr(decorator_node, "lineno"):
                dec_src = ast.get_source_segment("".join(self._source_code_lines), decorator_node)
                if dec_src:
                    return f"@{dec_src.strip()}"
        except (TypeError, ValueError, IndexError, AttributeError) as e:
            logger.debug("Could not get source segment for decorator string: %s", str(e))
        if isinstance(decorator_node, (ast.Name, ast.Attribute)):
            return f"@{self._get_decorator_name_str(decorator_node)}"
        if isinstance(decorator_node, ast.Call):
            return f"@{self._get_decorator_name_str(decorator_node.func)}(...)"
        return "@..."

    def visit_Module(self, node: ast.Module) -> None:
        self.module_doc = self._get_first_line_of_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        original_ctx = self._current_class_name
        self._current_class_name = node.name
        class_data = self.classes[node.name]
        class_data["doc"] = self._get_first_line_of_docstring(node)
        class_data["decorators"] = [self._get_decorator_str(d) for d in node.decorator_list]
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                class_data["attributes"].append(
                    {"name": child.target.id, "type": self._get_annotation_str(child.annotation) or "Any"}
                )
            elif isinstance(child, ast.Assign):
                for target in child.targets:
                    if isinstance(target, ast.Name):
                        class_data["attributes"].append({"name": target.id, "type": "Any # (Assigned)"})
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)
        self._current_class_name = original_ctx

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        sig = f"def {node.name}({self._format_arguments(node.args)}){self._format_return_annotation(node.returns)}"
        doc = self._get_first_line_of_docstring(node)
        target_list = self.classes[self._current_class_name]["methods"] if self._current_class_name else self.functions
        target_list.append({"signature": sig, "doc": doc})

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        sig = (
            f"async def {node.name}({self._format_arguments(node.args)}){self._format_return_annotation(node.returns)}"
        )
        doc = self._get_first_line_of_docstring(node)
        target_list = self.classes[self._current_class_name]["methods"] if self._current_class_name else self.functions
        target_list.append({"signature": sig, "doc": doc})

    def parse(self, code: str) -> ModuleStructure:
        self._source_code_lines = code.splitlines(keepends=True)
        self.module_doc = None
        self.classes.clear()
        self.functions.clear()
        self._current_class_name = None
        error_msg: Optional[str] = None
        try:
            self.visit(ast.parse(code))
        except SyntaxError as e_syn:
            error_msg = f"SyntaxError: {e_syn.msg} (line {e_syn.lineno}, offset {e_syn.offset or 0})"
        except (ValueError, TypeError, RecursionError, AttributeError) as e_ast:
            error_msg = f"AST Parsing Error: {type(e_ast).__name__}: {str(e_ast)}"
        if error_msg:
            logger.warning("AST parsing error for a file: %s", error_msg)
        return {
            "doc": self.module_doc or "",
            "classes": dict(self.classes),
            "functions": self.functions,
            "parsing_error": error_msg,
        }


def _ensure_newline_ast(lines: list[str]) -> None:
    if not lines:
        lines.append("\n")
        return
    if lines[-1] and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    elif not lines[-1]:
        lines[-1] = "\n"


def _append_module_functions_md_ast(lines: list[str], module_functions: list[FunctionStructure]) -> None:
    if module_functions:
        if lines and lines[-1].strip():
            lines.append("\n")
        for func_info in sorted(module_functions, key=lambda x: x.get("signature", "")):
            sig = func_info.get("signature", "Unknown sig")
            doc = func_info.get("doc", "")
            lines.append(f"*   **`{sig}:`**\n")
            if doc:
                lines.append(f"    ... {doc}\n")
            else:
                lines.append("    ... No function docstring found.\n")


def _append_class_attributes_md_ast(lines: list[str], attributes: list[ClassAttributeStructure]) -> None:
    if attributes:
        lines.append("#### *Class variables:*\n")  # No leading spaces here
        for attr in sorted(attributes, key=lambda x: x.get("name", "")):
            lines.append(f"*   **`{attr.get('name', 'N/A')}: {attr.get('type', 'Any')}`**\n")  # Indent items


def _append_class_methods_md_ast(lines: list[str], methods: list[ClassMethodStructure]) -> None:
    if methods:
        lines.append("#### *Methods:*\n")  # No leading spaces here
        for method_info in sorted(methods, key=lambda x: x.get("signature", "")):
            sig = method_info.get("signature", "Unknown sig")
            doc = method_info.get("doc", "")
            lines.append(f"*   **`{sig}:`**\n")  # Indent items
            if doc:
                lines.append(f"    ... {doc}\n")  # Docstring indented relative to the item's asterisk
            else:
                lines.append("    ... No method docstring found.\n")


def _append_class_md_ast(lines: list[str], class_name: str, class_data: ClassStructure) -> None:
    if lines and lines[-1].strip() and not lines[-1].endswith(("\n\n", "\n")):
        lines.append("\n\n")
    elif lines and not lines[-1].strip() and not lines[-1].endswith("\n\n"):
        lines[-1] = "\n\n"
    elif not lines:
        lines.append("\n")

    for decorator_str in class_data.get("decorators", []):
        lines.append(f"**`{decorator_str}`**\n")
    lines.append(f"### **`class {class_name}()`**\n")
    doc = class_data.get("doc", "")
    lines.append(f"... {doc}\n" if doc else "... No class docstring found.\n")

    attrs, methods_list = class_data.get("attributes", []), class_data.get("methods", [])
    if attrs or methods_list:  # Only add newline if there are attributes or methods
        lines.append("\n")  # Ensure blank line before attributes/methods sections

    if attrs:
        _append_class_attributes_md_ast(lines, attrs)
    if methods_list:
        if attrs and lines and lines[-1].strip():
            lines.append("\n")
        _append_class_methods_md_ast(lines, methods_list)


def _format_file_entry_ast(file_display_path: str, structure: ModuleStructure, file_number: int) -> list[str]:
    logger.debug("Formatting AST file entry for: %s (File #: %d)", file_display_path, file_number)
    lines: list[str] = ["\n##\n"]
    p = Path(file_display_path)
    parent_dir = "./" if p.parent.as_posix() == "." else f"{p.parent.as_posix().rstrip('/')}/"
    lines.extend([f"###### {file_number}) {parent_dir}\n", f"#  {p.name}\n"])
    parsing_error, module_doc = structure.get("parsing_error"), structure.get("doc", "")
    module_functions: list[FunctionStructure] = structure.get("functions", [])
    classes: dict[str, ClassStructure] = structure.get("classes", {})

    if parsing_error:
        lines.append(f"... Error parsing this file: {parsing_error}\n")
    elif module_doc:
        lines.append(f"... {module_doc}\n")
    elif not classes and not module_functions:
        lines.append("... (No parseable top-level functions or classes, and no module docstring found)\n")
    elif not module_doc:
        lines.append("... No module-level docstring found.\n")
    else:
        lines.append("\n")  # Ensure newline if module_doc was empty but elements exist

    _append_module_functions_md_ast(lines, module_functions)

    if module_functions and classes and lines and lines[-1].strip():
        lines.append("\n")

    for class_name_key in sorted(classes.keys()):
        _append_class_md_ast(lines, class_name_key, classes[class_name_key])

    if lines and lines[-1].strip() and not lines[-1].endswith("---\n"):
        _ensure_newline_ast(lines)
    if not lines or not lines[-1].endswith("---\n"):
        if lines and not lines[-1].endswith("\n"):
            lines.append("\n")
        lines.append("---\n")
    return lines


def format_python_index_from_ast(project_name: str, files_data: FileDataList, project_scan_root_display: str) -> str:
    """Format the 'Detailed File Content' for Python projects using AST parsing."""
    logger.info("Formatting Python source index from AST for: '%s'", project_name)
    markdown_lines: list[str] = []
    visitor = PythonCodeVisitor()
    processed_file_count = 0
    for path_from_files_data, content_opt in files_data:
        if path_from_files_data.endswith((".py", ".pyi")) and content_opt:
            processed_file_count += 1
            file_display_path = (Path(project_scan_root_display) / path_from_files_data).as_posix()
            structure = visitor.parse(content_opt)
            markdown_lines.extend(_format_file_entry_ast(file_display_path, structure, processed_file_count))
        elif content_opt is None and path_from_files_data.endswith((".py", ".pyi")):
            logger.warning("Skipping AST processing for Python file '%s' due to missing content.", path_from_files_data)

    if processed_file_count == 0 and any(fd[0].endswith((".py", ".pyi")) for fd in files_data):
        markdown_lines.append("\nNo Python files with content were processed for detailed AST indexing.\n")
    elif not any(fd[0].endswith((".py", ".pyi")) for fd in files_data) and files_data:
        markdown_lines.append("\nNo Python files found to index with AST.\n")

    result: str = "".join(markdown_lines)
    logger.info(
        "Finished AST-based Python source index part for '%s'. Python files processed: %d. Content length: %d",
        project_name,
        processed_file_count,
        len(result),
    )
    return result


# End of src/sourcelens/nodes/index_formatters/_ast_python_formatter.py
