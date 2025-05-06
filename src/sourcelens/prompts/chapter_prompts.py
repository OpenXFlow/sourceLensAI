# src/sourcelens/prompts/chapter_prompts.py

"""Prompts related to ordering and writing tutorial chapters."""

# Import common dataclasses and constants from the _common module
from ._common import (
    CODE_BLOCK_MAX_LINES,
    WriteChapterContext,
)


class ChapterPrompts:
    """Container for prompts related to tutorial chapter structure and content."""

    # --- Helper Functions for Chapter Writing Prompt ---
    @staticmethod
    def _prepare_chapter_language_hints(language: str) -> dict[str, str]:
        """Prepare language-specific hint strings for the chapter writing prompt.

        Args:
            language: The target language code (e.g., 'english', 'slovak').

        Returns:
            A dictionary containing language-specific instruction snippets.

        """
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
                f"This includes all explanatory text, comments within code examples, "
                f"and labels in diagrams. Use English ONLY for actual code keywords, "
                f"function/variable names, and standard technical terms that do not have "
                f"a common {lang_cap} translation (e.g., 'API', 'JSON').\n\n"
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

    @staticmethod
    def _prepare_chapter_transitions(data: WriteChapterContext, lang_hints: dict[str, str]) -> tuple[str, str]:
        """Prepare transition text based on previous/next chapter metadata.

        Args:
            data: The context object for the current chapter.
            lang_hints: Language-specific hints (unused in current version of this helper).

        Returns:
            A tuple containing the introductory and concluding transition strings.

        """
        # lang_hints is passed but not directly used in this specific helper's logic
        # It's kept for consistency with other _prepare helpers if needed in future.
        lang = data.language.lower()
        default_intro = "Let's begin exploring this concept."
        default_conclusion = "This concludes our look at this topic."
        default_prev_link_text = "Previously, we looked at"
        default_next_link_text = "Next, we will examine"

        translations: dict[str, dict[str, str]] = {
            "slovak": {
                "intro": "Začnime skúmať tento koncept.",
                "conclusion": "Týmto končíme náš pohľad na túto tému.",
                "prev_link": "Predtým sme sa pozreli na",
                "next_link": "Ďalej preskúmame",
            }
            # Add other language translations as needed
        }
        lang_trans = translations.get(lang, {})
        intro = lang_trans.get("intro", default_intro)
        conclusion = lang_trans.get("conclusion", default_conclusion)
        prev_link_text = lang_trans.get("prev_link", default_prev_link_text)
        next_link_text = lang_trans.get("next_link", default_next_link_text)

        transition_from_prev = intro
        if data.prev_chapter_meta:
            prev_name = str(data.prev_chapter_meta.get("name", "the previous concept"))
            prev_file = str(data.prev_chapter_meta.get("filename", "#"))
            transition_from_prev = f"{prev_link_text} [{prev_name}]({prev_file}). {intro}"

        transition_to_next = conclusion
        if data.next_chapter_meta:
            next_name = str(data.next_chapter_meta.get("name", "the next concept"))
            next_file = str(data.next_chapter_meta.get("filename", "#"))
            transition_to_next = f"{conclusion} {next_link_text} [{next_name}]({next_file})."

        return transition_from_prev, transition_to_next

    @staticmethod
    def _prepare_chapter_instructions(
        data: WriteChapterContext, hints: dict[str, str], transitions: tuple[str, str]
    ) -> str:
        """Prepare the numbered instructions list for the chapter writing prompt.

        Args:
            data: The context object for the current chapter.
            hints: Language-specific instruction snippets.
            transitions: Tuple with intro and conclusion transition strings.

        Returns:
            A formatted string containing all instructions for the LLM.

        """
        transition_from_prev, transition_to_next = transitions
        instr_part_1 = (
            f"1.  **Heading:** Start *immediately* with: `# Chapter {data.chapter_num}: "
            f"{data.abstraction_name}`. NO text before it."
        )
        instr_part_2 = (
            f"2.  **Introduction & Transition{hints['instr_note']}:** Start main content with: "
            f'"{transition_from_prev}". State chapter goal.'
        )
        instr_part_3 = (
            f"3.  **Motivation/Purpose{hints['instr_note']}:** Explain *why* this concept exists. Use analogies."
        )
        instr_part_4 = f"4.  **Key Concepts Breakdown{hints['instr_note']}:** Explain sub-parts if complex."
        instr_part_5 = f"5.  **Usage / How it Works{hints['instr_note']}:** Explain high-level function or use."
        instr_part_6 = (
            f"6.  **Code Examples (Short & Essential){hints['code_note']}:** Use ```<lang> blocks "
            f"ONLY if vital (< {CODE_BLOCK_MAX_LINES} lines). Translate comments."
        )
        instr_part_7 = (
            f"7.  **Inline Diagrams for Concepts (If Applicable){hints['mermaid_note']}:** "
            f"If explaining a fundamental concept (e.g., method call, function flow, conditional logic, "
            f"object creation, loops), consider illustrating it with a **very simple, focused `mermaid` "
            f"sequence or graph diagram** "
            f"(using ```mermaid ... ```). "
            f"**IMPORTANT MERMAID SYNTAX for INLINE DIAGRAMS:**\n"
            f"    - For **ALL** participant/actor/node names, especially those containing spaces or special "
            f"characters (like '()', '.', ':', '/'), **ALWAYS use aliases OR double quotes** "
            f'(e.g., `participant DS as "Data Source (File)"`, `participant "Output Console"`, `A(ModuleA)`).\n'
            f"    - In sequence diagrams, **EVERY message arrow (e.g., `->>`, `-->`) MUST have a text label** "
            f"after the colon. "
            f"If no specific message is returned, use a generic label like `: done`, `: ok`, or `: data processed`. "
            f"Example: `Item-->>IP: : marked as processed`.\n"
            f"    - **Ensure control flow blocks like `loop`, `alt`, `opt`, `par` are correctly paired with "
            f"`end` statements.** "
            f"Correct nesting is crucial if these blocks are within each other.\n"
            f"These diagrams should be small and illustrate ONLY the specific concept. Explain the diagram briefly."
        )
        instr_part_8 = (
            f"8.  **Core Logic Visualization (Optional){hints['mermaid_note']}:** If the main abstraction "
            f"involves a complex process, *consider* illustrating its core logic with a slightly more "
            f"detailed `mermaid` diagram (sequence/activity). Explain it."
        )
        instr_part_9 = (
            f"9.  **Relationships & Cross-Linking{hints['link_note']}:** Mention & link to related "
            f"chapters using Markdown `[Title](filename.md)` based on 'Overall Tutorial Structure'."
        )
        instr_part_10 = f"10. **Tone & Style{hints['tone_note']}:** Beginner-friendly, encouraging. Explain jargon."
        instr_part_11 = (
            f"11. **Conclusion & Transition{hints['instr_note']}:** Summarize takeaway. End main "
            f'content with: "{transition_to_next}".'
        )
        instr_part_12 = (
            "12. **Output Format:** Generate ONLY raw Markdown. Start with H1. NO outer ```markdown wrapper. NO footer."
        )

        instr_parts = [
            instr_part_1,
            instr_part_2,
            instr_part_3,
            instr_part_4,
            instr_part_5,
            instr_part_6,
            instr_part_7,
            instr_part_8,
            instr_part_9,
            instr_part_10,
            instr_part_11,
            instr_part_12,
        ]
        # The .format(**hints) was problematic if a part didn't use hints and had braces.
        # Since hints are already embedded via f-strings, direct join is safer.
        return "\n".join(instr_parts)

    # --- Public Prompt Formatting Methods ---
    @staticmethod
    def format_order_chapters_prompt(
        project_name: str, abstraction_listing: str, context: str, num_abstractions: int, list_lang_note: str
    ) -> str:
        """Format prompt for LLM to determine optimal tutorial chapter order.

        Args:
            project_name: The name of the project.
            abstraction_listing: String listing abstractions (Index # Name).
            context: String with project summary and relationship details.
            num_abstractions: Total number of identified abstractions.
            list_lang_note: Language hint for the abstraction list.

        Returns:
            A formatted string prompting for a YAML list representing chapter order.

        """
        if num_abstractions == 0:
            return "No abstractions provided."
        max_index = max(0, num_abstractions - 1)
        ordering_criteria = (
            "Determine logical order. Criteria:\n- Foundational First\n- Dependency Order\n- User Flow\n- Simplicity"
        )
        output_format_instruction = f"Output ONLY ordered list...Use 'idx # Name'...Cover indices 0-{max_index} once."
        example_yaml = "Example:\n```yaml\n- 2 # DB Connection\n- 0 # User Model\n# ... other ...\n```"
        prompt_lines = [
            f"Given abstractions/concepts for `{project_name}`:",
            f"\nAbstractions (Index # Name){list_lang_note}:",
            abstraction_listing,
            "\nContext (Project Summary & Relationships):\n```",
            context,
            "```",
            "\nTask:",
            ordering_criteria,
            "\n" + output_format_instruction,
            "\n" + example_yaml,
            "\nProvide ONLY YAML output block for chapter order. No extra text.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_write_chapter_prompt(context: WriteChapterContext) -> str:
        """Format the detailed LLM prompt for writing a single tutorial chapter.

        Args:
            context: A WriteChapterContext object with necessary data.

        Returns:
            A formatted string representing the complete prompt for chapter content.

        """
        hints = ChapterPrompts._prepare_chapter_language_hints(context.language)
        transitions = ChapterPrompts._prepare_chapter_transitions(context, hints)
        instructions = ChapterPrompts._prepare_chapter_instructions(context, hints, transitions)
        prompt_start = f"{hints['lang_instr']}You are AI writing chapter for `{context.project_name}`."
        prompt_lines = [
            prompt_start,
            f'Current task: write **Chapter {context.chapter_num}**: **"{context.abstraction_name}"**.',
            "\nTarget Audience: Beginners...",
            f"\nConcept Details{hints['concept_note']}:",
            f"- Name: {context.abstraction_name}",
            f"- Description: {context.abstraction_description}",
            f"\nOverall Structure{hints['struct_note']}:\n{context.full_chapter_structure}",
            f"\nContext from Previous{hints['prev_sum_note']}:\n{context.previous_context_info}",
            f'\nRelevant Code Snippets for "{context.abstraction_name}" (Use selectively):',
            "```",
            context.file_context_str,
            "```",
            f"\nInstructions for Writing Chapter {context.chapter_num}:",
            instructions,
            "\nGenerate complete Markdown...starting *directly* with H1 heading:",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/chapter_prompts.py
