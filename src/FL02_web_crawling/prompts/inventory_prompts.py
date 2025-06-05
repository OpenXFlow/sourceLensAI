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

"""Prompts related to generating an inventory or summary of web documents."""

from typing import Final

MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT: Final[int] = 1500
"""Maximum character length for the document chunk snippet provided to the LLM for summarization."""


class WebInventoryPrompts:
    """Container for prompts related to web content inventory and summarization."""

    @staticmethod
    def format_summarize_web_document_prompt(
        document_path: str,
        document_content_snippet: str,
        target_language: str,
        max_summary_sentences: int = 2,
    ) -> str:
        """Format prompt for LLM to summarize a single web document or chunk.

        Args:
            document_path (str): The path/identifier of the web document or chunk.
            document_content_snippet (str): A snippet of the document's/chunk's content.
            target_language (str): The target language for the summary.
            max_summary_sentences (int): Desired maximum number of sentences for the summary.

        Returns:
            str: A formatted string prompting the LLM for a concise summary.
        """
        lang_instr: str = ""
        lang_cap: str = target_language.capitalize()
        if target_language.lower() != "english":
            lang_instr_part1: str = f"IMPORTANT: You MUST provide the summary exclusively in **{lang_cap}**. "
            lang_instr_part2: str = (
                f"All explanatory text in the summary must be in {lang_cap}. "
                f"Do NOT use English unless it's a proper noun or a technical term that does not have "
                f"a common {lang_cap} equivalent (e.g., 'API', 'URL')."
            )
            lang_instr = lang_instr_part1 + lang_instr_part2
        else:
            # Even for English, explicitly state it to avoid ambiguity if model defaults to something else.
            lang_instr = "IMPORTANT: Provide the summary in **English**."

        prompt_lines: list[str] = [
            "You are an AI assistant tasked with creating a very concise summary for a web document/content chunk.",
            f"The document/chunk is identified as: `{document_path}`.",
            f"\n**Document/Chunk Content Snippet (up to {MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT} characters):**",
            f"```text\n{document_content_snippet}\n```",
            "\n**Your Task:**",
            f"Based *only* on the provided content snippet, write a brief summary of what this document/chunk "
            f"is about. The summary should be **{max_summary_sentences} sentence(s) long at most**.",
            "Focus on the main topic or purpose of the content. "
            "The summary should be a self-contained piece of text accurately reflecting the snippet.",
            lang_instr,  # Language instruction is now more prominent and always present
            "\n**Output Format:**",
            "Provide ONLY the summary text. Do NOT include introductory phrases like 'This document is about...' "
            "or 'The summary is...' unless it flows naturally as part of the summary itself. Just the summary.",
            "Example (if target language is English): Discusses advanced CLI configuration options and best practices for performance.",  # noqa: E501
            "Example (if target language is Slovak): Popisuje pokročilé možnosti konfigurácie CLI a osvedčené postupy pre výkon.",  # noqa: E501
        ]
        return "\n".join(filter(None, prompt_lines))


# End of src/FL02_web_crawling/prompts/inventory_prompts.py
