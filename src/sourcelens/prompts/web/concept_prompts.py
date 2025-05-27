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

from typing import Any, Final  # Removed List and Dict

from typing_extensions import TypeAlias

# Type Aliases to match node data structures
# Using built-in dict and list for modern Python (PEP 585)
WebContentConceptItem: TypeAlias = dict[str, Any]
WebContentConceptsList: TypeAlias = list[WebContentConceptItem]

# Constants for prompt formatting, can be shared or moved to a common web prompts module
MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS: Final[int] = 10
MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS: Final[int] = 1000


class WebConceptPrompts:
    """Container for prompts related to identifying web content concepts."""

    @staticmethod
    def format_identify_web_concepts_prompt(
        document_collection_name: str,
        content_context: str,
        document_listing: str,
        target_language: str,
        max_concepts: int = 7,
    ) -> str:
        """Format prompt for LLM to identify key concepts from web content.

        Args:
            document_collection_name (str): Name of the website or document collection.
            content_context (str): Concatenated/summarized content of web documents.
            document_listing (str): Listing of documents for reference.
            target_language (str): Target language for names and summaries.
            max_concepts (int): Desired maximum number of concepts. Defaults to 7.

        Returns:
            str: A formatted string prompting the LLM for concepts in YAML.
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

        name_field_desc = f"`name`: A short, descriptive name for the concept/topic.{lang_instr_suffix}"
        summary_field_desc_l1 = (
            "`summary`: A clear explanation (2-4 sentences) of the concept/topic and its significance "
        )
        summary_field_desc_l2 = f"within the context of the provided documents.{lang_instr_suffix}"
        summary_field_desc = summary_field_desc_l1 + summary_field_desc_l2
        source_docs_desc_l1 = (
            "`source_documents`: A list of document paths/titles (from the 'Available Documents' list above) "
        )
        source_docs_desc_l2 = (
            "where this concept/topic is most prominently discussed or introduced. "
            "List only the most relevant documents."
        )
        source_docs_desc = source_docs_desc_l1 + source_docs_desc_l2

        yaml_ex_name_a = f'- name: "Key Concept/Topic A Name"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_summary_a_l1 = (
            '  summary: "A concise 2-4 sentence summary of what this concept is about, its importance, '
        )
        yaml_ex_summary_a_l2 = (
            f'or its main idea within the provided documents.{lang_instr_suffix if lang_instr_suffix else ""}"'
        )
        yaml_ex_summary_a = yaml_ex_summary_a_l1 + "\n             " + yaml_ex_summary_a_l2
        yaml_ex_src_docs_a = '  source_documents:\n    - "doc_path_or_title_1.md"\n    - "another_doc_path_or_title.md"'
        yaml_ex_name_b = f'- name: "Key Concept/Topic B Name"{lang_instr_suffix if lang_instr_suffix else ""}'
        yaml_ex_summary_b = f'  summary: "Summary for Concept B.{lang_instr_suffix if lang_instr_suffix else ""}"'
        yaml_ex_src_docs_b = '  source_documents:\n    - "doc_path_or_title_3.md"'
        yaml_ex_footer = f"# ... up to {max_concepts} concepts ..."

        yaml_example_structure = (
            f"```yaml\n{yaml_ex_name_a}\n{yaml_ex_summary_a}\n{yaml_ex_src_docs_a}\n"
            f"{yaml_ex_name_b}\n{yaml_ex_summary_b}\n{yaml_ex_src_docs_b}\n{yaml_ex_footer}\n```"
        )

        prompt_lines = [
            f"You are an AI assistant tasked with analyzing a collection of text documents "
            f"from '{document_collection_name}' to identify its core concepts/topics.",
            f"Your goal is to extract up to {max_concepts} main themes or key informational units that a "
            f"reader should understand after reviewing these documents.{lang_instr_suffix}",
            f"\n**Provided Document Content Snippets (Context):**\n```text\n{content_context}\n```",
            f"\n**Available Documents for Reference (for `source_documents` field):**\n{document_listing}",
            "\n**Instructions:**",
            "For each identified core concept/topic, provide a YAML dictionary with these keys:",
            f"1. {name_field_desc}",
            f"2. {summary_field_desc}",
            f"3. {source_docs_desc}",
            "\n**Output Format:**",
            "Format your response STRICTLY as a YAML list of these dictionaries, enclosed in a single "
            "```yaml code block.",
            "Each dictionary represents one identified concept/topic.",
            "\n**Example YAML Output:**",
            yaml_example_structure,
            "\nProvide ONLY the YAML output block. No introductory text, explanations, or concluding remarks.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/web/concept_prompts.py
