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

MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT: Final[int] = 2000  # Max characters of document to show for summary


class WebInventoryPrompts:
    """Container for prompts related to web content inventory and summarization."""

    @staticmethod
    def format_summarize_web_document_prompt(
        document_path: str,
        document_content_snippet: str,
        target_language: str,
        max_summary_sentences: int = 2,
    ) -> str:
        """Format prompt for LLM to summarize a single web document.

        Args:
            document_path (str): The path/identifier of the web document (e.g., its original URL or filename).
            document_content_snippet (str): A snippet of the document's Markdown content.
            target_language (str): The target language for the summary.
            max_summary_sentences (int): Desired maximum number of sentences for the summary.
                                         Defaults to 2.

        Returns:
            str: A formatted string prompting the LLM for a concise summary.
        """
        lang_instr = ""
        lang_cap = target_language.capitalize()
        if target_language.lower() != "english":
            lang_instr = (
                f"IMPORTANT: Provide the summary exclusively in **{lang_cap}**. "
                f"Do NOT use English unless it's a proper noun or technical term without a common "
                f"{lang_cap} equivalent."
            )

        prompt_lines = [
            "You are an AI assistant tasked with creating a very concise summary for a web document.",
            f"The document is identified as: `{document_path}`.",
            f"\n**Document Content Snippet (first {MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT} characters):**",
            f"```markdown\n{document_content_snippet}\n```",
            "\n**Your Task:**",
            f"Based *only* on the provided content snippet, write a brief summary of what this document "
            f"is about. The summary should be **{max_summary_sentences} sentence(s) long at most**.",
            "Focus on the main topic or purpose of the document.",
            f"{lang_instr}" if lang_instr else "",
            "\n**Output Format:**",
            "Provide ONLY the summary text. No introductory phrases like 'This document is about...' "
            "unless it flows naturally as part of the summary. Just the summary itself.",
            "Example: Discusses advanced CLI configuration options and best practices for performance.",
        ]
        # Filter out empty lines that might result from empty lang_instr
        return "\n".join(filter(None, prompt_lines))


# End of src/sourcelens/prompts/web/inventory_prompts.py
