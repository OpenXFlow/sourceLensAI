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

"""Prompt formatting logic for Relationship Flowchart diagrams."""

from typing import Any, Optional, Union

# Teraz musíme importovať z FL01_code_analysis.prompts._common
from sourcelens.core.common_types import (
    DEFAULT_CODE_RELATIONSHIP_LABEL,
    MAX_CODE_FLOWCHART_LABEL_LEN,
    CodeAbstractionsList,
    CodeRelationshipsDict,
)


def _escape_mermaid_quotes(text: Union[str, int, float]) -> str:
    """Convert input to string and escape double quotes for Mermaid.

    Args:
        text: The input text, number, or float to be escaped.

    Returns:
        A string with double quotes replaced by the Mermaid escape sequence `#quot;`.
    """
    return str(text).replace('"', "#quot;")


def format_relationship_flowchart_prompt(
    project_name: str,
    abstractions: CodeAbstractionsList,
    relationships: CodeRelationshipsDict,
    diagram_format: str = "mermaid",
    structure_context: Optional[str] = None,
) -> str:
    """Format a prompt for the LLM to generate a relationship flowchart.

    Args:
        project_name: The name of the project.
        abstractions: A list of dictionaries representing abstractions.
        relationships: A dictionary containing relationship details.
        diagram_format: The target diagram format (must be "mermaid").
        structure_context: Optional project file structure context to integrate
                           module/file information into the flowchart.

    Returns:
        A formatted multi-line string constituting the complete prompt.
        Returns an error message if diagram_format is not "mermaid".
    """
    if diagram_format != "mermaid":
        return "Diagram format for relationship flowchart must be 'mermaid'."

    esc_quotes = _escape_mermaid_quotes
    abstraction_listing_parts: list[str] = []
    for i, abstr_item in enumerate(abstractions):
        name_val_any: Any = abstr_item.get("name", f"C_{i}")
        name_val: str = str(name_val_any)
        abstraction_listing_parts.append(f"- Index {i}: {esc_quotes(name_val)} (Node ID: A{i})")
    abstraction_listing: str = "\n".join(abstraction_listing_parts) or "N/A"

    rel_list_any: Any = relationships.get("details", [])
    rel_list: list[Any] = rel_list_any if isinstance(rel_list_any, list) else []

    relationship_listing_parts: list[str] = []
    for r_item in rel_list:
        if isinstance(r_item, dict) and "from" in r_item and "to" in r_item:
            label_raw_any: Any = r_item.get("label", DEFAULT_CODE_RELATIONSHIP_LABEL)
            label_raw_str: str = str(label_raw_any or DEFAULT_CODE_RELATIONSHIP_LABEL)
            label: str = esc_quotes(label_raw_str)
            if len(label) > MAX_CODE_FLOWCHART_LABEL_LEN:
                label = label[: MAX_CODE_FLOWCHART_LABEL_LEN - 3] + "..."
            from_idx: str = str(r_item["from"])
            to_idx: str = str(r_item["to"])
            relationship_listing_parts.append(
                f'- From A{from_idx} to A{to_idx} label: "{label}"'
            )  # Use A<index> for clarity
    relationship_listing: str = "\n".join(relationship_listing_parts) or "N/A"

    base_instructions: str = (
        "**Instructions for Mermaid Flowchart (diagram type `flowchart TD` or `graph TD`):**\n"
        "1.  Output MUST start *DIRECTLY* with `flowchart TD` or `graph TD`. NO ```mermaid fences or other text.\n"
        "2.  **Conceptual Abstraction Nodes:** Declare these using their assigned Node ID (e.g., `A0`, `A1`). "
        'Label them with their descriptive name in quotes (e.g., `A0["Configuration Management"]`).\n'
        "3.  **Relationship Lines:** Draw lines *between these conceptual abstraction Node IDs*. "
        "Use `-->` for general relationships or `-.->` for dependencies/calls.\n"
        '4.  **Labels on Lines:** To add text to a line, use the format `A0 -->|"Label Text"| A1` '
        'or `A0 -- "Label Text" --> A1`. The label text MUST be enclosed in quotes if it contains spaces.\n'
        "5.  Ensure all listed abstractions are declared as nodes with their correct Node ID (A0, A1, etc.).\n"
        "6.  Focus ONLY on the direct relationships provided between conceptual abstractions.\n"
        "7.  **NO inline comments like `// comment` or `# comment` within the diagram code.**"
    )

    structure_integration_instructions: str = ""
    if structure_context:
        structure_integration_instructions = (
            "\n\n**Integrating File/Module Structure (Optional, if contextually relevant):**\n"
            "8.  **Module Representation:** If showing how abstractions relate to files/modules from the "
            "'Structure Context', represent these files/modules as distinct nodes "
            '(e.g., `M_config["config.py"]`, `M_utils["utils_module"]`).\n'
            "9.  **Subgraphs for Containment:** To show an abstraction (e.g., A0) is primarily contained in a "
            "file/module, you MAY place its node within a subgraph representing that module. "
            'Example: `subgraph M_config_file ["config.py"]\n    A0\nend`\n'
            "10. **Linking Abstractions to File/Module Nodes:** If an abstraction (e.g., A4) interacts broadly with a "
            "module/file (e.g., `M_config_file`), draw a line from the abstraction node to the module/file node "
            'using a descriptive label on the line: `A4 -.->|"Uses settings from"| M_config_file`.\n'
            "11. **Avoid Direct Links to Subgraph IDs with Relationship Labels:** If using subgraphs, relationship "
            "lines with labels should target specific nodes (abstraction nodes or file/module nodes), "
            "not the ID of the subgraph itself.\n"
            "12. Aim for clarity. If combining conceptual and structural views becomes too cluttered, "
            "prioritize conceptual relationships."
        )

    example_prompt_part: str = (
        "**Example Output (Conceptual relationships, may include file nodes/subgraphs if relevant context provided):**\n"  # noqa: E501
        "```mermaid\n"
        "flowchart TD\n"
        '    A0["Configuration Management"]\n'
        '    A1["Data Model (Item)"]\n'
        '    A4["Main Application Orchestration"]\n'
        '    M_config_file["config.py"] %% Optional: if representing config.py as a node\n\n'
        '    subgraph SB_config ["config.py"] %% Optional: if A0 is in config.py\n'
        "        A0\n"
        "    end\n\n"
        '    A4 -->|"Reads configuration from"| A0\n'
        '    A4 -.->|"Depends on file"| M_config_file %% Example linking to a file node\n'
        "    A1 --> A0 %% Example of a relationship without a label\n"
        "```"
    )

    critical_reminder: str = (
        "\n**CRITICAL REMINDER:** Your entire response MUST be ONLY the raw Mermaid flowchart markup. "
        "It MUST start *exactly* with `flowchart TD` or `graph TD` on the first line. "
        "NO ```mermaid fences, NO introductory text, NO explanations, "
        "and NO `//` or `#` style comments before or within the diagram code. "
        'Line labels MUST use the `-->|"Text"|` or `-- "Text" -->` syntax.'
    )

    prompt_lines: list[str] = [
        f"Generate a Mermaid `{diagram_format}` relationship diagram for project '{esc_quotes(project_name)}'.",
        f"\nConceptual Abstractions (Node ID: Name):\n{abstraction_listing}",
        f"\nProvided Relationships (between Abstraction Node IDs):\n{relationship_listing}",
    ]
    if structure_context:
        prompt_lines.append(f"\nProject File Structure Context (for reference):\n```\n{structure_context}\n```")

    prompt_lines.extend(
        [
            "\n**Task:** Create a Mermaid diagram.",
            base_instructions,
            structure_integration_instructions if structure_context else "",
            example_prompt_part,
            critical_reminder,
        ]
    )
    return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagrams/relationship_flowchart_prompts.py
