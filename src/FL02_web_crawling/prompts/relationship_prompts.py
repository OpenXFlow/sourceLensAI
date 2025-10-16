# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Prompts related to analyzing relationships between identified web content concepts."""

from typing import Final

MAX_RELATIONSHIP_LABEL_LEN: Final[int] = 70  # Zvýšené z 50 na 70 pre viac flexibility


class WebRelationshipPrompts:
    """Container for prompts related to analyzing web content relationships."""

    @staticmethod
    def format_analyze_web_relationships_prompt(
        document_collection_name: str,
        concepts_listing_with_summaries: str,
        num_concepts: int,
        target_language: str,
        max_relationships: int = 10,
    ) -> str:
        """Format prompt for LLM to analyze relationships between web concepts.

        This prompt guides the LLM to identify how different concepts, previously
        extracted from web content, interrelate or follow a logical sequence.
        The output is expected in YAML format, containing an overall summary
        and a list of specific relationships.

        Args:
            document_collection_name: Name of the website or document collection
                                      (e.g., "Crawl4AI Documentation").
            concepts_listing_with_summaries: A string listing the identified web concepts,
                                             formatted typically as "Index. Name - Summary".
                                             This provides context for relationship analysis.
            num_concepts: The total number of concepts identified, used for validating
                          the indices in the LLM's response.
            target_language: The target language for the `overall_summary` and
                             relationship `label` fields in the output.
            max_relationships: A suggestion to the LLM for the maximum number of
                               key relationships to detail. Defaults to 10.

        Returns:
            A formatted multi-line string constituting the complete prompt for the LLM.
        """
        lang_instr_suffix = ""
        lang_cap = target_language.capitalize()
        if target_language.lower() != "english":
            lang_instr_suffix_part1 = (
                f" IMPORTANT: Generate `overall_summary` and relationship `label` fields exclusively "
                f"in **{lang_cap}**. Do NOT use English for these fields, unless "
                f"it's a proper noun or technical term without a common {lang_cap} equivalent."
            )
            lang_instr_suffix = lang_instr_suffix_part1

        max_index = max(0, num_concepts - 1)
        relationship_count_instr = (
            f"Identify and describe up to {max_relationships} key relationships "
            f"that illustrate how these concepts connect or build upon each other."
        )

        summary_instr = (
            f"`overall_summary`: Provide a high-level overview (2-4 sentences) explaining the main "
            f"narrative or logical flow connecting the core concepts. Focus on how they collectively "
            f"contribute to the overall message of '{document_collection_name}'.{lang_instr_suffix}"
        )
        rel_list_header = "`relationships`: A list detailing key connections:"
        from_instr = f"  - `from_concept_index`: Integer index (0 to {max_index}) of the source/preceding concept."
        to_instr = f"  - `to_concept_index`: Integer index (0 to {max_index}) of the target/subsequent concept."
        label_instr_l1 = (
            f"  - `label`: Brief, descriptive verb phrase or connection type{lang_instr_suffix} for the interaction "
        )
        label_instr_l2 = (
            f"(e.g., 'Explains prerequisites for', 'Is a sub-topic of', 'Contrasts with'). "
            f"Max {MAX_RELATIONSHIP_LABEL_LEN} chars."
        )
        label_instr = label_instr_l1 + label_instr_l2
        focus_note = (
            "    Focus on the most important, direct relationships that help understand the document's structure "
            "or argument flow."
        )

        yaml_ex_summary_l1 = (
            "overall_summary: |\n"
            "  The documentation first introduces core [Concept A Name (Index 0)], then elaborates on its practical\n"
            "  application in [Concept B Name (Index 2)], and finally discusses advanced configurations\n"
            f"  in [Concept C Name (Index 1)].{lang_instr_suffix if lang_instr_suffix else ''}"
        )
        yaml_ex_rels_header = "relationships:"
        yaml_ex_rel_1_from = "  - from_concept_index: 0"
        yaml_ex_rel_1_to = "    to_concept_index: 2"
        yaml_ex_rel_1_label = f'    label: "Provides foundation for"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_rel_2_from = "  - from_concept_index: 2"
        yaml_ex_rel_2_to = "    to_concept_index: 1"
        yaml_ex_rel_2_label = f'    label: "Leads to advanced topic"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_rels_footer = f"  # ... up to {max_relationships} key relationships ..."

        yaml_parts = [
            "```yaml",
            yaml_ex_summary_l1,
            yaml_ex_rels_header,
            yaml_ex_rel_1_from,
            yaml_ex_rel_1_to,
            yaml_ex_rel_1_label,
            yaml_ex_rel_2_from,
            yaml_ex_rel_2_to,
            yaml_ex_rel_2_label,
            yaml_ex_rels_footer,
            "```",
        ]
        yaml_example_structure = "\n".join(yaml_parts)

        prompt_lines = [
            f"You are an AI assistant analyzing the conceptual structure of content from '{document_collection_name}'.",
            "Based on the provided list of identified concepts and their summaries, describe how they relate to each other.",  # noqa: E501
            f"\n**Identified Concepts (Index. Name - Summary):**\n{concepts_listing_with_summaries}",
            f"\n{relationship_count_instr} {lang_instr_suffix}",
            "\n**Instructions for Output:**",
            "Provide your analysis as a YAML dictionary with two main keys:",
            f"1. {summary_instr}",
            f"2. {rel_list_header}",
            "   Each item in the 'relationships' list must be a dictionary with these keys:",
            f"   {from_instr}",
            f"   {to_instr}",
            f"   {label_instr}",
            f"   {focus_note}",
            "\n**Output Format:**",
            "Format your response STRICTLY as a YAML dictionary enclosed in a single ```yaml code block.",
            "\n**Example YAML Output:**",
            yaml_example_structure,
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML block.",
        ]
        return "\n".join(prompt_lines)


# End of src/FL02_web_crawling/prompts/relationship_prompts.py
