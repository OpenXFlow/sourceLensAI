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

"""Prompt formatting logic for Package Diagram generation."""


def format_package_diagram_prompt(project_name: str, structure_context: str, diagram_format: str = "mermaid") -> str:
    """Format a prompt for the LLM to generate a package/module dependency diagram.

    Args:
        project_name: The name of the project.
        structure_context: A string describing the file and directory structure.
        diagram_format: The target diagram format (must be "mermaid").

    Returns:
        A formatted multi-line string constituting the complete prompt.
        Returns an error message if diagram_format is not "mermaid".
    """
    if diagram_format != "mermaid":
        return "Diagram format for package diagram must be 'mermaid'."

    instructions: str = (
        "**Instructions for Mermaid Dependency Graph (diagram type `graph TD`):**\n"
        "1.  Output MUST start *DIRECTLY* with `graph TD`. NO ```mermaid fences or other text before it.\n"
        '2.  Represent modules/files as nodes. Use simple labels like `M(main.py)` or `C["config.py"]`. '
        "Node labels should be concise. If a label contains spaces or special characters (like `()`, `.`), "
        'it MUST be enclosed in double quotes. For example, `M_utils["utils (helpers).py"]` or `N1["data.json"]`.\n'
        "3.  Use `-->` to show dependencies (e.g., `M --> C` where M and C are node IDs).\n"
        "4.  Include labels on dependencies if the type is clear "
        '(e.g., `M -->|"imports"| C`). Keep labels short.\n'
        "5.  Focus on direct import relationships or clear logical dependencies shown in the structure.\n"
        "6.  Keep node IDs very simple (e.g., A, B, M1, F2). The labels will provide the detail.\n"
        "7.  **NO inline comments like `// comment` or `# comment` within the diagram code.**"
    )

    example_output: str = (
        "**Example (Output starts on the first line with `graph TD`):**\n"
        "graph TD\n"
        '    A["Project Root"]\n'
        '    B["src/main.py"]\n'
        '    C["src/utils.py"]\n'
        '    D["config.json"]\n'
        "    A --> B\n"
        "    A --> C\n"
        "    A --> D\n"
        '    B -->|"imports"| C\n'
        '    B -->|"reads"| D'
    )

    critical_reminder: str = (
        "\n**CRITICAL REMINDER:** Your entire response MUST be ONLY the raw Mermaid graph markup. "
        "It MUST start *exactly* with `graph TD` on the first line. "
        "NO ```mermaid fences, NO introductory text, NO explanations, and NO `//` or `#` style comments. "
        "Use simple, quoted node labels if they contain spaces or special characters."
    )

    prompt_lines: list[str] = [
        f"Analyze the file structure context for project '{project_name}' and generate a "
        f"Mermaid `graph TD` dependency graph.",
        f"\nStructure Context (File and directory listing):\n```\n{structure_context}\n```",
        f"\nTask: Create a graph showing key dependencies between modules/files "
        f"based on the provided structure.\n\n{instructions}\n\n{example_output}",
        critical_reminder,
    ]
    return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagrams/package_diagram_prompts.py
