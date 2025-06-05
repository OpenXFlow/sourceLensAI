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

"""Prompts for generating an AI-powered review of web content."""

from typing import TYPE_CHECKING, Any, Final, Optional

if TYPE_CHECKING:
    from sourcelens.core.common_types import WebContentConceptsList, WebContentRelationshipsDict


MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW: Final[int] = 100
"""Max character length for individual concept summary snippets used in the review prompt."""
MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW: Final[int] = 150
"""Max character length for the overall relationship summary snippet used in the review prompt."""
MAX_INVENTORY_SNIPPET_LEN_REVIEW: Final[int] = 1000
"""Max character length for the content inventory snippet provided to the review prompt."""
MAX_EXAMPLE_RELATIONSHIPS_IN_REVIEW_PROMPT: Final[int] = 2
"""Maximum number of example relationships to include in the review prompt for context."""

WEB_REVIEW_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "key_insights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key insights or takeaways from the web content, based on identified concepts and their relationships.",  # noqa: E501
        },
        "areas_for_improvement_or_clarification": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Suggestions for improving or clarifying the content, potentially referencing specific concepts.",  # noqa: E501
        },
        "content_structure_observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observations about the content's structure, flow, or presentation based on the relationships and inventory.",  # noqa: E501
        },
        "overall_assessment": {
            "type": "string",
            "minLength": 1,
            "description": "Overall AI-generated assessment of the web content, considering all provided context.",
        },
    },
    "required": [
        "key_insights",
        "areas_for_improvement_or_clarification",
        "content_structure_observations",
        "overall_assessment",
    ],
    "additionalProperties": False,
}


class WebReviewPrompts:
    """Container for prompts related to generating a review of web content."""

    @staticmethod
    def _format_concepts_for_review_prompt(concepts: "WebContentConceptsList", target_language: str) -> str:
        """Format the list of web concepts for the review prompt.

        Args:
            concepts (WebContentConceptsList): List of identified web concepts.
            target_language (str): The target language for the review.

        Returns:
            str: A formatted string of concepts for the prompt.
        """
        if not concepts:
            return "No core concepts were identified for this web content."

        lang_note: str = ""
        if target_language.lower() != "english":
            lang_cap: str = target_language.capitalize()
            lang_note = f" (Names/summaries are expected to be in {lang_cap})"

        header: str = f"Identified Core Concepts/Topics{lang_note} (Index. Name - Summary Snippet - Source Chunk IDs):"
        parts: list[str] = [header]
        for i, concept_item in enumerate(concepts):
            name_val: Any = concept_item.get("name", f"Unnamed Concept {i}")
            name: str = str(name_val)
            summary_val: Any = concept_item.get("summary", "N/A")
            summary: str = str(summary_val)
            summary_snippet: str = summary[:MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW]
            if len(summary) > MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW:
                summary_snippet += "..."

            source_ids_raw: Any = concept_item.get("source_chunk_ids", [])
            source_ids_list: list[str] = (
                [str(sid) for sid in source_ids_raw if isinstance(sid, str)] if isinstance(source_ids_raw, list) else []
            )
            source_info: str = (
                (
                    f"(Sources: {', '.join(source_ids_list[:2])}{'...' if len(source_ids_list) > 2 else ''})"  # noqa: PLR2004 (literal comparison is fine)
                )
                if source_ids_list
                else "(No specific source chunks listed)"
            )
            parts.append(f"  - {i}. {name} {source_info}: {summary_snippet}")
        return "\n".join(parts)

    @staticmethod
    def _format_relationships_for_review_prompt(
        relationships: "WebContentRelationshipsDict", target_language: str
    ) -> str:
        """Format the relationships summary for the review prompt.

        Args:
            relationships (WebContentRelationshipsDict): Dictionary of identified relationships.
            target_language (str): The target language for the review.

        Returns:
            str: A formatted string of the relationship summary for the prompt.
        """
        summary_val: Any = relationships.get("overall_summary", "No overall relationship summary provided.")
        summary: str = str(summary_val)
        summary_snippet: str = summary[:MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW]
        if len(summary) > MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW:
            summary_snippet += "..."

        lang_note: str = ""
        if target_language.lower() != "english":
            lang_cap_rel: str = target_language.capitalize()
            lang_note = f" (Summary and labels are expected to be in {lang_cap_rel})"

        rel_summary_header: str = (
            f"Relationship Summary{lang_note} (AI's interpretation of content flow between concepts):"
        )
        details_any: Any = relationships.get("relationships", [])
        details_list: list[Any] = details_any if isinstance(details_any, list) else []
        key_rels_parts: list[str] = []

        if details_list:
            key_rels_parts.append("  Key Interactions Example:")
            for rel_item_any in details_list[:MAX_EXAMPLE_RELATIONSHIPS_IN_REVIEW_PROMPT]:
                if isinstance(rel_item_any, dict):
                    from_idx_val: Any = rel_item_any.get("from_concept_index", "?")
                    from_idx: str = str(from_idx_val)
                    to_idx_val: Any = rel_item_any.get("to_concept_index", "?")
                    to_idx: str = str(to_idx_val)
                    label_val: Any = rel_item_any.get("label", "related to")
                    label: str = str(label_val)
                    key_rels_parts.append(f"    - Concept {from_idx} --[{label}]--> Concept {to_idx}")

        return f"{rel_summary_header}\n{summary_snippet}\n" + "\n".join(key_rels_parts)

    @staticmethod
    def _format_inventory_for_review_prompt(inventory_md: Optional[str]) -> str:
        """Format the content inventory for the review prompt.

        Args:
            inventory_md (Optional[str]): Markdown content of the web inventory.

        Returns:
            str: A formatted string of the inventory snippet for the prompt.
        """
        if not inventory_md or not inventory_md.strip():
            return "Content inventory: Not available or empty."
        header: str = "Content Inventory Snippet (Summaries of crawled documents/chunks):"
        snippet: str = inventory_md.strip()[:MAX_INVENTORY_SNIPPET_LEN_REVIEW]
        if len(inventory_md.strip()) > MAX_INVENTORY_SNIPPET_LEN_REVIEW:
            snippet += "..."
        return f"{header}\n```markdown\n{snippet}\n```"

    @staticmethod
    def _get_web_review_language_instruction(target_language: str) -> str:
        """Prepare language specific instruction for the web review.

        Args:
            target_language (str): The target language for the review.

        Returns:
            str: Language-specific instruction string.
        """
        instruction_parts: list[str] = []
        lang_cap_instr: str = target_language.capitalize()
        if target_language.lower() != "english":
            instruction_parts.append(
                f"IMPORTANT: You MUST generate all textual content for this review (summaries, characteristics, insights, etc.) "  # noqa: E501
                f"exclusively in **{lang_cap_instr}**."
            )
            instruction_parts.append(
                f"Use English ONLY for universally recognized technical terms, direct quotes from the English source, or "  # noqa: E501
                f"proper nouns that do not have a common {lang_cap_instr} equivalent (e.g., 'API', 'JSON', 'Crawl4AI').\n"  # noqa: E501
            )
        else:
            instruction_parts.append("IMPORTANT: Generate all textual content for this review in **English**.\n")
        return "".join(instruction_parts)

    @staticmethod
    def _get_web_review_yaml_example(collection_name: str, target_language: str) -> str:
        """Return the YAML example structure string for the web review prompt.

        Args:
            collection_name (str): The name of the document collection.
            target_language (str): The target language for localization of examples.

        Returns:
            str: A string representing the YAML example structure.
        """
        # Basic English examples, to be localized if needed
        ex_insight1_en: str = (
            "Insight: The content primarily focuses on [Main Topic A from Concepts]. "
            "Benefit: Provides a clear entry point for users interested in [Main Topic A]."
        )
        ex_suggestion1_en: str = (
            "Suggestion: The transition between [Concept D name (Index X)] and [Concept E name (Index Y)] "
            "could be smoother. Consider adding a brief introductory sentence to bridge them."
        )
        ex_observation1_en: str = (
            "Observation: The information flows logically from general introductions (e.g., [Concept A name "
            "(Index 0)]) to more specific details (e.g., [Concept B name (Index 2)])."
        )
        ex_assessment_en_l1: str = (
            f"    Overall, the web content for '{collection_name}' appears to be [e.g., well-structured, "
            "comprehensive on Topic X, somewhat fragmented]."
        )
        ex_assessment_en_l2: str = (
            "    A key strength is [e.g., its clear explanation of Concept A name (Index 0)]. A potential area for "
            "enhancement could be [e.g., providing more examples for Concept B name (Index 2)]. "
            "(AI-generated assessment for discussion)."
        )

        # Simple localization for Slovak example
        if target_language.lower() == "slovak":
            ex_insight1: str = (
                '  - "Poznatok: Obsah sa primárne zameriava na [Hlavná téma A z Konceptov]. '
                'Výhoda: Poskytuje jasný vstupný bod pre používateľov so záujmom o [Hlavná téma A]."'
            )
            ex_suggestion1: str = (
                '  - "Návrh: Prechod medzi [Názov konceptu D (Index X)] a [Názov konceptu E (Index Y)] '
                'by mohol byť plynulejší. Zvážte pridanie krátkej úvodnej vety na ich prepojenie."'
            )
            ex_observation1: str = (
                '  - "Pozorovanie: Informácie plynú logicky od všeobecných úvodov (napr. [Názov konceptu A (Index 0)]) '
                'k špecifickejším detailom (napr. [Názov konceptu B (Index 2)])."'
            )
            ex_assessment_l1: str = (
                f"    Celkovo sa webový obsah pre '{collection_name}' javí byť [napr. dobre štruktúrovaný, "
                "komplexný v téme X, trochu fragmentovaný]."
            )
            ex_assessment_l2: str = (
                "    Kľúčovou silnou stránkou je [napr. jasné vysvetlenie Názvu konceptu A (Index 0)]. Potenciálnou oblasťou "  # noqa: E501
                "na zlepšenie by mohlo byť [napr. poskytnutie viacerých príkladov pre Názov konceptu B (Index 2)]. "
                "(Hodnotenie vygenerované AI na diskusiu)."
            )
        else:  # Default to English if no specific translation
            ex_insight1 = f'  - "{ex_insight1_en}"'
            ex_suggestion1 = f'  - "{ex_suggestion1_en}"'
            ex_observation1 = f'  - "{ex_observation1_en}"'
            ex_assessment_l1 = ex_assessment_en_l1
            ex_assessment_l2 = ex_assessment_en_l2

        yaml_ex_kc_header: str = "key_insights:"
        yaml_ex_ad_header: str = "areas_for_improvement_or_clarification:"
        yaml_ex_op_header: str = "content_structure_observations:"
        yaml_ex_os_header: str = "overall_assessment: |"

        output_parts: list[str] = ["```yaml"]
        output_parts.extend([yaml_ex_kc_header, ex_insight1])
        output_parts.extend([yaml_ex_ad_header, ex_suggestion1])
        output_parts.extend([yaml_ex_op_header, ex_observation1])
        output_parts.extend([yaml_ex_os_header, ex_assessment_l1, ex_assessment_l2])
        output_parts.append("```")
        return "\n".join(output_parts)

    @staticmethod
    def format_generate_web_review_prompt(
        document_collection_name: str,
        concepts_data: "WebContentConceptsList",
        relationships_data: "WebContentRelationshipsDict",
        inventory_content: Optional[str],
        target_language: str,
    ) -> str:
        """Format the prompt for the LLM to generate a review of web content.

        Args:
            document_collection_name (str): The name of the document collection.
            concepts_data (WebContentConceptsList): List of identified web concepts.
            relationships_data (WebContentRelationshipsDict): Dictionary of identified relationships.
            inventory_content (Optional[str]): Markdown content of the web inventory.
            target_language (str): The target language for the review.

        Returns:
            str: A formatted string prompting the LLM for a structured web content review.
        """
        concepts_str: str = WebReviewPrompts._format_concepts_for_review_prompt(concepts_data, target_language)
        relationships_str: str = WebReviewPrompts._format_relationships_for_review_prompt(
            relationships_data, target_language
        )
        inventory_str: str = WebReviewPrompts._format_inventory_for_review_prompt(inventory_content)
        lang_instruction: str = WebReviewPrompts._get_web_review_language_instruction(target_language)
        output_structure_yaml: str = WebReviewPrompts._get_web_review_yaml_example(
            document_collection_name, target_language
        )

        task_desc_lines_l1: str = "Generate a high-level review of the provided web content. Focus on:"
        task_desc_lines_l2: str = " - Key insights or takeaways from the content."
        task_desc_lines_l3_part1: str = (
            " - Potential areas for improvement, clarification, or further discussion (phrase as suggestions or "
        )
        task_desc_lines_l3_part2: str = (
            "questions, referencing specific concepts using 'Concept Name (Index X)' format if relevant)."
        )
        task_desc_lines_l4: str = " - Observations about the content's structure or presentation."
        task_desc_lines_l5: str = "This is an AI-driven initial analysis based on extracted concepts and summaries."
        task_desc_full: str = "\n".join(
            [
                task_desc_lines_l1,
                task_desc_lines_l2,
                task_desc_lines_l3_part1 + task_desc_lines_l3_part2,
                task_desc_lines_l4,
                task_desc_lines_l5,
            ]
        )

        prompt_lines_l1_intro: str = (
            f"You are an AI assistant tasked with providing a review of web content from: '{document_collection_name}'."
        )
        prompt_lines_l2_context: str = (
            "Based on the following summarized information (identified concepts from document chunks, "
            "their relationships, and an inventory of documents/chunks), provide a structured review."
        )

        prompt_lines: list[str] = [
            prompt_lines_l1_intro,
            lang_instruction,  # Language instruction placed prominently
            prompt_lines_l2_context,
            "\n**Provided Contextual Information:**",
            f"1. Identified Core Concepts (from document chunks):\n{concepts_str}",
            f"\n2. Summary of Concept Relationships:\n{relationships_str}",
            f"\n3. Content Inventory (Summaries of Individual Documents/Chunks):\n{inventory_str}",
            "\n**Your Task:**",
            task_desc_full,
            "The review should be objective, constructive, and high-level.",
            "\n**Output Format:**",
            "Your response MUST be a single YAML dictionary strictly following this structure:",
            output_structure_yaml,
            "\n**Content Generation Guidelines:**",
            "  - Base your review **only** on the provided concepts, relationships, and inventory.",
            "  - When referencing concepts in your points, use the format 'Concept Name (Index X)' "
            "for clarity, using the names and indices from the 'Identified Core Concepts' section.",
            "  - Ensure your points are specific and actionable where possible.",
            f"  - All textual fields in the YAML output (key_insights, areas_for_improvement_or_clarification, content_structure_observations, overall_assessment) MUST be in **{target_language.capitalize()}**.",  # noqa: E501
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML.",
        ]
        return "\n".join(filter(None, prompt_lines))


# End of src/FL02_web_crawling/prompts/review_prompts.py
