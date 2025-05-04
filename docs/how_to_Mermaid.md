## Viewing Generated Diagrams (Mermaid)

`sourceLens` generates architectural diagrams (like the abstraction relationship flowchart and potentially class/package/sequence diagrams if configured) using the [Mermaid](https://mermaid.js.org/) syntax. These diagrams are embedded directly within the generated Markdown files (e.g., `index.md` or potentially separate files if configured).

**How to View the Diagrams Visually:**

*   **VS Code (Recommended):**
    1.  Install the **"Markdown Preview Mermaid Support"** extension (or a similar Mermaid rendering extension) from the Visual Studio Code Marketplace.
    2.  Once installed and enabled, open a generated Markdown file (like `output/your-project/index.md`).
    3.  Use the standard Markdown preview (`Ctrl+Shift+V` or `Cmd+Shift+V`). The Mermaid code blocks (```mermaid ... ```) should automatically render as visual diagrams within the preview pane.
*   **GitHub / GitLab:** When you commit and push the generated Markdown files to GitHub or GitLab, their web interfaces will automatically render the embedded Mermaid diagrams.
*   **Other Editors/Viewers:** Check if your preferred Markdown editor (like Obsidian, Typora, etc.) or viewer has built-in Mermaid support or requires a specific plugin/setting to be enabled.
*   **Online Tools:** You can copy the content within a ```mermaid ... ``` block and paste it into online editors like the official [Mermaid Live Editor](https://mermaid.live/) for rendering and debugging.

**Troubleshooting Rendering Issues:**

Sometimes, diagrams might not render correctly or might show parsing errors. This can happen if the LLM generates slightly invalid or ambiguous Mermaid syntax. Based on common issues encountered during development:



**Troubleshooting Rendering Issues:**

Sometimes, diagrams might not render correctly or might show parsing errors. This can happen if the LLM generates slightly invalid or ambiguous Mermaid syntax, or due to simple typos. Here are common issues and fixes:

*   **Error: `Trying to inactivate an inactive participant (X)` (Sequence Diagrams):**
    *   **Cause:** Mismatched `activate`/`deactivate` lines, often within `alt`/`opt`/`loop` blocks, or deactivating too early.
    *   **Fix Approach:** Ensure every `activate` has a matching `deactivate` after all interactions in that scope. Move `deactivate` outside/after `alt`/`else`/`end` if activation happened before the block. For simple request-reply, try removing `activate`/`deactivate` entirely for that participant.

*   **Error: `Expecting 'TXT', got 'NEWLINE'` (or similar) after an arrow (`-->`, `-->>`, `->>`) (Sequence Diagrams):**
    *   **Cause:** Some parsers strictly require text after a message arrow, especially reply arrows. An arrow followed immediately by only a newline can trigger this.
    *   **Fix Approach:** Add minimal, non-intrusive text after the arrow, like `: ok` or `: done`. (e.g., `Cache-->>ApiUtil: done`).

*   **Error: `Expecting 'NEWLINE', ..., got 'CLASS'` or `got 'NODE_STRING'` (Class/Graph Diagrams):**
    *   **Cause:** Invalid syntax placement, often comments (`%%`) or relationships defined immediately after a class/node definition on the same line without proper separation, or complex labels not quoted.
    *   **Fix Approach:**
        1.  Move comments (`%% ...`) to their own separate lines *before* the element or relationship they refer to.
        2.  Structure diagrams by defining *all* classes/nodes first, then defining *all* relationships/links in a separate block afterwards.
        3.  Ensure labels containing special characters (`:`, `/`, `(`, `)`, `[`, `]`, `#`, etc.) are enclosed in double quotes (`"Label with : special chars"`).

*   **Error: `Syntax error...` or `Cannot find function...` or Unspecified Parse Errors:**
    *   **Cause:** Simple typos in keywords (e.g., `participantt` instead of `participant`, `acotor` instead of `actor`), incorrect arrow types (`->>` vs `-->` in the wrong context), or missing/extra punctuation specific to the diagram type.
    *   **Fix Approach:** Carefully check the syntax against the official Mermaid documentation for the specific diagram type (Sequence, Class, Flowchart, etc.). Look for misspelled keywords or incorrect arrow usage.

*   **Error: Referring to Undefined Participant/Class/Node:**
    *   **Cause:** Using an identifier (e.g., `NodeA->>NodeB: message`) in a relationship or message *before* `NodeB` has been defined (e.g., `participant NodeB as "Node B"`).
    *   **Fix Approach:** Ensure all participants/classes/nodes are defined *before* they are used in messages or relationships.

*   **Error: Using Reserved Keywords:**
    *   **Cause:** Using Mermaid keywords (like `graph`, `class`, `sequenceDiagram`, `actor`, `participant`, `loop`, `alt`, `end`, `style`, `link`, etc.) directly as an ID or label without quoting.
    *   **Fix Approach:** Enclose the keyword used as an ID or label in double quotes (e.g., `participant "loop" as LoopProcess`).

*   **Error related to `end` or Block Structure:**
    *   **Cause:** Incorrectly nested blocks (`alt`, `opt`, `loop`, `par`, `critical`, `group`) or missing `end` statements for these blocks.
    *   **Fix Approach:** Verify that every block opener (`alt`, `loop`, etc.) has a corresponding `end` statement and that nesting is logical. Indentation helps visualize structure but doesn't affect parsing.

*   **General Rendering Issues (No specific error):**
    *   Verify the syntax against the [Mermaid Documentation](https://mermaid.js.org/syntax/sequenceDiagram.html) (or docs for the specific diagram type).
    *   Try simplifying the diagram markup temporarily to isolate the problematic part.
    *   Test the markup in the [Mermaid Live Editor](https://mermaid.live/) to get potentially more specific error feedback.


If you encounter persistent rendering issues with automatically generated diagrams, it might indicate a need to refine the prompts used by the LLM  or potential limitations in the LLM's ability to generate perfectly compliant syntax for complex diagrams.
