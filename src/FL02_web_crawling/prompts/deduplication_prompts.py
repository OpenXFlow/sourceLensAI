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

"""Prompts for advanced deduplication of original transcript text while preserving time blocks."""

from typing import Final


class OriginalTranscriptDeduplicationPrompts:
    """Provide methods to format prompts for cleaning and deduplicating original transcript text."""

    DEDUPLICATION_PROMPT_TEMPLATE: Final[str] = (
        "Your task is to meticulously clean and deduplicate the following text, which is a verbatim transcript "
        'likely from speech-to-text conversion. The text contains time block headers (e.g., "#### [MM:SS]").\n\n'
        "**CRITICAL INSTRUCTIONS:**\n"
        "1.  **Preserve Time Blocks:** All time block headers (lines starting with `#### [MM:SS]`) in the "
        "original text MUST be preserved in their exact positions relative to the text segments they precede. "
        "Do NOT remove, alter, merge, or shift these time block headers in any way. The cleaned text segments "
        "should remain associated with their original time block headers.\n"
        "2.  **Language Preservation:** The output text MUST be in the **same language** as the input text. "
        "Do NOT translate the text.\n"
        "3.  **Advanced Deduplication - Primary Goal:**\n"
        "    a.  **Consolidate Cumulative/Partial Repetitions:** Look for sequences where phrases or sentences build upon "  # noqa: E501
        'each other with slight additions (e.g., "Text A.", "Text A and B.", "Text A and B and C."). '
        "Retain only the most complete and final version of such cumulative statements within its time block context. "
        "If a cumulative statement spans across a time block header, treat it as a new context.\n"
        "    b.  **Merge Minor Variations:** Identify and merge phrases or short sentences that are repeated with only "
        "minor inconsequential variations (e.g., different filler words but same core meaning) if they appear "
        "very close to each other. Keep the most coherent and complete version.\n"
        '    c.  **Remove Stutters/False Starts:** If the transcript contains obvious stutters (e.g., "I, I, I mean") '
        "or false starts that were captured, remove them to improve readability, but only if it doesn't alter the "
        "intended meaning or remove a deliberate pause/emphasis.\n"
        "    d.  **Handle Exact Repetitions:** If entire sentences or significant phrases are repeated verbatim "
        "immediately or shortly after one another (within a few lines or within the same logical thought under a "
        "time block), keep only the first clear instance unless the repetition clearly serves an emphatic or "
        "structural purpose (e.g., speaker intentionally repeats for emphasis).\n"
        "4.  **Maintain Original Text Flow:** While deduplicating, strive to maintain the original flow and "
        "segmentation of the text as much as possible, only removing clear redundancies. Do not reorder "
        "sentences or merge distinct ideas unnecessarily.\n"
        "5.  **Line Breaks and Paragraphs:** Preserve the original line break structure of the textual content "
        "segments as much as possible, unless merging lines is essential for deduplication. "
        "The output should retain a similar visual structure to the input regarding where text segments start and end, "
        "relative to their time blocks.\n"
        "6.  **Output Format:** Return ONLY the cleaned and deduplicated text, including all original time block "
        "headers in their correct positions. Do not add any introductory text, explanations, or summaries. "
        "The output should be ready to be parsed as a transcript.\n\n"
        "**Example of Input Text (with time blocks and repetitions):**\n"
        "```text\n"
        "#### [00:01]\n"
        "hello this is\n"
        "hello this is a test\n"
        "hello this is a test of the system\n"
        "#### [00:05]\n"
        "we are checking\n"
        "we are checking the microphone\n"
        "the microphone now\n"
        "#### [00:08]\n"
        "this is another sentence this is another sentence\n"
        "and a final thought\n"
        "```\n\n"
        "**Example of Desired Output Text (cleaned, in the same language, with time blocks preserved):**\n"
        "```text\n"
        "#### [00:01]\n"
        "hello this is a test of the system\n"
        "#### [00:05]\n"
        "we are checking the microphone now\n"
        "#### [00:08]\n"
        "this is another sentence\n"
        "and a final thought\n"
        "```\n\n"
        "Now, please process the following text:\n"
        "---\n"
        "{text_to_clean}\n"
        "---\n"
        "Cleaned text:\n"
    )

    @staticmethod
    def format_deduplicate_transcript_prompt(text_to_clean: str) -> str:
        """Format a prompt for the LLM to clean and deduplicate original transcript text.

        The prompt instructs the LLM to perform advanced deduplication while
        strictly preserving the original time block headers and their positions.
        The language of the text must also be preserved.

        Args:
            text_to_clean: The original transcript text, potentially containing
                time block headers (e.g., "#### [MM:SS]") and various types
                of repetitions.

        Returns:
            A formatted multi-line string constituting the complete prompt for the LLM.
            Returns an empty string if `text_to_clean` is empty or only whitespace.
        """
        if not text_to_clean.strip():
            return ""

        return OriginalTranscriptDeduplicationPrompts.DEDUPLICATION_PROMPT_TEMPLATE.format(text_to_clean=text_to_clean)


# End of src/FL02_web_crawling/prompts/deduplication_prompts.py
