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


"""Provide prompts for ordering and writing tutorial chapters.

This module contains the `ChapterPrompts` class, which centralizes static methods
for formatting various prompts directed at a Large Language Model (LLM). These
prompts guide the LLM in determining a logical chapter order based on code
abstractions and in writing the content for individual tutorial chapters,
including specific instructions for structure, tone, code examples, and
inline Mermaid diagrams. It relies on common dataclasses like
`WriteChapterContext` for structured input.
"""

# Import common dataclasses and constants from the _common module
from ._common import (
    CODE_BLOCK_MAX_LINES,
    WriteChapterContext,
)

# Import the centralized inline Mermaid diagram guidelines from the diagrams package
from .diagrams import INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT


class ChapterPrompts:
    """Container for static methods that format prompts for chapter structuring and writing."""

    @staticmethod
    def _prepare_chapter_language_hints(language: str) -> dict[str, str]:
        """Prepare language-specific hint strings for the chapter writing prompt.

        This helper method generates a dictionary of string snippets tailored
        to the specified output language. These snippets are then used to
        infuse language-specific instructions into the main prompt, ensuring
        the LLM generates content (like concept names, descriptions, notes,
        and diagram labels) in the desired language, defaulting to English
        if no specific translations or hints are needed.

        Args:
            language: The target language code (e.g., 'english', 'slovak').
                      The comparison is case-insensitive.

        Returns:
            A dictionary where keys are hint identifiers (e.g., 'lang_instr',
            'concept_note') and values are the corresponding language-specific
            string snippets. If the language is 'english', most snippets
            will be empty strings.

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
            hints_l1 = (
                f"IMPORTANT: You MUST write the ENTIRE chapter content in **{lang_cap}**. "
                f"This includes all explanatory text, comments within code examples, "
            )
            hints_l2 = (
                f"and labels in diagrams. Use English ONLY for actual code keywords, "
                f"function/variable names, and standard technical terms that do not have "
                f"a common {lang_cap} translation (e.g., 'API', 'JSON').\n\n"
            )
            hints["lang_instr"] = hints_l1 + hints_l2
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
        """Prepare introductory and concluding transition phrases for a chapter.

        This method generates generic transition phrases based on the target
        language specified in `data.language`. The "Previously..." and "Next..."
        Markdown links are handled separately by the `CombineTutorial` node, so this
        method focuses only on the textual cues for the LLM to start and end
        the main content body.

        Args:
            data: The context object for the current chapter, containing
                  the target language.
            lang_hints: A dictionary of language-specific hint strings.
                        Currently unused in this specific method's logic but
                        kept for potential future use or consistency.

        Returns:
            A tuple containing two strings:
            1.  The introductory transition phrase (e.g., "Let's begin...").
            2.  The concluding transition phrase (e.g., "This concludes...").

        """
        del lang_hints  # Currently unused, acknowledge to avoid linter warnings

        lang = data.language.lower()
        default_intro = "Let's begin exploring this concept."
        default_conclusion = "This concludes our look at this topic."

        translations: dict[str, dict[str, str]] = {
            "slovak": {
                "intro": "Začnime skúmať tento koncept.",
                "conclusion": "Týmto končíme náš pohľad na túto tému.",
            }
            # Add other languages here if needed
        }
        lang_trans = translations.get(lang, {})
        intro = lang_trans.get("intro", default_intro)
        conclusion = lang_trans.get("conclusion", default_conclusion)

        return intro, conclusion

    @staticmethod
    def _prepare_chapter_instructions(
        data: WriteChapterContext,
        hints: dict[str, str],
        transitions: tuple[str, str],
    ) -> str:
        """Compile a list of detailed instructions for the LLM to write a chapter.

        This method constructs a multi-point instructional list guiding the LLM
        on aspects like heading, introduction, content structure, code examples,
        inline diagrams (with specific Mermaid syntax rules), cross-linking,
        tone, conclusion, and output format. It incorporates language-specific
        hints and transition phrases.

        Args:
            data: The context object for the current chapter, providing details
                  like chapter number and abstraction name.
            hints: A dictionary of language-specific hint strings.
            transitions: A tuple containing the introductory and concluding
                         transition phrases for the chapter.

        Returns:
            A formatted multi-line string containing all instructions for the LLM.

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
        # Use the imported guidelines for inline Mermaid diagrams
        instr_part_7 = (
            f"7.  **Inline Diagrams (Optional){hints['mermaid_note']}:** {INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT}"
        )
        instr_part_9 = (
            f"8.  **Relationships & Cross-Linking{hints['link_note']}:** Mention & link to related "
            f"chapters using Markdown `[Title](filename.md)` based on 'Overall Tutorial Structure'."
        )
        instr_part_10 = f"9.  **Tone & Style{hints['tone_note']}:** Beginner-friendly, encouraging. Explain jargon."
        instr_part_11_l1 = (
            f"10. **Conclusion:** Summarize the key takeaway. End the main content *EXACTLY* with: "
            f'"{transition_to_next}". '
        )
        instr_part_11_l2 = (
            '**CRITICAL: Do NOT add any "Next, we will examine..." link or '
            "similar transition phrase after this concluding sentence.** The linking will be handled later."
        )
        instr_part_11 = instr_part_11_l1 + instr_part_11_l2

        instr_part_12 = (
            "11. **Output Format:** Generate ONLY raw Markdown. Start with H1. NO outer ```markdown wrapper. NO footer."
        )

        instr_parts: list[str] = [
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

    @staticmethod
    def format_order_chapters_prompt(
        project_name: str,
        abstraction_listing: str,
        context: str,
        num_abstractions: int,
        list_lang_note: str,
    ) -> str:
        """Format a prompt for the LLM to determine the optimal tutorial chapter order.

        This prompt instructs the LLM to analyze a list of code abstractions,
        their relationships, and a project summary to suggest a logical and
        pedagogical sequence for tutorial chapters. The output is expected
        as a YAML list of abstraction indices.

        Args:
            project_name: The name of the project for which to order chapters.
            abstraction_listing: A string listing all identified abstractions,
                                 typically formatted as "Index # Name".
            context: A string containing the project summary and details of
                     relationships between abstractions.
            num_abstractions: The total number of identified abstractions, used
                              for validating the LLM's output.
            list_lang_note: A language hint for the abstraction list, indicating
                            the language of the abstraction names if not English.

        Returns:
            A formatted multi-line string constituting the complete prompt.
            Returns a simple message if `num_abstractions` is 0.

        """
        if num_abstractions == 0:
            return "No abstractions provided to order chapters."
        max_index = max(0, num_abstractions - 1)
        ordering_criteria_intro = (
            "Determine a logical and pedagogical order for tutorial chapters. "
            "Base the order on the following criteria, from most to least important:"
        )
        ordering_criteria_list = [
            "- **Foundational Concepts First:** Concepts that are prerequisites for others should come earlier.",
            "- **Dependency Flow:** If concept A uses or depends on concept B, B should ideally be explained before A.",
            "- **Logical Progression:** Group related concepts or follow a natural process flow if applicable.",
            "- **Simplicity to Complexity:** Start with simpler, more general concepts before diving into specifics.",
        ]
        ordering_criteria = f"{ordering_criteria_intro}\n{'\n'.join(ordering_criteria_list)}"

        output_format_instruction_l1 = (
            f"Your output MUST be a YAML list containing all integer indices from 0 to {max_index}, "
            f"each appearing exactly once, in the suggested chapter order. "
        )
        output_format_instruction_l2 = (
            "You can use the 'index # Name' format in your YAML list for clarity, "
            "but only the leading integer index matters."
        )
        output_format_instruction = output_format_instruction_l1 + output_format_instruction_l2
        example_yaml = (
            "Example (for 3 abstractions):\n"
            "```yaml\n"
            "- 2 # Database Connection (Considered foundational)\n"
            "- 0 # User Authentication (Depends on DB connection)\n"
            "- 1 # Profile Management (Uses User Authentication)\n"
            "```"
        )
        prompt_lines: list[str] = [
            f"You are an expert technical writer structuring a tutorial for the software project: `{project_name}`.",
            "The following code abstractions/concepts have been identified:",
            f"\nAbstractions (Index # Name){list_lang_note}:",
            abstraction_listing,
            "\nAdditional Context (Project Summary & Relationships):\n```",
            context,
            "```",
            f"\n**Your Task:**\n{ordering_criteria}",
            f"\n**Output Format:**\n{output_format_instruction}",
            f"\n{example_yaml}",
            "\nProvide ONLY the YAML list in a single ```yaml code block. "
            "Do not include any introductory text, explanations, or concluding remarks outside the YAML block.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_write_chapter_prompt(context: WriteChapterContext) -> str:
        """Format a detailed LLM prompt for writing a single tutorial chapter.

        This method assembles a comprehensive prompt that guides the LLM in
        generating the Markdown content for one chapter. It includes project
        context, details of the specific abstraction for the chapter, overall
        tutorial structure, relevant code snippets, and a list of explicit
        instructions covering style, tone, formatting, and content requirements.

        Args:
            context: A `WriteChapterContext` object containing all necessary
                     data and metadata for generating the chapter prompt.

        Returns:
            A formatted multi-line string representing the complete prompt.

        """
        hints = ChapterPrompts._prepare_chapter_language_hints(context.language)
        transitions = ChapterPrompts._prepare_chapter_transitions(context, hints)
        instructions = ChapterPrompts._prepare_chapter_instructions(context, hints, transitions)

        prompt_start_line1 = (
            f"{hints['lang_instr']}You are an expert technical writer and Python programmer, tasked with "
        )
        prompt_start_line2 = f"writing a chapter for a tutorial about the software project: `{context.project_name}`."
        prompt_start = prompt_start_line1 + prompt_start_line2

        prompt_lines: list[str] = [
            prompt_start,
            f"Your current task is to write the content for **Chapter {context.chapter_num}: "
            f'"{context.abstraction_name}"**.',
            "\n**Target Audience:** Beginners to this specific codebase, "
            "but they might have general programming knowledge.",
            f"\n**Current Chapter's Core Concept Details{hints['concept_note']}:**",
            f"- Abstraction Name: {context.abstraction_name}",
            f"- Description: {context.abstraction_description}",
            f"\n**Overall Tutorial Structure (for context and cross-linking){hints['struct_note']}:**",
            context.full_chapter_structure,
            f"\n**Brief Summary of Preceding Content (if any){hints['prev_sum_note']}:**",
            context.previous_context_info,
            f'\n**Relevant Code Snippets for "{context.abstraction_name}" (use selectively to illustrate points):**',
            "```python",  # Assuming python context for now, this could be made dynamic if needed
            context.file_context_str,
            "```",
            f"\n**Detailed Instructions for Writing Chapter {context.chapter_num}:**",
            instructions,
            "\nBegin your response *directly* with the H1 Markdown heading for the chapter. "
            "Generate only the raw Markdown content for this single chapter.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/chapter_prompts.py
