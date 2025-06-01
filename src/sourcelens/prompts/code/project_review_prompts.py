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

from typing_extensions import TypeAlias

AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
FileDataList: TypeAlias = list[tuple[str, str]]

_MAX_ABSTRACTION_DESC_SNIPPET_LEN: Final[int] = 120
_MAX_FILES_FOR_STRUCTURE_PROMPT: Final[int] = 15

PROJECT_REVIEW_SCHEMA: Final[dict[str, Any]] = {
    "type": "object",
    "properties": {
        "key_characteristics": {"type": "array", "items": {"type": "string"}},
        "areas_for_discussion": {"type": "array", "items": {"type": "string"}},
        "observed_patterns": {"type": "array", "items": {"type": "string"}},
        "coding_practice_observations": {"type": "array", "items": {"type": "string"}},
        "overall_summary": {"type": "string"},
    },
    "required": ["key_characteristics", "areas_for_discussion", "observed_patterns", "overall_summary"],
    "additionalProperties": False,
}


class ProjectReviewPrompts:
    """Container for prompts related to generating a project review."""

    PROJECT_REVIEW_SCHEMA: Final[dict[str, Any]] = PROJECT_REVIEW_SCHEMA

    @staticmethod
    def _format_abstractions_for_prompt(abstractions: AbstractionsList) -> str:
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
    def _format_relationships_for_prompt(relationships: RelationshipsDict, abstractions: AbstractionsList) -> str:
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
        summary: str = str(relationships.get("summary", "No overall relationship summary provided."))
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
    def _format_file_structure_for_prompt(files_data: FileDataList) -> str:
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
            language: The primary programming language of the project.

        Returns:
            A string containing language-specific instructions for the LLM.
        """
        instruction_parts: list[str] = []
        if language.lower() != "english":
            lang_cap = language.capitalize()
            instruction_parts.append(
                f"IMPORTANT: Generate all textual content for this review (summaries, characteristics, etc.) "
                f"exclusively in **{lang_cap}**,"
            )
            instruction_parts.append("unless quoting specific English technical terms or code identifiers.\n")
        return "\n".join(instruction_parts)

    @staticmethod
    def _get_yaml_example_structure(project_name: str) -> str:
        """Return the YAML example structure string for the project review prompt.

        Args:
            project_name: The name of the project.

        Returns:
            A string representing the example YAML structure for the LLM to follow.
        """
        # Reverted to explicit string concatenation with '+' to ensure correct formatting
        # and avoid E501 issues from excessively long single string literals.
        yaml_lines = [
            "```yaml",
            "key_characteristics:",
            (
                '  - "Characteristic: Modular Design. Example: `Configuration Management` (Index 0) in `config.py` '
                "clearly separates settings. Benefit: This enhances maintainability for this data processing project, "
                'as settings can be altered without deep code changes."'
            ),
            (
                '  - "Characteristic: Data Encapsulation. Example: The `Item` class (Index 1) in `models.py` '
                "effectively bundles data with relevant operations. Benefit: This promotes cleaner interfaces and "
                'reduces the risk of inconsistent data states throughout the processing pipeline."'
            ),
            "areas_for_discussion:",
            (
                '  - "Discussion Point: Orchestration by `Main Application Logic` (Index Z). Question: As features '
                "expand, could its direct control over `Data Handling` (Index X) and `Item Processing` (Index Y) "
                'lead to high coupling, impacting `Logging` (Index V) and `Configuration Management` (Index U) as well?"'  # noqa: E501
            ),
            (
                '  - "Discussion Point: `Item` Data Model (Index W) Flexibility. Question: For a project handling varied '  # noqa: E501
                "data items, is the current fixed dataclass structure of `Item` (Index W) sufficiently adaptable, "
                'or might a more dynamic schema be needed in the long run?"'
            ),
            "observed_patterns:",
            (
                '  - "Pattern: Pipeline Architecture. Evident where `Main Application Logic` (Index Z) orchestrates '
                "Load -> Process -> Save. Advantage: Simplifies understanding data flow. Consideration: Can become "
                'rigid if stages (`Data Handling` (Index X), `Item Processing` (Index Y)) are too interdependent."'
            ),
            (
                '  - "Structure: Centralized Configuration. `Configuration Management` (Index 0) provides settings to '
                "`ItemProcessor` (Index Y). Advantage: Easy to manage global settings. Consideration: Over-reliance "
                'might lead to hidden dependencies."'
            ),
            "coding_practice_observations: # Optional, focus on high-level architectural aspects",
            (
                '  - "Observation: Clear Abstraction Naming. Names like `Data Handling` (Index X) generally align with '
                'responsibilities, suggesting SRP adherence, which aids testability."'
            ),
            (
                '  - "Architectural Smell (discussion): `Main Application Logic` (Index Z) orchestrates many other '
                "abstractions. Discussion: Monitor for God Object tendencies; an event-driven model or mediators "
                'might be alternatives for enhanced extensibility."'
            ),
            "overall_summary: |",
            f"    Overall, the project (`{project_name}`) demonstrates a commendable modular design for its primary "
            "task of data processing. A standout aspect is the clear separation of concerns, particularly how "
            "`Configuration Management` (Index 0) is decoupled from core logic like `Item Processing` (Index Y).",
            "    This AI interpretation suggests a foundation built for clarity. However, future growth might "
            "necessitate revisiting the central orchestration strategy within `Main Application Logic` (Index Z) "
            "to maintain flexibility. (AI interpretation for discussion).",
            "```",
        ]
        return "\n".join(yaml_lines)

    @staticmethod
    def _get_content_generation_instructions() -> list[str]:
        """Return a list of detailed instructions for the LLM on review content generation.

        Returns:
            A list of strings, each an instruction point for the LLM.
        """
        instructions = [
            "\n**Important Considerations for Content Generation:**",
            "  - When referencing specific abstractions in your points, please use the format "
            "'Abstraction Name (Index X)' for clarity and consistency, using the names and indices provided "
            "in the 'Identified Core Abstractions' section.",
            "- `key_characteristics`: List 2-3 positive or neutral notable design/architectural features. "
            "**For each, provide a concrete example by referencing specific abstraction names (Index X) "
            "or filenames (e.g., 'module_y.py') that demonstrate this characteristic and **clearly state its "
            "specific benefit or positive impact *within the context of this particular data processing project*.**",
            "- `areas_for_discussion`: List 1-2 specific aspects that might warrant deeper review. "
            "**For each, briefly explain *why* it's a point of interest or *pose a question* for the team. "
            "If discussing coupling or bottlenecks, try to reference which other identified abstractions "
            "(by 'Abstraction Name (Index X)') might be most impacted based on the "
            "'Key Interactions Identified' context.**",
            "- `observed_patterns`: List **up to 3** observed design patterns, common practices, or distinct "
            "structural features. **If possible, name the key classes/modules or specific abstractions "
            "(e.g., 'Pattern Z observed in interaction between `Abstraction A (Index I)` and "
            "`Abstraction B (Index J)`) where this pattern is evident. "
            "**Briefly mention a common advantage or consideration associated with this pattern "
            "in the project's context (e.g., 'Pipeline architecture simplifies understanding data "
            "flow but can become rigid if stages are too interdependent').**",
            "- `coding_practice_observations` (Optional): List 1-2 observations on architectural practices or "
            "potential high-level 'smells' (e.g., a highly central abstraction). "
            "**Consider aspects like apparent consistency in abstraction design, potential impacts on "
            "testability or extensibility suggested by the relationships, or adherence to common principles "
            "like SRP based on abstraction descriptions. Base this ONLY on the provided "
            "abstractions/relationships, not detailed code style.** Phrase as points for discussion.",
            "- `overall_summary`: A brief, neutral summary of the project's apparent structure and approach "
            "based on the AI's understanding of the provided context. **Attempt to highlight one or two "
            "standout aspects (e.g., its primary strength or a key design choice) that characterize the project.** "
            "Clearly state this is an AI interpretation.",
            "Do NOT invent information not supported by the provided context. If context is insufficient "
            "for a section, state that (e.g., in `observed_patterns`:"
            "  'Insufficient data to identify specific design patterns beyond the overall pipeline structure.').",
        ]
        # Manually split long lines if necessary, for example:
        instructions[2] = (
            "- `key_characteristics`: List 2-3 positive or neutral notable design/architectural features. "
            "**For each, provide a concrete example by referencing specific abstraction names (Index X)\n"
            "  or filenames (e.g., 'module_y.py') that demonstrate this characteristic and **clearly state its\n"
            "  specific benefit or positive impact *within the context of this particular data processing project*.**"
        )
        instructions[3] = (
            "- `areas_for_discussion`: List 1-2 specific aspects that might warrant deeper review. "
            "**For each, briefly explain *why* it's a point of interest or *pose a question* for the team.\n"
            "  If discussing coupling or bottlenecks, try to reference which other identified abstractions\n"
            "  (by 'Abstraction Name (Index X)') might be most impacted based on the\n"
            "  'Key Interactions Identified' context.**"
        )
        instructions[4] = (
            "- `observed_patterns`: List **up to 3** observed design patterns, common practices, or distinct "
            "structural features. **If possible, name the key classes/modules or specific abstractions\n"
            "  (e.g., 'Pattern Z observed in interaction between `Abstraction A (Index I)` and "
            "`Abstraction B (Index J)`) where this pattern is evident.\n"
            "  **Briefly mention a common advantage or consideration associated with this pattern\n"
            "  in the project's context (e.g., 'Pipeline architecture simplifies understanding data "
            "flow but can become rigid if stages are too interdependent').**"
        )
        instructions[5] = (
            "- `coding_practice_observations` (Optional): List 1-2 observations on architectural practices or\n"
            "  potential high-level 'smells' (e.g., a highly central abstraction).\n"
            "  **Consider aspects like apparent consistency in abstraction design, potential impacts on\n"
            "  testability or extensibility suggested by the relationships, or adherence to common principles\n"
            "  like SRP based on abstraction descriptions. Base this ONLY on the provided\n"
            "  abstractions/relationships, not detailed code style.** Phrase as points for discussion."
        )
        instructions[6] = (
            "- `overall_summary`: A brief, neutral summary of the project's apparent structure and approach\n"
            "  based on the AI's understanding of the provided context. **Attempt to highlight one or two\n"
            "  standout aspects (e.g., its primary strength or a key design choice) that characterize the project.**\n"
            "  Clearly state this is an AI interpretation."
        )
        return instructions

    @staticmethod
    def format_project_review_prompt(
        project_name: str,
        abstractions_data: AbstractionsList,
        relationships_data: RelationshipsDict,
        files_data: FileDataList,
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
            language: The primary programming language of the project.

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
        output_structure_yaml: str = ProjectReviewPrompts._get_yaml_example_structure(project_name)
        content_instructions_str: str = "\n".join(ProjectReviewPrompts._get_content_generation_instructions())

        task_desc_parts = [
            "Generate a project review. Focus on identifying broad architectural characteristics,",
            "potential areas for discussion (NOT definitive problems, phrase as questions if possible,",
            "referencing specific abstractions using 'Abstraction Name (Index X)' format from the",
            "'Identified Core Abstractions' list if relevant), and any notable patterns or structural observations.",
            "This is an AI-driven initial analysis.",
        ]
        task_description = "\n".join(task_desc_parts)

        prompt_intro_parts = [
            f"You are an AI assistant analyzing the software project: '{project_name}'.",
            f"The primary programming language of the project is: {language}.",
            (
                "Based on the following automatically extracted information (abstractions, relationships, file structure), "  # noqa: E501
                "provide a high-level project review."
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
            "The review should be objective and constructive.",
            "\n**Output Format:**",
            "Your response MUST be a single YAML dictionary strictly following this structure:",
            output_structure_yaml,
            content_instructions_str,
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/code/project_review_prompts.py
