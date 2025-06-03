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

"""Generates Mermaid code for a file structure diagram.

This module provides a function to create a Mermaid graph definition
representing a directory tree structure based on a list of file paths.
"""

import logging
from collections import defaultdict
from pathlib import Path
from typing import Any

from typing_extensions import TypeAlias

from sourcelens.core.common_types import OptionalFilePathContentList

logger: logging.Logger = logging.getLogger(__name__)

DirTree: TypeAlias = dict[str, Any]


def generate_file_structure_mermaid(project_scan_root_display: str, files_data: OptionalFilePathContentList) -> str:
    """Generate Mermaid code for a file structure diagram.

    Args:
        project_scan_root_display: The display name for the root of the project scan
                                   (e.g., "./" or "my_project/").
        files_data: A list of tuples, where each tuple is (relative_path_to_scan_root, Optional[content]).
                    Only the path is used for structuring the diagram.

    Returns:
        A string containing the Mermaid graph definition for the file tree.
        Returns a simple message if files_data is empty.
    """
    if not files_data:
        return "graph TD\n    EMPTY[No files to display in structure diagram]"

    lines: list[str] = ["graph TD"]
    root_label = project_scan_root_display
    if not root_label.endswith("/") and root_label != ".":
        root_label += "/"
    elif root_label == ".":
        root_label = "./"

    root_node_id_mermaid = "ROOT_DIR_MERMAID_0"
    root_label_mermaid = f'"{root_label}"' if '"' in root_label or " " in root_label else root_label

    lines.append(f"    {root_node_id_mermaid}[{root_label_mermaid}]")

    node_definitions: list[str] = []
    connections: list[str] = []
    style_assignments: list[str] = [f"    class {root_node_id_mermaid} dir;"]
    tree: DirTree = defaultdict(dict)

    for i, (path_rel_to_scan_root, _) in enumerate(files_data):
        p_rel = Path(path_rel_to_scan_root)
        file_node_id = f"FILE_{i}"
        file_label_mermaid = f'"{p_rel.name}"' if '"' in p_rel.name or " " in p_rel.name else p_rel.name
        node_definitions.append(f"    {file_node_id}[{file_label_mermaid}]")
        style_assignments.append(f"    class {file_node_id} file;")

        current_level_tree_ref = tree
        for part in p_rel.parent.parts:
            sanitized_part = str(part).replace('"', "_quot_").replace(" ", "_space_")
            current_level_tree_ref = current_level_tree_ref.setdefault(sanitized_part, {})
        current_level_tree_ref[p_rel.name] = file_node_id

    dir_id_counter_val: int = 0

    def generate_recursive_mermaid_for_tree(
        _current_dir_name_disp: str, current_tree_lvl: DirTree, parent_id: str, current_path_parts: list[str]
    ) -> None:
        """Recursively generate Mermaid for the directory tree.

        Args:
            _current_dir_name_disp: Display name for current directory segment (used for node label).
            current_tree_lvl: Current level in the tree dict.
            parent_id: Mermaid ID of the parent directory node.
            current_path_parts: List of path parts to build unique IDs for subdirectories.
        """
        nonlocal dir_id_counter_val
        sorted_items = sorted(current_tree_lvl.items(), key=lambda item_pair: not isinstance(item_pair[1], dict))

        for name, content_or_subtree in sorted_items:
            display_name = str(name).replace("_quot_", '"').replace("_space_", " ")
            label_name_mermaid = f'"{display_name}"' if '"' in display_name or " " in display_name else display_name

            if isinstance(content_or_subtree, dict):
                dir_id_counter_val += 1
                path_prefix = "_".join(current_path_parts + [str(name).replace("/", "_").replace(".", "_")])
                sub_dir_mermaid_id = f"DIR_{path_prefix}_{dir_id_counter_val}"

                node_definitions.append(f"    {sub_dir_mermaid_id}[{label_name_mermaid}/]")
                style_assignments.append(f"    class {sub_dir_mermaid_id} dir;")
                connections.append(f"    {parent_id} --> {sub_dir_mermaid_id}")
                generate_recursive_mermaid_for_tree(
                    display_name, content_or_subtree, sub_dir_mermaid_id, current_path_parts + [str(name)]
                )
            else:
                file_node_id_str: str = content_or_subtree
                connections.append(f"    {parent_id} --> {file_node_id_str}")

    generate_recursive_mermaid_for_tree(root_label, tree, root_node_id_mermaid, [])

    lines.extend(node_definitions)
    lines.extend(connections)
    lines.extend(
        [
            "\n    %% Styling for better readability",
            "    classDef dir fill:#dadada,stroke:#333,stroke-width:2px,color:#333,font-weight:bold;",
            "    classDef file fill:#f9f9f9,stroke:#ccc,stroke-width:1px,color:#333;",
        ]
    )
    lines.extend(style_assignments)
    logger.debug("Generated file structure Mermaid diagram code of length %d.", len("\n".join(lines)))
    return "\n".join(lines)


# End of src/sourcelens/mermaid_diagrams/file_structure_diagram.py
