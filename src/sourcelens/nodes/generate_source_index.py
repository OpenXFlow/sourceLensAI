# src/sourcelens/nodes/generate_source_index.py

"""Node responsible for generating a source code index/inventory file.

This node can parse Python code using AST to extract modules, classes,
and functions, or provide a generic file listing for other languages.
The output is a Markdown formatted string.
"""

import ast
import logging
import re
from collections import defaultdict
from pathlib import Path
from typing import TYPE_CHECKING, Any, Final, Optional, Union

from typing_extensions import TypeAlias

from .base_node import BaseNode, SharedState

if TYPE_CHECKING:
    ConfigDict: TypeAlias = dict[str, Any]

# --- Type Aliases specific to this Node ---
SourceIndexPrepResult: TypeAlias = dict[str, Any]
SourceIndexExecResult: TypeAlias = Optional[str]

# --- Other Type Aliases used within this module ---
FileDataList: TypeAlias = list[tuple[str, str]]
ClassAttributeStructure: TypeAlias = dict[str, str]
ClassMethodStructure: TypeAlias = dict[str, str]
ClassStructure: TypeAlias = dict[str, Any]
FunctionStructure: TypeAlias = dict[str, str]
ModuleStructure: TypeAlias = dict[str, Any]
DirTree: TypeAlias = dict[str, Any]

# Type alias for AST nodes that can have docstrings processed by ast.get_docstring
DocstringParentNode: TypeAlias = Union[ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef]

visitor_logger: logging.Logger = logging.getLogger(__name__ + ".PythonCodeVisitor")

# --- Constants ---
DEBUG_SNIPPET_LENGTH: Final[int] = 50
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2
MAX_SUMMARY_DOC_LENGTH: Final[int] = 100
MAX_SUMMARY_DOC_SNIPPET_LEN: Final[int] = MAX_SUMMARY_DOC_LENGTH - 3


class PythonCodeVisitor(ast.NodeVisitor):
    """An AST visitor to extract classes, methods, and functions from Python code.

    This visitor traverses the Abstract Syntax Tree of a Python module
    and collects information about its top-level functions, classes (including
    their attributes and methods), and the module's docstring.
    """

    def __init__(self: "PythonCodeVisitor") -> None:
        """Initialize the visitor, resetting its internal state."""
        super().__init__()
        self.module_doc: Optional[str] = None
        self.classes: dict[str, ClassStructure] = defaultdict(
            lambda: {"doc": "", "decorators": [], "attributes": [], "methods": []}
        )
        self.functions: list[FunctionStructure] = []
        self._current_class_name: Optional[str] = None
        self._source_code_lines: list[str] = []
        visitor_logger.debug("PythonCodeVisitor initialized.")

    def _get_first_line_of_docstring(self: "PythonCodeVisitor", node: DocstringParentNode) -> str:
        """Extract the first line of a docstring from an AST node.

        Args:
            node: The AST node (e.g., Module, ClassDef, FunctionDef).

        Returns:
            The first line of the docstring if present and non-empty,
            otherwise an empty string.

        """
        docstring: Optional[str] = ast.get_docstring(node, clean=False)
        if docstring:
            return docstring.lstrip().split("\n", 1)[0].strip()
        return ""

    def _is_forward_ref_candidate(self: "PythonCodeVisitor", name: str) -> bool:
        """Heuristically determine if a name is a candidate for forward reference quoting.

        Args:
            name: The name string to check.

        Returns:
            True if the name is a likely candidate for forward reference, False otherwise.

        """
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

    def _parse_annotation_segment(self: "PythonCodeVisitor", segment: str, *, is_self_arg: bool) -> str:
        """Parse an annotation string obtained from ast.get_source_segment.

        Args:
            segment: The code segment for the annotation.
            is_self_arg: Keyword-only. True if annotation is for 'self' or 'cls'.

        Returns:
            A formatted string for the annotation.

        """
        cleaned_segment = segment.strip()
        if is_self_arg and self._current_class_name and cleaned_segment == self._current_class_name:
            return f'"{cleaned_segment}"'

        generic_match = re.fullmatch(r"(\w+)\[(['\"]?)(.+?)(['\"]?)\]", cleaned_segment)
        if generic_match:
            base_type, q1, inner_types_str, q2 = generic_match.groups()
            inner_params = [p.strip() for p in inner_types_str.split(",")]
            formatted_inner_params = []
            for p_raw in inner_params:
                p = p_raw.strip("'\" ")
                formatted_inner_params.append(f'"{p}"' if self._is_forward_ref_candidate(p) else p)
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

    def _parse_node_based_annotation(self: "PythonCodeVisitor", node: ast.expr, *, is_self_arg: bool) -> str:
        """Parse an annotation based on the AST node type (fallback).

        Args:
            node: The AST expression node for the annotation.
            is_self_arg: Keyword-only. True if annotation is for 'self' or 'cls'.

        Returns:
            A formatted string for the annotation.

        """
        res_str: str
        if isinstance(node, ast.Name):
            name_id = node.id
            if name_id == "None":
                res_str = "None"
            elif (
                is_self_arg and self._current_class_name and name_id == self._current_class_name
            ) or self._is_forward_ref_candidate(name_id):
                res_str = f'"{name_id}"'
            else:
                res_str = name_id
        elif isinstance(node, ast.Constant) and node.value is None:
            res_str = "None"
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            res_str = node.value
        elif isinstance(node, ast.Subscript):
            value_str = self._get_annotation_str(node.value, is_self_arg=False)
            slice_val = node.slice
            slice_inner_str: str
            if isinstance(slice_val, ast.Tuple):
                slice_elts = [self._get_annotation_str(elt, is_self_arg=False) for elt in slice_val.elts]
                slice_inner_str = ", ".join(slice_elts)
            else:
                slice_inner_str = self._get_annotation_str(slice_val, is_self_arg=False)
            res_str = f"{value_str}[{slice_inner_str}]"
        else:
            visitor_logger.debug(
                "Returning 'Any' for unparseable annotation node type: %s (Code: %s)",
                type(node).__name__,
                ast.dump(node) if hasattr(ast, "dump") else str(node),
            )
            res_str = "Any"
        return res_str

    def _get_annotation_str(self: "PythonCodeVisitor", node: Optional[ast.expr], *, is_self_arg: bool = False) -> str:
        """Attempt to get the source string for a type annotation node.

        Args:
            node: The AST expression node for the annotation. Can be None.
            is_self_arg: Keyword-only. True if for 'self' or 'cls' argument.

        Returns:
            A formatted string representation of the type annotation, or "Any" as a fallback.

        """
        if node is None:
            return ""
        if self._source_code_lines and hasattr(node, "lineno"):
            try:
                full_source_code = "".join(self._source_code_lines)
                segment = ast.get_source_segment(full_source_code, node)
                if segment:
                    return self._parse_annotation_segment(segment, is_self_arg=is_self_arg)
            except (AttributeError, TypeError, ValueError, IndexError) as e_segment:
                visitor_logger.debug(
                    "Failed to get source segment for annotation node (line %s): %s. Falling back to AST parsing.",
                    getattr(node, "lineno", "N/A"),
                    str(e_segment),
                )
        return self._parse_node_based_annotation(node, is_self_arg=is_self_arg)

    def _format_single_arg(self, arg_node: ast.arg, *, has_default: bool, is_self_or_cls: bool) -> str:
        """Format a single argument node. Helper for _format_arguments.

        Args:
            arg_node: The ast.arg node to format.
            has_default: Keyword-only. True if the argument has a default value.
            is_self_or_cls: Keyword-only. True if the argument is 'self' or 'cls'.

        Returns:
            A string representation of the formatted argument.

        """
        anno_str = self._get_annotation_str(arg_node.annotation, is_self_arg=is_self_or_cls)
        arg_repr = f"{arg_node.arg}: {anno_str}" if anno_str else arg_node.arg
        if has_default:
            arg_repr += " = ..."
        return arg_repr

    def _format_arguments(self: "PythonCodeVisitor", args_node: ast.arguments) -> str:
        """Format function arguments including type hints and default value indicators.

        Args:
            args_node: The AST arguments node.

        Returns:
            A string representing the formatted arguments list.

        """
        args_list: list[str] = []
        num_regular_args = len(args_node.args)

        for arg in args_node.posonlyargs:
            args_list.append(self._format_single_arg(arg, has_default=False, is_self_or_cls=False))
        if args_node.posonlyargs:
            args_list.append("/")

        for i, arg in enumerate(args_node.args):
            is_self_or_cls = (
                arg.arg in {"self", "cls"}
                and (i == 0 and not args_node.posonlyargs)
                and self._current_class_name is not None
            )
            has_default = (num_regular_args - 1 - i) < len(args_node.defaults)
            args_list.append(self._format_single_arg(arg, has_default=has_default, is_self_or_cls=is_self_or_cls))

        if args_node.vararg:
            vararg_anno = self._get_annotation_str(args_node.vararg.annotation)
            args_list.append(f"*{args_node.vararg.arg}: {vararg_anno}" if vararg_anno else f"*{args_node.vararg.arg}")

        if args_node.kwonlyargs:
            if not args_node.vararg:
                args_list.append("*")
            for i, arg in enumerate(args_node.kwonlyargs):
                has_default = args_node.kw_defaults[i] is not None
                args_list.append(self._format_single_arg(arg, has_default=has_default, is_self_or_cls=False))

        if args_node.kwarg:
            kwarg_anno = self._get_annotation_str(args_node.kwarg.annotation)
            args_list.append(f"**{args_node.kwarg.arg}: {kwarg_anno}" if kwarg_anno else f"**{args_node.kwarg.arg}")

        return ", ".join(filter(None, args_list))

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

    def _get_decorator_name_str(self: "PythonCodeVisitor", decorator_func_node: ast.expr) -> str:
        """Return the name part of a decorator's function or attribute chain.

        Args:
            decorator_func_node: The AST node representing the callable part of a decorator.

        Returns:
            A string representation of the decorator's function name.

        """
        if isinstance(decorator_func_node, ast.Name):
            return decorator_func_node.id
        if isinstance(decorator_func_node, ast.Attribute):
            value_str = self._get_decorator_name_str(decorator_func_node.value)
            return f"{value_str}.{decorator_func_node.attr}"
        try:
            if self._source_code_lines and hasattr(decorator_func_node, "lineno"):
                full_source_code = "".join(self._source_code_lines)
                segment = ast.get_source_segment(full_source_code, decorator_func_node)
                if segment:
                    return segment.strip()
        except (TypeError, ValueError, IndexError, AttributeError) as e_dec_segment:
            visitor_logger.debug(
                "Could not get source segment for decorator part: %s", str(e_dec_segment), exc_info=False
            )
        return "..."

    def _get_decorator_str(self: "PythonCodeVisitor", decorator_node: ast.expr) -> str:
        """Convert a decorator AST node to its string representation.

        Args:
            decorator_node: The AST node representing the decorator.

        Returns:
            A string representation of the decorator.

        """
        try:
            if self._source_code_lines and hasattr(decorator_node, "lineno"):
                full_source_code = "".join(self._source_code_lines)
                dec_src = ast.get_source_segment(full_source_code, decorator_node)
                if dec_src:
                    return f"@{dec_src.strip()}"
        except (TypeError, ValueError, IndexError, AttributeError) as e_dec_str_segment:  # noqa: BLE001
            visitor_logger.debug(
                "Failed to get source segment for decorator %s: %s. Falling back to AST parsing.",
                str(decorator_node),
                str(e_dec_str_segment),
                exc_info=False,
            )

        if isinstance(decorator_node, (ast.Name, ast.Attribute)):
            return f"@{self._get_decorator_name_str(decorator_node)}"
        if isinstance(decorator_node, ast.Call):
            func_str = self._get_decorator_name_str(decorator_node.func)
            return f"@{func_str}(...)"
        return "@..."

    def visit_Module(self: "PythonCodeVisitor", node: ast.Module) -> None:
        """Visit a Module node and extract its docstring.

        Args:
            node: The ast.Module node.

        """
        self.module_doc = self._get_first_line_of_docstring(node)
        self.generic_visit(node)

    def visit_ClassDef(self: "PythonCodeVisitor", node: ast.ClassDef) -> None:
        """Visit a ClassDef node.

        Args:
            node: The ast.ClassDef node.

        """
        class_name = node.name
        original_current_class_name_context = self._current_class_name
        self._current_class_name = class_name

        class_data = self.classes[class_name]
        class_data["doc"] = self._get_first_line_of_docstring(node)
        class_data["decorators"] = [self._get_decorator_str(d) for d in node.decorator_list]

        for child_node in node.body:
            if isinstance(child_node, ast.AnnAssign) and isinstance(child_node.target, ast.Name):
                annotation_str = self._get_annotation_str(child_node.annotation) or "Any"
                class_data["attributes"].append({"name": child_node.target.id, "type": annotation_str})
            elif isinstance(child_node, ast.Assign):
                for target_node in child_node.targets:
                    if isinstance(target_node, ast.Name):
                        class_data["attributes"].append({"name": target_node.id, "type": "Any # (Assigned)"})
            elif isinstance(child_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(child_node)
        self._current_class_name = original_current_class_name_context

    def visit_FunctionDef(self: "PythonCodeVisitor", node: ast.FunctionDef) -> None:
        """Visit a FunctionDef node.

        Args:
            node: The ast.FunctionDef node.

        """
        func_name = node.name
        args_str = self._format_arguments(node.args)
        return_anno_str = self._format_return_annotation(node.returns)
        signature = f"def {func_name}({args_str}){return_anno_str}"
        doc = self._get_first_line_of_docstring(node)

        if self._current_class_name:
            self.classes[self._current_class_name]["methods"].append({"signature": signature, "doc": doc})
        else:
            self.functions.append({"signature": signature, "doc": doc})

    def visit_AsyncFunctionDef(self: "PythonCodeVisitor", node: ast.AsyncFunctionDef) -> None:
        """Visit an AsyncFunctionDef node.

        Args:
            node: The ast.AsyncFunctionDef node.

        """
        func_name = node.name
        args_str = self._format_arguments(node.args)
        return_anno_str = self._format_return_annotation(node.returns)
        signature = f"async def {func_name}({args_str}){return_anno_str}"
        doc = self._get_first_line_of_docstring(node)

        if self._current_class_name:
            self.classes[self._current_class_name]["methods"].append({"signature": signature, "doc": doc})
        else:
            self.functions.append({"signature": signature, "doc": doc})

    def parse(self: "PythonCodeVisitor", code: str) -> ModuleStructure:
        """Parse Python code and return its structured representation.

        Args:
            code: The Python source code as a string.

        Returns:
            A `ModuleStructure` dictionary.

        """
        self._source_code_lines = code.splitlines(keepends=True)
        self.module_doc = None
        self.classes.clear()
        self.functions.clear()
        self._current_class_name = None
        parsing_error_message: Optional[str] = None

        try:
            ast_tree = ast.parse(code)
            self.visit(ast_tree)
        except SyntaxError as e:
            parsing_error_message = f"SyntaxError: {e.msg} (line {e.lineno}, offset {e.offset or 0})"
            visitor_logger.warning("Failed to parse code due to SyntaxError: %s", e)
        except Exception as e:  # noqa: BLE001
            parsing_error_message = f"AST Parsing Error: {str(e)}"
            visitor_logger.error("An unexpected error occurred during AST parsing: %s", e, exc_info=True)

        return {
            "doc": self.module_doc or "",
            "classes": dict(self.classes),
            "functions": self.functions,
            "parsing_error": parsing_error_message,
        }


class GenerateSourceIndexNode(BaseNode[SourceIndexPrepResult, SourceIndexExecResult]):
    """Generates a Markdown file listing files, classes, and functions."""

    def _generate_mermaid_file_structure(
        self: "GenerateSourceIndexNode", project_scan_root_display: str, files_data: FileDataList
    ) -> str:
        """Generate Mermaid code for a file structure diagram.

        Args:
            project_scan_root_display: The display name for the root of the project scan.
            files_data: A list of (relative_path_to_scan_root, content) tuples.

        Returns:
            A string containing the Mermaid graph definition for the file tree.

        """
        lines: list[str] = ["graph TD"]
        root_label = project_scan_root_display
        if not root_label.endswith("/") and root_label != ".":
            root_label += "/"
        elif root_label == ".":
            root_label = "./"
        root_node_id_mermaid = "ROOT_DIR_MERMAID"
        lines.append(f'    {root_node_id_mermaid}["{root_label}"]')
        node_definitions: list[str] = []
        connections: list[str] = []
        style_assignments: list[str] = [f"    class {root_node_id_mermaid} dir;"]
        tree: DirTree = defaultdict(dict)
        file_id_map: dict[str, str] = {}
        for i, (path_rel_to_scan_root, _) in enumerate(files_data):
            p_rel = Path(path_rel_to_scan_root)
            file_node_id = f"FILE_{i}"
            file_id_map[path_rel_to_scan_root] = file_node_id
            node_definitions.append(f'    {file_node_id}["{p_rel.name}"]')
            style_assignments.append(f"    class {file_node_id} file;")
            current_level = tree
            for part in p_rel.parent.parts:
                current_level = current_level.setdefault(part, {})
            current_level[p_rel.name] = file_node_id
        dir_id_counter: dict[str, int] = {"val": 0}

        def generate_recursive_mermaid_for_tree(
            _current_dir_name_disp: str, current_tree_lvl: DirTree, parent_id: str
        ) -> None:
            """Recursively generate Mermaid for the directory tree.

            Args:
                _current_dir_name_disp: Display name for current directory (unused).
                current_tree_lvl: Current level in the tree dict.
                parent_id: Mermaid ID of the parent directory node.

            """
            sorted_items = sorted(current_tree_lvl.items(), key=lambda item_pair: not isinstance(item_pair[1], dict))
            for name, content_or_subtree in sorted_items:
                if isinstance(content_or_subtree, dict):
                    safe_dir_name_part = name.replace("/", "_").replace(".", "_")
                    sub_dir_mermaid_id = f"DIR_{safe_dir_name_part}_{dir_id_counter['val']}"
                    dir_id_counter["val"] += 1
                    node_definitions.append(f'    subgraph {sub_dir_mermaid_id} ["{name}/"]')
                    style_assignments.append(f"    class {sub_dir_mermaid_id} dir;")
                    connections.append(f"    {parent_id} --> {sub_dir_mermaid_id}")
                    generate_recursive_mermaid_for_tree(name, content_or_subtree, sub_dir_mermaid_id)
                    node_definitions.append("    end")
                else:
                    file_node_id_str: str = content_or_subtree
                    connections.append(f"    {parent_id} --> {file_node_id_str}")

        generate_recursive_mermaid_for_tree(root_label, tree, root_node_id_mermaid)
        lines.extend(node_definitions)
        lines.extend(connections)
        lines.extend(
            [
                "\n    %% Styling for better readability",
                "    classDef dir fill:#dadada,stroke:#333,stroke-width:2px,color:#333,font-weight:bold",
                "    classDef file fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#333",
            ]
        )
        lines.extend(style_assignments)
        return "\n".join(lines)

    def _append_module_functions_md(
        self: "GenerateSourceIndexNode", lines: list[str], module_functions: list[FunctionStructure], path_str: str
    ) -> None:
        """Append Markdown for module-level functions.

        Args:
            lines: List of Markdown lines to append to.
            module_functions: List of function structures.
            path_str: File path, for logging context.

        """
        if module_functions:
            self._logger.debug("Formatting %d module functions for %s", len(module_functions), path_str)
            if lines and lines[-1].strip():
                lines.append("\n")
            for func_info in sorted(module_functions, key=lambda x: x.get("signature", "")):
                signature = func_info.get("signature", "Unknown signature")
                doc = func_info.get("doc", "")
                lines.append(f"*   **`{signature}:`**\n")
                if doc:
                    lines.append(f"    ... {doc}\n")

    def _append_class_attributes_md(
        self: "GenerateSourceIndexNode", lines: list[str], attributes: list[ClassAttributeStructure]
    ) -> None:
        """Append Markdown for class attributes.

        Args:
            lines: List of Markdown lines to append to.
            attributes: List of attribute structures.

        """
        if attributes:
            lines.append("    #### *Class variables:*\n")
            for attr in sorted(attributes, key=lambda x: x.get("name", "")):
                name = attr.get("name", "N/A")
                attr_type = attr.get("type", "Any")
                lines.append(f"    *   **`{name}: {attr_type}`**\n")

    def _append_class_methods_md(
        self: "GenerateSourceIndexNode", lines: list[str], methods: list[ClassMethodStructure]
    ) -> None:
        """Append Markdown for class methods.

        Args:
            lines: List of Markdown lines to append to.
            methods: List of method structures.

        """
        if methods:
            lines.append("    #### *Methods:*\n")
            for method_info in sorted(methods, key=lambda x: x.get("signature", "")):
                signature = method_info.get("signature", "Unknown signature")
                doc = method_info.get("doc", "")
                lines.append(f"    *   **`{signature}:`**\n")
                if doc:
                    lines.append(f"        ... {doc}\n")

    def _append_class_md(
        self: "GenerateSourceIndexNode", lines: list[str], class_name: str, class_data: ClassStructure
    ) -> None:
        """Append Markdown for a single class.

        Args:
            lines: List of Markdown lines to append to.
            class_name: The name of the class.
            class_data: Structure of the class.

        """
        if lines and lines[-1].strip() and not lines[-1].endswith(("\n\n", "\n")):
            lines.append("\n\n")
        elif lines and not lines[-1].endswith("\n"):
            lines.append("\n")

        for decorator_str in class_data.get("decorators", []):
            lines.append(f"**`{decorator_str}`**\n")

        lines.append(f"### **`class {class_name}()`**\n")
        class_doc_str = class_data.get("doc", "")
        lines.append(f"... {class_doc_str}\n" if class_doc_str else "... No class docstring found.\n")
        lines.append("\n")

        attributes: list[ClassAttributeStructure] = class_data.get("attributes", [])
        methods: list[ClassMethodStructure] = class_data.get("methods", [])

        if attributes:
            self._append_class_attributes_md(lines, attributes)
        if methods:
            if attributes:
                lines.append("\n")
            self._append_class_methods_md(lines, methods)

    def _format_file_entry(
        self: "GenerateSourceIndexNode", file_display_path: str, structure: ModuleStructure, file_number: int
    ) -> list[str]:
        """Format the Markdown entry for a single Python file using its parsed structure.

        Args:
            file_display_path: The path of the file to display.
            structure: The `ModuleStructure` dictionary from `PythonCodeVisitor`.
            file_number: The sequential number of the file in the index.

        Returns:
            A list of Markdown lines representing the entry for this file.

        """
        self._logger.debug("Formatting file entry for: %s (File #: %d)", file_display_path, file_number)
        lines: list[str] = ["\n##\n"]
        p = Path(file_display_path)
        parent_dir_for_h6 = p.parent.as_posix()
        if parent_dir_for_h6 == ".":
            parent_dir_for_h6 = "./"
        elif parent_dir_for_h6 and not parent_dir_for_h6.endswith("/"):
            parent_dir_for_h6 += "/"
        elif not parent_dir_for_h6:
            parent_dir_for_h6 = "./"

        lines.append(f"###### {file_number}) {parent_dir_for_h6}\n")
        lines.append(f"#  {p.name}\n")

        parsing_error = structure.get("parsing_error")
        module_doc = structure.get("doc", "")
        module_functions = structure.get("functions", [])
        classes = structure.get("classes", {})

        if parsing_error:
            lines.append(f"... Error parsing this file: {parsing_error}\n")
        elif module_doc:
            lines.append(f"... {module_doc}\n")
        elif not classes and not module_functions:
            lines.append("... (No parseable top-level functions or classes, and no module docstring found)\n")
        elif not module_doc:
            lines.append("... No module-level docstring found.\n")

        self._append_module_functions_md(lines, module_functions, file_display_path)
        for class_name in sorted(classes.keys()):
            self._append_class_md(lines, class_name, classes[class_name])

        if lines and lines[-1].strip():
            lines.append("\n")
        lines.append("---\n")
        return lines

    def _format_file_summary_list(
        self: "GenerateSourceIndexNode", files_data: FileDataList, visitor: PythonCodeVisitor
    ) -> list[str]:
        """Format a summary list of files with their module docstrings.

        Args:
            files_data: List of (filepath, content) tuples.
            visitor: An instance of PythonCodeVisitor.

        Returns:
            A list of Markdown lines for the file summary.

        """
        summary_lines: list[str] = ["\n## File Descriptions Summary\n"]
        if not files_data:
            summary_lines.append("No files to summarize.\n")
            return summary_lines

        for path_rel_to_scan_root, file_content_str in files_data:
            file_name_only = Path(path_rel_to_scan_root).name
            module_doc_for_summary = ""
            if path_rel_to_scan_root.endswith((".py", ".pyi")) and file_content_str:
                temp_structure = visitor.parse(file_content_str)
                module_doc_for_summary = temp_structure.get("doc", "")
            elif file_content_str:
                first_line = file_content_str.strip().split("\n", 1)[0].strip()
                if (first_line.startswith('"""') and first_line.endswith('"""')) or (
                    first_line.startswith("'''") and first_line.endswith("'''")
                ):
                    module_doc_for_summary = first_line[3:-3].strip()
                elif first_line.startswith("#"):
                    module_doc_for_summary = first_line[1:].strip()
                else:
                    module_doc_for_summary = first_line
                if len(module_doc_for_summary) > MAX_SUMMARY_DOC_LENGTH:
                    module_doc_for_summary = module_doc_for_summary[:MAX_SUMMARY_DOC_SNIPPET_LEN] + "..."
            doc_to_display = module_doc_for_summary if module_doc_for_summary else "No specific description available."
            summary_lines.append(f"*   **`{file_name_only}`**: {doc_to_display}\n")
        summary_lines.append("\n---\n")
        return summary_lines

    def _format_detailed_file_entries(
        self: "GenerateSourceIndexNode",
        files_data: FileDataList,
        project_scan_root_display: str,
        visitor: PythonCodeVisitor,
    ) -> tuple[list[str], int]:
        """Format detailed entries for each file.

        Args:
            files_data: List of (filepath, content) tuples.
            project_scan_root_display: Display root for paths.
            visitor: An instance of PythonCodeVisitor.

        Returns:
            A tuple: list of Markdown lines for detailed entries, and count of processed files.

        """
        detailed_lines: list[str] = ["\n## Detailed File Content\n"]
        processed_file_count = 0
        for i, item in enumerate(files_data):
            processed_file_count += 1
            if not (isinstance(item, tuple) and len(item) == EXPECTED_FILE_DATA_TUPLE_LENGTH):
                self._log_error("Invalid item structure at index %d. Skipping.", i)
                continue
            path_from_files_data, content = item
            if not (isinstance(path_from_files_data, str) and (isinstance(content, str) or content is None)):
                self._log_error("Invalid path/content type for item at index %d. Skipping.", i)
                continue

            file_display_path = (Path(project_scan_root_display) / path_from_files_data).as_posix()
            if path_from_files_data.endswith((".py", ".pyi")):
                structure = visitor.parse(content if isinstance(content, str) else "")
                detailed_lines.extend(self._format_file_entry(file_display_path, structure, processed_file_count))
            else:
                detailed_lines.extend(
                    self._format_non_python_file_entry(processed_file_count, file_display_path, content)
                )
        return detailed_lines, processed_file_count

    def _format_python_index(
        self: "GenerateSourceIndexNode", project_name: str, files_data: FileDataList, project_scan_root_display: str
    ) -> str:
        """Format the source index for Python projects using AST parsing.

        Args:
            project_name: The name of the project.
            files_data: List of (filepath, content) tuples.
            project_scan_root_display: Display string for the project scan root.

        Returns:
            A string containing the Markdown formatted source index.

        """
        self._log_info("Formatting Python source index for: '%s'", project_name)
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}\n"]

        if files_data:
            mermaid_code = self._generate_mermaid_file_structure(project_scan_root_display, files_data)
            markdown_lines.extend(["\n## File Structure\n", f"```mermaid\n{mermaid_code}\n```\n"])
        else:
            markdown_lines.append("\nNo files found to display structure.\n")

        visitor = PythonCodeVisitor()
        markdown_lines.extend(self._format_file_summary_list(files_data, visitor))
        detailed_lines, processed_count = self._format_detailed_file_entries(
            files_data, project_scan_root_display, visitor
        )
        markdown_lines.extend(detailed_lines)

        if processed_count == 0 and files_data:
            markdown_lines.append("\n\nNo files were processed for detailed indexing.\n")
        elif not files_data:
            markdown_lines.append("\n\nNo files found in the source to index.\n")

        result = "".join(markdown_lines)
        self._log_info(
            "Finished Python source index for '%s'. Files: %d. Length: %d", project_name, processed_count, len(result)
        )
        return result

    def _format_non_python_file_entry(
        self: "GenerateSourceIndexNode", processed_file_number: int, file_display_path: str, content: Optional[str]
    ) -> list[str]:
        """Format entry for a non-Python file.

        Args:
            processed_file_number: Sequential number of this file.
            file_display_path: Display path of the file.
            content: Optional content of the file.

        Returns:
            A list of Markdown lines for this file entry.

        """
        lines: list[str] = ["\n##\n"]
        p_non_py = Path(file_display_path)
        parent_dir_for_h6 = p_non_py.parent.as_posix()  # Corrected variable name
        if parent_dir_for_h6 == ".":
            parent_dir_for_h6 = "./"
        elif parent_dir_for_h6 and not parent_dir_for_h6.endswith("/"):
            parent_dir_for_h6 += "/"  # Corrected variable name
        elif not parent_dir_for_h6:
            parent_dir_for_h6 = "./"  # Corrected variable name

        lines.append(f"###### {processed_file_number}) {parent_dir_for_h6}\n")
        lines.append(f"#  {p_non_py.name}\n")
        first_line_doc = ""
        if content and content.strip():
            first_line_doc_raw = content.strip().split("\n", 1)[0].strip()
            if (first_line_doc_raw.startswith('"""') and first_line_doc_raw.endswith('"""')) or (
                first_line_doc_raw.startswith("'''") and first_line_doc_raw.endswith("'''")
            ):
                first_line_doc = first_line_doc_raw[3:-3].strip()
            elif first_line_doc_raw.startswith("#"):
                first_line_doc = first_line_doc_raw[1:].strip()
            else:
                first_line_doc = first_line_doc_raw
            if len(first_line_doc) > MAX_SUMMARY_DOC_LENGTH:
                first_line_doc = first_line_doc[:MAX_SUMMARY_DOC_SNIPPET_LEN] + "..."
        lines.append(f"\n... {first_line_doc}\n" if first_line_doc else "\n... (Non-Python file)\n")
        if lines[-1].strip() and not lines[-1].endswith("\n\n"):
            lines.append("\n")
        lines.append("---\n")
        return lines

    def _format_generic_index(
        self: "GenerateSourceIndexNode", project_name: str, files_data: FileDataList, project_scan_root_display: str
    ) -> str:
        """Format a generic source index listing files.

        Args:
            project_name: The name of the project.
            files_data: List of (filepath, content) tuples.
            project_scan_root_display: Display string for the project scan root.

        Returns:
            A string containing the Markdown formatted generic source index.

        """
        self._log_info("Formatting generic source index for: '%s'", project_name)
        markdown_lines: list[str] = [f"# Code Inventory: {project_name}\n"]
        if files_data:
            mermaid_code = self._generate_mermaid_file_structure(project_scan_root_display, files_data)
            markdown_lines.extend(["\n## File Structure\n", f"```mermaid\n{mermaid_code}\n```\n"])
        else:
            markdown_lines.append("\nNo files found to display structure.\n")

        markdown_lines.append("\n## File List\n")
        if files_data:
            for i, (path_rel_to_scan_root, content_str_opt) in enumerate(files_data):
                file_display_path_obj = Path(project_scan_root_display) / path_rel_to_scan_root
                file_display_path = file_display_path_obj.as_posix()
                lines_for_file = self._format_non_python_file_entry(i + 1, file_display_path, content_str_opt)
                filtered_lines = [
                    line
                    for line in lines_for_file
                    if line.strip() != "##" and not line.startswith("######") and not line.startswith("#  ")
                ]
                markdown_lines.append(f"* **`{Path(file_display_path).name}`** (`{file_display_path}`)\n")
                if filtered_lines and "".join(filtered_lines).strip() != "---":
                    markdown_lines.extend(["    " + line for line in filtered_lines if line.strip() != "---"])
        else:
            markdown_lines.append("No files found in the source to list.\n")
        return "".join(markdown_lines)

    def prep(self, shared: SharedState) -> SourceIndexPrepResult:
        """Prepare data and configuration for source index generation.

        Args:
            shared: The shared state dictionary from the workflow.

        Returns:
            A dictionary containing parameters for `exec` or a skip flag.

        """
        self._log_info(">>> GenerateSourceIndexNode.prep: Preparing for source index generation. <<<")
        try:
            files_data: FileDataList = self._get_required_shared(shared, "files")
            project_name: str = self._get_required_shared(shared, "project_name")
            config: ConfigDict = self._get_required_shared(shared, "config")
            source_config: ConfigDict = self._get_required_shared(shared, "source_config")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

            project_scan_root_display_val: Any = shared.get("local_dir_display_root", "./")
            project_scan_root_display = (
                str(project_scan_root_display_val).rstrip("/") if project_scan_root_display_val else "./"
            )
            if project_scan_root_display == ".":
                project_scan_root_display = "./"
            elif project_scan_root_display and not project_scan_root_display.endswith("/"):
                project_scan_root_display += "/"

            output_config: dict[str, Any] = config.get("output", {})
            include_source_index_flag_raw: Any = output_config.get("include_source_index")
            include_source_index_flag = (
                include_source_index_flag_raw if isinstance(include_source_index_flag_raw, bool) else False
            )
            if not isinstance(include_source_index_flag_raw, bool) and include_source_index_flag_raw is not None:
                self._log_warning("Config 'output.include_source_index' not boolean, defaulting to False.")

            self._log_info("Effective config for prep: include_source_index=%s", include_source_index_flag)
            if not include_source_index_flag:
                return {"skip": True, "reason": "Disabled via 'output.include_source_index'"}

            language: str = str(source_config.get("language", "unknown"))
            parser_type: str = str(source_config.get("source_index_parser", "none"))
            self._log_info("Decision for source_index: lang=%s, parser=%s", language, parser_type)
            return {
                "skip": False,
                "files_data": files_data,
                "project_name": project_name,
                "language": language,
                "parser_type": parser_type,
                "project_scan_root_display": project_scan_root_display,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
        except ValueError as e:
            self._log_error("Prep for source index failed (missing data): %s", e, exc_info=True)
            return {"skip": True, "reason": f"Missing shared data: {e!s}"}
        except Exception as e:  # noqa: BLE001
            self._log_error("Unexpected error during GenerateSourceIndexNode.prep: %s", e, exc_info=True)
            return {"skip": True, "reason": f"Unexpected prep error: {e!s}"}

    def exec(self, prep_res: SourceIndexPrepResult) -> SourceIndexExecResult:
        """Generate the Markdown content for the source index.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A string with Markdown content, or None if skipped/failed.

        """
        self._log_info(">>> GenerateSourceIndexNode.exec: Start. Skip flag: %s <<<", prep_res.get("skip"))
        if not isinstance(prep_res, dict) or prep_res.get("skip", True):
            reason = prep_res.get("reason", "N/A") if isinstance(prep_res, dict) else "Invalid prep_res"
            self._log_info("Skipping source index generation in exec. Reason: %s", reason)
            return None

        files_data: FileDataList = prep_res["files_data"]
        project_name: str = prep_res["project_name"]
        language: str = prep_res["language"]
        parser_type: str = prep_res["parser_type"]
        scan_root: str = prep_res["project_scan_root_display"]
        log_exec_params_format = "project '%s' (Language:%s, Parser:%s, Files:%d, Scan Root Display:'%s')"
        self._log_info(
            "Executing source index generation for " + log_exec_params_format,
            project_name,
            language,
            parser_type,
            len(files_data),
            scan_root,
        )

        if not files_data:
            self._log_warning("No files data to generate source index, though not skipped.")
            return f"# Code Inventory: {project_name}\n\nNo files found in the source to index.\n"
        try:
            markdown_content: str
            if parser_type == "ast" and language == "python":
                self._log_info("Using AST-based parser for Python source index.")
                markdown_content = self._format_python_index(project_name, files_data, scan_root)
            elif parser_type == "llm":
                self._log_warning("LLM-based source index for '%s' not implemented. Using generic.", language)
                markdown_content = self._format_generic_index(project_name, files_data, scan_root)
            else:
                self._log_info("Using generic file list for source index (parser: %s).", parser_type)
                markdown_content = self._format_generic_index(project_name, files_data, scan_root)
            return markdown_content if markdown_content.strip() else None
        except Exception as e:  # noqa: BLE001
            self._log_error("Unexpected error formatting source index: %s", e, exc_info=True)
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
            exec_res: The Markdown content string from `exec`, or None.

        """
        del prep_res
        self._log_info(">>> GenerateSourceIndexNode.post: Finalizing. <<<")
        shared["source_index_content"] = None

        if isinstance(exec_res, str) and exec_res.strip():
            shared["source_index_content"] = exec_res
            self._log_info("Stored valid source index content (length: %d).", len(exec_res))
        else:
            self._log_warning("Source index content from exec was None or empty. Not storing.")
        self._log_info(">>> GenerateSourceIndexNode.post: Finished. <<<")


# End of src/sourcelens/nodes/generate_source_index.py
