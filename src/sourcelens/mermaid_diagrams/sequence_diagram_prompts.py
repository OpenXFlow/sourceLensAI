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

# Import SequenceDiagramContext from the central common_types module
from sourcelens.core.common_types import SequenceDiagramContext


# https://mermaid.js.org/syntax/sequenceDiagram.html
def format_sequence_diagram_prompt(context: SequenceDiagramContext) -> str:
    """Format a prompt for the LLM to generate a robust, error-free Mermaid sequence diagram.

    Args:
        context: A `SequenceDiagramContext` object containing project name,
                 scenario details, diagram format, abstractions, and relationships.
                 The `abstractions` and `relationships` attributes within this context
                 are expected to conform to `CodeAbstractionsList` and
                 `CodeRelationshipsDict` types, respectively.

    Returns:
        A formatted multi-line string constituting the complete prompt.
        Returns an error message if the diagram format is not "mermaid".
    """
    if context.diagram_format.lower() != "mermaid":
        return "Error: Diagram format must be 'mermaid'."

    # Enhanced Core Instructions with clearer activation rules
    instructions: str = (
        "**STRICT Rules for Error-Free Mermaid Sequence Diagram:**\n\n"
        "**1. DIAGRAM START:**\n"
        "   - First line MUST be exactly `sequenceDiagram`\n"
        "   - No extra text, comments, or formatting before this line\n\n"
        "**2. PARTICIPANTS:**\n"
        "   - Use simple names: `participant User`, `participant API`\n"
        "   - Avoid quotes, spaces, or special characters in names\n"
        "   - Declare all participants at the start (optional but recommended)\n\n"
        "**3. MESSAGE SYNTAX:**\n"
        "   - Synchronous call: `A->>B: Message`\n"
        "   - Response/return: `B-->>A: Response`\n"
        "   - Async call: `A-)B: Async message`\n"
        "   - Self-call: `A->>A: Internal process`\n\n"
        "**4. ACTIVATION RULES (CRITICAL - READ CAREFULLY):**\n"
        "   - Rule #1: A participant can ONLY be activated if it's currently INACTIVE\n"
        "   - Rule #2: A participant can ONLY be deactivated if it's currently ACTIVE\n"
        "   - Rule #3: Each activate MUST have exactly ONE matching deactivate\n"
        "   - Rule #4: Track state mentally: INACTIVE → activate → ACTIVE → deactivate → INACTIVE\n\n"
        "**5. ALT/ELSE BLOCK RULES (MOST COMMON ERROR SOURCE):**\n"
        "   - SAFE APPROACH: Avoid activate/deactivate inside alt/else blocks entirely\n"
        "   - IF you must activate inside alt/else:\n"
        "     * Activate in ONE branch only\n"
        "     * Deactivate in the SAME branch\n"
        "     * NEVER deactivate the same participant in multiple branches\n"
        "   - PREFERRED: Do all activation/deactivation outside alt/else blocks\n\n"
        "**6. OTHER CONTROL STRUCTURES:**\n"
        "   - Same rules apply for `loop`, `par`, `opt`, `critical` blocks\n"
        "   - Always close blocks with `end`\n"
        "   - Keep activation logic simple within these blocks\n\n"
        "**7. VALIDATION CHECKLIST:**\n"
        "   - Count activates vs deactivates for each participant (must be equal)\n"
        "   - Ensure no participant is activated twice without deactivation\n"
        "   - Ensure no participant is deactivated when already inactive\n"
        "   - Check that all control blocks end with `end`"
    )

    example_output: str = (
        "**EXAMPLE 1 - SAFE PATTERN (No activation in alt blocks):**\n"
        "```\n"
        "sequenceDiagram\n"
        "    participant User\n"
        "    participant API\n"
        "    participant Database\n"
        "    participant Logger\n"
        "\n"
        "    User->>API: Send request\n"
        "    activate API\n"
        "    \n"
        "    API->>Database: Query data\n"
        "    activate Database\n"
        "    \n"
        "    alt Success case\n"
        "        Database-->>API: Return data\n"
        "        API-->>User: Success response\n"
        "    else Error case\n"
        "        Database-->>API: Error\n"
        "        API->>Logger: Log error\n"
        "        Logger-->>API: Logged\n"
        "        API-->>User: Error response\n"
        "    end\n"
        "    \n"
        "    deactivate Database\n"
        "    deactivate API\n"
        "```\n\n"
        "**EXAMPLE 2 - ADVANCED PATTERN (Careful activation in branches):**\n"
        "```\n"
        "sequenceDiagram\n"
        "    participant User\n"
        "    participant API\n"
        "    participant Cache\n"
        "    participant Database\n"
        "\n"
        "    User->>API: Request data\n"
        "    activate API\n"
        "    \n"
        "    API->>Cache: Check cache\n"
        "    \n"
        "    alt Cache hit\n"
        "        Cache-->>API: Cached data\n"
        "        API-->>User: Return cached data\n"
        "    else Cache miss\n"
        "        Cache-->>API: No data\n"
        "        API->>Database: Query database\n"
        "        activate Database\n"
        "        Database-->>API: Fresh data\n"
        "        deactivate Database\n"
        "        API-->>User: Return fresh data\n"
        "    end\n"
        "    \n"
        "    deactivate API\n"
        "```\n\n"
        "**EXAMPLE 3 - LOOP PATTERN:**\n"
        "```\n"
        "sequenceDiagram\n"
        "    participant Client\n"
        "    participant Server\n"
        "    participant Database\n"
        "\n"
        "    Client->>Server: Start batch process\n"
        "    activate Server\n"
        "    \n"
        "    loop Process each item\n"
        "        Server->>Database: Process item\n"
        "        Database-->>Server: Item processed\n"
        "    end\n"
        "    \n"
        "    Server-->>Client: Batch complete\n"
        "    deactivate Server\n"
        "```"
    )

    critical_reminder: str = (
        "\n**🚨 CRITICAL ERROR PREVENTION:**\n\n"
        "**COMMON MISTAKES TO AVOID:**\n"
        "1. ❌ Activating already active participant\n"
        "2. ❌ Deactivating already inactive participant\n"
        "3. ❌ Deactivating same participant in multiple alt/else branches\n"
        "4. ❌ Forgetting to close control blocks with `end`\n"
        "5. ❌ Mismatched activate/deactivate pairs\n\n"
        "**GOLDEN RULES:**\n"
        "✅ When in doubt, avoid activation inside alt/else/loop blocks\n"
        "✅ Use the 'SAFE PATTERN' from Example 1 above\n"
        "✅ Always do: INACTIVE → activate → ACTIVE → deactivate → INACTIVE\n"
        "✅ Count your activates and deactivates - they must match!\n"
        "✅ Test mentally: 'Is this participant currently active or inactive?'\n\n"
        "**RESPONSE FORMAT:**\n"
        "- Start IMMEDIATELY with `sequenceDiagram`\n"
        "- No markdown code blocks, no explanatory text\n"
        "- Just the pure Mermaid diagram code"
    )

    prompt_lines: list[str] = [
        "🎯 **TASK:** Generate a bulletproof Mermaid sequence diagram for:",
        f"   • Project: '{context.project_name}'",
        f"   • Scenario: '{context.scenario_name}'",
        f"\n📋 **SCENARIO DETAILS:**\n{context.scenario_description}",
        f"\n{instructions}",
        f"\n{example_output}",
        f"{critical_reminder}",
        "\n" + "=" * 80,
        "🚀 **GENERATE THE DIAGRAM NOW:**",
        "Your response must contain ONLY the Mermaid diagram code, starting with `sequenceDiagram`.",
        "Follow the SAFE PATTERN from Example 1 to avoid activation errors.",
        "=" * 80,
    ]

    return "\n".join(prompt_lines)


# End of src/sourcelens/mermaid_diagrams/sequence_diagram_prompts.py
