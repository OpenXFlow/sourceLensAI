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

# Type Aliases to match node data structures

# Constants for prompt formatting, can be shared or moved to a common web prompts module
MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS: Final[int] = 15
MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS: Final[int] = 700


class WebConceptPrompts:
    """Container for prompts related to identifying web content concepts."""

    @staticmethod
    def format_identify_web_concepts_prompt(
        document_collection_name: str,
        content_context: str,  # Teraz by mal obsahovať zreťazené chunky
        document_listing: str,  # Teraz by mal obsahovať zoznam chunk_id
        target_language: str,
        max_concepts: int = 10,
    ) -> str:
        """Format prompt for LLM to identify key concepts from web content chunks.

        Args:
            document_collection_name: Name of the website or document collection.
            content_context: Concatenated content of web document chunks.
            document_listing: Listing of chunk_ids for reference.
            target_language: Target language for names and summaries.
            max_concepts: Desired maximum number of concepts.

        Returns:
            A formatted string prompting the LLM for concepts in YAML.
        """
        lang_instr_suffix = ""
        lang_cap = target_language.capitalize()
        if target_language.lower() != "english":
            lang_instr_suffix_part1 = f" IMPORTANT: Generate `name` and `summary` fields exclusively in **{lang_cap}**."
            lang_instr_suffix_part2 = (
                f" Do NOT use English for these fields, unless "
                f"it's a proper noun or technical term without a common {lang_cap} equivalent."
            )
            lang_instr_suffix = lang_instr_suffix_part1 + lang_instr_suffix_part2

        name_field_desc = f"`name`: A short, specific, and descriptive name for the concept/topic found in the chunks.{lang_instr_suffix}"  # noqa: E501
        summary_field_desc_l1 = "`summary`: A clear explanation (2-4 sentences) of the specific concept/topic and its "
        summary_field_desc_l2 = f"significance within the context of the provided document chunks.{lang_instr_suffix}"
        summary_field_desc = summary_field_desc_l1 + summary_field_desc_l2
        source_docs_desc_l1 = (
            "`source_chunk_ids`: A list of `chunk_id` strings (from the 'Available Document Chunks' list below) "
        )
        source_docs_desc_l2 = (
            "where this specific concept/topic is most prominently discussed or defined. "
            "List only the most relevant chunk_ids. Each concept should ideally map to only 1-3 core chunks."
        )
        source_docs_desc = source_docs_desc_l1 + source_docs_desc_l2

        yaml_ex_name_a = f'- name: "Specific Feature X Configuration"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_summary_a_l1 = (
            '  summary: "Describes how to configure Feature X using parameters Y and Z, focusing on its impact '
        )
        yaml_ex_summary_a_l2 = f'on performance.{lang_instr_suffix if lang_instr_suffix else ""}"'
        yaml_ex_summary_a = yaml_ex_summary_a_l1 + "\n             " + yaml_ex_summary_a_l2
        # E501 fix: Rozdelenie dlhého reťazca
        yaml_ex_src_docs_a_l1 = '  source_chunk_ids:\n    - "original_doc_name_section_config_feature_x"'
        yaml_ex_src_docs_a_l2 = '\n    - "original_doc_name_advanced_performance_tuning"'
        yaml_ex_src_docs_a = yaml_ex_src_docs_a_l1 + yaml_ex_src_docs_a_l2

        yaml_ex_name_b = f'- name: "Basic Usage of Command YYY"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_summary_b = f'  summary: "Explains the fundamental syntax and common options for command YYY.{lang_instr_suffix if lang_instr_suffix else ""}"'  # noqa: E501
        yaml_ex_src_docs_b = '  source_chunk_ids:\n    - "original_doc_name_cli_reference_command_yyy"'
        yaml_ex_footer = f"# ... up to {max_concepts} specific concepts ..."

        yaml_example_structure = (
            f"```yaml\n{yaml_ex_name_a}\n{yaml_ex_summary_a}\n{yaml_ex_src_docs_a}\n"
            f"{yaml_ex_name_b}\n{yaml_ex_summary_b}\n{yaml_ex_src_docs_b}\n{yaml_ex_footer}\n```"
        )

        prompt_task_line1 = (
            f"You are an AI assistant tasked with analyzing a collection of segmented text chunks "
            f"from '{document_collection_name}' to identify its core, granular concepts/topics."
        )
        prompt_task_line2 = (
            f"Your goal is to extract up to {max_concepts} specific themes or key informational units. "
            f"Each concept should be detailed and actionable, not overly broad.{lang_instr_suffix}"
        )

        prompt_lines = [
            prompt_task_line1,
            prompt_task_line2,
            f"\n**Provided Document Chunk Snippets (Context):**\n```text\n{content_context}\n```",
            # E501 fix: Rozdelenie dlhého reťazca
            f"\n**Available Document Chunks (for `source_chunk_ids` field, use these exact IDs):**\n{document_listing}",
            "\n**Instructions:**",
            "Identify fine-grained, specific concepts. Avoid very general topics.",
            "For each identified core concept/topic, provide a YAML dictionary with these keys:",
            f"1. {name_field_desc}",
            f"2. {summary_field_desc}",
            f"3. {source_docs_desc}",
            "\n**Output Format:**",
            "Format your response STRICTLY as a YAML list of these dictionaries, enclosed in a single "
            "```yaml code block.",
            "Each dictionary represents one identified specific concept/topic.",
            "\n**Example YAML Output:**",
            yaml_example_structure,
            "\nProvide ONLY the YAML output block. No introductory text, explanations, or concluding remarks.",
        ]
        return "\n".join(prompt_lines)


# End of src/FL02_web_crawling/prompts/concept_prompts.py
