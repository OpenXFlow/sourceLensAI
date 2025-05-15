# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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

# Common data types and constants from the parent 'prompts' package
from .._common import (
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,
    RelationshipsDict,
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
    abstractions: AbstractionsList,
    relationships: RelationshipsDict,
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
        # This case should ideally be handled before calling,
        # but added for robustness.
        return "Diagram format for relationship flowchart must be 'mermaid'."

    esc_quotes = _escape_mermaid_quotes
    abstraction_listing_parts: list[str] = []
    for i, abstr_item in enumerate(abstractions):
        name_val_any: Any = abstr_item.get("name", f"C_{i}")
        name_val: str = str(name_val_any)
        abstraction_listing_parts.append(f"- Index {i}: {esc_quotes(name_val)}")
    abstraction_listing: str = "\n".join(abstraction_listing_parts) or "N/A"

    rel_list_any: Any = relationships.get("details", [])
    rel_list: list[Any] = rel_list_any if isinstance(rel_list_any, list) else []

    relationship_listing_parts: list[str] = []
    for r_item in rel_list:
        if isinstance(r_item, dict) and "from" in r_item and "to" in r_item:
            label_raw_any: Any = r_item.get("label", DEFAULT_RELATIONSHIP_LABEL)
            label_raw_str: str = str(label_raw_any or DEFAULT_RELATIONSHIP_LABEL)
            label: str = esc_quotes(label_raw_str)
            if len(label) > MAX_FLOWCHART_LABEL_LEN:
                label = label[: MAX_FLOWCHART_LABEL_LEN - 3] + "..."
            from_idx: str = str(r_item["from"])
            to_idx: str = str(r_item["to"])
            relationship_listing_parts.append(f'- From {from_idx} to {to_idx} label: "{label}"')
    relationship_listing: str = "\n".join(relationship_listing_parts) or "N/A"

    instructions_simple: str = (
        "**Instructions for Simple Flowchart (diagram type `flowchart TD`):**\n"
        "1.  Output MUST start *DIRECTLY* with `flowchart TD`. NO ```mermaid fences or other text before it.\n"
        "2.  Declare nodes using index (e.g., `A0`, `A1`) "
        'and label in quotes (e.g., `A0["Configuration"]`).\n'
        "3.  Declare relationships using `-->` "
        '(e.g., `A0 -->|Reads| A1` or `A0 --> A1:"Sends Data To"`).\n'
        "4.  Keep labels short. Use `A` prefix for indices (e.g., A0, A1, ...).\n"
        "5.  Ensure all listed abstractions are declared as nodes.\n"
        "6.  Focus ONLY on the direct relationships provided.\n"
        "7.  **NO inline comments like `// comment` or `# comment` within the diagram code.**"
    )
    example_simple: str = (
        "**Example (Simple Flowchart - relationships between conceptual abstractions):**\n"
        "flowchart TD\n"
        '    A0["Config Loader"]\n'
        '    A1["Data Processor"]\n'
        '    A0 -->|"Provides Settings"| A1'
    )
    task_simple: str = (
        "**Task:** Create a **Mermaid `flowchart TD` diagram** based *only* on "
        "the Abstractions and Relationships provided."
    )

    critical_reminder: str = (
        "\nCRITICAL REMINDER: Your entire response MUST be ONLY the raw Mermaid flowchart markup. "
        "It MUST start *exactly* with `flowchart TD` on the first line. "
        "NO ```mermaid fences, NO introductory text, NO explanations, "
        "and NO `//` or `#` style comments before or within the diagram code."
    )

    prompt_lines: list[str]
    if structure_context:
        instructions_combined_specific: str = (
            "\n\n**Additional Instructions for Combined Flowchart (integrating file/module structure):**\n"
            '8. Define module nodes representing files (e.g., `M_utils["utils.py"]`).\n'
            "9. If a conceptual abstraction (e.g., A0) is primarily contained in a file/module, "
            "place its node within a subgraph representing that module "
            '(e.g., `subgraph M_utils["utils.py"]\n    A0["Config Loader"]\nend`).\n'
            "10. Draw dependency lines (`-.->` or `-->`) between conceptual nodes and modules/files if an interaction "
            " (like 'reads file in' or 'calls function from') is implied by the context or relationships.\n"
            "11. Focus on key file/module interactions evident from the structure_context.\n"
            "12. Aim for clarity over exhaustive detail for the structural part."
        )
        final_instructions = instructions_simple + instructions_combined_specific
        example_combined: str = (
            example_simple
            + '\n    subgraph M_utils ["utils.py"]\n        A1\n    end\n    A0 -.-> M_utils:"Reads file in"'
        )
        task_combined: str = (
            "**Task:** Create a single **Mermaid `flowchart TD` diagram** showing "
            "both conceptual abstraction relationships AND key module/file "
            "dependencies based on all provided context."
        )
        prompt_lines = [
            f"Generate a COMBINED Mermaid `flowchart TD` diagram for project '{esc_quotes(project_name)}'.",
            f"\nAbstractions:\n{abstraction_listing}",
            f"\nRelationships:\n{relationship_listing}",
            f"\nStructure Context (Overview of project files/modules):\n```\n{structure_context}\n```",
            f"\n{task_combined}\n\n{final_instructions}\n\n{example_combined}",
            critical_reminder,
        ]
    else:
        final_instructions = instructions_simple
        prompt_lines = [
            f"Generate a Mermaid `flowchart TD` relationship diagram for project '{esc_quotes(project_name)}'.",
            f"\nAbstractions:\n{abstraction_listing}",
            f"\nRelationships:\n{relationship_listing}",
            f"\n{task_simple}\n\n{final_instructions}\n\n{example_simple}",
            critical_reminder,
        ]
    return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagrams/relationship_flowchart_prompts.py
