# src/sourcelens/prompts/diagram_prompts.py

"""Prompts related to generating various architectural diagrams."""

from typing import TYPE_CHECKING, Any, Optional, Union

# Import common dataclasses and constants
from ._common import (
    DEFAULT_RELATIONSHIP_LABEL,
    MAX_FLOWCHART_LABEL_LEN,
    AbstractionsList,
    RelationshipsDict,
    SequenceDiagramContext,
)

if TYPE_CHECKING:
    from collections.abc import Mapping


class DiagramPrompts:
    """Container for prompts related to architectural diagram generation."""

    @staticmethod
    def _escape_mermaid_quotes(text: Union[str, int, float]) -> str:
        """Convert input to string and escape double quotes for Mermaid."""
        return str(text).replace('"', "#quot;")

    @staticmethod
    def format_relationship_flowchart_prompt(
        project_name: str,
        abstractions: AbstractionsList,
        relationships: RelationshipsDict,
        diagram_format: str = "mermaid",
        structure_context: Optional[str] = None,
    ) -> str:
        """Format prompt for LLM to generate a relationship flowchart.

        Args:
            project_name: The name of the project.
            abstractions: List of identified abstraction dictionaries.
            relationships: Dictionary containing relationship details.
            diagram_format: Target diagram format (must be 'mermaid').
            structure_context: Optional string describing project structure.

        Returns:
            A formatted string prompting for raw Mermaid flowchart markup.

        """
        # --- Bez zmeny oproti predchádzajúcej verzii ---
        if diagram_format != "mermaid":
            return "Diagram format must be 'mermaid'."
        esc_quotes = DiagramPrompts._escape_mermaid_quotes
        abstraction_listing = (
            "\n".join(f"- Index {i}: {esc_quotes(a.get('name', f'C_{i}'))}" for i, a in enumerate(abstractions))
            or "N/A"
        )
        rel_list_raw = relationships.get("details", [])
        rel_list: list[Mapping[str, Any]] = rel_list_raw if isinstance(rel_list_raw, list) else []
        relationship_listing_parts: list[str] = []
        for r_item in rel_list:
            if isinstance(r_item, dict) and "from" in r_item and "to" in r_item:
                label_raw = r_item.get("label", DEFAULT_RELATIONSHIP_LABEL)
                label = esc_quotes(str(label_raw or DEFAULT_RELATIONSHIP_LABEL))
                if len(label) > MAX_FLOWCHART_LABEL_LEN:
                    label = label[: MAX_FLOWCHART_LABEL_LEN - 3] + "..."
                from_idx = str(r_item["from"])
                to_idx = str(r_item["to"])
                relationship_listing_parts.append(f'- From {from_idx} to {to_idx} label: "{label}"')
        relationship_listing = "\n".join(relationship_listing_parts) or "N/A"
        instructions_simple = (
            "**Instructions for Simple Flowchart:**\n"
            "**CRITICAL:** Start output *DIRECTLY* with `flowchart TD`. "
            "NO ```mermaid fences.\n"
            "1.  Declare nodes using index (e.g., `A0`, `A1`) "
            'and label in quotes (e.g., `A0["Configuration"]`).\n'
            "2.  Declare relationships using `-->` "
            '(e.g., `A0 -->|Reads| A1` or `A0 --> A1:"Sends Data To"`).\n'
            "3.  Keep labels short. Use `A` prefix for indices.\n"
            "4.  Ensure all abstractions are declared.\n"
            "5.  Focus ONLY on the direct relationships provided."
        )
        example_simple = (
            "**Example (Simple):**\n"
            "flowchart TD\n"
            '    A0["Config Loader"]\n'
            '    A1["Data Processor"]\n'
            '    A0 -->|"Provides Settings"| A1'
        )
        task_simple = (
            "**Task:** Create a **Mermaid flowchart diagram** based *only* on "
            "the Abstractions and Relationships provided."
        )

        if structure_context:
            instructions_combined = (
                instructions_simple + "\n\n**Part 2: Module Subgraph Inclusion:**\n"
                "6. Define module nodes (e.g., `M_utils(utils.py)`).\n"
                "7. Show conceptual nodes within modules using subgraphs if clear.\n"
                "8. Draw dependency lines (`-.->`) between conceptual nodes and modules.\n"
                "9. Focus on key file/module interactions from context.\n"
                "10. Aim for clarity over exhaustive detail."
            )
            example_combined = (
                example_simple + '\n    subgraph ModuleX\n        A1\n    end\n    A0 -.-> ModuleX:"Reads file in"'
            )
            task_combined = (
                "**Task:** Create a single **Mermaid flowchart diagram** showing "
                "both conceptual abstraction relationships AND key module/file "
                "dependencies based on all provided context."
            )
            prompt_lines = [
                f"Generate a COMBINED Mermaid flowchart diagram for project '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\nStructure Context:\n```\n{structure_context}\n```",
                f"\n{task_combined}\n\n{instructions_combined}\n\n{example_combined}",
                "\nCRITICAL: ONLY the combined raw Mermaid flowchart markup, starting directly with `flowchart TD`.",
            ]
        else:
            prompt_lines = [
                f"Generate a Mermaid relationship flowchart diagram for project '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\n{task_simple}\n\n{instructions_simple}\n\n{example_simple}",
                "\nCRITICAL: ONLY the raw Mermaid flowchart markup, starting directly with `flowchart TD`.",
            ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_class_diagram_prompt(project_name: str, code_context: str, diagram_format: str = "mermaid") -> str:
        """Format prompt for LLM to generate a class diagram."""
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
        # --- UPDATED Instructions for Class Diagram ---
        instructions = (
            "**Instructions for Mermaid Class Diagram:**\n"
            "**CRITICAL:** Output MUST start *EXACTLY* with the keyword `classDiagram` on the very first line. "
            "NO ```mermaid fences, NO introductory text (like 'Here is the diagram:'), and NO comments before it.\n"
            "1.  Declare classes using `class ClassName { ... }`.\n"
            "2.  Define attributes with visibility (+public, -private, #protected) "
            "and type (e.g., `+userId: int`, `-data: List[str]`).\n"
            "3.  Define methods similarly (e.g., `+load_data(path: str) : bool`, "
            "`-process_internal() : void`).\n"
            "4.  Show relationships: Inheritance (`<|--`), Composition (`*--`), "
            "Aggregation (`o--`), Association (`--`), Dependency (`..>`).\n"
            "5.  Add relationship labels using `:` "
            "(e.g., `ClassA --|> ClassB : Inherits`).\n"
            "6.  Focus on the **key** classes and relationships evident in the provided code context.\n"
            "7.  Include generic types like `List[str]` if clear from context.\n"
            "8.  Omit trivial getters/setters unless they contain logic."
        )
        # --- UPDATED Example for Class Diagram ---
        example_output = (
            "**Example (Starts on the first line):**\n"
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
            "    ItemProcessor ..> Item : Uses"
        )
        # --- UPDATED Prompt Lines for Class Diagram ---
        prompt_lines = [
            f"Analyze the provided code context for project '{project_name}' "
            f"and generate a Mermaid class diagram showing key components.",
            f"\nCode Context:\n```\n{code_context}\n```",
            f"\nTask: Create a class diagram showing key classes, attributes, "
            f"methods, and relationships found *only* in the provided code.\n\n{instructions}\n\n{example_output}",
            "\n**CRITICAL REMINDER:** Your entire response MUST be ONLY the raw Mermaid class diagram markup. "
            "It MUST start *exactly* with `classDiagram` on the first line. NO explanations, NO comments, NO fences.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_package_diagram_prompt(
        project_name: str, structure_context: str, diagram_format: str = "mermaid"
    ) -> str:
        """Format prompt for LLM to generate package/module dependency diagram."""
        # --- Bez zmeny oproti predchádzajúcej verzii ---
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
        instructions = (
            "**Instructions for Mermaid Dependency Graph:**\n"
            "**CRITICAL:** Start output *DIRECTLY* with `graph TD`. "
            "NO ```mermaid fences.\n"
            "1.  Represent modules/files as nodes (e.g., `M(main.py)`).\n"
            "2.  Use `-->` to show dependencies (e.g., `M --> C(config.py)` "
            "means main.py depends on config.py).\n"
            "3.  Include labels on dependencies if the type is clear "
            '(e.g., `M -->|"imports"| C`).\n'
            "4.  Focus on direct import relationships shown in the structure.\n"
            "5.  Keep node labels concise (filename or module name)."
        )
        example_output = (
            "**Example:**\n"
            "graph TD\n"
            "    M(main.py) --> C(config.py)\n"
            "    M --> DH(data_handler.py)\n"
            "    DH --> MO(models.py)"
        )
        prompt_lines = [
            f"Analyze the file structure context for project '{project_name}' and generate a Mermaid dependency graph.",
            f"\nStructure Context:\n```\n{structure_context}\n```",
            f"\nTask: Create a graph showing key dependencies between modules/files "
            f"based on the structure.\n\n{instructions}\n\n{example_output}",
            "\nCRITICAL: ONLY the raw Mermaid graph markup, starting directly with `graph TD`.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_sequence_diagram_prompt(context: SequenceDiagramContext) -> str:
        """Format prompt for LLM to generate a sequence diagram (Mermaid).

        Args:
            context: A SequenceDiagramContext object.

        Returns:
            Formatted string prompting for raw Mermaid sequence diagram markup.

        """
        # --- Bez zmeny oproti predchádzajúcej oprave ---
        if context.diagram_format != "mermaid":
            return "Diagram format must be 'mermaid' for sequence diagrams."

        instructions = (
            "**Instructions for Generating Mermaid Sequence Diagram:**\n"
            "**CRITICAL OUTPUT FORMAT RULE:** Your entire response MUST start *DIRECTLY* "
            "with the line `sequenceDiagram`. NO ```mermaid fences or other text before it.\n\n"
            "1.  **Diagram Type:** The first line MUST be `sequenceDiagram`.\n"
            "2.  **Participants:** Define participants relevant to the scenario using "
            '`participant Alias as "Clear Label"` or `participant "Quoted Label"`.'
            " Choose clear, concise labels reflecting common software roles "
            '(e.g., "CLI", "MainApp", "DataHandler", "ItemProcessor", "Logger", "Config").\n'
            "3.  **Messages:** Show interactions chronologically based *only* on the Scenario Description. "
            "Use message arrows (`->>`, `->`, `-->>`, `-->`). **CRITICAL: The syntax MUST be "
            "`PARTICIPANT_A ->> PARTICIPANT_B: Label Text` (one colon, text follows).** "
            "Every message MUST have a label text after the colon. (e.g., `App->>Config: Get threshold`, "
            "`DataHandler-->>App: Items list`). DO NOT use extra colons like `: : Label` "
            "or end lines with a colon.\n"
            "4.  **Activations:** Use `activate` and `deactivate` appropriately to show participant lifelines. "
            "**Ensure activations are balanced** (every `activate` needs a `deactivate` on the same participant).\n"
            "5.  **Control Flow:** Use `alt`, `opt`, `loop`, `par` if the Scenario Description "
            "clearly implies conditional logic, options, loops, or parallel actions. "
            "**CRITICAL: The line IMMEDIATELY following `alt`, `else`, or `opt` MUST be a valid Mermaid command "
            "(usually a message arrow like `->>`).** DO NOT use `return`, `stop`, or leave a blank line. "
            "Ensure EVERY `alt`, `opt`, `loop`, or `par` block is correctly "
            "terminated with its corresponding `end` statement.** Ensure proper nesting.\n"
            "6.  **Notes:** Use `note right of Participant: Text` sparingly for essential clarifications "
            "derived *directly* from the scenario text.\n"
            "7.  **Focus:** The diagram MUST accurately reflect the sequence of events described ONLY "
            "in the **Scenario Description**. Infer standard interactions based *only* on the description.\n"
            "8.  **Output:** ONLY raw Mermaid code. Start EXACTLY with `sequenceDiagram`."
        )
        example_output = (
            "**Example Output Format (RAW Mermaid Content Only):**\n"
            "sequenceDiagram\n"
            "    participant User\n"
            "    participant App\n\n"
            "    User->>App: Start Interaction\n"
            "    activate App\n"
            "    alt Condition A\n"
            "        App->>User: Response A\n"
            "    else Condition B\n"
            "        App->>User: Response B\n"
            "    end\n"
            "    App-->>User: Final Result\n"
            "    deactivate App"
        )
        prompt_lines = [
            f"Generate a **Mermaid sequence diagram** for project '{context.project_name}' "
            f"illustrating the specific scenario: **'{context.scenario_name}'**.",
            f"\nScenario Description:\n{context.scenario_description}",
            "\nTask: Create the sequence diagram based *strictly and only* on the "
            "**Scenario Description** provided above. Infer likely interactions between "
            "standard software components you define based *only* on the scenario description. "
            "Follow the formatting instructions below with ABSOLUTE precision, especially for message labels "
            "AND control flow structure.",
            f"\n{instructions}\n\n{example_output}",
            "\nCRITICAL REMINDER: Provide ONLY the raw Mermaid sequence diagram content, starting "
            "EXACTLY with `sequenceDiagram`. NO ```mermaid wrapper. NO introductory or "
            "concluding text. Double-check syntax for message labels, "
            "control flow blocks (NO blank lines or invalid words after alt/else/opt), "
            "balanced activations, and `end` blocks.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagram_prompts.py
