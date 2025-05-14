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


"""Provide prompts for generating various architectural diagrams.

This module houses the `DiagramPrompts` class, which contains static methods
for formatting prompts aimed at an LLM. These prompts guide the LLM in
creating Mermaid syntax for different types of diagrams, such as relationship
flowcharts, class diagrams, package dependency graphs, and sequence diagrams,
based on analyzed code structure and identified scenarios. It utilizes common
dataclasses like `SequenceDiagramContext` and predefined constants for clarity
and consistency in prompt generation.
"""

from typing import Any, Optional, Union

# Import common dataclasses and constants
from ._common import (
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,
    RelationshipsDict,
    SequenceDiagramContext,
)


class DiagramPrompts:
    """Container for static methods that format prompts for diagram generation."""

    @staticmethod
    def _escape_mermaid_quotes(text: Union[str, int, float]) -> str:
        """Convert input to string and escape double quotes for Mermaid.

        Args:
            text: The input text, number, or float to be escaped.

        Returns:
            A string with double quotes replaced by the Mermaid escape sequence `#quot;`.

        """
        return str(text).replace('"', "#quot;")

    @staticmethod
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
            diagram_format: The target diagram format.
            structure_context: Optional project file structure context.

        Returns:
            A formatted multi-line string constituting the complete prompt.

        """
        if diagram_format != "mermaid":
            return "Diagram format must be 'mermaid'."
        esc_quotes = DiagramPrompts._escape_mermaid_quotes
        abstraction_listing_parts: list[str] = []
        for i, a in enumerate(abstractions):
            name_val: Any = a.get("name", f"C_{i}")
            abstraction_listing_parts.append(f"- Index {i}: {esc_quotes(str(name_val))}")
        abstraction_listing: str = "\n".join(abstraction_listing_parts) or "N/A"

        rel_list_raw: Any = relationships.get("details", [])
        rel_list: list[Any] = rel_list_raw if isinstance(rel_list_raw, list) else []

        relationship_listing_parts: list[str] = []
        for r_item in rel_list:
            if isinstance(r_item, dict) and "from" in r_item and "to" in r_item:
                label_raw: Any = r_item.get("label", DEFAULT_RELATIONSHIP_LABEL)
                label: str = esc_quotes(str(label_raw or DEFAULT_RELATIONSHIP_LABEL))
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
            "4.  Keep labels short. Use `A` prefix for indices.\n"
            "5.  Ensure all abstractions are declared.\n"
            "6.  Focus ONLY on the direct relationships provided.\n"
            "7.  **NO inline comments like `// comment` or `# comment` within the diagram code.**"
        )
        example_simple: str = (
            "**Example (Simple):**\n"
            "flowchart TD\n"
            '    A0["Config Loader"]\n'
            '    A1["Data Processor"]\n'
            '    A0 -->|"Provides Settings"| A1'
        )
        task_simple: str = (
            "**Task:** Create a **Mermaid `flowchart TD` diagram** based *only* on "
            "the Abstractions and Relationships provided."
        )
        prompt_lines: list[str]
        final_instructions: str
        critical_reminder: str = (
            "\nCRITICAL REMINDER: Your entire response MUST be ONLY the raw Mermaid flowchart markup. "
            "It MUST start *exactly* with `flowchart TD` on the first line. "
            "NO ```mermaid fences, NO introductory text, NO explanations, "
            "and NO `//` or `#` style comments before or within the diagram code."
        )

        if structure_context:
            instructions_combined_specific: str = (
                "\n\n**Additional Instructions for Combined Flowchart (including structure):**\n"
                '8. Define module nodes representing files (e.g., `M_utils["utils.py"]`).\n'
                "9. If a conceptual abstraction (e.g., A0) is primarily contained in a file/module, "
                "place its node within a subgraph representing that module "
                '(e.g., `subgraph M_utils["utils.py"]\n    A0\nend`).\n'
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
                f"Generate a COMBINED Mermaid `flowchart TD` diagram for project '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\nStructure Context:\n```\n{structure_context}\n```",
                f"\n{task_combined}\n\n{final_instructions}\n\n{example_combined}",
                critical_reminder,
            ]
        else:
            final_instructions = instructions_simple
            prompt_lines = [
                f"Generate a Mermaid `flowchart TD` relationship diagram for project '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\n{task_simple}\n\n{final_instructions}\n\n{example_simple}",
                critical_reminder,
            ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_class_diagram_prompt(project_name: str, code_context: str, diagram_format: str = "mermaid") -> str:
        """Format a prompt for the LLM to generate a class diagram.

        Args:
            project_name: The name of the project.
            code_context: A string containing relevant code snippets or file structure.
            diagram_format: The target diagram format.

        Returns:
            A formatted multi-line string constituting the complete prompt.

        """
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
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
            f"\nCode Context:\n```\n{code_context}\n```",
            f"\nTask: Create a class diagram showing key classes, attributes, "
            f"methods, and relationships found *only* in the provided code. "
            f"Relationships must be between defined classes only.\n\n{instructions}\n\n{example_output}",
            critical_reminder,
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_package_diagram_prompt(
        project_name: str, structure_context: str, diagram_format: str = "mermaid"
    ) -> str:
        """Format a prompt for the LLM to generate a package/module dependency diagram.

        Args:
            project_name: The name of the project.
            structure_context: A string describing the file and directory structure.
            diagram_format: The target diagram format.

        Returns:
            A formatted multi-line string constituting the complete prompt.

        """
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
        instructions: str = (
            "**Instructions for Mermaid Dependency Graph (diagram type `graph TD`):**\n"
            "1.  Output MUST start *DIRECTLY* with `graph TD`. NO ```mermaid fences or other text before it.\n"
            '2.  Represent modules/files as nodes. Use simple labels like `M(main.py)` or `C["config.py"]`. '
            "**Node labels should be concise and ideally not contain parentheses `()` or `e.g.,` unless properly quoted.** "
            'For example, prefer `M["data_handling.py"]` over `M[data_handling.py (handles data)]`.\n'  # Upravené
            "3.  Use `-->` to show dependencies (e.g., `M --> C` where M and C are node IDs).\n"
            "4.  Include labels on dependencies if the type is clear "
            '(e.g., `M -->|"imports"| C`).\n'
            "5.  Focus on direct import relationships shown in the structure.\n"
            "6.  Keep node labels concise (filename or module name if very short).\n"
            "7.  **NO inline comments like `// comment` or `# comment` within the diagram code.**"
        )
        example_output: str = (  # Upravený príklad podľa tvojho funkčného návrhu
            "**Example (Output starts on the first line with `graph TD`):**\n"
            "graph TD\n"
            '    A["Project Root Directory"] --> B((__init__.py))\n'
            '    A --> C["Module A: data_handling.py"]\n'
            '    A --> D["Module B: item_processing.py"]\n'
            '    B -- "Marks as Package" --> A\n'  # Popisky na hranách v úvodzovkách
            '    C -- "Importable within package" --> A\n'
            '    D -- "Importable within package" --> A'
        )
        critical_reminder: str = (
            "\n**CRITICAL REMINDER:** Your entire response MUST be ONLY the raw Mermaid graph markup. "
            "It MUST start *exactly* with `graph TD` on the first line. "
            "NO ```mermaid fences, NO introductory text, NO explanations, and NO `//` or `#` style comments. "
            "Use simple, quoted node labels if they contain spaces or special characters."
        )
        prompt_lines: list[str] = [
            f"Analyze the file structure context for project '{project_name}' and generate a Mermaid `graph TD` dependency graph.",
            f"\nStructure Context:\n```\n{structure_context}\n```",
            f"\nTask: Create a graph showing key dependencies between modules/files "
            f"based on the structure.\n\n{instructions}\n\n{example_output}",
            critical_reminder,
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_sequence_diagram_prompt(context: SequenceDiagramContext) -> str:
        """Format a prompt for the LLM to generate a robust, error-free Mermaid sequence diagram.

        Args:
            context: A `SequenceDiagramContext` object.

        Returns:
            A formatted multi-line string constituting the complete prompt.

        """
        if context.diagram_format != "mermaid":
            return "Diagram format must be 'mermaid' for sequence diagrams."

        # Enhanced instructions for sequence diagram generation
        instructions: str = (
            "**Instructions for Generating Mermaid Sequence Diagram (`sequenceDiagram`):**\n"
            "1. **Start Diagram Properly:**\n"
            "   - The response MUST start *exactly* with `sequenceDiagram`. No `mermaid` fences or extra text before it.\n"
            "2. **Defining Participants:**\n"
            "   - Declare all participants using `participant ParticipantName`.\n"
            "   - If a participant name contains spaces or special characters, enclose it in **double quotes**:\n"
            '     - Example: `participant "Main Application"`\n'
            "   - Prefer aliases for clarity:\n"
            '     - Example: `participant MainApp as "Main Application"`\n'
            "   - Use **consistent and meaningful naming**:\n"
            '     - ✅ Recommended: `"MainApp"`, `"ConfigManager"`, `"Logger"`, `"DataHandler"`, `"ThresholdEvaluator"`\n'
            '     - ❌ Avoid: `"X123"`, `"Some Process"`\n'
            "3. **Message Formatting:**\n"
            "   - Use `SENDER->>RECEIVER: Message` syntax. Messages must be complete and clear.\n"
            "   - **Use double arrows (`->>`)** for active communication.\n"
            "4. **Activation & Deactivation Rules (`activate` / `deactivate`):**\n"
            "   - **Primary participants**, activated before an `alt` or `opt` block, MUST be deactivated **only once**, after `end`.\n"
            "   - **Secondary participants** (e.g., Logger) can be activated/deactivated *inside* an `alt` or `opt` block if their role is specific to that branch.\n"
            "   - **NEVER deactivate a participant that wasn't activated**—this will cause errors.\n"
            "5. **Control Flow (`alt`, `opt`, `loop`, `par`):**\n"
            "   - Use `alt` for conditional branches with an `else` statement.\n"
            "   - Use `opt` for optional operations that do NOT require an `else`.\n"
            "   - Ensure every block is correctly **closed with `end`**.\n"
            "6. **Notes (`note`):**\n"
            "   - Use `note right of Participant: Text` only for essential clarifications.\n"
            "7. **Output Cleanliness:**\n"
            "   - **No unsupported Mermaid elements (e.g., `try`, `catch`, `finally`).**\n"
            "   - **No `//` or `#` comments**—only Mermaid-standard `%%` comments if absolutely necessary.\n"
        )

        # Improved example diagrams to prevent common errors
        example_output: str = (
            "**Example 1: Correct activation/deactivation in `alt/else` block:**\n"
            "sequenceDiagram\n"
            '    participant App as "Main Application"\n'
            '    participant Config as "Configuration Manager"\n'
            '    participant Logger as "Logger"\n\n'
            "    App->>Config: Load pipeline configuration\n"
            "    activate Config\n\n"
            "    alt Configuration file invalid\n"
            "        Config-->>App: Configuration error\n"
            "        App->>Logger: Log configuration error\n"
            "        activate Logger\n"
            "        Logger-->>App: Error logged\n"
            "        deactivate Logger\n"
            "        App->>App: Graceful shutdown\n"
            "    else Configuration file valid\n"
            "        Config-->>App: Configuration data\n"
            "        App->>App: Proceed with pipeline initialization\n"
            "    end\n\n"
            "    deactivate Config\n\n"
            "**Example 2: Correct `opt` block usage for optional operations:**\n"
            "sequenceDiagram\n"
            "    participant User\n"
            "    participant Application\n"
            "    participant TempLogger\n\n"
            "    User->>Application: Perform Action\n"
            "    activate Application\n\n"
            "    opt Log Debug Details\n"
            "        Application->>TempLogger: Log details\n"
            "        activate TempLogger\n"
            "        TempLogger-->>Application: Logged Details\n"
            "        deactivate TempLogger\n"
            "    end\n\n"
            "    Application-->>User: Action Completed\n"
            "    deactivate Application\n"
        )

        # Strict formatting reminder
        critical_reminder: str = (
            "\n**CRITICAL REMINDER:**\n"
            "- The response MUST start *exactly* with `sequenceDiagram`.\n"
            "- **Follow strict activation/deactivation rules**—never deactivate an inactive participant.\n"
            "- **For `alt/else` or `opt` blocks, primary participants activated before the block MUST be deactivated *after* the `end` statement.**\n"
            "- **Secondary participants (e.g., Logger) can be activated/deactivated within branches if their role is specific to that branch.**\n"
        )

        # Construct full prompt
        prompt_lines: list[str] = [
            f"Generate a **Mermaid `sequenceDiagram`** for project '{context.project_name}' "
            f"illustrating the specific scenario: **'{context.scenario_name}'**.",
            f"\n**Scenario Description:**\n{context.scenario_description}",
            "\n**Task:** Create the sequence diagram strictly based on the provided scenario description.",
            f"\n{instructions}\n\n{example_output}",
            critical_reminder,
        ]

        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagram_prompts.py
