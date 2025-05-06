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

        If structure_context is provided, it guides towards a combined diagram.
        Otherwise, a simple abstraction relationship flowchart is generated.

        Args:
            project_name: The name of the project.
            abstractions: List of identified abstraction dictionaries.
            relationships: Dictionary containing relationship details.
            diagram_format: Target diagram format (must be 'mermaid').
            structure_context: Optional string describing project structure.

        Returns:
            A formatted string prompting for raw Mermaid flowchart markup.

        """
        # ... (Implementation for simple/combined flowchart remains the same) ...
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
        instructions_simple = "**Instructions...:**\n**CRITICAL...:** Start `flowchart TD`. NO fences.\n1-5..."
        example_simple = '**Example...:**\nflowchart TD\nA0["Cfg"]\nA1["Proc"]\nA0-->A1'
        task_simple = "**Task:** Create **Mermaid flowchart** based *only* on Abstractions/Relationships."
        if structure_context:
            instructions_combined = f"{instructions_simple}\n\n**Part 2: Module Subgraph...**\n6-10..."
            example_combined = f"{example_simple}\n    %% Part 2: Modules...\n    A0 -.-> M\n"
            task_combined = "**Task:** Create single **Mermaid flowchart** with conceptual & module dependencies..."
            prompt_lines = [
                f"Generate COMBINED Mermaid diagram for '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\nStructure Context:\n```\n{structure_context}\n```",
                f"\n{task_combined}\n\n{instructions_combined}\n{example_combined}",
                "\nCRITICAL: ONLY combined raw Mermaid...",
            ]
        else:
            prompt_lines = [
                f"Generate Mermaid diagram for '{project_name}'.",
                f"\nAbstractions:\n{abstraction_listing}",
                f"\nRelationships:\n{relationship_listing}",
                f"\n{task_simple}\n\n{instructions_simple}\n{example_simple}",
                "\nCRITICAL: ONLY raw Mermaid starting `flowchart TD`.",
            ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_class_diagram_prompt(project_name: str, code_context: str, diagram_format: str = "mermaid") -> str:
        """Format prompt for LLM to generate a detailed class diagram."""
        # ... (Implementation remains the same) ...
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
        instructions = "Instructions:\nCRITICAL: Start `classDiagram`. NO fences.\n1-8..."
        example_output = "Example:\nclassDiagram\n    class Item{+id:int}\n..."
        prompt_lines = [
            f"Analyze '{project_name}'... Generate DETAILED Mermaid class diagram.",
            "\nCode Context:\n```",
            code_context,
            "```",
            f"\nTask: ...\n\n{instructions}\n{example_output}",
            "\nCRITICAL: ONLY raw Mermaid starting `classDiagram`.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_package_diagram_prompt(
        project_name: str, structure_context: str, diagram_format: str = "mermaid"
    ) -> str:
        """Format prompt for LLM to generate package/module dependency diagram."""
        # ... (Implementation remains the same) ...
        if diagram_format != "mermaid":
            return "Format must be 'mermaid'."
        instructions = "Instructions:\nCRITICAL: Start `graph TD`. NO fences.\n1-5..."
        example_output = "Example:\ngraph TD\n    M(main.py) --> C(config.py)\n..."
        prompt_lines = [
            f"Analyze '{project_name}'... Generate Mermaid graph dependencies.",
            "\nStructure Context:\n```",
            structure_context,
            "```",
            f"\nTask: ...\n\n{instructions}\n{example_output}",
            "\nCRITICAL: ONLY raw Mermaid starting `graph TD`.",
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
        if context.diagram_format != "mermaid":
            return "Diagram format must be 'mermaid' for sequence diagrams."

        # >>> UPDATED INSTRUCTIONS for Chyba 2 (Sequence Diagram Syntax) <<<
        instructions = (
            "**Instructions for Generating Mermaid Sequence Diagram:**\n"
            "**CRITICAL OUTPUT FORMAT RULE:** Your entire response MUST start *DIRECTLY* "
            "with the line `sequenceDiagram`. NO ```mermaid fences or other text before it.\n\n"
            "1.  **Diagram Type:** The first line MUST be `sequenceDiagram`.\n"
            "2.  **Participants:** Define participants relevant to the scenario using "
            '`participant Alias as "Clear Label"` or `participant "Quoted Label"`. '  # Emph. quotes for complex labels
            "Choose clear, concise labels reflecting common software roles "
            '(e.g., "CLI", "MainApp", "DataHandler", "ItemProcessor", "Logger").\n'
            "3.  **Messages:** Show interactions chronologically based *only* on the Scenario Description. "
            "Use message arrows (`->>`, `->`, `-->>`, `-->`). **EVERY message arrow MUST have a text label** "
            "after the colon (e.g., `: getData()`, `: process item`, `: done`).\n"  # More examples for labels
            "4.  **Activations:** Use `activate` and `deactivate` appropriately to show participant lifelines. "
            "**Ensure activations are balanced** (every `activate` needs a `deactivate` on the same participant).\n"
            "5.  **Control Flow:** Use `alt`, `opt`, `loop`, `par` if the Scenario Description "
            "clearly implies conditional logic, options, loops, or parallel actions. "
            "**Crucially, ensure EVERY `alt`, `opt`, `loop`, or `par` block is correctly "
            "terminated with its corresponding `end` statement.** "
            "Ensure proper nesting if control blocks are inside each other.\n"  # Emphasized end blocks
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
            "    User->>App: : Start Interaction\n"  # Example with label
            "    activate App\n"
            "    alt Condition A\n"
            "        App->>User: : Response A\n"
            "    else Condition B\n"
            "        App->>User: : Response B\n"
            "    end\n"  # Example of alt-end
            "    App-->>User: : Final Result\n"  # Example with label
            "    deactivate App"
        )
        prompt_lines = [
            f"Generate a **Mermaid sequence diagram** for project '{context.project_name}' "
            f"illustrating the specific scenario: **'{context.scenario_name}'**.",
            f"\nScenario Description:\n{context.scenario_description}",
            "\nTask: Create the sequence diagram based *strictly and only* on the "
            "**Scenario Description** provided above. Infer likely interactions between "
            "standard software components you define based *only* on the scenario description. "
            "Follow the formatting instructions below with ABSOLUTE precision.",
            f"\n{instructions}\n\n{example_output}",
            "\nCRITICAL REMINDER: Provide ONLY the raw Mermaid sequence diagram content, starting "
            "EXACTLY with `sequenceDiagram`. NO ```mermaid wrapper. NO introductory or "
            "concluding text.Double-check syntax, especially balanced activations and `end` blocks for `alt/opt/loop`.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagram_prompts.py
