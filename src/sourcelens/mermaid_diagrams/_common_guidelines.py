# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Guidelines for LLM on generating inline Mermaid diagrams within chapter content."""

from typing import Final

# This text is intended to be part of a larger prompt (e.g., for writing chapters).
# It provides specific instructions to the LLM on how to correctly format
# simple, inline Mermaid diagrams if it chooses to include them.
INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT: Final[str] = (
    "If helpful for explaining a core concept, "
    "method call flow, or process logic, consider embedding a SIMPLE `mermaid` diagram "
    "(sequence, flowchart, graph TD) using ```mermaid ... ```. Explain the diagram briefly.\n"
    "    **CRITICAL MERMAID SYNTAX (for diagrams inside chapters):**\n"
    "        - **First Line Keyword:** The line *immediately* after ```mermaid MUST be the diagram type keyword "
    "(e.g., `sequenceDiagram`, `flowchart TD`, `graph TD`). NO leading spaces, comments, or other text "
    "before this keyword on that first line.\n"
    "        - **Participants (Sequence & others):** Define participants clearly. If a participant name contains spaces or special "  # noqa: E501
    "characters (like '.', '(', ')'), it MUST be enclosed in double quotes, e.g., `participant \"My Component (v1)\"`. "
    'Alternatively, use an alias: `participant MCV1 as "My Component (v1)"`. Ensure the entire alias description is quoted if it contains spaces/special chars.\n'  # noqa: E501
    "        - **Sequence Diagrams:**\n"
    "            - **Messages & Replies:**\n"
    "                - `SENDER->>RECEIVER: Message Text` (Colon MUST be present, text is required).\n"
    "                - `RECEIVER-->>SENDER: Reply Text` (Reply text is REQUIRED - use 'OK', 'Success', 'Done', etc. if no specific reply).\n"  # noqa: E501
    "                - **NEVER leave message arrows empty** - always provide some text after the colon.\n"
    "            - **VERY IMPORTANT - New Lines for Commands:**\n"
    "                - Each distinct command (`activate`, `deactivate`, `alt`, `loop`, `opt`, `par`, `else`, `end`, `note`) "  # noqa: E501
    "MUST be on its **OWN SEPARATE LINE** and correctly indented.\n"
    "                - After any message arrow (e.g., `A->>B: text` or `B-->>A: reply`), the NEXT command "
    "(like `activate B` or `deactivate A`) MUST start on a **NEW LINE**.\n"
    "                - **Correct Example:**\n"
    "                    `A->>B: Request data`\n"
    "                    `activate B`\n"
    "                    `B-->>A: Data response`\n"
    "                    `deactivate B`\n"
    "                - **Incorrect Example (DO NOT DO THIS):**\n"
    "                    `A->>B: Request data activate B`\n"
    "                    `B-->>A: deactivate B`  # Missing reply text!\n"
    "            - **Control Flow (`alt`, `opt`, `loop`, `par`):** The line IMMEDIATELY following `alt Condition`, `opt Text`, "  # noqa: E501
    "`loop Text`, `par Action` or `else` MUST be a valid, indented Mermaid command on a NEW LINE (e.g., a message, `activate`, or `note`). "  # noqa: E501
    "DO NOT leave it blank or start with `end` directly on the next line without an action. `end` must also be on its own new line.\n"  # noqa: E501
    "            - **Balanced Activations:** `activate ParticipantName`/`deactivate ParticipantName` MUST be strictly balanced for each participant.\n"  # noqa: E501
    "        - **Flowchart/Activity Diagrams:**\n"
    "            - **CRITICAL: Start with `flowchart TD` (top-down) or `flowchart LR` (left-right) on the very first line after ```mermaid.** "  # noqa: E501
    'Example: `flowchart TD\\n    Start --> "Step 1"`.\n'
    "            - Use `Start([Start])` and `End([End])` for start/end states, or simple node names.\n"
    "            - Use `-->` for transitions. Use `-->|Label Text|` for edge labels (avoid quotes in labels when possible).\n"  # noqa: E501
    "            - Decision nodes: Use `{Decision Text}` for diamond shapes (decisions/conditions).\n"
    "            - Process nodes: Use `[Process Text]` for rectangular shapes (actions/processes).\n"
    '            - Subgraphs: Use `subgraph ID ["Title"]` and `end` to group related nodes.\n'
    "            - Ensure all paths logically flow and terminate correctly.\n"
    "        - **General Code Purity:** Generate ONLY valid Mermaid syntax. "
    "ABSOLUTELY NO inline comments (like `// comment` or `# comment`) within the diagram code "
    "(between diagram keyword and final ```). Standard Mermaid comments `%% comment` are okay if on their own line.\n"
    "        - **General:** Keep inline diagrams SIMPLE and FOCUSED. Explain them briefly in the text."
)
# End of src/sourcelens/prompts/diagrams/_inline_diagram_guidelines.py
