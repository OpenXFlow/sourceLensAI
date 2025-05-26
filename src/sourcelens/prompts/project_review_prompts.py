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

# Type Aliases to match context provided by the calling node
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
FileDataList: TypeAlias = list[tuple[str, str]]

# Constants for formatting
_MAX_ABSTRACTION_DESC_SNIPPET_LEN: Final[int] = 120
_MAX_FILES_FOR_STRUCTURE_PROMPT: Final[int] = 15
_MAX_FILES_PER_ABSTRACTION_IN_PROMPT: Final[int] = 3


class ProjectReviewPrompts:
    """Container for prompts related to generating a project review."""

    @staticmethod
    def _format_abstractions_for_prompt(abstractions: AbstractionsList) -> str:
        """Format the list of abstractions for inclusion in a prompt."""
        if not abstractions:
            return "No core abstractions were identified for detailed review."
        header = "Identified Core Abstractions (Index. Name - Files Associated - Description Snippet):"
        parts: list[str] = [header]
        for i, abstr in enumerate(abstractions):
            name: str = str(abstr.get("name", f"Unnamed Abstraction {i}"))
            description: str = str(abstr.get("description", "N/A"))
            files_associated_any: Any = abstr.get("files", [])
            files_associated: list[int] = files_associated_any if isinstance(files_associated_any, list) else []
            num_files = len(files_associated)
            desc_snippet: str = description[:_MAX_ABSTRACTION_DESC_SNIPPET_LEN]
            if len(description) > _MAX_ABSTRACTION_DESC_SNIPPET_LEN:
                desc_snippet += "..."

            file_info = f" (Associated with {num_files} file(s))" if num_files > 0 else ""
            parts.append(f"  - {i}. {name}{file_info}: {desc_snippet}")
        return "\n".join(parts)

    @staticmethod
    def _format_relationships_for_prompt(relationships: RelationshipsDict, abstractions: AbstractionsList) -> str:
        """Format relationships for inclusion in a prompt."""
        summary: str = str(relationships.get("summary", "No overall relationship summary provided."))
        details: list[dict[str, Any]] = relationships.get("details", [])
        if not isinstance(details, list):
            details = []

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
                try:
                    from_name: str = str(abstractions[from_idx].get("name", f"Abstraction {from_idx}"))
                    to_name: str = str(abstractions[to_idx].get("name", f"Abstraction {to_idx}"))
                    parts.append(f"  - '{from_name}' (Index {from_idx}) --[{label}]--> '{to_name}' (Index {to_idx})")
                except IndexError:
                    err_msg_part1 = f"  - Abstraction Index {from_idx} --[{label}]--> Abstraction Index {to_idx}"
                    err_msg_part2 = " (Name lookup failed due to index out of bounds)"
                    parts.append(err_msg_part1 + err_msg_part2)
            else:
                parts.append(f"  - Malformed relationship data: {rel}")
        return "\n".join(parts)

    @staticmethod
    def _format_file_structure_for_prompt(files_data: FileDataList) -> str:
        """Format a summary of the file structure for inclusion in a prompt."""
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
        """Prepare language specific instruction."""
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
    def _get_yaml_example_structure(project_name: str) -> str:  # Added project_name parameter
        """Return the YAML example structure string for the prompt."""
        # YAML Example parts carefully broken down
        yaml_ex_kc_header = "key_characteristics:"
        yaml_ex_kc_items = [
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
        ]
        yaml_ex_ad_header = "areas_for_discussion:"
        yaml_ex_ad_items = [
            (
                '  - "Discussion Point: Orchestration by `Main Application Logic` (Index Z). Question: As features '
                "expand, could its direct control over `Data Handling` (Index X) and `Item Processing` (Index Y) "
                'lead to high coupling, impacting `Logging` (Index V) and `Configuration Management` (Index U) as well?"'
            ),
            (
                '  - "Discussion Point: `Item` Data Model (Index W) Flexibility. Question: For a project handling varied '
                "data items, is the current fixed dataclass structure of `Item` (Index W) sufficiently adaptable, "
                'or might a more dynamic schema be needed in the long run?"'
            ),
        ]
        yaml_ex_op_header = "observed_patterns:"
        yaml_ex_op_items = [
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
        ]
        yaml_ex_cpo_header = "coding_practice_observations: # Optional, focus on high-level architectural aspects"
        yaml_ex_cpo_items = [
            (
                '  - "Observation: Clear Abstraction Naming. Names like `Data Handling` (Index X) generally align with '
                'responsibilities, suggesting SRP adherence, which aids testability."'
            ),
            (
                '  - "Architectural Smell (discussion): `Main Application Logic` (Index Z) orchestrates many other '
                "abstractions. Discussion: Monitor for God Object tendencies; an event-driven model or mediators "
                'might be alternatives for enhanced extensibility."'
            ),
        ]
        yaml_ex_os_header = "overall_summary: |"
        # Using project_name in the example summary
        yaml_ex_os_lines = [
            f"    Overall, the project (`{project_name}`) demonstrates a commendable modular design for its primary "
            "task of data processing. A standout aspect is the clear separation of concerns, particularly how "
            "`Configuration Management` (Index 0) is decoupled from core logic like `Item Processing` (Index Y).",
            "    This AI interpretation suggests a foundation built for clarity. However, future growth might "
            "necessitate revisiting the central orchestration strategy within `Main Application Logic` (Index Z) "
            "to maintain flexibility. (AI interpretation for discussion).",
        ]

        output_parts: list[str] = ["```yaml"]
        output_parts.append(yaml_ex_kc_header)
        output_parts.extend(yaml_ex_kc_items)
        output_parts.append(yaml_ex_ad_header)
        output_parts.extend(yaml_ex_ad_items)
        output_parts.append(yaml_ex_op_header)
        output_parts.extend(yaml_ex_op_items)
        output_parts.append(yaml_ex_cpo_header)
        output_parts.extend(yaml_ex_cpo_items)
        output_parts.append(yaml_ex_os_header)
        output_parts.extend(yaml_ex_os_lines)
        output_parts.append("```")
        return "\n".join(output_parts)

    @staticmethod
    def _get_content_generation_instructions() -> list[str]:
        """Return a list of instructions for content generation, split for line length."""
        considerations_header = "\n**Important Considerations for Content Generation:**"
        ref_instr = [
            "  - When referencing specific abstractions in your points, please use the format",
            "    'Abstraction Name (Index X)' for clarity and consistency, using the names and indices provided",
            "    in the 'Identified Core Abstractions' section.",
        ]
        kc_instr = [
            "- `key_characteristics`: List 2-3 positive or neutral notable design/architectural features.",
            "  **For each, provide a concrete example by referencing specific abstraction names (Index X)",
            "  or filenames (e.g., 'module_y.py') that demonstrate this characteristic and **clearly state its",
            "  specific benefit or positive impact *within the context of this particular data processing project*.**",
        ]
        ad_instr = [
            "- `areas_for_discussion`: List 1-2 specific aspects that might warrant deeper review.",
            "  **For each, briefly explain *why* it's a point of interest or *pose a question* for the team.",
            "  If discussing coupling or bottlenecks, try to reference which other identified abstractions",
            "  (by 'Abstraction Name (Index X)') might be most impacted based on the",
            "  'Key Interactions Identified' context.**",
        ]
        op_instr = [
            "- `observed_patterns`: List **up to 3** observed design patterns, common practices, or distinct",
            "  structural features. **If possible, name the key classes/modules or specific abstractions",
            "  (e.g., 'Pattern Z observed in interaction between `Abstraction A (Index I)` and",
            "  `Abstraction B (Index J)`) where this pattern is evident.",
            "  **Briefly mention a common advantage or consideration associated with this pattern",
            "  in the project's context (e.g., 'Pipeline architecture simplifies understanding data",
            "  flow but can become rigid if stages are too interdependent').**",
        ]
        cpo_instr = [
            "- `coding_practice_observations` (Optional): List 1-2 observations on architectural practices or",
            "  potential high-level 'smells' (e.g., a highly central abstraction).",
            "  **Consider aspects like apparent consistency in abstraction design, potential impacts on",
            "  testability or extensibility suggested by the relationships, or adherence to common principles",
            "  like SRP based on abstraction descriptions. Base this ONLY on the provided",
            "  abstractions/relationships, not detailed code style.** Phrase as points for discussion.",
        ]
        os_instr = [
            "- `overall_summary`: A brief, neutral summary of the project's apparent structure and approach",
            "  based on the AI's understanding of the provided context. **Attempt to highlight one or two",
            "  standout aspects (e.g., its primary strength or a key design choice) that characterize the project.**",
            "  Clearly state this is an AI interpretation.",
        ]
        no_invent_instr = [
            "Do NOT invent information not supported by the provided context. If context is insufficient",
            "for a section, state that (e.g., in `observed_patterns`:",
            "  'Insufficient data to identify specific design patterns beyond the overall pipeline structure.').",
        ]

        all_instructions: list[str] = [considerations_header]
        all_instructions.extend(
            [
                "\n".join(instr_part)
                for instr_part in [ref_instr, kc_instr, ad_instr, op_instr, cpo_instr, os_instr, no_invent_instr]
            ]
        )
        return all_instructions

    @staticmethod
    def format_project_review_prompt(
        project_name: str,
        abstractions_data: AbstractionsList,
        relationships_data: RelationshipsDict,
        files_data: FileDataList,
        language: str,
    ) -> str:
        """Format the prompt for the LLM to generate a project review.

        Args:
            project_name: The name of the project.
            abstractions_data: List of identified abstractions.
            relationships_data: Dictionary of identified relationships.
            files_data: List of (filepath, content) tuples for file structure.
            language: The primary programming language of the project.

        Returns:
            A formatted string prompting the LLM for a structured project review.
        """
        abstractions_str: str = ProjectReviewPrompts._format_abstractions_for_prompt(abstractions_data)
        relationships_str: str = ProjectReviewPrompts._format_relationships_for_prompt(
            relationships_data, abstractions_data
        )
        file_structure_str: str = ProjectReviewPrompts._format_file_structure_for_prompt(files_data)
        lang_instruction: str = ProjectReviewPrompts._get_language_instruction(language)
        output_structure_yaml: str = ProjectReviewPrompts._get_yaml_example_structure(project_name)
        content_instructions: list[str] = ProjectReviewPrompts._get_content_generation_instructions()

        task_desc_lines = [
            "Generate a project review. Focus on identifying broad architectural characteristics,",
            "potential areas for discussion (NOT definitive problems, phrase as questions if possible,",
            "referencing specific abstractions using 'Abstraction Name (Index X)' format from the",
            "'Identified Core Abstractions' list if relevant), and any notable patterns or structural observations.",
            "This is an AI-driven initial analysis.",
        ]

        prompt_lines: list[str] = [
            f"You are an AI assistant analyzing the software project: '{project_name}'.",
            f"The primary programming language of the project is: {language}.",
            lang_instruction,
            "Based on the following automatically extracted information (abstractions, relationships, file structure), "
            "provide a high-level project review.",
            "\n**Provided Information:**",
            f"1. {abstractions_str}",
            f"\n2. {relationships_str}",
            f"\n3. {file_structure_str}",
            "\n**Your Task:**",
            *task_desc_lines,
            "The review should be objective and constructive.",
            "\n**Output Format:**",
            "Your response MUST be a single YAML dictionary strictly following this structure:",
            output_structure_yaml,
            *content_instructions,
            "\nProvide ONLY the YAML output block. No introductory text or explanations outside the YAML.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/project_review_prompts.py
