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

"""Prompts for generating an AI-powered project review."""

from typing import Any, Final

from sourcelens.core.common_types import (
    CodeAbstractionsList,
    CodeRelationshipsDict,
    FilePathContentList,
)

_MAX_ABSTRACTION_DESC_SNIPPET_LEN: Final[int] = 120
_MAX_FILES_FOR_STRUCTURE_PROMPT: Final[int] = 15

PROJECT_REVIEW_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "key_characteristics": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Key insights or takeaways about the project's architecture or design.",
        },
        "areas_for_discussion": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Suggestions for improving or clarifying aspects of the project.",
        },
        "observed_patterns": {
            "type": "array",
            "items": {"type": "string"},
            "description": "Observations about design patterns or structural features.",
        },
        "coding_practice_observations": {
            "type": "array",
            "items": {"type": "string"},
            "description": (
                "Optional: High-level observations on architectural coding practices or potential structural 'smells'."
            ),
        },
        "overall_summary": {
            "type": "string",
            "minLength": 1,
            "description": "Overall AI-generated summary of the project's structure and approach.",
        },
        "overall_rating_score": {
            "type": "integer",
            "minimum": 1,
            "maximum": 100,
            "description": "Numerical rating from 1 to 100 based on the provided scale.",
        },
        "rating_level_name": {
            "type": "string",
            "minLength": 1,
            "description": "The name of the rating level corresponding to the score.",
        },
        "rating_justification": {
            "type": "string",
            "minLength": 1,
            "description": "Brief justification for the assigned rating, referencing specific observations.",
        },
    },
    "required": [
        "key_characteristics",
        "areas_for_discussion",
        "observed_patterns",
        "overall_summary",
        "overall_rating_score",
        "rating_level_name",
        "rating_justification",
    ],
    "additionalProperties": False,
}


class ProjectReviewPrompts:
    """Container for prompts related to generating a project review."""

    PROJECT_REVIEW_SCHEMA: Final[dict[str, Any]] = PROJECT_REVIEW_SCHEMA

    _RATING_SCALE_TEXT: Final[str] = (
        "**Rating Scale (1-100) for Project Assessment:**\n"
        "*   **1-10: Basic Concept** - Idea only, minimal/no implementation, major fundamental issues.\n"
        "*   **11-20: Early Prototype** - Functional core exists but with many bugs and unfinished parts, "
        "weak architecture.\n"
        "*   **21-30: Functional Prototype** - Basic functionality works but needs significant usability, robustness, "
        "and architectural improvements.\n"
        "*   **31-40: Promising Start** - Good core idea and partial implementation, but with visible gaps in "
        "architecture or functionality.\n"
        "*   **41-50: Developed Project** - Most key functionality implemented, architecture partially thought out, "
        "but still areas for significant improvement. Usable with reservations.\n"
        "*   **51-60: Solid Foundation** - Good architecture and implementation of key parts, tool is usable "
        "but needs refinement, more testing, and potential expansion.\n"
        "*   **61-70: Good Tool** - Most aspects well-handled, tool is reliable for its main purpose, "
        "architecture is sound. Minor room for improvement.\n"
        "*   **71-80: Very Good Tool** - Robust, well-designed, with thoughtful architecture and broad "
        "functionality. Minor shortcomings or room for advanced features.\n"
        "*   **81-90: Excellent Tool** - Nearly flawless, highly innovative, with excellent architecture, "
        "implementation, and usability. A leader in its field.\n"
        "*   **91-100: State-of-the-Art / Industry Standard** - Defines standards, no apparent weaknesses, "
        "extremely high value and impact."
    )

    @staticmethod
    def _format_abstractions_for_prompt(abstractions: CodeAbstractionsList) -> str:
        """Format the list of abstractions for inclusion in a prompt.

        Args:
            abstractions: A list of dictionaries, where each dictionary represents
                          an identified code abstraction with keys like 'name',
                          'description', and 'files' (list of file indices).

        Returns:
            A string formatted for embedding in a larger LLM prompt, summarizing
            the identified abstractions.
        """
        if not abstractions:
            return "No core abstractions were identified for detailed review."
        header = "Identified Core Abstractions (Index. Name - Files Associated - Description Snippet):"
        parts: list[str] = [header]
        for i, abstr in enumerate(abstractions):
            name: str = str(abstr.get("name", f"Unnamed Abstraction {i}"))
            description: str = str(abstr.get("description", "N/A"))
            files_associated_any: Any = abstr.get("files", [])
            files_associated: list[int] = files_associated_any if isinstance(files_associated_any, list) else []
            valid_file_indices = [idx for idx in files_associated if isinstance(idx, int)]
            num_files = len(valid_file_indices)

            desc_snippet: str = description[:_MAX_ABSTRACTION_DESC_SNIPPET_LEN]
            if len(description) > _MAX_ABSTRACTION_DESC_SNIPPET_LEN:
                desc_snippet += "..."

            file_info = (
                f" (Associated with {num_files} file(s))" if num_files > 0 else " (Not linked to specific files)"
            )
            parts.append(f"  - {i}. {name}{file_info}: {desc_snippet}")
        return "\n".join(parts)

    @staticmethod
    def _format_relationships_for_prompt(
        relationships: CodeRelationshipsDict, abstractions: CodeAbstractionsList
    ) -> str:
        """Format relationships for inclusion in a prompt.

        Args:
            relationships: A dictionary containing a 'summary' of relationships
                           and a 'details' list of specific interactions.
            abstractions: The list of identified abstractions, used for looking up
                          names based on indices in relationship details.

        Returns:
            A string formatted for embedding in a larger LLM prompt, summarizing
            the relationships between abstractions.
        """
        summary: str = str(relationships.get("overall_summary", "No overall relationship summary provided."))
        details_any: Any = relationships.get("details", [])
        details: list[dict[str, Any]] = details_any if isinstance(details_any, list) else []

        rel_summary_header = "Relationship Summary (AI's interpretation):"
        key_interactions_header = "Key Interactions Identified:"
        parts: list[str] = [f"{rel_summary_header}\n{summary}\n\n{key_interactions_header}"]

        if not details:
            parts.append("  No specific key interactions were detailed by the AI.")
            return "\n".join(parts)

        for rel in details:
            from_idx_any: Any = rel.get("from")
            to_idx_any: Any = rel.get("to")
            label: str = str(rel.get("label", "interacts with"))

            if isinstance(from_idx_any, int) and isinstance(to_idx_any, int):
                from_idx: int = from_idx_any
                to_idx: int = to_idx_any
                from_name: str = f"Abstraction {from_idx}"
                to_name: str = f"Abstraction {to_idx}"
                try:
                    if 0 <= from_idx < len(abstractions):
                        from_name = str(abstractions[from_idx].get("name", from_name))
                    if 0 <= to_idx < len(abstractions):
                        to_name = str(abstractions[to_idx].get("name", to_name))
                    parts.append(f"  - '{from_name}' (Index {from_idx}) --[{label}]--> '{to_name}' (Index {to_idx})")
                except IndexError:
                    err_msg_part1 = f"  - Abstraction Index {from_idx} --[{label}]--> Abstraction Index {to_idx}"
                    err_msg_part2 = " (Name lookup failed due to index out of bounds)"
                    parts.append(err_msg_part1 + err_msg_part2)
            else:
                parts.append(f"  - Malformed relationship data: from_idx='{from_idx_any}', to_idx='{to_idx_any}'")
        return "\n".join(parts)

    @staticmethod
    def _format_file_structure_for_prompt(files_data: FilePathContentList) -> str:
        """Format a summary of the file structure for inclusion in a prompt.

        Args:
            files_data: A list of (filepath, content) tuples. Only filepaths are used.

        Returns:
            A string summarizing the project's file structure, truncated if too long.
        """
        if not files_data:
            return "File structure overview: Not available (no files data provided)."
        paths: list[str] = sorted([path for path, _ in files_data])
        display_paths: list[str]
        num_total_paths = len(paths)
        header = "Project File Structure Overview (Partial List):"
        if num_total_paths > _MAX_FILES_FOR_STRUCTURE_PROMPT:
            num_omitted = num_total_paths - _MAX_FILES_FOR_STRUCTURE_PROMPT
            display_paths = paths[:_MAX_FILES_FOR_STRUCTURE_PROMPT] + [f"... (and {num_omitted} more files)"]
        else:
            display_paths = paths
        return header + "\n" + "\n".join([f"  - {p}" for p in display_paths])

    @staticmethod
    def _get_language_instruction(language: str) -> str:
        """Prepare language specific instruction for the project review prompt.

        Args:
            language: The target language for the review.

        Returns:
            A string containing language-specific instructions for the LLM.
        """
        instruction_parts: list[str] = []
        if language.lower() != "english":
            lang_cap = language.capitalize()
            instruction_parts.append(
                f"IMPORTANT: You MUST generate all textual content for this review (summaries, characteristics, "
                f"insights, justifications, etc.) exclusively in **{lang_cap}**,"
            )
            instruction_parts.append("unless quoting specific English technical terms or code identifiers.\n")
        else:
            instruction_parts.append("IMPORTANT: Generate all textual content for this review in **English**.\n")
        return "".join(instruction_parts)

    @staticmethod
    def _get_yaml_example_structure(project_name: str, target_language: str) -> str:
        """Return the YAML example structure string for the project review prompt.

        Args:
            project_name: The name of the document collection.
            target_language: The target language for localization of examples.

        Returns:
            A string representing the YAML example structure.
        """
        ex_insight1_en: str = (
            "Characteristic: Modular Design. Example: `Configuration Management` (Index 0) in `config.py` "
            "clearly separates settings. Benefit: This enhances maintainability for this data processing project, "
            "as settings can be altered without deep code changes."
        )
        ex_suggestion1_en: str = (
            "Discussion Point: Orchestration by `Main Application Logic` (Index Z). Question: As features "
            "expand, could its direct control over `Data Handling` (Index X) and `Item Processing` (Index Y) "
            "lead to high coupling, impacting `Logging` (Index V) and `Configuration Management` (Index U) as well?"
        )
        ex_observation1_en: str = (
            "Pattern: Pipeline Architecture. Evident where `Main Application Logic` (Index Z) orchestrates "
            "Load -> Process -> Save. Advantage: Simplifies understanding data flow. Consideration: Can become "
            "rigid if stages (`Data Handling` (Index X), `Item Processing` (Index Y)) are too interdependent."
        )
        ex_assessment_en_l1: str = (
            f"    Overall, the project (`{project_name}`) appears to be [e.g., well-structured, "
            "comprehensive on Topic X, somewhat fragmented]."
        )
        ex_assessment_en_l2: str = (
            "    A key strength is [e.g., its clear explanation of Abstraction A (Index 0)]. A potential area for "
            "enhancement could be [e.g., providing more examples for Abstraction B (Index 2)]. "
            "(AI interpretation for discussion)."
        )
        ex_rating_score: int = 65
        ex_rating_level: str = "Good Tool"
        ex_rating_just_en_l1: str = "    The project shows a solid foundation with good modularity (Characteristic 1). "
        ex_rating_just_en_l2: str = (
            "However, the potential scalability concerns with Main Processing Pipeline (Index Z) and "
            "the need for clearer error handling (Discussion Point 1) prevent a higher rating at this stage."
        )
        ex_rating_just_en: str = ex_rating_just_en_l1 + ex_rating_just_en_l2

        lang_cap_for_example = target_language.capitalize()
        if target_language.lower() == "slovak":
            ex_insight1 = (
                f'"Charakteristika: Modulárny dizajn. Príklad: `Správa konfigurácie` (Index 0) v `config.py` '
                f"jasne oddeľuje nastavenia. Výhoda: Toto zlepšuje udržiavateľnosť tohto projektu na spracovanie dát, "
                f'keďže nastavenia sa dajú meniť bez hlbokých zmien v kóde." (Text v {lang_cap_for_example})'
            )
            ex_suggestion1 = (
                f'"Diskusný bod: Orchestrácia pomocou `Hlavnej aplikačnej logiky` (Index Z). Otázka: Ako sa budú '
                f"funkcie rozširovať, mohla by jej priama kontrola nad `Spracovaním dát` (Index X) a "
                f"`Spracovaním položiek` (Index Y) viesť k vysokej previazanosti, ovplyvňujúc aj `Logovanie` "
                f'(Index V) a `Správu konfigurácie` (Index U)?" (Text v {lang_cap_for_example})'
            )
            ex_observation1 = (
                f'"Vzor: Potrubná architektúra (Pipeline). Zrejmá tam, kde `Hlavná aplikačná logika` (Index Z) '
                f"organizuje Načítanie -> Spracovanie -> Uloženie. Výhoda: Zjednodušuje pochopenie toku dát. "
                f"Zváženie: Môže sa stať rigidnou, ak sú fázy (`Spracovanie dát` (Index X), "
                f'`Spracovanie položiek` (Index Y)) príliš vzájomne závislé." (Text v {lang_cap_for_example})'
            )
            ex_assessment_l1 = (
                f"    Celkovo sa projekt (`{project_name}`) javí byť [napr. dobre štruktúrovaný, "
                f"komplexný v téme X, trochu fragmentovaný]. (Text v {lang_cap_for_example})"
            )
            ex_assessment_l2 = (
                "    Kľúčovou silnou stránkou je [napr. jasné vysvetlenie Abstraktu A (Index 0)]. "
                "Potenciálnou oblasťou na zlepšenie by mohlo byť [napr. poskytnutie viacerých príkladov pre "
                f"Abstrakt B (Index 2)]. (Interpretácia AI na diskusiu). (Text v {lang_cap_for_example})"
            )
            ex_rating_just_l1: str = "    Projekt ukazuje solídny základ s dobrou modularitou (Charakteristika 1). "
            ex_rating_just_l2: str = (
                "Avšak potenciálne obavy o škálovateľnosť Hlavného Spracovateľského Potrubia (Index Z) a "
                "potreba jasnejšieho spracovania chýb (Diskusný bod 1) bránia vyššiemu hodnoteniu v tejto fáze. "
            )
            ex_rating_just: str = ex_rating_just_l1 + ex_rating_just_l2 + f"(Text v {lang_cap_for_example})"

        else:
            ex_insight1 = f'"{ex_insight1_en}"'
            ex_suggestion1 = f'"{ex_suggestion1_en}"'
            ex_observation1 = f'"{ex_observation1_en}"'
            ex_assessment_l1 = ex_assessment_en_l1
            ex_assessment_l2 = ex_assessment_en_l2
            ex_rating_just = ex_rating_just_en

        yaml_lines = [
            "```yaml",
            "key_characteristics:",
            f"  - {ex_insight1}",
            "areas_for_discussion:",
            f"  - {ex_suggestion1}",
            "observed_patterns:",
            f"  - {ex_observation1}",
            "coding_practice_observations: []",
            "overall_summary: |",
            ex_assessment_l1,
            ex_assessment_l2,
            f"overall_rating_score: {ex_rating_score}",
            f'rating_level_name: "{ex_rating_level}"',
            "rating_justification: |",
            ex_rating_just,
            "```",
        ]
        return "\n".join(yaml_lines)

    @staticmethod
    def _get_content_generation_instructions(target_language: str) -> str:
        """Return a list of detailed instructions for the LLM on review content generation.

        Args:
            target_language: The target language for the review.

        Returns:
            A list of strings, each an instruction point for the LLM.
        """
        lang_cap_instr = target_language.capitalize()
        rating_just_lang_instr = (
            f"This justification MUST be in **{lang_cap_instr}**."
            if target_language.lower() != "english"
            else "This justification must be in English."
        )

        instructions_list: list[str] = [
            "\n**Important Considerations for Content Generation:**",
            "  - When referencing specific abstractions in your points, please use the format "
            "'Abstraction Name (Index X)' for clarity and consistency, using the names and indices provided "
            "in the 'Identified Core Abstractions' section.",
            "- `key_characteristics`: List 2-3 positive or neutral notable design/architectural features. "
            "**For each, provide a concrete example by referencing specific abstraction names (Index X)\n"
            "  or filenames (e.g., 'module_y.py') that demonstrate this characteristic and **clearly state its\n"
            "  specific benefit or positive impact *within the context of this particular project*.**",
            "- `areas_for_discussion`: List 1-2 specific aspects that might warrant deeper review. "
            "**For each, briefly explain *why* it's a point of interest or *pose a question* for the team.\n"
            "  If discussing coupling or bottlenecks, try to reference which other identified abstractions\n"
            "  (by 'Abstraction Name (Index X)') might be most impacted based on the\n"
            "  'Key Interactions Identified' context.**",
            "- `observed_patterns`: List **up to 3** observed design patterns, common practices, or distinct "
            "structural features. **If possible, name the key classes/modules or specific abstractions\n"
            "  (e.g., 'Pattern Z observed in interaction between `Abstraction A (Index I)` and "
            "`Abstraction B (Index J)`) where this pattern is evident.\n"
            "  **Briefly mention a common advantage or consideration associated with this pattern\n"
            "  in the project's context (e.g., 'Pipeline architecture simplifies understanding data "
            "flow but can become rigid if stages are too interdependent').**",
            "- `coding_practice_observations` (Optional): List 1-2 observations on architectural practices or\n"
            "  potential high-level 'smells' (e.g., a highly central abstraction).\n"
            "  **Consider aspects like apparent consistency in abstraction design, potential impacts on\n"
            "  testability or extensibility suggested by the relationships, or adherence to common principles\n"
            "  like SRP based on abstraction descriptions. Base this ONLY on the provided\n"
            "  abstractions/relationships, not detailed code style.** Phrase as points for discussion.",
            "- `overall_summary`: A brief, neutral summary of the project's apparent structure and approach\n"
            "  based on the AI's understanding of the provided context. **Attempt to highlight one or two\n"
            "  standout aspects (e.g., its primary strength or a key design choice) that characterize the project.**\n"
            "  Clearly state this is an AI interpretation.",
            "Do NOT invent information not supported by the provided context. If context is insufficient "
            "for a section, state that (e.g., in `observed_patterns`:"
            "  'Insufficient data to identify specific design patterns beyond the overall pipeline structure.').",
            "\n  - **Expert Rating (Final Step of Analysis):**",
            "    After completing all other sections of the review, assign an overall 'Expert Rating' "
            "to the project based on the 'Rating Scale' provided below. This rating should reflect your "
            "holistic understanding derived from the abstractions, relationships, and file structure.",
            "    Your rating MUST include these fields in the YAML:",
            "    - `overall_rating_score`: An integer from 1-100.",
            "    - `rating_level_name`: The exact name of the level corresponding to your score from the scale.",
            f"    - `rating_justification`: A brief (2-3 sentences) explanation for your score, linking it to "
            f"your previous observations. {rating_just_lang_instr}",
        ]
        return "\n".join(instructions_list)

    @staticmethod
    def format_project_review_prompt(
        project_name: str,
        abstractions_data: CodeAbstractionsList,
        relationships_data: CodeRelationshipsDict,
        files_data: FilePathContentList,
        language: str,
    ) -> str:
        """Format the prompt for the LLM to generate a structured project review.

        This method constructs a comprehensive prompt by combining formatted
        summaries of abstractions, relationships, file structure, and language-specific
        instructions with detailed guidelines on the expected YAML output structure
        and content for each section of the review.

        Args:
            project_name: The name of the project being reviewed.
            abstractions_data: A list of dictionaries, each representing an
                               identified code abstraction.
            relationships_data: A dictionary containing a summary and details of
                                relationships between abstractions.
            files_data: A list of (filepath, content) tuples representing the
                        project's file structure. Content is not directly used here.
            language: The target language for the review.

        Returns:
            A formatted multi-line string constituting the complete prompt for
            the LLM.
        """
        abstractions_str: str = ProjectReviewPrompts._format_abstractions_for_prompt(abstractions_data)
        relationships_str: str = ProjectReviewPrompts._format_relationships_for_prompt(
            relationships_data, abstractions_data
        )
        file_structure_str: str = ProjectReviewPrompts._format_file_structure_for_prompt(files_data)
        lang_instruction: str = ProjectReviewPrompts._get_language_instruction(language)
        output_structure_yaml: str = ProjectReviewPrompts._get_yaml_example_structure(project_name, language)
        content_instructions_str: str = ProjectReviewPrompts._get_content_generation_instructions(language)

        task_desc_parts = [
            "Generate a high-level review of the provided source code project. Focus on:",
            " - Key architectural characteristics (with examples and benefits in this project's context).",
            " - Potential areas for discussion or deeper review (phrased as questions or suggestions, "
            "referencing specific abstractions using 'Abstraction Name (Index X)' format from the\n"
            "   'Identified Core Abstractions' list if relevant).",  # Zalomenie pre E501
            " - Observed design patterns or notable structural features (with examples and their implications).",
            " - Optionally, high-level coding practice observations related to architecture.",
            " - A concise overall summary of the project's apparent structure and approach.",
            " - Finally, assign an expert rating based on the provided scale and justify it.",
            "This is an AI-driven initial analysis based on extracted abstractions, relationships, and file structure.",
        ]
        task_description = "\n".join(task_desc_parts)

        prompt_intro_parts = [
            f"You are an AI assistant analyzing the software project: '{project_name}'.",
            f"The primary programming language of the project is: {language}.",
            (
                "Based on the following automatically extracted information (abstractions, relationships, "
                "file structure), provide a structured project review."  # Zalomenie pre E501
            ),
        ]
        if lang_instruction:
            prompt_intro_parts.insert(1, lang_instruction)

        prompt_lines: list[str] = [
            "\n".join(prompt_intro_parts),
            "\n**Provided Information:**",
            f"1. {abstractions_str}",
            f"\n2. {relationships_str}",
            f"\n3. {file_structure_str}",
            "\n**Your Task:**",
            task_description,
            "The review should be objective, constructive, and based ONLY on the information provided.",
            "\n**Output Format:**",
            "Your response MUST be a single YAML dictionary strictly following this structure:",
            output_structure_yaml,
            content_instructions_str,
            "\n**Rating Scale to Use for `overall_rating_score` and `rating_level_name`:**",
            ProjectReviewPrompts._RATING_SCALE_TEXT,
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML.",
        ]
        return "\n".join(filter(None, prompt_lines))


# End of src/FL01_code_analysis/prompts/project_review_prompts.py
