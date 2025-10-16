# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Prompts related to translating text content using an LLM.

This module provides a class to format prompts for text translation,
including instructions for specific output formatting like sentence-per-line,
paragraph grouping, and removal of time-block headers. This version assumes
the input text has already undergone a separate advanced deduplication step.
"""

from typing import Final


class TranslationPrompts:
    """Provide methods to format prompts for text translation and reformatting."""

    _TRANSLATION_INSTRUCTION_SIMPLIFIED_PART1: Final[str] = (
        "Your task is to translate the following text from {source_language_name} "
        "to {target_language_name}.\n"
        "The original {source_language_name} text has ALREADY undergone a prior deduplication "
        'step but still contains time block headers (e.g., "#### [MM:SS]").\n\n'
        "**Primary Instructions:**\n"
        "1.  Translate the provided {source_language_name} text into fluent and "
        "accurate {target_language_name}, preserving the original meaning and tone.\n"
        '2.  **Completely remove all time block headers** (e.g., "#### [MM:SS]") '
        "from the translated text. The final output should contain NO time block headers.\n"
        "3.  **Final Text Formatting (for the translated, time-block-free text):**\n"
        "    a.  Identify clear and **complete grammatical sentence boundaries**. "
        "A sentence typically ends with a period (.), question mark (?), or exclamation mark (!).\n"
        "    b.  Each **complete sentence** MUST start on a new line. "
        "Do NOT break sentences across multiple lines unless it's a very long sentence that "
        "would exceed a reasonable line length (though for this task, prefer one sentence per line).\n"
        "    c.  Group related complete sentences (typically 2-5 sentences) into **logical paragraphs**. "
        "A paragraph should represent a coherent thought or sub-topic.\n"
        "    d.  Crucially, separate these paragraphs with a **single empty line "
        "(a blank line)**. This means there should be two newline characters between "
        "the end of the last sentence of one paragraph and the start of the first sentence of the next.\n"
        "    e.  Avoid creating paragraphs with only a fragment of a sentence or starting a new paragraph "
        "in the middle of a sentence. Ensure each line of text is a grammatically complete sentence "
        "or a well-formed list item if applicable.\n"
        '4.  Do NOT add any new headings or list markers (like "-" or "*") unless '
        "they are a natural part of the translated content itself (e.g., "
        "translating an existing list within a sentence).\n"
        "5.  Ensure the final output is clean, with no redundant leading/trailing "
        "whitespace on lines or paragraphs.\n"
        "6.  If, after translation, you notice any very obvious and highly "
        "repetitive short phrases that were not caught by the prior deduplication, "
        "you may cautiously consolidate them, but prioritize accurate translation "
        "of the (already cleaned) source.\n\n"
    )

    _TRANSLATION_OUTPUT_EXAMPLE_SIMPLIFIED_PART2: Final[str] = (
        "**Example of desired final paragraph structure (if target is English):**\n"
        "This is the first complete sentence of the first paragraph. "
        "This is the second complete sentence of the first paragraph, developing the same idea. "
        "This might be the third complete sentence, continuing the same thought and concluding it.\n\n"
        "This is the first complete sentence of a new, second paragraph, because it starts a new, distinct idea. "
        "This is the second complete sentence of this paragraph, adding more detail to the new idea.\n\n"
        "Output ONLY the translated and reformatted text. Do not include any additional "
        "explanations, introductions, or formatting beyond what is requested.\n\n"
        "Original text ({source_language_name}) including time blocks (already partially deduplicated):\n"
        "---\n"
        "{text_to_translate}\n"
        "---\n\n"
        "Final translated and formatted text ({target_language_name}), "
        "without time blocks:\n"
    )

    BASIC_TRANSLATION_PROMPT_TEMPLATE: Final[str] = (
        _TRANSLATION_INSTRUCTION_SIMPLIFIED_PART1 + _TRANSLATION_OUTPUT_EXAMPLE_SIMPLIFIED_PART2
    )

    @staticmethod
    def format_translate_text_prompt(
        text_to_translate: str,
        source_language_name: str,
        target_language_name: str,
    ) -> str:
        """Format a prompt for the LLM to translate and reformat a given text.

        This version assumes the input `text_to_translate` has already undergone
        a primary deduplication step (still containing time blocks). The LLM's main
        tasks are now translation, removal of time blocks, and final formatting,
        with an emphasis on complete sentences per line.

        Args:
            text_to_translate: The text content to be translated. This text
                is expected to have time block headers but should be relatively
                clean of major repetitions.
            source_language_name: The full name of the source language (e.g., "English").
            target_language_name: The full name of the target language (e.g., "Slovak").

        Returns:
            A formatted multi-line string constituting the complete prompt for the LLM.
            Returns an empty string if `text_to_translate` is empty or only whitespace.
        """
        if not text_to_translate.strip():
            return ""

        return TranslationPrompts.BASIC_TRANSLATION_PROMPT_TEMPLATE.format(
            source_language_name=source_language_name,
            target_language_name=target_language_name,
            text_to_translate=text_to_translate,
        )


# End of src/FL02_web_crawling/prompts/translation_prompts.py
