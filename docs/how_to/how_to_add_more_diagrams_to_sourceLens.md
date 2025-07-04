
# How to Add New Diagram Types to SourceLens

This guide explains how to extend `sourceLens` to generate new types of architectural diagrams using Large Language Models (LLMs), building upon the existing, modular diagram generation infrastructure.

## 1. Overview of the Existing Diagram Generation Flow

The `FL01_code_analysis` flow contains a dedicated node, `GenerateDiagramsNode`, located at `src/FL01_code_analysis/nodes/n06_generate_diagrams.py`. This node acts as the central hub for creating all LLM-powered diagrams.

**Current Workflow:**

1.  **Configuration Check:** `GenerateDiagramsNode.pre_execution` reads the `diagram_generation` section from the resolved configuration to see which diagrams are enabled (e.g., `include_class_diagram`, `sequence_diagrams.enabled`).
2.  **LLM Calls:** `GenerateDiagramsNode.execution` calls specific helper methods (e.g., `_generate_class_diagram`). Each helper:
    *   Imports a dedicated prompt formatter from `src/sourcelens/mermaid_diagrams/`.
    *   Calls the LLM with the formatted prompt.
    *   Cleans and validates the resulting Mermaid markup.
3.  **Store Results:** The generated markup for each diagram is stored in the `shared_context` under a unique key (e.g., `class_diagram_markup`).
4.  **Final Assembly:** The `CombineTutorial` node (`n10_combine_tutorial.py`) later reads these keys from `shared_context` and embeds the diagrams into a special `diagrams.md` chapter.

To add a new diagram, we will follow this established pattern. Let's use a "Mind Map Diagram" as our example.

---

## 2. Step-by-Step Guide to Add a New Diagram

### Step 1: Update the Configuration

First, add a flag to control the generation of the new diagram.

*   **Location:** `src/sourcelens/config_loader.py`
*   **Action:** Add a new property to the diagram generation schema. This makes the configuration discoverable and gives it a default value.

**Example Addition to `CODE_ANALYSIS_DIAGRAM_GENERATION_SCHEMA`:**
```python
# In src/sourcelens/config_loader.py

CODE_ANALYSIS_DIAGRAM_GENERATION_SCHEMA: ConfigDict = {
    "type": "object",
    "properties": {
        # ... existing properties like "enabled", "format", etc. ...
        "include_package_diagram": {"type": "boolean", "default": True},
        "include_file_structure_diagram": {"type": "boolean", "default": DEFAULT_CODE_INCLUDE_FILE_STRUCTURE_DIAGRAM},
        
        # ADD THE NEW DIAGRAM FLAG HERE
        "include_mind_map_diagram": {"type": "boolean", "default": False},

        "sequence_diagrams": CODE_ANALYSIS_DIAGRAM_GENERATION_SEQUENCE_SCHEMA,
    },
    # ...
    "default": {
        # ... existing defaults ...
        "include_file_structure_diagram": DEFAULT_CODE_INCLUDE_FILE_STRUCTURE_DIAGRAM,

        # ADD THE NEW DEFAULT VALUE HERE
        "include_mind_map_diagram": False,

        "sequence_diagrams": CODE_ANALYSIS_DIAGRAM_GENERATION_SEQUENCE_SCHEMA["default"],
    },
}
```
*You would also update your local `config.json` to set `"include_mind_map_diagram": true` for testing.*

### Step 2: Create the Prompt Formatter

Create a dedicated module for the new diagram's prompt engineering.

*   **New File:** `src/sourcelens/mermaid_diagrams/mind_map_diagram_prompts.py`
*   **Action:** Create a function that takes context (e.g., project name, abstractions) and returns a fully formatted prompt string.

**Example `mind_map_diagram_prompts.py`:**
```python
# src/sourcelens/mermaid_diagrams/mind_map_diagram_prompts.py

def format_mind_map_prompt(project_name: str, abstractions: list) -> str:
    """Formats a prompt to generate a Mermaid mind map."""
    
    instructions = (
        "**Instructions for Mermaid Mind Map:**\n"
        "1.  Start your response DIRECTLY with the `mindmap` keyword.\n"
        "2.  Use indentation to create the hierarchy.\n"
        "3.  Represent key abstractions as main branches.\n"
        "4.  Represent related concepts or files as sub-branches.\n"
        "5.  NO comments or other text outside the diagram code."
    )
    
    abstraction_list = "\\n".join(
        [f"- {abstr.get('name', '')}" for abstr in abstractions]
    )

    prompt = (
        f"Generate a Mermaid `mindmap` for the project '{project_name}'.\n\n"
        f"Key Abstractions:\n{abstraction_list}\n\n"
        f"{instructions}\n\n"
        "Your response MUST be only the raw Mermaid markup."
    )
    return prompt
```

### Step 3: Update the `GenerateDiagramsNode`

Modify the existing diagram generation node to include the logic for your new diagram.

*   **Location:** `src/FL01_code_analysis/nodes/n06_generate_diagrams.py`
*   **Actions:**

    1.  **Import the new prompt formatter.**
    2.  **In `pre_execution` (or its helper `_gather_diagram_context_data`):** Read your new config flag (`include_mind_map_diagram`) and add it to the `prepared_inputs` dictionary.
    3.  **In `execution`:** Add a new `if` block that checks this flag and calls a new helper method.
    4.  **Create the new helper method:** This method will call the LLM and store the result.

**Example Modifications in `n06_generate_diagrams.py`:**

```python
# 1. Import the new prompt formatter
from sourcelens.mermaid_diagrams.mind_map_diagram_prompts import format_mind_map_prompt

class GenerateDiagramsNode(BaseNode[...]):
    # ... existing methods ...

    def _gather_diagram_context_data(self, ...):
        # ... existing logic to get gen_class, gen_pkg, etc. ...

        # 2. Read the new config flag
        gen_mind_map = bool(diagram_gen_cfg.get("include_mind_map_diagram", False))

        # ... existing logging ...
        self._log_debug(
            "Diagram flags: ... MindMap=%s", ..., gen_mind_map
        )
        
        # ... prepare other inputs ...
        prepared_inputs: dict[str, Any] = {
            # ... existing keys ...
            "gen_mind_map": gen_mind_map,
        }
        return prepared_inputs

    # 4. Create the new helper method
    def _generate_mind_map_diagram(self, prepared_inputs: dict[str, Any]) -> DiagramMarkup:
        """Generate the mind map diagram."""
        abstractions = prepared_inputs.get("abstractions", [])
        prompt = format_mind_map_prompt(
            project_name=str(prepared_inputs.get("project_name")),
            abstractions=abstractions,
        )
        return self._call_llm_for_diagram(
            prompt=prompt,
            llm_config=prepared_inputs["llm_config"],
            cache_config=prepared_inputs["cache_config"],
            diagram_type="mind_map",
            expected_keywords=["mindmap"] # IMPORTANT: For basic validation
        )

    def execution(self, prepared_inputs: ...) -> ...:
        # ... existing logic ...
        results: GenerateDiagramsExecutionResult = {
            # ... existing keys ...
            "mind_map_markup": None, # Add a key for the new diagram
            "sequence_diagrams_markup": [],
        }

        # ... existing if blocks for other diagrams ...

        # 3. Add the new if block
        if prep_dict.get("gen_mind_map"):
            results["mind_map_markup"] = self._generate_mind_map_diagram(prep_dict)
            
        return results
```

### Step 4: Update the `CombineTutorial` Node

Finally, update the assembly node to handle the new diagram's markup from the `shared_context`.

*   **Location:** `src/FL01_code_analysis/nodes/n10_combine_tutorial.py`
*   **Action:** In the `_create_diagrams_chapter_content` method, add logic to check for your new diagram's markup and append it to the chapter content.

**Example Modification in `n10_combine_tutorial.py`:**

```python
# In _create_diagrams_chapter_content method

class CombineTutorial(BaseNode[...]):
    
    def _create_diagrams_chapter_content(...) -> Optional[str]:
        # ... existing code ...
        has_any_diagram_content = False

        # ... logic for existing diagrams (class, package) ...
        
        # ADD LOGIC FOR THE NEW DIAGRAM
        markup_val = shared_context.get("mind_map_markup")
        ctx_mind_map = DiagramMarkupContext(
            content_parts,
            cast(DiagramMarkup, markup_val),
            "Project Mind Map",
            "A conceptual overview of the project's main components.",
            fmt, # diagram format from config
            "Adding Mind Map to diagrams chapter.",
        )
        if self._add_diagram_markup(ctx_mind_map):
            has_any_diagram_content = True

        # ... logic for sequence diagrams ...
        
        return "\n".join(content_parts) if has_any_diagram_content else None
```

### Key Challenges & Considerations

*   **Prompt Engineering:** The success of the diagram depends entirely on the quality of the prompt. It must be specific, provide good examples, and clearly state the desired output format (`mindmap`, `graph TD`, etc.).
*   **Context Window:** For complex diagrams, you might need to provide more context (like code snippets). Be mindful of the LLM's context window limits.
*   **Validation:** LLM output can be syntactically incorrect. The `_call_llm_for_diagram` helper performs a basic check for a keyword, but more robust validation is difficult. Testing with the [Mermaid Live Editor](https://mermaid.live/) is recommended during development.
*   **Cost & Latency:** Each new diagram type adds at least one more LLM call, increasing the overall execution time and cost.

By following this pattern, you can systematically extend SourceLens with new, powerful visualization capabilities.

