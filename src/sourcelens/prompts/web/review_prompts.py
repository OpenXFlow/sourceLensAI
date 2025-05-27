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

from typing import Any, Final, Optional

from typing_extensions import TypeAlias

# Type Aliases to match context provided by the calling node
WebContentConceptsList: TypeAlias = list[dict[str, Any]]
WebContentRelationshipsDict: TypeAlias = dict[str, Any]

MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW: Final[int] = 100
MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW: Final[int] = 150
MAX_INVENTORY_SNIPPET_LEN_REVIEW: Final[int] = 1000

# Schema for the expected YAML output of the web content review
WEB_REVIEW_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "key_insights": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key insights or takeaways from the web content.",
        },
        "areas_for_improvement_or_clarification": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Suggestions for improving or clarifying the content.",
        },
        "content_structure_observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observations about the content's structure or presentation.",
        },
        "overall_assessment": {
            "type": "string",
            "minLength": 1,
            "description": "Overall AI-generated assessment of the web content.",
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
    def _format_concepts_for_review_prompt(concepts: WebContentConceptsList) -> str:
        """Format the list of web concepts for the review prompt.

        Args:
            concepts (WebContentConceptsList): List of identified web concepts.

        Returns:
            str: A formatted string of concepts for the prompt.
        """
        if not concepts:
            return "No core concepts were identified for this web content."
        header = "Identified Core Concepts/Topics (Name - Summary Snippet):"
        parts: list[str] = [header]
        for i, concept_item in enumerate(concepts):
            name: str = str(concept_item.get("name", f"Unnamed Concept {i}"))
            summary: str = str(concept_item.get("summary", "N/A"))
            summary_snippet: str = summary[:MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW]
            if len(summary) > MAX_CONCEPT_DESC_SNIPPET_LEN_REVIEW:
                summary_snippet += "..."
            parts.append(f"  - {name}: {summary_snippet}")
        return "\n".join(parts)

    @staticmethod
    def _format_relationships_for_review_prompt(relationships: WebContentRelationshipsDict) -> str:
        """Format the relationships summary for the review prompt.

        Args:
            relationships (WebContentRelationshipsDict): Dictionary of identified relationships.

        Returns:
            str: A formatted string of the relationship summary for the prompt.
        """
        summary: str = str(relationships.get("overall_summary", "No overall relationship summary provided."))
        summary_snippet: str = summary[:MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW]
        if len(summary) > MAX_REL_SUMMARY_SNIPPET_LEN_REVIEW:
            summary_snippet += "..."
        rel_summary_header = "Relationship Summary (AI's interpretation of content flow):"
        return f"{rel_summary_header}\n{summary_snippet}"

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
        header = "Content Inventory Snippet (Summary of crawled pages):"
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
        if target_language.lower() != "english":
            lang_cap = target_language.capitalize()
            instruction_parts.append(
                f"IMPORTANT: Generate all textual content for this review (summaries, characteristics, etc.) "
                f"exclusively in **{lang_cap}**,"
            )
            instruction_parts.append("unless quoting specific English technical terms, titles, or proper nouns.\n")
        return "\n".join(instruction_parts)

    @staticmethod
    def _get_web_review_yaml_example(collection_name: str) -> str:
        """Return the YAML example structure string for the web review prompt.

        Args:
            collection_name (str): The name of the document collection.

        Returns:
            str: A string representing the YAML example structure.
        """
        yaml_ex_kc_header = "key_insights:"
        yaml_ex_kc_items_l1 = '  - "Insight: The content primarily focuses on [Main Topic A from Concepts]. '
        yaml_ex_kc_items_l2 = 'Benefit: Provides a clear entry point for users interested in [Main Topic A]."'
        yaml_ex_kc_items_l3 = '  - "Insight: A strong connection exists between [Concept B] and [Concept C]. '
        yaml_ex_kc_items_l4 = 'Benefit: Helps users understand how these ideas build upon each other."'

        yaml_ex_ad_header = "areas_for_improvement_or_clarification:"
        yaml_ex_ad_items_l1 = '  - "Suggestion: The transition between [Concept D] and [Concept E] could be smoother. '
        yaml_ex_ad_items_l2 = 'Consider adding a brief introductory sentence to bridge them."'
        yaml_ex_ad_items_l3 = '  - "Question: Is the target audience for [Concept F] beginners or advanced users? '
        yaml_ex_ad_items_l4 = 'The current explanation might be too [simple/complex]."'

        yaml_ex_op_header = "content_structure_observations:"
        yaml_ex_op_items_l1 = (
            '  - "Observation: The information flows logically from general introductions to more specific details."'
        )
        yaml_ex_op_items_l2 = (
            '  - "Observation: The use of examples in [Concept G source document] is effective for illustration."'
        )

        yaml_ex_os_header = "overall_assessment: |"
        yaml_ex_os_lines_l1 = (
            f"    Overall, the web content for '{collection_name}' appears to be [e.g., well-structured, "
        )
        yaml_ex_os_lines_l2 = "comprehensive on Topic X, somewhat fragmented]."
        yaml_ex_os_lines_l3 = "    A key strength is [e.g., its clear explanation of Concept A]. A potential area for "
        yaml_ex_os_lines_l4 = "enhancement could be [e.g., providing more examples for Concept B]. "
        yaml_ex_os_lines_l5 = "(AI-generated assessment for discussion)."

        output_parts: list[str] = ["```yaml"]
        output_parts.append(yaml_ex_kc_header)
        output_parts.extend([yaml_ex_kc_items_l1 + yaml_ex_kc_items_l2, yaml_ex_kc_items_l3 + yaml_ex_kc_items_l4])
        output_parts.append(yaml_ex_ad_header)
        output_parts.extend([yaml_ex_ad_items_l1 + yaml_ex_ad_items_l2, yaml_ex_ad_items_l3 + yaml_ex_ad_items_l4])
        output_parts.append(yaml_ex_op_header)
        output_parts.extend([yaml_ex_op_items_l1, yaml_ex_op_items_l2])
        output_parts.append(yaml_ex_os_header)
        output_parts.extend(
            [yaml_ex_os_lines_l1 + yaml_ex_os_lines_l2, yaml_ex_os_lines_l3 + yaml_ex_os_lines_l4 + yaml_ex_os_lines_l5]
        )
        output_parts.append("```")
        return "\n".join(output_parts)

    @staticmethod
    def format_generate_web_review_prompt(
        document_collection_name: str,
        concepts_data: WebContentConceptsList,
        relationships_data: WebContentRelationshipsDict,
        inventory_content: Optional[str],
        target_language: str,
    ) -> str:
        """Format the prompt for the LLM to generate a review of web content.

        Args:
            document_collection_name (str): The name of the document collection (e.g., website name).
            concepts_data (WebContentConceptsList): List of identified web concepts.
            relationships_data (WebContentRelationshipsDict): Dictionary of identified relationships.
            inventory_content (Optional[str]): Markdown content of the web inventory (summaries of pages).
            target_language (str): The target language for the review.

        Returns:
            str: A formatted string prompting the LLM for a structured web content review.
        """
        concepts_str: str = WebReviewPrompts._format_concepts_for_review_prompt(concepts_data)
        relationships_str: str = WebReviewPrompts._format_relationships_for_review_prompt(relationships_data)
        inventory_str: str = WebReviewPrompts._format_inventory_for_review_prompt(inventory_content)
        lang_instruction: str = WebReviewPrompts._get_web_review_language_instruction(target_language)
        output_structure_yaml: str = WebReviewPrompts._get_web_review_yaml_example(document_collection_name)

        task_desc_lines_l1 = "Generate a high-level review of the provided web content. Focus on:"
        task_desc_lines_l2 = " - Key insights or takeaways from the content."
        task_desc_lines_l3_part1 = (
            " - Potential areas for improvement, clarification, or further discussion (phrase as suggestions or "
        )
        task_desc_lines_l3_part2 = (  # Line broken for length
            "questions, referencing specific concepts using 'Concept Name (Index X)' format if relevant)."
        )
        task_desc_lines_l4 = " - Observations about the content's structure or presentation."
        task_desc_lines_l5 = "This is an AI-driven initial analysis based on extracted concepts and summaries."
        task_desc_full = "\n".join(
            [
                task_desc_lines_l1,
                task_desc_lines_l2,
                task_desc_lines_l3_part1 + task_desc_lines_l3_part2,
                task_desc_lines_l4,
                task_desc_lines_l5,
            ]
        )

        prompt_lines_l1 = (
            f"You are an AI assistant tasked with providing a review of web content from: '{document_collection_name}'."
        )
        prompt_lines_l2 = (  # Line broken for length
            "Based on the following summarized information (identified concepts, their relationships, "
            "and an inventory of documents), provide a structured review."
        )

        prompt_lines: list[str] = [
            prompt_lines_l1,
            lang_instruction,
            prompt_lines_l2,
            "\n**Provided Contextual Information:**",
            f"1. Identified Core Concepts:\n{concepts_str}",
            f"\n2. Summary of Concept Relationships:\n{relationships_str}",
            f"\n3. Content Inventory (Summaries of Individual Documents):\n{inventory_str}",
            "\n**Your Task:**",
            task_desc_full,
            "The review should be objective, constructive, and high-level.",
            "\n**Output Format:**",
            "Your response MUST be a single YAML dictionary strictly following this structure:",
            output_structure_yaml,
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML.",
        ]
        return "\n".join(filter(None, prompt_lines))


# End of src/sourcelens/prompts/web/review_prompts.py
