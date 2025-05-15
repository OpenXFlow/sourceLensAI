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

"""Guidelines for LLM on generating inline Mermaid diagrams within chapter content."""

from typing import Final

# This text is intended to be part of a larger prompt (e.g., for writing chapters).
# It provides specific instructions to the LLM on how to correctly format
# simple, inline Mermaid diagrams if it chooses to include them.
INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT: Final[str] = (
    "If helpful for explaining a core concept, "
    "method call flow, or process logic, consider embedding a SIMPLE `mermaid` diagram "
    "(sequence, activity, graph TD) using ```mermaid ... ```. Explain the diagram briefly.\n"
    "    **CRITICAL MERMAID SYNTAX (for diagrams inside chapters):**\n"
    "        - **First Line Keyword:** The line *immediately* after ```mermaid MUST be the diagram type keyword "
    "(e.g., `sequenceDiagram`, `activityDiagram`, `graph TD`). NO leading spaces, comments, or other text "
    "before this keyword on that first line.\n"
    "        - **Participants (Sequence & others):** Define participants clearly. If a participant name contains spaces or special "
    "characters (like '.', '(', ')'), it MUST be enclosed in double quotes, e.g., `participant \"My Component (v1)\"`. "
    'Alternatively, use an alias: `participant MCV1 as "My Component (v1)"`. Ensure the entire alias description is quoted.\n'
    "        - **Sequence Diagrams:**\n"
    "            - Messages: `SENDER->>RECEIVER: Message Text`. Colon MUST be present. Message text must be valid.\n"
    "            - Control Flow (`alt`, `opt`, `loop`): The line IMMEDIATELY following `alt`, `opt`, `loop` or `else` MUST be a valid "
    "Mermaid command (e.g., a message, `activate`, or `note`). DO NOT leave it blank or start with `end` directly. "
    "Every `activate Participant` inside a block must have a corresponding `deactivate Participant` "
    "before the block ends or before transitioning to an `else` or another part of the flow for that participant, "
    "unless the participant is meant to stay active across blocks.\n"
    "            - Balanced Activations: `activate ParticipantName`/`deactivate ParticipantName` MUST be strictly balanced for each participant.\n"
    "        - **Activity Diagrams:**\n"
    "            - **CRITICAL: Start with `activityDiagram` on the very first line after ```mermaid.** "
    "For example: `activityDiagram\\n    (*) --> Step 1`.\n"
    "            - Use `(*)` for start/end states if appropriate.\n"
    "            - Use `-->` for transitions. Use `:` for labels on transitions (e.g., `--> Condition Met`).\n"
    "            - Conditional logic uses `if (Condition?) then (yes)` and `else (no) ... endif` "
    "or diamond shapes using `-->|yes|` and `-->|no|` from a condition node "
    "(e.g., `cond1{{Condition?}}`).\n"
    "            - Ensure all paths logically flow and terminate correctly "
    "(e.g., converge before end state if needed).\n"
    "        - **General Code Purity:** Generate ONLY valid Mermaid syntax. "
    "ABSOLUTELY NO inline comments (like `// my comment`) or any text other than valid Mermaid syntax "
    "within the diagram code. Standard Mermaid comments `%% comment on its own line` are acceptable if necessary "
    "but try to avoid them for GitHub rendering unless essential.\n"
    "        - **General:** Avoid overly complex styling or labels inside chapters. Keep diagrams focused."
)

# End of src/sourcelens/prompts/diagrams/_inline_diagram_guidelines.py
