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

"""Prompts related to ordering and writing chapters for web content."""

from dataclasses import dataclass
from typing import Optional

# Type Aliases
from sourcelens.core.common_types import WebChapterMetadata
from sourcelens.mermaid_diagrams._common_guidelines import INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT


@dataclass(frozen=True)
class WriteWebChapterContext:
    """Encapsulate all context needed to format the write web chapter prompt.

    Attributes:
        document_collection_name: Name of the website/document collection.
        chapter_num: The sequential number of this chapter.
        concept_name: The core concept/topic this chapter covers.
        concept_summary: A summary of the concept.
        full_chapter_structure_md: Markdown formatted list of all planned chapters.
        relevant_document_snippets: String containing relevant text snippets
                                    from original web document chunks for this concept.
        target_language: Target language for the chapter content.
        prev_chapter_meta: Metadata of the preceding chapter.
        next_chapter_meta: Metadata of the succeeding chapter.
    """

    document_collection_name: str
    chapter_num: int
    concept_name: str
    concept_summary: str
    full_chapter_structure_md: str
    relevant_document_snippets: str  # Now expects snippets from relevant chunks
    target_language: str
    prev_chapter_meta: Optional[WebChapterMetadata] = None
    next_chapter_meta: Optional[WebChapterMetadata] = None


class WebChapterPrompts:
    """Container for prompts related to web content chapter structuring and writing."""

    @staticmethod
    def format_order_web_chapters_prompt(
        document_collection_name: str,
        concepts_listing_with_summaries: str,  # This should now list concepts based on chunks
        relationships_summary: str,
        num_concepts: int,
        target_language: str,
    ) -> str:
        """Format prompt for LLM to determine chapter order for web content.

        Args:
            document_collection_name: Name of the website or document collection.
            concepts_listing_with_summaries: String listing identified concepts derived
                                             from document chunks (Index. Name - Summary).
            relationships_summary: LLM-generated summary of how concepts interrelate.
            num_concepts: Total number of identified concepts.
            target_language: The target language for any textual elements in the prompt.

        Returns:
            A formatted string prompting for a YAML list of concept indices.
        """
        if num_concepts == 0:
            return "No web concepts provided to order into chapters."

        lang_cap = target_language.capitalize()
        list_lang_note = ""
        if target_language.lower() != "english":
            list_lang_note = f" (Concept names/summaries are expected to be in {lang_cap})"

        max_index = max(0, num_concepts - 1)
        ordering_criteria_intro = (
            "Based on the identified concepts (derived from document chunks) and their relationships, "
            "determine a logical and pedagogical order for chapters that would summarize this web content effectively."
        )
        ordering_criteria_list = [
            "- **Foundational First:** Concepts that introduce or are prerequisites for others should come earlier.",
            "- **Logical Flow:** Follow a natural progression of topics as presented or implied by relationships.",
            "- **Narrative Cohesion:** Group related concepts to build a coherent understanding.",
            "- **User Journey(if applicable):** Consider how a user might typically explore or learn this information.",
        ]
        ordering_criteria = f"{ordering_criteria_intro}\n" + "\n".join(ordering_criteria_list)

        output_format_instruction_l1 = (
            f"Your output MUST be a YAML list containing all integer indices from 0 to {max_index}, "
            f"each appearing exactly once, in the suggested chapter order. "
        )
        output_format_instruction_l2 = (
            "You can use the 'index # Concept Name' format in your YAML list for clarity if you wish, "
            "but only the leading integer index for each list item will be parsed."
        )
        output_format_instruction = output_format_instruction_l1 + output_format_instruction_l2
        example_yaml = (
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
            target_language: The target language for the chapter.

        Returns:
            A dictionary of language-specific hint strings.
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
            lang_cap = hints["lang_cap"]
            hints_l1 = (
                f"IMPORTANT: You MUST write the ENTIRE chapter content in **{lang_cap}**. "
                f"This includes all explanatory text and labels in diagrams. "
            )
            hints_l2 = (
                f"Use English ONLY for universally recognized technical terms or direct quotes "
                f"that do not have a common {lang_cap} translation (e.g., 'API', 'JSON').\n\n"
            )
            hints["lang_instr"] = hints_l1 + hints_l2
            hints["concept_note"] = f" (This name/summary is expected in {lang_cap})"
            hints["struct_note"] = f" (Chapter titles/links expected in {lang_cap})"
            hints["instr_note"] = f" (Explain in {lang_cap})"
            hints["mermaid_note"] = f" (Use {lang_cap} labels/text)"
            hints["link_note"] = f" (Use {lang_cap} chapter title)"
            hints["tone_note"] = f" (appropriate for {lang_cap}-speaking audience)"
        return hints

    @staticmethod
    def _prepare_web_chapter_transitions(context: WriteWebChapterContext) -> tuple[str, str]:
        """Prepare intro/concluding transition phrases for a web chapter.

        Args:
            context: Context for the current web chapter.

        Returns:
            Introductory and concluding transition phrases.
        """
        lang = context.target_language.lower()
        translations: dict[str, dict[str, str]] = {
            "slovak": {
                "intro": "Poďme sa bližšie pozrieť na tento koncept.",
                "conclusion": "Týmto uzatvárame prehľad tejto témy.",
            }
        }
        lang_trans = translations.get(lang, {})
        intro = lang_trans.get("intro", "Let's delve deeper into this concept.")
        conclusion = lang_trans.get("conclusion", "This concludes our overview of this topic.")
        return intro, conclusion

    @staticmethod
    def format_write_web_chapter_prompt(context: WriteWebChapterContext) -> str:
        """Format prompt for LLM to write a single chapter based on web content chunks.

        Args:
            context: Dataclass containing all necessary
                     information for generating the chapter from web content chunks.

        Returns:
            A formatted multi-line string constituting the complete prompt.
        """
        hints = WebChapterPrompts._prepare_web_chapter_language_hints(context.target_language)
        intro_transition, concl_transition = WebChapterPrompts._prepare_web_chapter_transitions(context)

        instr_heading = (
            f"1.  **Heading:** Start *immediately* with: `# Chapter {context.chapter_num}: "
            f"{context.concept_name}`. NO text before it."
        )
        instr_intro = (
            f"2.  **Introduction{hints['instr_note']}:** Begin main content with: "
            f'"{intro_transition}". Briefly state the chapter\'s purpose based on the concept summary.'
        )
        instr_elaboration = (
            f"3.  **Elaboration{hints['instr_note']}:** Expand on the concept's summary. "
            "Use the 'Relevant Document Chunk Snippets' to extract key information, facts, "
            "and explanations specific to this concept. Synthesize and rephrase; do NOT just copy. "
            "Aim for 3-5 well-structured paragraphs focusing on the details from the provided snippets for THIS concept."  # noqa: E501
        )
        instr_examples = (
            f"4.  **Key Points/Examples (if applicable){hints['instr_note']}:** "
            "If the snippets for THIS concept contain clear examples, bullet points, CLI commands, or config snippets "
            "illustrating the concept, include 1-2 concise examples or a short bulleted list derived from these "
            "snippets. Keep it brief and directly related to the chunk content."
        )
        instr_diagrams = (
            f"5.  **Inline Diagrams (Optional & Simple){hints['mermaid_note']}:** "
            f"{INLINE_MERMAID_DIAGRAM_GUIDELINES_TEXT}"
        )
        instr_linking = (
            f"6.  **Contextual Links{hints['link_note']}:** If relevant, subtly mention how this concept "
            "relates to concepts in previous or next chapters (use titles from 'Overall Summary Structure'). "
            "Use Markdown links `[Chapter Title](filename.md)`."
        )
        instr_tone = (
            f"7.  **Tone & Style{hints['tone_note']}:** Clear, concise, informative, and easy to understand "
            "for someone learning about this content. Avoid jargon where possible or explain it based on "
            "the provided snippets."
        )
        instr_conclusion_l1 = (
            f"8.  **Conclusion{hints['instr_note']}:** Briefly summarize the main takeaway of this chapter. "
            f"End the main content *EXACTLY* with: "
        )
        instr_conclusion_l2 = (
            f'"{concl_transition}". '
            "**CRITICAL: Do NOT add any 'Next, we will examine...' link or similar "
            "navigational phrase after this concluding sentence.**"
        )
        instr_conclusion = instr_conclusion_l1 + instr_conclusion_l2
        instr_format = (
            "9.  **Output Format:** Generate ONLY raw Markdown. Start with H1. NO outer ```markdown wrapper. NO footer."
        )

        instructions_list = [
            instr_heading,
            instr_intro,
            instr_elaboration,
            instr_examples,
            instr_diagrams,
            instr_linking,
            instr_tone,
            instr_conclusion,
            instr_format,
        ]
        instructions = "\n".join(instructions_list)

        prompt_start_l1 = f"{hints['lang_instr']}You are an expert technical writer creating a summary chapter for "
        prompt_start_l2 = f"a tutorial about the web content from: `{context.document_collection_name}`."
        prompt_start = prompt_start_l1 + prompt_start_l2

        prompt_lines: list[str] = [
            prompt_start,
            f'Your task is to write **Chapter {context.chapter_num}: "{context.concept_name}"**.',
            f"\n**Core Concept for this Chapter{hints['concept_note']}:**",
            f"- Name: {context.concept_name}",
            f"- Summary from initial analysis: {context.concept_summary}",
            f"\n**Overall Summary Structure (for context and cross-linking){hints['struct_note']}:**",
            context.full_chapter_structure_md,
            # Zmenené z "Relevant Document Snippets" na "Relevant Document CHUNK Snippets"
            f"\n**Relevant Document CHUNK Snippets for '{context.concept_name}' "
            "(use these to elaborate on the concept, focusing on information within these specific chunks):\n**"
            f"```text\n{context.relevant_document_snippets}\n```",  # Toto by teraz mali byť snippety z chunkov
            f"\n**Detailed Instructions for Writing Chapter {context.chapter_num}:**",
            instructions,
            "\nBegin your response *directly* with the H1 Markdown heading. "
            "Generate only the raw Markdown for this single chapter.",
        ]
        return "\n".join(prompt_lines)


# End of src/FL02_web_crawling/prompts/chapter_prompts.py
