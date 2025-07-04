# Working with Mermaid Diagrams in SourceLens

`sourceLens` uses the [Mermaid](https://mermaid.js.org/) syntax to generate architectural diagrams within its Markdown output. This guide explains how to view these diagrams and troubleshoot common rendering issues.

## 1. Viewing Generated Diagrams

The diagrams are embedded directly within the generated Markdown files (e.g., `index.md`, `diagrams.md`) inside ```mermaid code blocks. To see them visually, you need a compatible viewer.

*   **VS Code (Recommended):**
    1.  Install the **"Markdown Preview Mermaid Support"** extension from the Visual Studio Code Marketplace.
    2.  Once installed, open a generated Markdown file (e.g., `output/your-project-name/index.md`).
    3.  Open the Markdown preview (`Ctrl+Shift+V` on Windows/Linux, `Cmd+Shift+V` on macOS). The Mermaid diagrams will render automatically.

*   **GitHub / GitLab:**
    When you commit and push the generated Markdown files to a repository on these platforms, their web interface will automatically render the embedded Mermaid diagrams.

*   **Online Live Editor:**
    For quick testing and debugging, you can copy the code from a ```mermaid ... ``` block and paste it into the official **[Mermaid Live Editor](https://mermaid.live/)**. This is often the best way to get specific syntax error feedback.

## 2. Troubleshooting Common Rendering Errors

LLMs can sometimes generate syntactically incorrect or ambiguous Mermaid code. Here are the most common errors and how to fix them manually.

---

### **Sequence Diagram Errors**

#### Error: `Trying to inactivate an inactive participant (X)`
*   **Cause:** The most common error. There is an imbalance of `activate` and `deactivate` calls, or they are used in the wrong order. A participant cannot be deactivated if it isn't currently active.
*   **Fix:**
    1.  **Count them:** Ensure every `activate ParticipantX` has a corresponding `deactivate ParticipantX`.
    2.  **Check Scope:** If you activate a participant *before* an `alt` or `loop` block, you must deactivate it *after* the `end` of that block.
    3.  **Simplify:** When in doubt, remove the `activate` / `deactivate` pair causing the error. Simple request-reply diagrams often work fine without them.

#### Error: `Expecting 'TXT', got 'NEWLINE'` (or similar) after a message arrow
*   **Cause:** A message arrow (especially a reply arrow like `-->>`) is followed immediately by a newline without any descriptive text.
*   **Fix:** Add a short, descriptive text after the colon.
    *   **Incorrect:** `B-->>A:`
    *   **Correct:** `B-->>A: Acknowledged` or `B-->>A: Data`

---

### **Flowchart / Graph / Class Diagram Errors**

#### Error: `Syntax error...` near a node or link
*   **Cause 1: Unquoted Labels with Special Characters.** Node labels or link text containing spaces, parentheses, or special characters must be enclosed in double quotes.
    *   **Incorrect:** `A[My Node] --> B(Another Node)`
    *   **Correct:** `A["My Node"] --> B["Another Node"]`
*   **Cause 2: Mermaid Keywords Used as IDs.** Using reserved words like `graph`, `class`, or `end` as node IDs can cause parsing failures.
    *   **Incorrect:** `class --> user`
    *   **Correct:** `class_node["class"] --> user_node["user"]`

---

### **General Mermaid Errors**

#### Error: Diagram doesn't render at all, or shows a generic parse error.
*   **Cause 1: Missing Diagram Type Keyword.** The very first line inside the ```mermaid block **must** be the diagram type (e.g., `flowchart TD`, `sequenceDiagram`, `classDiagram`).
*   **Cause 2: Invalid Comments.** Do not use standard programming comments like `#` or `//`. Mermaid comments start with `%%` and must be on their own line. It's safest to remove all comments when debugging.
*   **Cause 3: Typo in a Keyword.** A simple misspelling like `participent` instead of `participant` will break the entire diagram.
*   **Fix:**
    1.  Verify the diagram type is present and correct on the first line.
    2.  Remove any non-Mermaid comments (`#`, `//`).
    3.  Carefully proofread all keywords (`participant`, `activate`, `loop`, `end`, etc.) against the official documentation.

If you encounter persistent issues, it likely points to a need for refining the LLM prompts in `src/sourcelens/mermaid_diagrams/` to provide stricter formatting instructions.
