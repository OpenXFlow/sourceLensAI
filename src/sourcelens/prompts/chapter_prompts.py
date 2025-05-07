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
        # --- Bez zmeny ---
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
            lang_hints: Language-specific hints.

        Returns:
            A tuple containing the introductory and concluding transition strings.

        """
        # --- Bez zmeny ---
        lang = data.language.lower()
        default_intro = "Let's begin exploring this concept."
        default_conclusion = "This concludes our look at this topic."
        default_prev_link_text = "Previously, we looked at"
        translations: dict[str, dict[str, str]] = {
            "slovak": {
                "intro": "Začnime skúmať tento koncept.",
                "conclusion": "Týmto končíme náš pohľad na túto tému.",
                "prev_link": "Predtým sme sa pozreli na",
            }
        }
        lang_trans = translations.get(lang, {})
        intro = lang_trans.get("intro", default_intro)
        conclusion = lang_trans.get("conclusion", default_conclusion)
        prev_link_text = lang_trans.get("prev_link", default_prev_link_text)

        transition_from_prev = intro
        if data.prev_chapter_meta:
            prev_name = str(data.prev_chapter_meta.get("name", "the previous concept"))
            prev_file = str(data.prev_chapter_meta.get("filename", "#"))
            transition_from_prev = f"{prev_link_text} [{prev_name}]({prev_file}). {intro}"

        transition_to_next = conclusion  # Conclusion only, NO next link

        return transition_from_prev, transition_to_next

    @staticmethod
    def _prepare_chapter_instructions(
        data: WriteChapterContext,
        hints: dict[str, str],
        transitions: tuple[str, str],
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
        # Updated/Combined Instruction #7 for Inline Diagrams
        instr_part_7 = (
            f"7.  **Inline Diagrams (Optional){hints['mermaid_note']}:** If helpful for explaining a core concept, "
            f"method call flow, or process logic, consider embedding a SIMPLE `mermaid` diagram "
            f"(sequence, activity, graph TD) using ```mermaid ... ```. Explain the diagram briefly.\n"
            f"    **CRITICAL MERMAID SYNTAX (for diagrams inside chapters):**\n"
            f"        - **First Line:** The line *immediately* after ```mermaid MUST be the diagram type keyword "
            f"(e.g., `sequenceDiagram`, `activityDiagram`, `graph TD`). NO leading spaces, comments, or text.\n"
            f"        - **Sequence Diagrams:**\n"
            f"            - Message labels MUST use format `Arrow: Label Text` (e.g., `A->>B: Request data`). "
            f"**EVERY arrow (`->>`, `->`, `-->>`, `-->`) MUST be followed by a colon `:` "
            f"and then the message text.** Even if the message is just confirmation, use text like `: ok` or `: done`.\n"
            # E501 fix: Wrapped line
            f"            - The line IMMEDIATELY following `alt`, `else`, `opt` MUST be a valid command "
            f"(e.g., a message).\n"
            f"            - Ensure `activate`/`deactivate` and `alt/else/opt/loop/par`/`end` blocks are balanced.\n"
            f"        - **Activity Diagrams:**\n"
            f"            - Use `(*)` for start/end states if appropriate.\n"
            f"            - Use `-->` for transitions. Use `:` for labels on transitions (e.g., `--> Condition Met`).\n"
            # E501 fix: Wrapped line
            f"            - Conditional logic uses `if (Condition?) then (yes)` and `else (no) ... endif` "
            f"or diamond shapes.\n"
            # E501 fix: Wrapped line
            f"            - Ensure all paths logically flow and terminate correctly "
            f"(e.g., converge before end state).\n"
            f"        - **General:** Avoid overly complex styling or labels inside chapters. Keep diagrams focused."
        )
        instr_part_9 = (  # Renumbered
            f"8.  **Relationships & Cross-Linking{hints['link_note']}:** Mention & link to related "
            f"chapters using Markdown `[Title](filename.md)` based on 'Overall Tutorial Structure'."
        )
        instr_part_10 = (  # Renumbered
            f"9.  **Tone & Style{hints['tone_note']}:** Beginner-friendly, encouraging. Explain jargon."
        )
        instr_part_11 = (  # Renumbered
            f"10. **Conclusion:** Summarize the key takeaway. End the main content *EXACTLY* with: "
            f'"{transition_to_next}". **CRITICAL: Do NOT add any "Next, we will examine..." link or '
            f"similar transition phrase after this concluding sentence.** The linking will be handled later."
        )
        instr_part_12 = (  # Renumbered
            "11. **Output Format:** Generate ONLY raw Markdown. Start with H1. NO outer ```markdown wrapper. NO footer."
        )

        instr_parts = [
            instr_part_1,
            instr_part_2,
            instr_part_3,
            instr_part_4,
            instr_part_5,
            instr_part_6,
            instr_part_7,
            instr_part_9,
            instr_part_10,
            instr_part_11,
            instr_part_12,
        ]
        return "\n".join(instr_parts)

    # --- Public Prompt Formatting Methods ---
    @staticmethod
    def format_order_chapters_prompt(
        project_name: str,
        abstraction_listing: str,
        context: str,
        num_abstractions: int,
        list_lang_note: str,
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
        # --- Bez zmeny ---
        if num_abstractions == 0:
            return "No abstractions provided."
        max_index = max(0, num_abstractions - 1)
        ordering_criteria = "Determine logical order. Criteria:\n- Foundational\n- Dependency\n- Flow\n- Simplicity"
        output_format_instruction = f"Output ONLY ordered list...Use 'idx # Name'...Cover indices 0-{max_index} once."
        example_yaml = "Example:\n```yaml\n- 2 # DB Connection\n- 0 # User Model\n# ... other ...\n```"
        prompt_lines = [
            f"Given abstractions/concepts for `{project_name}`:",
            f"\nAbstractions (Index # Name){list_lang_note}:",
            abstraction_listing,
            "\nContext:\n```",
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
