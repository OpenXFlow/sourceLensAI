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

"""Prompt formatting logic for Class Diagram generation."""


def format_class_diagram_prompt(project_name: str, code_context: str, diagram_format: str = "mermaid") -> str:
    """Format a prompt for the LLM to generate a class diagram.

    Args:
        project_name: The name of the project.
        code_context: A string containing relevant code snippets, file structure,
                      or other context about classes and their relationships.
        diagram_format: The target diagram format (must be "mermaid").

    Returns:
        A formatted multi-line string constituting the complete prompt.
        Returns an error message if diagram_format is not "mermaid".
    """
    if diagram_format != "mermaid":
        return "Diagram format for class diagram must be 'mermaid'."

    instructions: str = (
        "**Instructions for Mermaid Class Diagram (diagram type `classDiagram`):**\n"
        "1.  Output MUST start *EXACTLY* with the keyword `classDiagram` on the very first line. "
        "NO ```mermaid fences, NO introductory text, NO explanations, and NO comments before the keyword.\n"
        "2.  Declare classes using `class ClassName { ... }`.\n"
        "3.  Define attributes with visibility (+public, -private, #protected) "
        "and type (e.g., `+userId: int`, `-data: List[str]`). Attribute types should be class names "
        "if they are custom classes, or primitive types.\n"
        "4.  Define methods similarly (e.g., `+load_data(path: str) : bool`, "
        "`-process_internal() : void`).\n"
        "5.  Show relationships **ONLY BETWEEN DEFINED CLASSES**: Inheritance (`<|--`), Composition (`*--`), "
        "Aggregation (`o--`), Association (`--`), Dependency (`..>`).\n"
        "6.  Add relationship labels using `:` "
        "(e.g., `ClassA --|> ClassB : Inherits`).\n"
        "7.  Focus on the **key** classes and relationships evident in the provided code context. "
        "**Do NOT invent relationships to primitive or generic types like `List[str]`**.\n"
        "8.  Include generic types like `List[str]` or `dict[str, int]` for attributes and method signatures "
        "if clear from context, but do not draw relationship lines to these generic types themselves.\n"
        "9.  Omit trivial getters/setters unless they contain significant logic.\n"
        "10. **NO inline comments like `// comment` or `# comment` within the diagram code.**"
    )

    example_output: str = (
        "**Example (Output starts on the first line with `classDiagram`):**\n"
        "classDiagram\n"
        "    class Item {\n"
        "        +item_id: int\n"
        "        +name: str\n"
        "        -processed: bool\n"
        "        +mark_as_processed() void\n"
        "    }\n"
        "    class ItemProcessor {\n"
        "        -threshold: int\n"
        "        +process_item(item: Item) bool\n"
        "    }\n"
        "    class DataHandler {\n"
        "        -items: List[Item]\n"
        "        +load_items() List[Item]\n"
        "    }\n"
        "    ItemProcessor ..> Item : Uses\n"
        "    DataHandler ..> Item : Contains/Manages"
    )

    critical_reminder: str = (
        "\n**CRITICAL REMINDER:** Your entire response MUST be ONLY the raw Mermaid class diagram markup. "
        "It MUST start *exactly* with `classDiagram` on the first line. "
        "NO ```mermaid fences, NO introductory text, NO explanations, and NO `//` or `#` style comments. "
        "Ensure all relationships are between explicitly defined classes in the diagram."
    )

    prompt_lines: list[str] = [
        f"Analyze the provided code context for project '{project_name}' "
        f"and generate a Mermaid `classDiagram` showing key components.",
        f"\nCode Context (May include file structure, snippets, or abstraction details):\n```\n{code_context}\n```",
        f"\nTask: Create a class diagram showing key classes, attributes, "
        f"methods, and relationships found *only* in the provided code. "
        f"Relationships must be between defined classes only.\n\n{instructions}\n\n{example_output}",
        critical_reminder,
    ]
    return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagrams/class_diagram_prompts.py
