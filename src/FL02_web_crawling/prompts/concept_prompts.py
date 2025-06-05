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

"""Prompts related to identifying core concepts from web content."""

from typing import Final

# Constants for prompt formatting, defined at the module level.
# Using previously agreed-upon values for testing.
MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS: Final[int] = 5
"""Maximum number of document chunk snippets to include in the detailed context for the LLM.
If more chunks exist, a summary notice will be added.
"""

MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS: Final[int] = 400
"""Maximum character length for each individual document chunk snippet included in the prompt.
Longer chunks will be truncated.
"""

DEFAULT_MAX_CONCEPTS_TO_IDENTIFY: Final[int] = 12
"""Default desired maximum number of specific concepts the LLM should try to identify.
This helps guide the LLM towards a reasonable level of granularity.
"""


class WebConceptPrompts:
    """Container for prompts related to identifying web content concepts."""

    @staticmethod
    def format_identify_web_concepts_prompt(
        document_collection_name: str,
        content_context: str,
        document_listing: str,
        target_language: str,
        max_concepts: int = DEFAULT_MAX_CONCEPTS_TO_IDENTIFY,
    ) -> str:
        """Format prompt for LLM to identify key concepts from web content chunks.

        This prompt instructs the LLM to analyze provided text snippets from web document
        chunks and extract core, granular, and "actionable" concepts. These concepts
        should be suitable for forming the basis of tutorial chapters or summary sections.
        The LLM is guided to link each concept back to its source chunk(s).

        Args:
            document_collection_name (str): Name of the website or document collection.
            content_context (str): Concatenated snippets of content from document chunks.
            document_listing (str): Listing of all available chunk IDs and their titles.
            target_language (str): The desired language for the 'name' and 'summary'.
            max_concepts (int): Desired maximum number of concepts to identify.

        Returns:
            str: A formatted multi-line string for the LLM prompt.
        """
        lang_instr_suffix: str = ""
        lang_cap: str = target_language.capitalize()
        if target_language.lower() != "english":
            lang_instr_suffix_part1: str = (
                f" IMPORTANT: Generate `name` and `summary` fields exclusively in **{lang_cap}**."
            )
            lang_instr_suffix_part2: str = (
                f" Do NOT use English for these fields, unless it's a proper noun or technical term "
                f"without a common {lang_cap} equivalent (e.g., 'API', 'JSON')."
            )
            lang_instr_suffix = lang_instr_suffix_part1 + lang_instr_suffix_part2

        name_field_desc_l1: str = (
            "`name`: A short, specific, and descriptive name for the concept/topic found in the chunks. "
            "This name should be suitable as a potential chapter title. "
        )
        name_field_desc: str = name_field_desc_l1 + lang_instr_suffix.strip()

        summary_field_desc_l1: str = (
            "`summary`: A clear explanation (2-4 sentences) of the specific concept/topic and its "
            "significance or key takeaway, as evident from the provided document chunk snippets. "
            "Focus on what makes this concept distinct and useful. "
        )
        summary_field_desc: str = summary_field_desc_l1 + lang_instr_suffix.strip()

        source_docs_desc_l1: str = (
            "`source_chunk_ids`: A list of `chunk_id` strings (from the 'Available Document Chunks' list below) "
            "where this specific concept/topic is most prominently discussed, defined, or exemplified. "
        )
        source_docs_desc_l2: str = (
            "List only the 1-3 most relevant chunk_ids that form the core basis for this concept. "
            "Ensure these IDs exactly match those in the 'Available Document Chunks' list."
        )
        source_docs_desc: str = source_docs_desc_l1 + source_docs_desc_l2

        yaml_ex_name_a: str = '- name: "Specific Feature X Configuration"'
        yaml_ex_summary_a_l1: str = (
            '  summary: "Describes how to configure Feature X using parameters Y and Z, '
            'focusing on its impact on performance and common use-cases. Configuration involves editing the primary_config.xml file."'  # noqa: E501
        )
        yaml_ex_src_docs_a_l1: str = '  source_chunk_ids:\n    - "original_doc_name_section_config_feature_x"'
        yaml_ex_src_docs_a_l2: str = '\n    - "original_doc_name_advanced_performance_tuning_intro"'

        yaml_ex_name_b: str = '- name: "Basic Usage of Command YYY"'
        yaml_ex_summary_b: str = (
            '  summary: "Explains the fundamental syntax and common options for command YYY, including how to list '
            'available items and filter results. Essential for initial interaction with the tool via CLI."'
        )
        yaml_ex_src_docs_b: str = '  source_chunk_ids:\n    - "original_doc_name_cli_reference_command_yyy_overview"'
        yaml_ex_footer: str = f"# ... up to {max_concepts} specific, actionable concepts ..."

        if lang_instr_suffix:
            yaml_ex_name_a += lang_instr_suffix
            yaml_ex_summary_a_l1 += lang_instr_suffix
            yaml_ex_name_b += lang_instr_suffix
            yaml_ex_summary_b += lang_instr_suffix

        yaml_example_structure: str = (
            f"```yaml\n{yaml_ex_name_a}\n{yaml_ex_summary_a_l1}\n"
            f"{yaml_ex_src_docs_a_l1}{yaml_ex_src_docs_a_l2}\n"
            f"{yaml_ex_name_b}\n{yaml_ex_summary_b}\n{yaml_ex_src_docs_b}\n{yaml_ex_footer}\n```"
        )

        prompt_task_line1: str = (
            f"You are an AI assistant tasked with analyzing a collection of segmented text chunks "
            f"from '{document_collection_name}' to identify its core, granular, and actionable concepts/topics."
        )
        prompt_task_line2_l1: str = (
            f"Your goal is to extract up to {max_concepts} specific themes or key informational units that are "
            "detailed enough to form the basis of a useful tutorial chapter or a distinct section in a summary. "
        )
        prompt_task_line2_l2: str = (
            "Each concept should be self-contained and focus on a specific piece of functionality, "
            "a particular sub-topic, or a key aspect of the overall content. "
            "Prioritize concepts that are concrete and provide practical value to a reader. "
        )
        prompt_task_line2: str = prompt_task_line2_l1 + prompt_task_line2_l2 + lang_instr_suffix

        prompt_lines: list[str] = [
            prompt_task_line1,
            prompt_task_line2,
            f"\n**Provided Document Chunk Snippets (Context - up to {MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS} snippets, "
            f"each up to {MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS} chars):**\n"
            f"```text\n{content_context}\n```",
            f"\n**Available Document Chunks (for `source_chunk_ids` field, use these exact IDs and titles for context):**\n{document_listing}",  # noqa: E501
            "\n**Instructions:**",
            "1.  Identify fine-grained, specific, and actionable concepts. Avoid overly broad or vague topics.",
            "2.  Each concept should be substantial enough to potentially be a standalone chapter or a significant, "
            "well-defined section.",
            "3.  Ensure each concept is primarily derived from the content of 1 to 3 closely related source chunks. "
            "The `summary` should reflect the information within these specific `source_chunk_ids`.",
            "4.  For each identified core concept/topic, provide a YAML dictionary with these keys:",
            f"    - {name_field_desc}",
            f"    - {summary_field_desc}",
            f"    - {source_docs_desc}",
            "\n**Output Format:**",
            "Format your response STRICTLY as a YAML list of these dictionaries, enclosed in a single "
            "```yaml code block.",
            "Each dictionary in the list represents one identified specific concept/topic.",
            "\n**Example YAML Output:**",
            yaml_example_structure,
            "\nProvide ONLY the YAML output block. No introductory text, explanations, or concluding remarks outside the YAML block.",  # noqa: E501
        ]
        return "\n".join(prompt_lines)


# End of src/FL02_web_crawling/prompts/concept_prompts.py
