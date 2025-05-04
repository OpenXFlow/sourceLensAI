# src/sourcelens/prompts.py

"""Centralized definitions for all LLM prompts used in the SourceLens application.

Provides functions to format prompts dynamically based on context data, ensuring
consistency and maintainability. Includes prompts for identifying abstractions,
analyzing relationships, ordering chapters, writing chapter content, and generating
various diagram types (flowchart, class, package, sequence). This version includes
enhanced formatting instructions for diagram generation prompts.
"""

from dataclasses import dataclass, field
from typing import Any, Optional, TypeAlias

# Type Aliases matching those used in nodes for context clarity
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
# Metadata for a single chapter used during prompt generation
ChapterMetadata: TypeAlias = dict[str, Any]  # keys: num, name, filename, abstraction_index

# --- Constants ---
# Maximum number of lines for code snippets included in chapter prompts
CODE_BLOCK_MAX_LINES = 20
# Default relationship label if not provided in analysis
DEFAULT_RELATIONSHIP_LABEL = "related to"
# Maximum characters for relationship labels in flowcharts
MAX_FLOWCHART_LABEL_LEN = 30


# --- Dataclasses for Prompt Context ---


@dataclass(frozen=True)
class WriteChapterContext:
    """Encapsulates all context needed to format the write chapter prompt.

    Attributes:
        project_name: Name of the project being documented.
        chapter_num: The sequential number of this chapter.
        abstraction_name: The name of the core concept/abstraction this chapter covers.
        abstraction_description: A description of the abstraction.
        full_chapter_structure: A Markdown formatted list of all tutorial chapters (for context).
        previous_context_info: Summaries of previously generated chapters in the current run.
        file_context_str: String containing relevant code snippets for this abstraction.
        language: The target language for the tutorial chapter (e.g., 'english', 'spanish').
        prev_chapter_meta: Metadata (name, filename) of the preceding chapter, if any.
        next_chapter_meta: Metadata (name, filename) of the succeeding chapter, if any.

    """

    project_name: str
    chapter_num: int
    abstraction_name: str
    abstraction_description: str
    full_chapter_structure: str
    previous_context_info: str
    file_context_str: str
    language: str
    prev_chapter_meta: Optional[ChapterMetadata] = None
    next_chapter_meta: Optional[ChapterMetadata] = None


@dataclass(frozen=True)
class SequenceDiagramContext:
    """Encapsulates context needed for sequence diagram generation prompt.

    Attributes:
        project_name: Name of the project.
        scenario_name: The key name identifying the scenario (e.g., 'main_success_flow').
        scenario_description: A textual description of the scenario to be visualized.
        abstractions: List of identified abstractions (primarily for context).
        relationships: Dictionary of relationships summary/details (primarily for context).
        diagram_format: The target diagram format (currently only 'mermaid').

    """

    project_name: str
    scenario_name: str
    scenario_description: str
    abstractions: AbstractionsList = field(default_factory=list)
    relationships: RelationshipsDict = field(default_factory=dict)
    diagram_format: str = "mermaid"


# --- Prompt Formatting Functions ---


def format_identify_abstractions_prompt(project_name: str, context: str, file_listing: str, language: str) -> str:
    """Format the prompt for the LLM to identify core abstractions from code context.

    Args:
        project_name: The name of the project.
        context: String containing concatenated code file contents.
        file_listing: String listing file indices and paths available in the context.
        language: The target language for the abstraction names and descriptions.

    Returns:
        A formatted string prompting the LLM to identify abstractions and output them
        as a YAML list.

    """
    language_instruction, name_lang_hint, desc_lang_hint = "", "", ""
    if language.lower() != "english":
        lang_cap = language.capitalize()
        language_instruction = (
            f"IMPORTANT: Generate the `name` and `description` fields exclusively in **{lang_cap}**. "
            f"Do NOT use English for these fields.\n\n"
        )
        name_lang_hint = f" (in {lang_cap})"
        desc_lang_hint = f" (in {lang_cap})"

    file_indices_instruction = (
        "3. Relevant `file_indices`: List the integer indices of files related to this abstraction. "
        "You can use the format 'index # path/comment' for clarity, but only the leading integer matters. "
        "Use ONLY indices provided in the 'Available File Indices/Paths' list below."
    )

    return f"""
Analyze the provided codebase context for the project named `{project_name}`.
Your goal is to identify the top 5-10 core conceptual abstractions or components that a beginner
programmer would need to understand first.

Codebase Context:
```
{context}
```

{language_instruction}Instructions:
For each core abstraction you identify, provide the following information:
1. Concise `name`{name_lang_hint}: A short, descriptive name for the abstraction
   (e.g., "User Authentication", "Request Router").
2. Beginner-friendly `description`{desc_lang_hint}: A clear explanation (approx. 50-100 words) of
   what the abstraction does and why it's important. Use simple terms and analogies if helpful.
{file_indices_instruction}

Available File Indices/Paths:
{file_listing}

Output Format:
Format your response STRICTLY as a YAML list of dictionaries, enclosed within a single ```yaml
code block. Each dictionary represents one abstraction.

Example:
```yaml
- name: |
    Query Processing Module{name_lang_hint}
  description: |
    This component is responsible for receiving incoming user queries, parsing them,
    and directing them to the appropriate data retrieval or processing units.
    Think of it like a mail sorting facility's dispatcher.{desc_lang_hint}
  file_indices:
    - 0 # src/processing/query_handler.py
    - 3 # src/utils/parser.py
    - "5 # src/config/routes.yaml" # Example with comment
- name: |
    Data Model Definitions{name_lang_hint}
  description: |
    Defines the core data structures used throughout the application, specifying
    their fields and relationships. Acts like blueprints for the data objects. {desc_lang_hint}
  file_indices:
    - 6 # src/models/user.py
    - 7 # src/models/order.py
# ... up to 10 abstractions ...
```

Provide ONLY the YAML output block. Do not include any introductory text, explanations,
or concluding remarks outside the ```yaml block.
"""


def format_analyze_relationships_prompt(
    project_name: str, context: str, abstraction_listing: str, num_abstractions: int, language: str
) -> str:
    """Format the prompt for the LLM to analyze relationships between identified abstractions.

    Args:
        project_name: The name of the project.
        context: String containing abstraction details and relevant code snippets.
        abstraction_listing: String listing the identified abstractions (Index # Name).
        num_abstractions: The total number of identified abstractions.
        language: The target language for the summary and relationship labels.

    Returns:
        A formatted string prompting the LLM to provide a summary and a list of
        relationships in YAML format.

    """
    language_instruction, lang_hint, list_lang_note = "", "", ""
    if language.lower() != "english":
        lang_cap = language.capitalize()
        language_instruction = (
            f"IMPORTANT: Generate the `summary` and relationship `label` fields exclusively in **{lang_cap}**. "
            f"Do NOT use English for these fields.\n\n"
        )
        lang_hint = f" (in {lang_cap})"
        list_lang_note = f" (Names/Indices correspond to the list below, expected in {lang_cap})"

    max_index = max(0, num_abstractions - 1)

    summary_instruction = (
        f"1. `summary`: Provide a high-level overview (2-4 sentences) explaining how the main abstractions "
        f"interact to achieve the project's purpose. Target audience is a beginner.{lang_hint} "
        f"Use **bold** or *italic* for emphasis where appropriate."
    )
    rel_header = "2. `relationships`: A list detailing the key interactions between abstractions:"
    from_instr = (
        f"    - `from_abstraction`: The integer index (0 to {max_index}) of the source abstraction "
        f"(or 'index # Name' format)."
    )
    to_instr = (
        f"    - `to_abstraction`: The integer index (0 to {max_index}) of the target abstraction "
        f"(or 'index # Name' format)."
    )
    label_instr = (
        f"    - `label`: A brief, descriptive verb phrase{lang_hint} indicating the nature of the interaction "
        f'(e.g., "Sends data to", "Depends on", "Manages instances of", "Uses configuration from"). '
        f"Keep labels concise."
    )
    simplify_note = (
        "    Focus only on the most important, direct relationships necessary for understanding "
        "the core flow. Exclude minor or indirect interactions."
    )
    coverage_instr = ""
    # Ensure some relationships are generated if there are multiple abstractions
    if num_abstractions > 1:
        min_expected_rels = min(3, num_abstractions)  # Ask for at least a few relationships
        coverage_instr = (
            f"\nIMPORTANT: Ensure you identify relationships connecting the core abstractions. "
            f"Aim to describe at least {min_expected_rels} key interactions if they exist."
        )

    return f"""
Based on the identified abstractions and relevant code context for the project `{project_name}`,
analyze how these components interact.

Identified Abstractions List{list_lang_note}:
{abstraction_listing}

Context (Abstraction Details & Relevant Code Snippets):
```
{context}
```

{language_instruction}Instructions:
Provide an analysis containing the following two parts:
{summary_instruction}
{rel_header}
{from_instr}
{to_instr}
{label_instr}
{simplify_note}
{coverage_instr}

Output Format:
Format your response STRICTLY as a YAML dictionary enclosed within a single ```yaml code block.

Example:
```yaml
summary: |
  This project processes user requests by first validating them (**Validation Service**),
  then fetching required data using the *Data Access Layer*, and finally
  generating a response via the **Response Formatter**.{lang_hint}
relationships:
  - from_abstraction: 0 # Request Validator
    to_abstraction: 2 # Data Access Layer
    label: "Passes validated request to"{lang_hint}
  - from_abstraction: 2 # Data Access Layer
    to_abstraction: 1 # Response Formatter
    label: "Provides data for"{lang_hint}
  - from_abstraction: "3 # Configuration Loader" # Example with name
    to_abstraction: 2 # Data Access Layer
    label: "Configures database for"{lang_hint}
  # ... other key relationships ...
```

Provide ONLY the YAML output block. Do not include any introductory text, explanations,
or concluding remarks outside the ```yaml block.
"""


def format_order_chapters_prompt(
    project_name: str, abstraction_listing: str, context: str, num_abstractions: int, list_lang_note: str
) -> str:
    """Format the prompt for the LLM to determine the optimal tutorial chapter order.

    Args:
        project_name: The name of the project.
        abstraction_listing: String listing identified abstractions (Index # Name).
        context: String containing project summary and relationship details.
        num_abstractions: The total number of identified abstractions.
        list_lang_note: Language hint for the abstraction list.

    Returns:
        A formatted string prompting the LLM to output a YAML list representing
        the suggested chapter order based on abstraction indices.

    """
    if num_abstractions == 0:
        return "No abstractions provided to determine chapter order."

    max_index = max(0, num_abstractions - 1)
    ordering_criteria = (
        "Determine the most logical and beginner-friendly order to explain these abstractions. "
        "Consider the following criteria:\n"
        "- **Foundational First:** Start with the most fundamental or high-level concepts.\n"
        "- **Dependency Order:** If Abstraction B depends on or uses Abstraction A, explain A before B.\n"
        "- **User Flow:** Consider the typical flow of data or control through the system.\n"
        "- **Simplicity:** Group related simple concepts together if possible."
    )
    output_format_instruction = (
        f"Output ONLY the ordered list of abstraction indices. Use the format 'index # Name' for clarity, "
        f"but only the integer index is essential. The list MUST contain each index from 0 to {max_index} "
        f"exactly once."
    )

    return f"""
Given the following identified abstractions and their relationships for the project `{project_name}`:

Abstractions (Index # Name){list_lang_note}:
{abstraction_listing}

Context (Project Summary & Relationships):
```
{context}
```

Task:
{ordering_criteria}

{output_format_instruction}

Output Format:
Format your response STRICTLY as a YAML list enclosed within a single ```yaml code block.

Example (for 4 abstractions):
```yaml
- 2 # Foundational Database Connection
- 0 # Core User Model
- 3 # Authentication Service (uses User Model)
- 1 # Request Handler (uses Authentication Service)
```

Provide ONLY the YAML output block. Do not include any introductory text, explanations,
or concluding remarks outside the ```yaml block.
"""


def _prepare_chapter_language_hints(language: str) -> dict[str, str]:
    """Prepare language-specific hint strings for the chapter writing prompt."""
    hints: dict[str, str] = {
        "lang_instr": "",
        "concept_note": "",
        "struct_note": "",
        "prev_sum_note": "",
        "instr_note": "",
        "mermaid_note": "",
        "code_note": "",
        "link_note": "",
        "tone_note": "",
        "lang_cap": language.capitalize(),
    }
    if language.lower() != "english":
        lang_cap = hints["lang_cap"]
        hints["lang_instr"] = (
            f"IMPORTANT: You MUST write the ENTIRE chapter content in **{lang_cap}**. "
            f"This includes all explanatory text, comments within code examples, and labels in diagrams. "
            f"Use English ONLY for actual code keywords, function/variable names, and standard technical terms "
            f"that don't have a common {lang_cap} translation (e.g., 'API', 'JSON').\n\n"
        )
        hints["concept_note"] = f" (This name/description is expected in {lang_cap})"
        hints["struct_note"] = f" (Chapter titles/links expected in {lang_cap})"
        hints["prev_sum_note"] = f" (Summaries expected in {lang_cap})"
        hints["instr_note"] = f" (Explain in {lang_cap})"
        hints["mermaid_note"] = f" (Use {lang_cap} labels/text)"
        hints["code_note"] = f" (Translate comments to {lang_cap})"
        hints["link_note"] = f" (Use {lang_cap} chapter title)"
        hints["tone_note"] = f" (appropriate for {lang_cap}-speaking beginners)"
    return hints


def _prepare_chapter_transitions(data: WriteChapterContext, lang_hints: dict[str, str]) -> tuple[str, str]:
    """Prepare transition text based on previous/next chapter metadata."""
    lang = data.language.lower()
    # Basic transitions, can be enhanced with actual language dictionaries
    default_intro = "Let's begin exploring this concept."
    default_conclusion = "This concludes our look at this topic."
    default_prev_link_text = "Previously, we looked at"
    default_next_link_text = "Next, we will examine"

    # --- Simple placeholder translations ---
    translations: dict[str, dict[str, str]] = {
        "spanish": {
            "intro": "Empecemos a explorar este concepto.",
            "conclusion": "Esto concluye nuestro vistazo a este tema.",
            "prev_link": "Previamente, vimos",
            "next_link": "A continuación, examinaremos",
        },
        # Add other languages here
    }
    lang_trans = translations.get(lang, {})
    intro = lang_trans.get("intro", default_intro)
    conclusion = lang_trans.get("conclusion", default_conclusion)
    prev_link_text = lang_trans.get("prev_link", default_prev_link_text)
    next_link_text = lang_trans.get("next_link", default_next_link_text)
    # --- End placeholder translations ---

    transition_from_prev = intro
    if data.prev_chapter_meta:
        prev_name = str(data.prev_chapter_meta.get("name", "the previous concept"))
        prev_file = data.prev_chapter_meta.get("filename", "#")
        transition_from_prev = f"{prev_link_text} [{prev_name}]({prev_file}). {intro}"

    transition_to_next = conclusion
    if data.next_chapter_meta:
        next_name = str(data.next_chapter_meta.get("name", "the next concept"))
        next_file = data.next_chapter_meta.get("filename", "#")
        transition_to_next = f"{conclusion} {next_link_text} [{next_name}]({next_file})."

    return transition_from_prev, transition_to_next


def _prepare_chapter_instructions(
    data: WriteChapterContext, hints: dict[str, str], transitions: tuple[str, str]
) -> str:
    """Prepare the numbered instructions list for the chapter writing prompt."""
    transition_from_prev, transition_to_next = transitions
    # Instructions split for readability and easier formatting
    instr_parts = [
        f"1.  **Heading:** Start the chapter *immediately* with the heading: "
        f"`# Chapter {data.chapter_num}: {data.abstraction_name}`. NO text before it.",
        f"2.  **Introduction & Transition{hints['instr_note']}:** Begin the main content with: "
        f'"{transition_from_prev}". Briefly state what this chapter covers.',
        f"3.  **Motivation/Purpose{hints['instr_note']}:** Explain *why* this abstraction exists. "
        f"What problem does it solve? Use a simple analogy or real-world use case relevant "
        f"to a beginner. Keep it concise.",
        f"4.  **Key Concepts Breakdown{hints['instr_note']}:** If the abstraction is complex, "
        f"break it down into smaller, digestible parts. Explain each part clearly using "
        f"simple language and analogies if helpful.",
        f"5.  **Usage / How it Works{hints['instr_note']}:** Explain how this abstraction is typically "
        f"used or how it functions internally at a high level. Simple conceptual examples "
        f"(pseudo-code, input/output flow) are better than complex code here.",
        (
            f"6.  **Code Examples (Use Sparingly){hints['instr_note']}:** Include VERY SHORT code snippets "
            f"(ideally < {CODE_BLOCK_MAX_LINES} lines, max 20) using ```<language> ... ``` blocks ONLY IF "
            f"they are essential to illustrate a core point and are easy to understand. "
            f"Focus on the *concept*, not complex implementation. "
            f"Translate any comments within the code.{hints['code_note']}"
        ),
        (
            f"7.  **Core Logic Visualization{hints['mermaid_note']}:** If the abstraction involves a process "
            f"or internal steps, **strongly prefer illustrating the core logic with a simple "
            f"`mermaid` sequence or activity diagram** (using ```mermaid ... ```). "
            f"Explain the diagram. This is often clearer for beginners than code."
        ),
        (
            f"8.  **Relationships & Cross-Linking{hints['link_note']}:** IMPORTANT: Where relevant, mention "
            f"how this abstraction relates to others discussed in the tutorial. "
            f"Link to other chapters using Markdown links (`[Chapter Title](filename.md)`) based on "
            f"the 'Overall Tutorial Structure' provided above. "
            f"Use the chapter title in the target language as the link text."
        ),
        f"9.  **Tone & Style{hints['tone_note']}:** Maintain a welcoming, encouraging, and "
        f"beginner-friendly tone. Explain any technical jargon clearly or avoid it. Use formatting "
        f"(bold, italics, lists) to improve readability.",
        f"10. **Conclusion & Transition{hints['instr_note']}:** Briefly summarize the main takeaway point "
        f'of the chapter. End the main content with: "{transition_to_next}"',
        "11. **Output Format:** Generate ONLY the raw Markdown content for the chapter body. Start "
        "directly with the H1 heading (Instruction 1). Do NOT include an outer ```markdown ... ``` "
        "wrapper. Do NOT add any kind of footer or generation metadata.",
    ]
    # Format the instructions using the language hints
    return "\n".join(instr_parts).format(**hints)


# --- End of Chapter Prompt Helpers ---


def format_write_chapter_prompt(context: WriteChapterContext) -> str:
    """Format the detailed LLM prompt for writing a single tutorial chapter's content.

    Args:
        context: A WriteChapterContext object containing all necessary data for the prompt.

    Returns:
        A formatted string representing the complete prompt to be sent to the LLM
        for generating the content of the specified chapter.

    """
    hints = _prepare_chapter_language_hints(context.language)
    transitions = _prepare_chapter_transitions(context, hints)
    instructions = _prepare_chapter_instructions(context, hints, transitions)

    prompt_start = (
        f"{hints['lang_instr']}You are an AI assistant tasked with writing a single chapter for a beginner-friendly "
        f"Markdown tutorial about the software project `{context.project_name}`."
    )

    return f"""{prompt_start}
Your current task is to write **Chapter {context.chapter_num}**, focusing on the concept:
**"{context.abstraction_name}"**.

**Target Audience:** Beginners learning about this codebase. Assume they have basic programming
knowledge but are new to this specific project.

**Concept Details{hints["concept_note"]}:**
- Name: {context.abstraction_name}
- Description Provided:
{context.abstraction_description}

**Overall Tutorial Structure{hints["struct_note"]} (For Context and Linking):**
{context.full_chapter_structure}

**Context from Previous Chapters{hints["prev_sum_note"]} (Summaries of what came before this chapter in this session):**
{context.previous_context_info}

**Relevant Code Snippets associated with "{context.abstraction_name}" (Use very selectively):**
```
{context.file_context_str}
```

**Instructions for Writing Chapter {context.chapter_num} (Follow ALL instructions precisely):**

{instructions}

Now, generate the complete Markdown content for Chapter {context.chapter_num}: {context.abstraction_name},
starting *directly* with the H1 heading:
"""


# --- Prompts for Diagram Generation (REVISED) ---


def format_relationship_flowchart_prompt(
    project_name: str, abstractions: AbstractionsList, relationships: RelationshipsDict, diagram_format: str = "mermaid"
) -> str:
    """Format prompt for LLM to generate abstraction relationship flowchart (Mermaid).

    Args:
        project_name: The name of the project.
        abstractions: List of identified abstraction dictionaries.
        relationships: Dictionary containing relationship summary and details.
        diagram_format: The target diagram format (must be 'mermaid').

    Returns:
        A formatted string prompting the LLM to generate raw Mermaid flowchart markup.

    """
    if diagram_format != "mermaid":
        return (
            f"Diagram format '{diagram_format}' is not supported for relationship flowcharts. Please request 'mermaid'."
        )

    abstraction_listing_parts: list[str] = []
    for i, a in enumerate(abstractions):
        # Escape potential double quotes in names for Mermaid compatibility
        name = str(a.get("name", f"Concept_{i}")).replace('"', "#quot;")
        abstraction_listing_parts.append(f"- Index {i}: {name}")
    abstraction_listing = (
        "\n".join(abstraction_listing_parts) if abstraction_listing_parts else "No abstractions provided."
    )

    relationship_listing_parts: list[str] = []
    for r in relationships.get("details", []):
        if isinstance(r, dict) and "from" in r and "to" in r:
            from_idx = r["from"]
            to_idx = r["to"]
            label_raw = r.get("label", DEFAULT_RELATIONSHIP_LABEL)
            # Escape quotes and truncate long labels
            label = str(label_raw or DEFAULT_RELATIONSHIP_LABEL).replace('"', "#quot;")
            if len(label) > MAX_FLOWCHART_LABEL_LEN:
                label = label[: MAX_FLOWCHART_LABEL_LEN - 3] + "..."
            relationship_listing_parts.append(f'- From {from_idx} to {to_idx} label: "{label}"')
    relationship_listing = (
        "\n".join(relationship_listing_parts) if relationship_listing_parts else "No relationships provided."
    )

    # --- Enhanced Instructions ---
    # noqa: S608 - False positive: f-string is used for formatting instructions, not SQL
    instructions = f"""
**Instructions for Generating Mermaid Flowchart:**
1.  **Diagram Type:** You MUST use `flowchart TD` (Top Down direction).
2.  **Node Definition:** Define nodes for EACH abstraction using the EXACT format: `A<index>["<Name>"]`.
    - Replace `<index>` with the integer index from the 'Abstractions' list.
    - Replace `<Name>` with the corresponding abstraction name.
    - IMPORTANT: Escape any double quotes within the `<Name>` using `#quot;`.
      Example: `A1["User Service (#quot;Core#quot;)"]`.
3.  **Link Definition:** Create links ONLY for the relationships listed in the 'Relationships' section.
    Use the EXACT format: `A<from_index> -- "<Label>" --> A<to_index>`.
    - Replace `<from_index>`, `<to_index>`, and `<Label>` with the correct values from the 'Relationships' list.
    - IMPORTANT: Escape any double quotes within the `<Label>` using `#quot;`.
    - Keep link labels concise (max {MAX_FLOWCHART_LABEL_LEN} chars).
4.  **Strict ID Matching:** Ensure ALL node IDs (`A<index>`) and link indices (`<from_index>`, `<to_index>`)
    precisely match the integer indices provided in the lists.
5.  **Output Format:** Your response MUST contain ONLY the raw Mermaid code.
    - It MUST start *DIRECTLY* with the line `flowchart TD`.
    - It MUST NOT be enclosed in ```mermaid or any other markdown code fences.
    - Do NOT include any explanations, titles, or text before or after the Mermaid code.
"""  # noqa: S608

    return f"""
Generate a Mermaid diagram visualizing the relationships between core abstractions for the project '{project_name}'.

**Abstractions (Index: Name):**
{abstraction_listing}

**Relationships (From Index -> To Index, Label):**
{relationship_listing}

**Task:** Create a **Mermaid flowchart** based *only* on the provided Abstractions and Relationships.
Follow the instructions below with extreme precision.

{instructions}

**Example Output Format (RAW Mermaid Content Only):**
flowchart TD
    A0["Configuration Settings (#quot;Config#quot;)"]
    A1["DataProcessor Class"]
    A2["Utility Functions"]
    A0 -- "Provides settings to" --> A1
    A1 -- "Uses" --> A2
    # ... more nodes and links based STRICTLY on the provided lists ...

**CRITICAL:** Provide ONLY the raw Mermaid flowchart content, starting EXACTLY with `flowchart TD`.
NO ```mermaid wrapper. NO extra text.
"""


def format_class_diagram_prompt(
    project_name: str,
    code_context: str,
    diagram_format: str = "mermaid",
) -> str:
    """Format the prompt for the LLM to generate a class diagram (Mermaid syntax).

    Args:
        project_name: The name of the project.
        code_context: String containing code snippets or file structure overview.
        diagram_format: The target diagram format (must be 'mermaid').

    Returns:
        A formatted string prompting the LLM to generate raw Mermaid class diagram markup.

    """
    if diagram_format != "mermaid":
        return f"Diagram format '{diagram_format}' is not supported for class diagrams. Please request 'mermaid'."

    # --- Enhanced Instructions ---
    instructions = """
**Instructions for Generating Mermaid Class Diagram:**
1.  **Diagram Type:** You MUST start the diagram block *DIRECTLY* with `classDiagram`.
2.  **Class Definition:** Define important classes using `class ClassName { ... members ... }`.
3.  **Members:** Show key attributes and methods within braces. Use visibility markers (`+`, `-`, `#`, `~`).
    Specify types (`+userId: int`). Use `*` for abstract, `$` for static members.
4.  **Relationships:** Use standard Mermaid syntax for relationships:
    - Inheritance: `<|--`
    - Realization (Interface): `<|..`
    - Association: `-->` (or `--`, `*--`, `o--`)
    - Add cardinality and labels to associations if helpful (e.g., `"1" --> "*" : label`).
5.  **Stereotypes:** Use `<<Interface>>`, `<<Abstract>>`, `<<Service>>` etc. where appropriate.
6.  **Focus & Conciseness:** Include only the most important classes and relationships for
    understanding the core structure. Avoid overwhelming detail.
7.  **Output Format:** Your response MUST contain ONLY the raw Mermaid code.
    - It MUST start *DIRECTLY* with the line `classDiagram`.
    - It MUST NOT be enclosed in ```mermaid or any other markdown code fences.
    - Do NOT include any explanations, titles, or text before or after the Mermaid code.
"""

    # Corrected Example - simpler, valid Mermaid class syntax within the f-string
    example_output = """classDiagram
    class DataProcessor {
        +mode: str
        +endpoint: str
        +submit_data(user String, data Dict) String
    }
    class Utils {
        <<Module>>
        +format_message(name String, message String) String$
        +validate_input(data Dict) Boolean$
    }
    class Config {
        <<Module>>
        +API_ENDPOINT: str$
        +get_timeout() int$
    }
    DataProcessor --> Utils : uses
    DataProcessor --> Config : uses
"""

    return f"""
Analyze the provided code context for the project '{project_name}'. Identify the main classes,
their key members (attributes/methods), and the primary relationships between them.

**Code Context / Structure Overview:**
```
{code_context}
```

**Task:** Generate a **Mermaid class diagram** summarizing the core object-oriented
structure based *only* on the provided context. Follow the instructions below with extreme precision.

{instructions}

**Example Output Format (RAW Mermaid Content Only):**
{example_output}
**CRITICAL:** Provide ONLY the raw Mermaid class diagram content, starting EXACTLY with `classDiagram`.
NO ```mermaid wrapper. NO extra text.
"""


def format_package_diagram_prompt(
    project_name: str,
    structure_context: str,
    diagram_format: str = "mermaid",
) -> str:
    """Format the prompt for the LLM to generate a package/module dependency diagram (Mermaid).

    Args:
        project_name: The name of the project.
        structure_context: String describing the project's file/directory structure.
        diagram_format: The target diagram format (must be 'mermaid').

    Returns:
        A formatted string prompting the LLM to generate raw Mermaid graph markup for dependencies.

    """
    if diagram_format != "mermaid":
        return f"Diagram format '{diagram_format}' is not supported for package diagrams. Please request 'mermaid'."

    # --- Enhanced Instructions ---
    instructions = """
**Instructions for Generating Mermaid Graph (Package/Module Dependencies):**
1.  **Diagram Type:** You MUST use `graph TD` (Top Down direction).
2.  **Nodes:** Represent major packages or modules as nodes. Use clear names based on the
    context (e.g., `nodes["nodes_pkg"]`, `utils(utils_module)`). Use different shapes if meaningful.
3.  **Dependencies:** Indicate a direct dependency (A uses B) using a directed arrow `-->`. Example: `A --> B`.
4.  **Focus:** Show only the high-level dependencies between the main identified
    components/packages. Avoid excessive detail.
5.  **Subgraphs (Optional):** Use `subgraph GroupName ... end` to group related modules if it improves clarity.
6.  **Output Format:** Your response MUST contain ONLY the raw Mermaid code.
    - It MUST start *DIRECTLY* with the line `graph TD`.
    - It MUST NOT be enclosed in ```mermaid or any other markdown code fences.
    - Do NOT include any explanations, titles, or text before or after the Mermaid code.
"""

    return f"""
Analyze the provided project structure information for '{project_name}'. Identify the main
packages/modules (e.g., `main`, `config`, `nodes`, `utils`) and their primary import dependencies.

**Project Structure Context:**
```
{structure_context}
```

**Task:** Generate a **Mermaid graph** visualizing the high-level dependencies between the core
packages or modules of the project based *only* on the provided context. Follow the instructions
below with extreme precision.

{instructions}

**Example Output Format (RAW Mermaid Content Only):**
graph TD
    M(main_logic) --> C(config)
    M --> U(utils)
    # ... more dependencies based on context ...

**CRITICAL:** Provide ONLY the raw Mermaid graph content, starting EXACTLY with `graph TD`.
NO ```mermaid wrapper. NO extra text.
"""


def format_sequence_diagram_prompt(context: SequenceDiagramContext) -> str:
    """Format the prompt for the LLM to generate a sequence diagram (Mermaid).

    Args:
        context: A SequenceDiagramContext object containing scenario details and project context.

    Returns:
        A formatted string prompting the LLM to generate raw Mermaid sequence diagram markup.

    """
    if context.diagram_format != "mermaid":
        return (
            f"Diagram format '{context.diagram_format}' is not supported for sequence diagrams. "
            f"Please request 'mermaid'."
        )

    potential_participants = [str(a.get("name", f"Concept_{i}")) for i, a in enumerate(context.abstractions)]
    participants_hint = (
        f"Potential Participants (for context): {', '.join(potential_participants)}\n" if potential_participants else ""
    )
    relationships_summary = str(context.relationships.get("summary", "N/A"))

    # --- Enhanced Instructions ---
    instructions = """
**Instructions for Generating Mermaid Sequence Diagram:**
1.  **Diagram Type:** You MUST start the diagram block *DIRECTLY* with `sequenceDiagram`.
2.  **Participants:** Define participants relevant to the scenario using `participant Alias as "Clear Label"`.
    Choose clear, concise labels (e.g., "CLI", "DataProcessor", "Utils Module", "LLM API").
3.  **Messages:** Show interactions chronologically using message arrows (`->>`, `->`, `-->>`, `-->`).
    Add descriptive labels to messages.
4.  **Activations:** Use `activate` and `deactivate` to show participant lifelines accurately. Ensure they are balanced.
5.  **Control Flow:** Use `alt`, `opt`, `loop`, `par` where needed to represent conditional logic, options,
    loops, or parallel actions described in the scenario.
6.  **Notes:** Use `note right of Participant: Text` or `note over P1,P2: Text` for brief explanations if necessary.
7.  **Focus:** The diagram MUST accurately reflect the sequence of events described in the
    **Scenario Description**. Base interactions on this description.
8.  **Output Format:** Your response MUST contain ONLY the raw Mermaid code.
    - It MUST start *DIRECTLY* with the line `sequenceDiagram`.
    - It MUST NOT be enclosed in ```mermaid or any other markdown code fences.
    - Do NOT include any explanations, titles, or text before or after the Mermaid code.
"""

    return f"""
Generate a **Mermaid sequence diagram** for the project '{context.project_name}'
illustrating the specific scenario: **'{context.scenario_name}'**.

**Scenario Description:**
{context.scenario_description}

**General Project Context (Background Only):**
{participants_hint}Relationships Summary: {relationships_summary}

**Task:** Create the sequence diagram based *only* on the **Scenario Description**.
Infer likely interactions between components as needed to fulfill the scenario. Follow the instructions
below with extreme precision.

{instructions}

**Example Output Format (RAW Mermaid Content Only):**
sequenceDiagram
    participant User
    participant Processor as "DataProcessor"
    participant Util as "Utils"

    User->>Processor: submit_data(user, data)
    activate Processor
    Processor->>Util: validate_input(data)
    activate Util
    Util-->>Processor: validation_result
    deactivate Util
    alt validation_result is True
        Processor->>Util: format_message(user, success_msg)
        activate Util
        Util-->>Processor: formatted_success_log
        deactivate Util
        Processor-->>User: Success: log
    else validation_result is False
        Processor->>Util: format_message(user, error_msg)
        activate Util
        Util-->>Processor: formatted_error_log
        deactivate Util
        Processor-->>User: Error: log
    end
    deactivate Processor

**CRITICAL:** Provide ONLY the raw Mermaid sequence diagram content, starting EXACTLY with `sequenceDiagram`.
NO ```mermaid wrapper. NO extra text.
"""


# End of src/sourcelens/prompts.py
