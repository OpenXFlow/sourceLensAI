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

"""Prompt formatting logic for Sequence Diagram generation."""

# Common data types and constants from the parent 'prompts' package
from .._common import SequenceDiagramContext


def format_sequence_diagram_prompt(context: SequenceDiagramContext) -> str:
    """Format a prompt for the LLM to generate a robust, error-free Mermaid sequence diagram.

    Args:
        context: A `SequenceDiagramContext` object containing project name,
                 scenario details, and diagram format.

    Returns:
        A formatted multi-line string constituting the complete prompt.
        Returns an error message if the diagram format is not "mermaid".
    """
    if context.diagram_format != "mermaid":
        return "Diagram format for sequence diagrams must be 'mermaid'."

    instructions: str = (
        "**Instructions for Generating Mermaid Sequence Diagram (`sequenceDiagram`):**\n"
        "1. **Start Diagram Correctly:**\n"
        "   - Begin exactly with `sequenceDiagram`. NO extra text or `mermaid` fences before it.\n"
        "2. **Participant Declaration:**\n"
        "   - Use `participant Name` format.\n"
        '   - If using spaces, enclose names in **double quotes** (`participant "Main Application"`).\n'
        '   - Prefer aliases for clarity: `participant MainApp as "Main Application"`.\n'
        "3. **Message Formatting:**\n"
        "   - Use `Sender->>Receiver: Message Text` for synchronous calls.\n"
        "   - Use `Sender->Receiver: Message Text` for asynchronous calls.\n"
        "   - Use `Receiver-->>Sender: Return Value` for responses.\n"
        "4. **Activation & Deactivation Rules (`activate` / `deactivate`):**\n"
        "   - A participant **must always be activated before deactivation**.\n"
        "   - Ensure a **balanced number** of activations & deactivations.\n"
        "   - **In conditional blocks (`alt`, `opt`, etc.):**\n"
        "     - Activate within a branch if a participant is used **only** in that branch.\n"
        "     - Deactivate **inside** the branch before it ends.\n"
        "     - If the participant spans multiple branches, deactivate **after** `end`.\n"
        "5. **Control Flow (`alt`, `opt`, `loop`, `par`):**\n"
        "   - Always close with `end`. Ensure the first line after `alt`, `else`, `opt`, `loop`, or `par` is valid.\n"
        "6. **Notes (`note`):**\n"
        "   - Use `note right of Participant: Note text` or `note over P1,P2: Note text`.\n"
        "7. **Output Cleanliness:**\n"
        "   - **No unsupported elements (`try`, `catch`, `finally`).**\n"
        "   - **No extra comments (`//` or `#`).** Use `%% Mermaid comment` if necessary.\n"
    )

    example_output: str = (
        "**Example (Error-free `alt/else` block with proper activation/deactivation):**\n"
        "sequenceDiagram\n"
        '    participant App as "Main Application"\n'
        '    participant Config as "Configuration Manager"\n'
        '    participant Logger as "Logger"\n\n'
        "    App->>Config: Load pipeline configuration\n"
        "    activate Config\n\n"
        "    alt Configuration file invalid\n"
        "        Config-->>App: Error\n"
        "        deactivate Config\n"
        "        App->>Logger: Log error\n"
        "        activate Logger\n"
        "        Logger-->>App: Error logged\n"
        "        deactivate Logger\n"
        "    else Configuration file valid\n"
        "        Config-->>App: Configuration data\n"
        "    end\n"
        "    deactivate Config\n"
    )

    critical_reminder: str = (
        "\n**CRITICAL REMINDER:**\n"
        "- Follow **strict activation/deactivation rules**. Never deactivate an inactive participant.\n"
        "- Participants **only involved in one branch** of an `alt` block should be activated and deactivated **inside** that branch.\n"
        "- If a participant’s role spans multiple branches, deactivate it **after** the `end` statement.\n"
    )

    prompt_lines: list[str] = [
        f"Generate a **Mermaid `sequenceDiagram`** for project '{context.project_name}' "
        f"illustrating the scenario: **'{context.scenario_name}'**.",
        f"\n**Scenario Description:**\n{context.scenario_description}",
        "\n**Task:** Construct the sequence diagram **strictly following the scenario** while ensuring correctness.",
        f"\n{instructions}\n\n{example_output}",
        critical_reminder,
    ]

    return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/diagrams/sequence_diagram_prompts.py
