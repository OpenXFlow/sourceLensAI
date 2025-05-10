# src/sourcelens/nodes/generate_source_index.py

"""Node responsible for generating a source code index/inventory file."""

import ast
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Literal, Optional, TypeAlias

from sourcelens.nodes.base_node import BaseNode, SharedState

if TYPE_CHECKING:
    from sourcelens.config import ConfigDict

# Type Aliases
FileData: TypeAlias = list[tuple[str, str]]
SourceIndexPrepResult: TypeAlias = dict[str, Any]
SourceIndexExecResult: TypeAlias = Optional[str]
ChapterType: TypeAlias = Literal["standard", "diagrams", "source_index"]
ChapterFileData: TypeAlias = dict[str, Any]

ClassAttributeStructure: TypeAlias = dict[str, str]
ClassMethodStructure: TypeAlias = dict[str, str]
ClassStructure: TypeAlias = dict[str, Any]
FunctionStructure: TypeAlias = dict[str, str]
ModuleStructure: TypeAlias = dict[str, Any]


module_logger = logging.getLogger(__name__ + ".PythonCodeVisitor")

SHORT_PYTHON_INDEX_CONTENT_THRESHOLD: Final[int] = 200
SHORT_SOURCE_INDEX_CONTENT_THRESHOLD: Final[int] = 100
SHORT_EXEC_RES_CONTENT_THRESHOLD: Final[int] = 200
DEBUG_SNIPPET_LENGTH: Final[int] = 50
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2


class PythonCodeVisitor(ast.NodeVisitor):
    """An AST visitor to extract classes, methods, and functions from Python code."""

    def __init__(self: "PythonCodeVisitor") -> None:
        """Initialize the visitor."""
        super().__init__()
        self.module_doc: Optional[str] = None
        self.classes: dict[str, ClassStructure] = defaultdict(
            lambda: {"doc": "", "decorators": [], "attributes": [], "methods": []}
        )
        self.functions: list[FunctionStructure] = []
        self._current_class_name: Optional[str] = None
        self._source_code: str = ""
        module_logger.debug("PythonCodeVisitor initialized.")

    def _get_first_line_of_docstring(self: "PythonCodeVisitor", node: ast.AST) -> str:
        """Extract the first line of a docstring from an AST node.

        Args:
            node: The AST node (e.g., Module, ClassDef, FunctionDef).

        Returns:
            The first line of the docstring, or an empty string if no docstring.

        """
        docstring = ast.get_docstring(node, clean=False)
        if docstring:
            return docstring.split("\n", 1)[0].strip()
        return ""

    def _is_forward_ref_candidate(self: "PythonCodeVisitor", name: str) -> bool:
        """Heuristically determine if a name is a candidate for forward reference quoting.

        Args:
            name: The name string to check.

        Returns:
            True if the name is a likely candidate for forward reference, False otherwise.

        """
        known_basic_types_or_keywords = {
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
        }
        if name in known_basic_types_or_keywords:
            return False
        return name[0].isupper() and name.replace("_", "").isalpha() and "." not in name

    def _parse_segment_annotation(self, segment: str, *, is_self_arg: bool) -> str:
        """Parse an annotation string obtained from ast.get_source_segment.

        Args:
            segment: The code segment for the annotation.
            is_self_arg: True if the annotation is for a 'self' argument.

        Returns:
            A formatted string for the annotation.

        """
        cleaned_segment = segment.strip()
        if is_self_arg and self._current_class_name and cleaned_segment == self._current_class_name:
            return f'"{cleaned_segment}"'

        list_match = re.fullmatch(r"list\[(['\"])(.+?)\1\]", cleaned_segment)
        if list_match:
            inner_type = list_match.group(2)
            return f'list["{inner_type}"]'

        if (cleaned_segment.startswith('"') and cleaned_segment.endswith('"')) or (
            cleaned_segment.startswith("'") and cleaned_segment.endswith("'")
        ):
            inner_content = cleaned_segment[1:-1]
            if "[" in inner_content and "]" in inner_content:
                base_type, params_str = inner_content.split("[", 1)
                params_str = params_str[:-1]
                params_parts = [p.strip() for p in params_str.split(",")]
                formatted_params = [f'"{p}"' if self._is_forward_ref_candidate(p) else p for p in params_parts]
                return f"{base_type}[{', '.join(formatted_params)}]"
            return f'"{inner_content}"' if self._is_forward_ref_candidate(inner_content) else inner_content
        if self._is_forward_ref_candidate(cleaned_segment):
            return f'"{cleaned_segment}"'
        return cleaned_segment

    def _parse_node_based_annotation(self, node: ast.expr, *, is_self_arg: bool) -> str:
        """Parse an annotation based on the AST node type (fallback).

        Args:
            node: The AST expression node for the annotation.
            is_self_arg: True if the annotation is for a 'self' argument.

        Returns:
            A formatted string for the annotation.

        """
        res_str = ""
        if isinstance(node, ast.Name):
            name_id = node.id
            if name_id == "None":
                res_str = "None"
            elif (is_self_arg and self._current_class_name and name_id == self._current_class_name) or (
                self._is_forward_ref_candidate(name_id)
            ):
                res_str = f'"{name_id}"'
            else:
                res_str = name_id
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == "None":
                res_str = "None"
            elif self._is_forward_ref_candidate(node.value):
                res_str = f'"{node.value}"'
            else:
                res_str = node.value
        elif isinstance(node, ast.Subscript):
            value_str = self._get_annotation_str(node.value, is_self_arg=False)
            slice_val = node.slice
            slice_inner_str = ""
            if isinstance(slice_val, ast.Tuple):
                slice_elts = [self._get_annotation_str(elt, is_self_arg=False) for elt in slice_val.elts]
                slice_inner_str = ", ".join(slice_elts)
            else:
                slice_inner_str = self._get_annotation_str(slice_val, is_self_arg=False)
            res_str = f"{value_str}[{slice_inner_str}]"
        else:
            res_str = "..."
            module_logger.debug("Returning '...' for unparseable node type: %s (%s)", type(node), node)
        return res_str

    def _get_annotation_str(self, node: Optional[ast.expr], *, is_self_arg: bool = False) -> str:
        """Attempt to get the source string for a type annotation node.

        Args:
            node: The AST expression node for the annotation. Can be None.
            is_self_arg: Keyword-only argument, True if for a 'self' argument.

        Returns:
            A formatted string representation of the type annotation.

        """
        if node is None:
            return ""
        try:
            if self._source_code:
                segment = ast.get_source_segment(self._source_code, node)
                if segment:
                    return self._parse_segment_annotation(segment, is_self_arg=is_self_arg)
        except (AttributeError, TypeError, ValueError, IndexError):
            module_logger.debug("Failed to get source segment for annotation node: %s", node, exc_info=False)
        return self._parse_node_based_annotation(node, is_self_arg=is_self_arg)

    def _format_arguments(self: "PythonCodeVisitor", args_node: ast.arguments) -> str:
        """Format function arguments including type hints and default value indicators.

        Args:
            args_node: The AST arguments node from a function or method definition.

        Returns:
            A string representing the formatted arguments list.

        """
        args_list: list[str] = []
        num_posonly_args = len(args_node.posonlyargs)
        num_regular_args = len(args_node.args)
        total_main_args = num_posonly_args + num_regular_args
        total_defaults = len(args_node.defaults)
        first_arg_with_default_overall_idx = total_main_args - total_defaults
        for i, arg_node in enumerate(args_node.posonlyargs):
            anno_str = self._get_annotation_str(arg_node.annotation)
            arg_r = f"{arg_node.arg}: {anno_str}" if anno_str else arg_node.arg
            default_idx = i - (total_main_args - total_defaults)
            if default_idx >= 0 and default_idx < total_defaults:
                arg_r += " = ..."
            args_list.append(arg_r)
        for i, arg_node in enumerate(args_node.args):
            is_self = (
                arg_node.arg == "self"
                and (i == 0 and not args_node.posonlyargs)
                and self._current_class_name is not None
            )
            anno_str = self._get_annotation_str(arg_node.annotation, is_self_arg=is_self)
            arg_r = f"{arg_node.arg}: {anno_str}" if anno_str else arg_node.arg
            current_arg_idx_overall = num_posonly_args + i
            if current_arg_idx_overall >= first_arg_with_default_overall_idx:
                arg_r += " = ..."
            args_list.append(arg_r)
        for i, arg_node in enumerate(args_node.kwonlyargs):
            anno_str = self._get_annotation_str(arg_node.annotation)
            arg_r = f"{arg_node.arg}: {anno_str}" if anno_str else arg_node.arg
            if args_node.kw_defaults[i] is not None:
                arg_r += " = ..."
            args_list.append(arg_r)
        if args_node.vararg:
            vararg_anno = self._get_annotation_str(args_node.vararg.annotation)
            args_list.append(f"*{args_node.vararg.arg}: {vararg_anno}" if vararg_anno else f"*{args_node.vararg.arg}")
        if args_node.kwarg:
            kwarg_anno = self._get_annotation_str(args_node.kwarg.annotation)
            args_list.append(f"**{args_node.kwarg.arg}: {kwarg_anno}" if kwarg_anno else f"**{args_node.kwarg.arg}")
        return ", ".join(args_list)

    def _format_return_annotation(self: "PythonCodeVisitor", returns_node: Optional[ast.expr]) -> str:
        """Format the return type annotation of a function or method.

        Args:
            returns_node: The AST expression node for the return annotation.

        Returns:
            A string representing the formatted return annotation.

        """
        if returns_node:
            anno_str = self._get_annotation_str(returns_node, is_self_arg=False)
            return f" -> {anno_str}" if anno_str else ""
        return ""

    def _get_decorator_name_str(self, decorator_func_node: ast.expr) -> str:
        """Return the name part of a decorator function node.

        Args:
            decorator_func_node: The AST node representing the function part of a decorator.

        Returns:
            A string representation of the decorator's function name.

        """
        if isinstance(decorator_func_node, ast.Name):
            return decorator_func_node.id
        if isinstance(decorator_func_node, ast.Attribute):
            value_str = self._get_decorator_name_str(decorator_func_node.value)
            return f"{value_str}.{decorator_func_node.attr}"
        return self._get_annotation_str(decorator_func_node)

    def _get_decorator_str(self: "PythonCodeVisitor", decorator_node: ast.expr) -> str:
        """Convert a decorator AST node to its string representation.

        Args:
            decorator_node: The AST node representing the decorator.

        Returns:
            A string representation of the decorator.

        """
        try:
            if self._source_code:
                dec_src = ast.get_source_segment(self._source_code, decorator_node)
                if dec_src:
                    return f"@{dec_src.strip()}"
        except (AttributeError, TypeError, ValueError) as e:
            module_logger.debug("Fail get src segment for decorator %s: %s", decorator_node, e, exc_info=False)

        if isinstance(decorator_node, ast.Name):
            return f"@{decorator_node.id}"
        if isinstance(decorator_node, ast.Call):
            func_str = self._get_decorator_name_str(decorator_node.func)
            args_repr_list: list[str] = []
            for arg_node_in_call in decorator_node.args:
                args_repr_list.append(self._get_annotation_str(arg_node_in_call))
            for kw_node in decorator_node.keywords:
                args_repr_list.append(f"{kw_node.arg}={self._get_annotation_str(kw_node.value)}")
            return f"@{func_str}({', '.join(args_repr_list)})"
        if isinstance(decorator_node, ast.Attribute):
            return f"@{self._get_decorator_name_str(decorator_node)}"
        return "@..."

    def visit_Module(self: "PythonCodeVisitor", node: ast.Module) -> None:
        """Visit a Module node and extract its docstring."""
        self.module_doc = self._get_first_line_of_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self: "PythonCodeVisitor", node: ast.ClassDef) -> None:
        """Visit a ClassDef node and extract its structure."""
        class_name = node.name
        orig_ctx = self._current_class_name
        self._current_class_name = class_name
        cls_data = self.classes[class_name]
        cls_data["doc"] = self._get_first_line_of_docstring(node)
        cls_data["decorators"] = [self._get_decorator_str(d) for d in node.decorator_list]
        for child in node.body:
            if isinstance(child, ast.AnnAssign) and isinstance(child.target, ast.Name):
                cls_data["attributes"].append(
                    {"name": child.target.id, "type": self._get_annotation_str(child.annotation) or "Any"}
                )
            elif isinstance(child, ast.Assign):
                for tgt_node in child.targets:
                    if isinstance(tgt_node, ast.Name):
                        cls_data["attributes"].append({"name": tgt_node.id, "type": "Any # (Assigned value)"})
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child)
        self._current_class_name = orig_ctx

    def visit_FunctionDef(self: "PythonCodeVisitor", node: ast.FunctionDef) -> None:
        """Visit a FunctionDef node and extract its signature and docstring."""
        sig = f"def {node.name}({self._format_arguments(node.args)}){self._format_return_annotation(node.returns)}"
        doc = self._get_first_line_of_docstring(node)
        if self._current_class_name:
            self.classes[self._current_class_name]["methods"].append({"signature": sig, "doc": doc})
        else:
            self.functions.append({"signature": sig, "doc": doc})

    def visit_AsyncFunctionDef(self: "PythonCodeVisitor", node: ast.AsyncFunctionDef) -> None:
        """Visit an AsyncFunctionDef node and extract its signature and docstring."""
        sig = (
            f"async def {node.name}({self._format_arguments(node.args)}){self._format_return_annotation(node.returns)}"
        )
        doc = self._get_first_line_of_docstring(node)
        if self._current_class_name:
            self.classes[self._current_class_name]["methods"].append({"signature": sig, "doc": doc})
        else:
            self.functions.append({"signature": sig, "doc": doc})

    def parse(self: "PythonCodeVisitor", code: str) -> ModuleStructure:
        """Parse Python code and return its structured representation.

        Args:
            code: The Python source code as a string.

        Returns:
            A dictionary representing the module's structure.

        """
        self._source_code = code
        self.module_doc = None
        self.classes.clear()
        self.functions.clear()
        self._current_class_name = None
        p_err = None
        try:
            ast_tree = ast.parse(code)
            self.visit(ast_tree)
        except SyntaxError as e:
            p_err = f"SyntaxError: {e.msg} L{e.lineno} C{e.offset}"
            module_logger.warning("Parse fail: %s", e)
        except Exception as e:
            p_err = f"AST Error: {e!s}"
            module_logger.error("AST fail: %s", e, exc_info=True)
        return {
            "doc": self.module_doc or "",
            "classes": dict(self.classes),
            "functions": self.functions,
            "parsing_error": p_err,
        }


class GenerateSourceIndexNode(BaseNode):
    """Generates a Markdown file listing files, classes, and functions."""

    def _append_module_functions_md(
        self: "GenerateSourceIndexNode", lines: list[str], module_functions: list[FunctionStructure], path_str: str
    ) -> None:
        """Append Markdown for module-level functions to the lines list."""
        if module_functions:
            self._logger.debug("Formatting %d module functions for %s", len(module_functions), path_str)
            if lines and lines[-1].strip():
                lines.append("\n")

            for func_info in sorted(module_functions, key=lambda x: x["signature"]):
                lines.append(f"*   **`{func_info['signature']}:`**\n")
                if func_info["doc"]:
                    lines.append(f"... {func_info['doc']}\n")

    def _append_class_attributes_md(self, lines: list[str], attributes: list[ClassAttributeStructure]) -> None:
        """Append Markdown for class attributes."""
        if attributes:
            lines.append("#### *Class variables:*\n")  # H4, kurzíva, bez odrážky
            for attr in sorted(attributes, key=lambda x: x["name"]):
                lines.append(f"*   **`{attr['name']}: {attr['type']}`**\n")

    def _append_class_methods_md(self, lines: list[str], methods: list[ClassMethodStructure]) -> None:
        """Append Markdown for class methods."""
        if methods:
            lines.append("#### *Methods:*\n")  # H4, kurzíva, bez odrážky
            for method_info in sorted(methods, key=lambda x: x["signature"]):
                lines.append(f"*   **`{method_info['signature']}:`**\n")
                if method_info["doc"]:
                    lines.append(f"... {method_info['doc']}\n")

    def _append_class_md(
        self: "GenerateSourceIndexNode", lines: list[str], class_name: str, class_data: ClassStructure
    ) -> None:
        """Append Markdown for a single class to the lines list."""
        if lines and lines[-1].strip():
            lines.append("\n")  # Blank line if previous content
        lines.append("\n")  # Always start a class block with a blank line for separation

        for decorator_str in class_data.get("decorators", []):
            lines.append(f"**`{decorator_str}`**\n")  # Podľa vzoru to vyzerá, že dekorátory nie sú H3

        # Definícia triedy ako H3, tučné, kód + zátvorky
        lines.append(f"### **`class {class_name}()`**\n")
        class_doc_str = class_data.get("doc", "")
        if class_doc_str:
            lines.append(f"... {class_doc_str}\n")
        else:
            lines.append("... No class docstring found.\n")

        lines.append("\n")  # Prázdny riadok za popisom triedy

        attributes: list[ClassAttributeStructure] = class_data.get("attributes", [])
        methods: list[ClassMethodStructure] = class_data.get("methods", [])

        if attributes:
            self._append_class_attributes_md(lines, attributes)

        if methods:
            if attributes:
                lines.append("\n")  # Prázdny riadok medzi Class variables a Methods
            self._append_class_methods_md(lines, methods)
        elif attributes:  # Iba atribúty, žiadne metódy
            lines.append("\n")  # Prázdny riadok za atribútmi

    def _format_file_entry(
        self: "GenerateSourceIndexNode", file_display_path: str, structure: ModuleStructure, file_number: int
    ) -> list[str]:
        """Format the Markdown entry for a single Python file using its parsed structure."""
        # ... (väčšina metódy zostáva rovnaká) ...
        self._logger.debug("Formatting file entry for: %s (File #: %d)", file_display_path, file_number)
        lines: list[str] = ["\n##\n"]

        p = Path(file_display_path)
        parent_dir_for_h6 = p.parent.as_posix()
        if parent_dir_for_h6 == ".":
            parent_dir_for_h6 = "./"
        elif parent_dir_for_h6 and not parent_dir_for_h6.endswith("/"):
            parent_dir_for_h6 = f"{parent_dir_for_h6}/"

        lines.append(f"###### {file_number}) {parent_dir_for_h6}\n")
        lines.append(f"#  {p.name}\n")  # H1 for filename

        parsing_error = structure.get("parsing_error")
        module_doc = structure.get("doc", "")
        module_functions = structure.get("functions", [])
        classes = structure.get("classes", {})

        # Popis modulu priamo pod H1 názvom súboru
        if parsing_error:
            lines.append(f"... Error parsing this file: {parsing_error}\n")
        elif module_doc:
            lines.append(f"... {module_doc}\n")
        elif not classes and not module_functions:
            lines.append("... (No parseable content or docstring found)\n")
        # Ak chýba modulový docstring, ale sú funkcie/triedy, tak sa nevypíše nič špeciálne tu.

        self._append_module_functions_md(lines, module_functions, file_display_path)

        sorted_class_names = sorted(classes.keys())
        for class_name in sorted_class_names:
            self._append_class_md(lines, class_name, classes[class_name])

        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append("---\n")

        self._logger.debug("Generated %d Markdown lines for file entry: %s", len(lines), file_display_path)
        return lines

    # ... (prep, exec, post and other formatting methods remain the same as previous version) ...
    def _format_non_python_file_entry(
        self, lines: list[str], processed_file_number: int, file_display_path: str, content: Optional[str]
    ) -> None:
        """Format entry for a non-Python file."""
        p_non_py = Path(file_display_path)
        parent_for_h6 = p_non_py.parent.as_posix()
        parent_for_h6 = "./" if parent_for_h6 == "." else f"{parent_for_h6}/" if parent_for_h6 else "./"
        lines.extend(["\n##\n", f"###### {processed_file_number}) {parent_for_h6}\n", f"#  {p_non_py.name}\n"])
        first_line_doc = ""
        if content and content.strip():
            first_line_doc = content.strip().split("\n", 1)[0].strip()
            if (first_line_doc.startswith('"""') and first_line_doc.endswith('"""')) or (
                first_line_doc.startswith("'''") and first_line_doc.endswith("'''")
            ):
                first_line_doc = first_line_doc[3:-3].strip()
            elif first_line_doc.startswith("#"):
                first_line_doc = first_line_doc[1:].strip()
        lines.append(
            f"\n... {first_line_doc}\n"
            if first_line_doc
            else "\n... (Content for non-Python file or no parseable first line)\n"
        )
        if not lines[-1].endswith("\n\n") and lines[-1].endswith("\n"):
            lines.append("\n")
        elif not lines[-1].endswith("\n"):
            lines.append("\n\n")
        lines.append("---\n")

    def _format_python_index(
        self: "GenerateSourceIndexNode", project_name: str, files_data: FileData, project_scan_root_display: str
    ) -> str:
        """Format the source index for Python projects using AST parsing."""
        self._logger.info(
            "Method _format_python_index entered for project: '%s'. Scan root display for H6: '%s'",
            project_name,
            project_scan_root_display,
        )
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}"]
        python_file_count = 0
        non_python_file_count = 0
        visitor = PythonCodeVisitor()
        processed_file_number = 0
        for i, item in enumerate(files_data):
            processed_file_number += 1
            if not (isinstance(item, tuple) and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH):
                self._logger.error("Item %d invalid. Skipping.", i)
                continue
            path_from_files_data, content = item
            if not isinstance(path_from_files_data, str) or not (isinstance(content, str) or content is None):
                self._logger.error("Path/content for item %d invalid. Skipping.", i)
                continue

            file_display_path = (Path(project_scan_root_display) / path_from_files_data).as_posix()
            if path_from_files_data.endswith((".py", ".pyi")):
                python_file_count += 1
                parse_content = content if isinstance(content, str) else ""
                structure = visitor.parse(parse_content)
                file_entry_lines = self._format_file_entry(file_display_path, structure, processed_file_number)
                markdown_lines.extend(file_entry_lines)
            else:
                non_python_file_count += 1
                self._logger.debug("Adding simple entry for non-Python file: %s", file_display_path)
                self._format_non_python_file_entry(markdown_lines, processed_file_number, file_display_path, content)

        if processed_file_number == 0:
            markdown_lines.append("\n\nNo files found to index.\n")
        result = "".join(markdown_lines)
        self._logger.info(
            "Finished Python index for '%s'. Py files: %d, Non-Py: %d. Len: %d",
            project_name,
            python_file_count,
            non_python_file_count,
            len(result),
        )
        return result

    def _format_generic_index(
        self: "GenerateSourceIndexNode", project_name: str, files_data: FileData, project_scan_root_display: str
    ) -> str:
        """Format a generic source index listing files."""
        self._logger.info(
            "Starting generic source index for project: '%s', Scan root: '%s'", project_name, project_scan_root_display
        )
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}"]
        if not files_data:
            markdown_lines.append("\n\nNo files found or provided.\n")
        else:
            for i, item in enumerate(files_data):
                if not (isinstance(item, tuple) and len(item) >= 1 and isinstance(item[0], str)):
                    continue
                path_from_files_data = item[0]
                content_str = item[1] if len(item) > 1 and isinstance(item[1], str) else ""
                file_display_path_obj = Path(project_scan_root_display) / path_from_files_data
                parent_for_h6 = file_display_path_obj.parent.as_posix()
                parent_for_h6 = "./" if parent_for_h6 == "." else f"{parent_for_h6}/" if parent_for_h6 else "./"
                markdown_lines.extend(
                    ["\n##\n", f"###### {i + 1}) {parent_for_h6}\n", f"#  {file_display_path_obj.name}\n"]
                )
                first_line_doc = ""
                if content_str:
                    cleaned_content = content_str.strip()
                    doc_match_py = re.match(r"^\s*(\"\"\"(.*?)\"\"\"|'''(.*?)''')", cleaned_content, re.DOTALL)
                    if doc_match_py:
                        doc_content = doc_match_py.group(2) or doc_match_py.group(3)
                        first_line_doc = doc_content.strip().split("\n", 1)[0].strip() if doc_content else ""
                    if not first_line_doc:
                        first_line_doc = cleaned_content.split("\n", 1)[0].strip()
                    if first_line_doc.startswith("#"):
                        first_line_doc = first_line_doc[1:].strip()
                markdown_lines.append(
                    f"\n... {first_line_doc}\n"
                    if first_line_doc
                    else "\n... (No descriptive first line or docstring found)\n"
                )
                if not markdown_lines[-1].endswith("\n\n") and markdown_lines[-1].endswith("\n"):
                    markdown_lines.append("\n")
                elif not markdown_lines[-1].endswith("\n"):
                    markdown_lines.append("\n\n")
                markdown_lines.append("---\n")
        result = "".join(markdown_lines)
        self._logger.info("Finished generic source index. Content length: %d", len(result))
        return result

    def prep(self: "GenerateSourceIndexNode", shared: SharedState) -> SourceIndexPrepResult:
        """Prepare data and configuration for source index generation.

        Args:
            shared: The shared state dictionary from the workflow.

        Returns:
            A dictionary containing preparation results and parameters for the `exec` method.

        """
        self._logger.info(">>> GenerateSourceIndexNode.prep: METHOD ENTRY POINT <<<")
        try:
            files_data: FileData = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            config: ConfigDict = self._get_required_shared(shared, "config")
            source_config: ConfigDict = self._get_required_shared(shared, "source_config")
            project_scan_root_display = shared.get("local_dir_display_root", "")
            project_scan_root_display = (
                "./"
                if project_scan_root_display == "."
                else project_scan_root_display.rstrip("/")
                if project_scan_root_display
                else "./"
            )
            output_config = config.get("output", {})
            include_source_index_flag = output_config.get("include_source_index", False)
            self._logger.info(
                "Effective config: include_source_index=%s, scan_root_display='%s'",
                include_source_index_flag,
                project_scan_root_display,
            )
            if not include_source_index_flag:
                return {"skip": True, "reason": "Disabled via output.include_source_index"}
            language = source_config.get("language", "unknown")
            parser_type = source_config.get("source_index_parser", "none")
            self._logger.info("Decision for source_index details: language=%s, parser_type=%s", language, parser_type)
            return {
                "skip": False,
                "files_data": files_data,
                "project_name": project_name,
                "language": language,
                "parser_type": parser_type,
                "project_scan_root_display": project_scan_root_display,
                "llm_config": self._get_required_shared(shared, "llm_config"),
                "cache_config": self._get_required_shared(shared, "cache_config"),
            }
        except ValueError as e:
            self._logger.error("Prep missing data: %s", e, exc_info=True)
            return {"skip": True, "reason": f"Missing data: {e!s}"}
        except Exception as e:
            self._logger.error("Prep error: %s", e, exc_info=True)
            return {"skip": True, "reason": f"Prep error: {e!s}"}

    def exec(self: "GenerateSourceIndexNode", prep_res: SourceIndexPrepResult) -> SourceIndexExecResult:
        """Generate the Markdown content for the source index.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A string containing the generated Markdown content, or None if skipped/failed.

        """
        self._logger.info(">>> GenerateSourceIndexNode.exec: ENTRY. prep_res type: %s <<<", type(prep_res).__name__)
        if not isinstance(prep_res, dict):
            self._logger.error("Exec prep_res not dict. Skipping.")
            return None
        if prep_res.get("skip", True):
            self._logger.info("Skipping exec: %s", prep_res.get("reason"))
            return None

        files_data: FileData = prep_res.get("files_data", [])
        project_name: str = prep_res.get("project_name", "Unknown")
        language: str = prep_res.get("language", "unknown")
        parser_type: str = prep_res.get("parser_type", "none")
        scan_root: str = prep_res.get("project_scan_root_display", "./")
        self._logger.info(
            "Executing index for '%s' (Lang:%s, Parser:%s, Files:%d, Root:'%s')",
            project_name,
            language,
            parser_type,
            len(files_data),
            scan_root,
        )

        if not files_data:
            return f"# Code Inventory: {project_name}\n\nNo files for indexing.\n"
        try:
            markdown_content: str
            if parser_type == "ast" and language == "python":
                self._logger.info("Calling _format_python_index (AST based).")
                markdown_content = self._format_python_index(project_name, files_data, scan_root)
            elif parser_type == "llm":
                self._logger.warning(
                    "LLM-based source index parsing for language '%s' is not yet fully implemented. "
                    "Falling back to generic file list.",
                    language,
                )
                markdown_content = self._format_generic_index(project_name, files_data, scan_root)
            else:
                self._logger.info("Using generic file list for source index (parser: %s).", parser_type)
                markdown_content = self._format_generic_index(project_name, files_data, scan_root)

            return markdown_content if markdown_content.strip() else None
        except Exception as e:
            self._logger.error("Error generating index markdown: %s", e, exc_info=True)
            return None

    def post(
        self: "GenerateSourceIndexNode",
        shared: SharedState,
        prep_res: SourceIndexPrepResult,
        exec_res: SourceIndexExecResult,
    ) -> None:
        """Store the generated source index content in the shared state.

        Args:
            shared: The shared state dictionary.
            prep_res: The result from the `prep` method.
            exec_res: The result from the `exec` method.

        """
        self._logger.info(">>> GenerateSourceIndexNode.post: ENTRY <<<")
        shared["source_index_content"] = None
        prep_summary = (
            {k: v for k, v in prep_res.items() if k != "files_data"} if isinstance(prep_res, dict) else str(prep_res)
        )
        if isinstance(prep_res, dict) and "files_data" in prep_res:
            prep_summary["files_data_count"] = len(prep_res["files_data"])
        self._logger.info("Post called. prep_res summary: %r", prep_summary)
        self._logger.info("exec_res type: %s", type(exec_res).__name__)
        if isinstance(exec_res, str):
            self._logger.info("exec_res length: %d", len(exec_res))

        should_proc = isinstance(prep_res, dict) and not prep_res.get("skip", True)
        if should_proc and isinstance(exec_res, str) and exec_res.strip():
            shared["source_index_content"] = exec_res
            self._logger.info("Stored VALID index content (len: %d).", len(exec_res))
        elif should_proc:
            self._logger.warning(
                "Index content None/empty from exec. Shared state not updated. exec_res type: %s.",
                type(exec_res).__name__,
            )
        else:
            self._logger.info(
                "Index gen skipped. Reason: %s.", prep_res.get("reason", "N/A") if isinstance(prep_res, dict) else "N/A"
            )
        self._logger.info(">>> GenerateSourceIndexNode.post: EXIT <<<")


# End of src/sourcelens/nodes/generate_source_index.py
