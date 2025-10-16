# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Prompts related to ordering and writing chapters for web content."""

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ._common import WriteWebChapterContext


from sourcelens.mermaid_diagrams._common_guidelines import INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT


class WebChapterPrompts:
    """Container for prompts related to web content chapter structuring and writing."""

    @staticmethod
    def format_order_web_chapters_prompt(
        document_collection_name: str,
        concepts_listing_with_summaries: str,
        relationships_summary: str,
        num_concepts: int,
        target_language: str,
    ) -> str:
        """Format prompt for LLM to determine chapter order for web content.

        Args:
            document_collection_name (str): Name of the website or document collection.
            concepts_listing_with_summaries (str): String listing identified concepts derived
                                                   from document chunks (Index. Name - Summary).
            relationships_summary (str): LLM-generated summary of how concepts interrelate.
            num_concepts (int): Total number of identified concepts.
            target_language (str): The target language for any textual elements in the prompt.

        Returns:
            str: A formatted string prompting for a YAML list of concept indices.
                 Returns an error message string if num_concepts is 0.
        """
        if num_concepts == 0:
            return "Error: No web concepts provided to order into chapters. Cannot generate prompt."

        lang_cap: str = target_language.capitalize()
        list_lang_note: str = ""
        if target_language.lower() != "english":
            list_lang_note = f" (Note: Concept names/summaries are expected to be in {lang_cap})"

        max_index: int = max(0, num_concepts - 1)
        ordering_criteria_intro: str = (
            "Based on the identified concepts (derived from document chunks) and their relationships, "
            "determine a logical and pedagogical order for chapters that would summarize this web content effectively."
        )
        ordering_criteria_list: list[str] = [
            "- **Foundational First:** Concepts that introduce or are prerequisites for others should come earlier.",
            "- **Logical Flow:** Follow a natural progression of topics as presented or implied by relationships.",
            "- **Narrative Cohesion:** Group related concepts to build a coherent understanding.",
            "- **User Journey (if applicable):** Consider how a user might typically explore or learn this information.",
        ]
        ordering_criteria: str = f"{ordering_criteria_intro}\n" + "\n".join(ordering_criteria_list)

        output_format_instruction_l1: str = (
            f"Your output MUST be a YAML list containing all integer indices from 0 to {max_index}, "
            f"each appearing exactly once, in the suggested chapter order. "
        )
        output_format_instruction_l2: str = (
            "You can use the 'index # Concept Name' format in your YAML list for clarity if you wish, "
            "but only the leading integer index for each list item will be parsed."
        )
        output_format_instruction: str = output_format_instruction_l1 + output_format_instruction_l2
        example_yaml: str = (
            "Example (for 3 concepts):\n"
            "```yaml\n"
            "- 2 # Introduction to Topic (Considered foundational)\n"
            "- 0 # Core Feature X (Builds on introduction)\n"
            "- 1 # Advanced Usage of X (Details Core Feature X)\n"
            "```"
        )
        prompt_lines: list[str] = [
            f"You are an expert technical writer structuring a summary or tutorial based on analyzed web content "
            f"from: '{document_collection_name}'.",
            "The following core concepts/topics have been identified from segmented document chunks:",
            f"\n**Identified Concepts (Index # Name - Summary):**{list_lang_note}\n{concepts_listing_with_summaries}",
            f"\n**Summary of Concept Relationships:**\n{relationships_summary}",
            f"\n**Your Task:**\n{ordering_criteria}",
            f"\n**Output Format:**\n{output_format_instruction}",
            f"\n{example_yaml}",
            "\nProvide ONLY the YAML list in a single ```yaml code block. "
            "Do not include any introductory text, explanations, or concluding remarks outside the YAML block.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def _prepare_web_chapter_language_hints(target_language: str) -> dict[str, str]:
        """Prepare language-specific hint strings for writing web chapters.

        Args:
            target_language (str): The target language for the chapter.

        Returns:
            dict[str, str]: A dictionary of language-specific hint strings.
        """
        hints: dict[str, str] = {
            "lang_instr": "",
            "concept_note": "",
            "struct_note": "",
            "instr_note": "",
            "mermaid_note": "",
            "link_note": "",
            "tone_note": "",
            "lang_cap": target_language.capitalize(),
        }
        if target_language.lower() != "english":
            lang_cap_val: str = hints["lang_cap"]
            hints_l1: str = (
                f"IMPORTANT: You MUST write the ENTIRE chapter content in **{lang_cap_val}**. "
                f"This includes all explanatory text and labels in diagrams. "
            )
            hints_l2: str = (
                f"Use English ONLY for universally recognized technical terms or direct quotes "
                f"that do not have a common {lang_cap_val} translation (e.g., 'API', 'JSON').\n\n"
            )
            hints["lang_instr"] = hints_l1 + hints_l2
            hints["concept_note"] = f" (This name/summary is expected in {lang_cap_val})"
            hints["struct_note"] = f" (Chapter titles/links expected in {lang_cap_val})"
            hints["instr_note"] = f" (Explain in {lang_cap_val})"
            hints["mermaid_note"] = f" (Use {lang_cap_val} labels/text)"
            hints["link_note"] = f" (Use {lang_cap_val} chapter title)"
            hints["tone_note"] = f" (appropriate for {lang_cap_val}-speaking audience)"
        return hints

    @staticmethod
    def _prepare_web_chapter_transitions(target_language_lower: str) -> tuple[str, str]:
        """Prepare intro/concluding transition phrases for a web chapter.

        Args:
            target_language_lower (str): The target language for the chapter, in lowercase.

        Returns:
            tuple[str, str]: Introductory and concluding transition phrases.
        """
        translations: dict[str, dict[str, str]] = {
            "slovak": {
                "intro": "Poďme sa bližšie pozrieť na tento koncept.",
                "conclusion": "Týmto uzatvárame prehľad tejto témy.",
            }
        }
        lang_trans: dict[str, str] = translations.get(target_language_lower, {})
        intro: str = lang_trans.get("intro", "Let's delve deeper into this concept.")
        conclusion: str = lang_trans.get("conclusion", "This concludes our overview of this topic.")
        return intro, conclusion

    @staticmethod
    def format_write_web_chapter_prompt(context: "WriteWebChapterContext") -> str:
        """Format prompt for LLM to write a single chapter based on web content chunks.

        Args:
            context (WriteWebChapterContext): Dataclass (imported from ._common)
                                              containing all necessary information for
                                              generating the chapter.

        Returns:
            str: A formatted multi-line string constituting the complete prompt.
        """
        hints: dict[str, str] = WebChapterPrompts._prepare_web_chapter_language_hints(context.target_language)
        intro_transition, concl_transition = WebChapterPrompts._prepare_web_chapter_transitions(
            context.target_language.lower()
        )

        instr_heading: str = (
            f"1.  **Heading:** Start *immediately* with: `# Chapter {context.chapter_num}: "
            f"{context.concept_name}`. NO text before it."
        )
        instr_intro: str = (
            f"2.  **Introduction{hints['instr_note']}:** Begin main content with: "
            f'"{intro_transition}". Briefly state the chapter\'s purpose and main topic based on the '
            f"concept's name and summary. Clearly set the context for the reader (1-2 insightful sentences)."
        )
        instr_elaboration: str = (
            f"3.  **Detailed Elaboration & Structure{hints['instr_note']}:** This is the CORE of the chapter. "
            "Provide a COMPREHENSIVE and DETAILED explanation of the concept, drawing EXTENSIVELY from ALL relevant information within the 'Relevant Document CHUNK Snippets'. "  # noqa: E501
            "Your primary goal is to educate the reader thoroughly on this specific concept. "
            "Before writing, mentally identify 3-5 key sub-topics or aspects of the main concept that are present in the snippets."  # noqa: E501
            "\n    a.  **Extract and Explain Key Facts & Information:** For each identified sub-topic/aspect, "
            "extract ALL important facts, definitions, functionalities, and detailed information from the provided snippets. Be thorough and specific."  # noqa: E501
            "\n    b.  **Explain Significance & Purpose:** For each sub-topic/aspect, clarify why it is important, "
            f"what problem it solves, or what value it provides in the context of '{context.document_collection_name}' or the specific topic area."  # noqa: E501
            "\n    c.  **Synthesize and Rephrase:** Do NOT just copy text. Understand and rephrase the information clearly, "  # noqa: E501
            f"concisely, and in an engaging manner in your own words (in {hints['lang_cap'] if hints['lang_cap'] else 'the target language'}). "  # noqa: E501
            "Maintain technical accuracy and ensure a well-written, flowing narrative for each section."
            "\n    d.  **Structure with Subheadings (MANDATORY):** You MUST divide the elaborated content into logical sections "  # noqa: E501
            "using Markdown subheadings (e.g., `## Key Features`, `### Configuration Details`, `## How it Works`). "
            "Use H2 (`##`) for each of your mentally identified 3-5 key sub-topics/aspects. Use H3 (`###`) for further detailing within an H2 section if necessary. "  # noqa: E501
            "Each subheading MUST be descriptive of the section's content and be followed by substantial explanatory text (several well-developed paragraphs if the source material allows)."  # noqa: E501
            "\n    e.  **Content Depth per Section:** Each section under an H2 subheading should be well-developed and provide a meaningful level of detail. "  # noqa: E501
            "AVOID very short sections with only one or two sentences. If a sub-topic from the snippets is important, dedicate a proper, detailed section to it."  # noqa: E501
            "\n    f.  **Clarity and Flow:** Use paragraphs, bullet points, or numbered lists within sections where "
            "appropriate to make the information digestible. Ensure a logical flow between sections."
        )
        instr_examples: str = (
            f"4.  **Code Examples, CLI Commands, Configs (if present in snippets){hints['instr_note']}:**"
            "\n    a.  **Identify and Extract:** Carefully scan the 'Relevant Document CHUNK Snippets' for any code "
            "examples (Python, Java, JavaScript, SQL, etc.), Command-Line Interface (CLI) commands, "
            "configuration blocks (JSON, YAML, XML, .ini), or similar structured technical data."
            "\n    b.  **Format Correctly:** If found, present them accurately using Markdown code fences "
            "with appropriate language identifiers (e.g., ```python, ```bash, ```json)."
            "\n    c.  **Explain Thoroughly:** Provide a clear explanation of what each example demonstrates, "
            "what its key parts do, and how it relates to the concept. If it's a configuration, explain important parameters shown. "  # noqa: E501
            "Do not just show the code; explain its purpose and usage in detail."
            "\n    d.  **Placement:** Integrate these examples within relevant sub-sections (under H2 or H3 headings) created in step 3d. "  # noqa: E501
            "A dedicated `## Examples` or `### Usage Example` subheading might be appropriate if multiple examples exist for the concept."  # noqa: E501
        )
        instr_how_to: str = (
            f"5.  **'How-To' Guides or Procedural Steps (if applicable){hints['instr_note']}:**"
            "\n    a.  If the snippets for THIS concept describe a sequence of steps, a process, or a 'how-to' guide, "
            "extract these steps and present them clearly as a numbered list under an appropriate subheading (e.g., `## Step-by-Step: Configuring X`)."  # noqa: E501
            "\n    b.  Ensure the steps are logical, complete (as per snippets), easy to follow, and well-explained."
        )
        instr_param_explain: str = (
            f"6.  **Explanation of Parameters/Options/Key Terms (if applicable){hints['instr_note']}:**"
            "\n    a.  If the snippets mention specific parameters, API endpoints, command-line options, configuration settings, "  # noqa: E501
            "or key technical terms crucial to THIS concept, list them (perhaps under a `## Key Parameters and Terms` subheading) and provide a clear, detailed explanation "  # noqa: E501
            "of their purpose, possible values, and meaning, as derived from the snippets."
        )
        instr_diagrams: str = (
            f"7.  **Inline Diagrams (Use Sparingly & Simply){hints['mermaid_note']}:** "
            f"{INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT}"
        )
        instr_linking: str = (
            f"8.  **Contextual Links (Subtle Integration){hints['link_note']}:** If relevant and natural, subtly mention how this concept "  # noqa: E501
            "relates to concepts in the (immediately) previous or next chapters (use titles from 'Overall Summary Structure'). "  # noqa: E501
            "Use Markdown links `[Chapter Title](filename.md)`. Avoid forced or excessive linking; prioritize the current chapter's content."  # noqa: E501
        )
        instr_tone: str = (
            f"9.  **Tone & Style{hints['tone_note']}:** Clear, concise, yet sufficiently detailed and informative. "
            "The chapter should be easy to understand for someone learning about this content. Maintain a technical and objective tone. "  # noqa: E501
            "Explain jargon if present in snippets, or use simpler terms if appropriate while preserving accuracy."
        )
        instr_conclusion_l1: str = (
            f"10. **Conclusion{hints['instr_note']}:** Briefly summarize the main takeaway or key learning points "
            f"of this chapter (1-2 insightful sentences). End the main content *EXACTLY* with: "
        )
        instr_conclusion_l2: str = (
            f'"{concl_transition}". '
            "**CRITICAL: Do NOT add any 'Next, we will examine...' link or similar "
            "navigational phrase after this concluding sentence.** (Nav links are handled separately)."
        )
        instr_conclusion: str = instr_conclusion_l1 + instr_conclusion_l2
        instr_format: str = (
            "11. **Output Format & Length:** Generate ONLY raw Markdown. Start with H1. NO outer ```markdown wrapper. NO footer. "  # noqa: E501
            "The chapter should be comprehensive. AVOID generating overly short chapters (e.g., only one or two brief paragraphs) if the source snippets provide enough material for more detail. "  # noqa: E501
            "Strive for depth and completeness based on the provided text."
        )

        instructions_list: list[str] = [
            instr_heading,
            instr_intro,
            instr_elaboration,
            instr_examples,
            instr_how_to,
            instr_param_explain,
            instr_diagrams,
            instr_linking,
            instr_tone,
            instr_conclusion,
            instr_format,
        ]
        instructions_text: str = "\n".join(instructions_list)

        prompt_start_l1: str = f"{hints['lang_instr']}You are an expert technical writer creating a detailed, "
        prompt_start_l2: str = (
            f"well-structured, and practical summary chapter for a tutorial about the web content from: `{context.document_collection_name}`. "  # noqa: E501
            "Your primary source of information is the 'Relevant Document CHUNK Snippets' provided below. Your goal is to produce a chapter that is informative and easy to read, leveraging all relevant details from the snippets."  # noqa: E501
        )
        prompt_start: str = prompt_start_l1 + prompt_start_l2

        prompt_lines: list[str] = [
            prompt_start,
            f'Your task is to write **Chapter {context.chapter_num}: "{context.concept_name}"**.',
            f"\n**Core Concept for this Chapter{hints['concept_note']}:**",
            f"- Name: {context.concept_name}",
            f"- Summary from initial analysis: {context.concept_summary}",
            f"\n**Overall Summary Structure (for context and cross-linking){hints['struct_note']}:**",
            context.full_chapter_structure_md,
            f"\n**Relevant Document CHUNK Snippets for '{context.concept_name}' "
            "(Base your chapter ENTIRELY on the information found within these specific snippets. "
            "Elaborate on ALL key details, examples, and explanations found here. "
            "Structure the chapter logically with H2 and H3 subheadings.):\n**"  # Added emphasis
            f"```text\n{context.relevant_document_snippets}\n```",
            f"\n**Detailed Instructions for Writing Chapter {context.chapter_num}:**",
            instructions_text,
            "\nBegin your response *directly* with the H1 Markdown heading for this chapter. "
            "Generate only the raw Markdown content for this single chapter.",
        ]
        return "\n".join(prompt_lines)


# End of src/FL02_web_crawling/prompts/chapter_prompts.py
