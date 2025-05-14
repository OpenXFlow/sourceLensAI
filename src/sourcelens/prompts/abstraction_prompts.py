# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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


"""Prompts related to identifying and analyzing code abstractions."""


class AbstractionPrompts:
    """Container for prompts related to code abstractions and relationships."""

    @staticmethod
    def format_identify_abstractions_prompt(project_name: str, context: str, file_listing: str, language: str) -> str:
        """Format the prompt for the LLM to identify core abstractions from code.

        Args:
            project_name: The name of the project.
            context: String containing concatenated code file contents.
            file_listing: String listing file indices and paths available.
            language: The target language for names and descriptions.

        Returns:
            A formatted string prompting the LLM for abstractions in YAML.

        """
        language_instruction, name_lang_hint, desc_lang_hint = "", "", ""
        if language.lower() != "english":
            lang_cap = language.capitalize()
            language_instruction = (
                f"IMPORTANT: Generate `name` and `description` fields exclusively "
                f"in **{lang_cap}**.\nDo NOT use English for these fields.\n\n"
            )
            name_lang_hint = f" (in {lang_cap})"
            desc_lang_hint = f" (in {lang_cap})"

        file_indices_instruction = (
            "3. Relevant `file_indices`: List integer indices of related files. "
            "Format 'index # path/comment' allowed, only leading integer matters. "
            "Use ONLY indices from 'Available File Indices/Paths' below."
        )
        name_instruction = (
            f"1. Concise `name`{name_lang_hint}: A short, descriptive name. "
            f"**MUST be a single-line string enclosed in double quotes** "
            f'(e.g., "User Authentication").'
        )
        description_instruction = (
            f"2. Beginner-friendly `description`{desc_lang_hint}: Clear explanation "
            f"(50-100 words). **MUST be a single-line string enclosed in double quotes.** "
            f"Newlines are NOT allowed in the description string itself."
        )
        example_yaml = f"""```yaml
- name: "Query Processing Module{name_lang_hint}"
  description: "This component receives queries, parses them, and directs them. Like a mail dispatcher.{desc_lang_hint}"
  file_indices:
    - 0 # path/to/file.py
    - "3 # another/file.py"
- name: "Data Model Definitions{name_lang_hint}"
  description: "Defines core data structures, specifying fields and relationships.{desc_lang_hint}"
  file_indices: [6, 7]
# ... up to 10 abstractions ...
```"""
        prompt_lines = [
            f"Analyze codebase context for project `{project_name}`.",
            "Identify top 5-10 core conceptual abstractions/components a beginner needs to understand first.",
            "\nCodebase Context:\n```",
            context,
            "```",
            f"\n{language_instruction}Instructions:",
            "For each core abstraction, provide:",
            name_instruction,
            description_instruction,
            file_indices_instruction,
            "\nAvailable File Indices/Paths:",
            file_listing,
            "\nOutput Format:",
            "Format response STRICTLY as a YAML list of dictionaries, enclosed in a single ```yaml code block.",
            "Each dictionary represents one abstraction.",
            "\nExample:",
            example_yaml,
            "\nProvide ONLY the YAML output block. No introductory text, explanations, or concluding remarks.",
        ]
        return "\n".join(prompt_lines)

    @staticmethod
    def format_analyze_relationships_prompt(
        project_name: str, context: str, abstraction_listing: str, num_abstractions: int, language: str
    ) -> str:
        """Format prompt for LLM to analyze relationships between abstractions.

        Args:
            project_name: The name of the project.
            context: String with abstraction details and code snippets.
            abstraction_listing: String listing identified abstractions (Index # Name).
            num_abstractions: Total number of identified abstractions.
            language: Target language for summary and relationship labels.

        Returns:
            A formatted string prompting for a YAML summary and relationship list.

        """
        language_instruction, lang_hint, list_lang_note = "", "", ""
        if language.lower() != "english":
            lang_cap = language.capitalize()
            language_instruction = (
                f"IMPORTANT: Generate `summary` and relationship `label` fields exclusively "
                f"in **{lang_cap}**.\nDo NOT use English for these fields.\n\n"
            )
            lang_hint = f" (in {lang_cap})"
            list_lang_note = f" (Names/Indices correspond to list below, expected in {lang_cap})"

        max_index = max(0, num_abstractions - 1)
        min_expected_rels = min(3, max(0, num_abstractions - 1))  # Ensure non-negative
        coverage_instr = ""
        if num_abstractions > 1:
            coverage_instr = (
                f"\nIMPORTANT: Ensure you identify relationships connecting core abstractions. "
                f"Aim to describe at least {min_expected_rels} key interactions if they exist."
            )

        summary_instruction = (
            f"1. `summary`: Provide a high-level overview (2-4 sentences) explaining how main "
            f"abstractions interact for the project's purpose. Target beginner.{lang_hint} "
            f"Use **bold** or *italic* for emphasis."
        )
        rel_header = "2. `relationships`: A list detailing key interactions between abstractions:"
        from_instr = f"    - `from_abstraction`: Integer index (0 to {max_index}) of source (or 'index # Name' format)."
        to_instr = f"    - `to_abstraction`: Integer index (0 to {max_index}) of target (or 'index # Name' format)."
        label_instr = (
            f"    - `label`: Brief, descriptive verb phrase{lang_hint} for interaction "
            f'(e.g., "Sends data to", "Depends on"). Keep labels concise.'
        )
        simplify_note = (
            "    Focus only on most important, direct relationships for understanding core flow. "
            "Exclude minor/indirect."
        )
        example_yaml = f"""```yaml
summary: |
  This project processes user requests by first validating them (**Validation Service**),
  then fetching data using *Data Access Layer*, and finally generating a response
  via the **Response Formatter**.{lang_hint}
relationships:
  - from_abstraction: 0 # Request Validator
    to_abstraction: 2 # Data Access Layer
    label: "Passes validated request to"{lang_hint}
  - from_abstraction: "3 # Configuration Loader"
    to_abstraction: 2
    label: "Configures database for"{lang_hint}
  # ... other key relationships ...
```"""
        prompt_lines = [
            f"Based on identified abstractions and code context for project `{project_name}`, "
            f"analyze how components interact.",
            f"\nIdentified Abstractions List{list_lang_note}:",
            abstraction_listing,
            "\nContext (Abstraction Details & Relevant Code Snippets):",
            "```",
            context,
            "```",
            f"\n{language_instruction}Instructions:",
            "Provide an analysis with two parts:",
            summary_instruction,
            rel_header,
            from_instr,
            to_instr,
            label_instr,
            simplify_note,
            coverage_instr,
            "\nOutput Format:",
            "Format response STRICTLY as a YAML dictionary enclosed in a single ```yaml code block.",
            "\nExample:",
            example_yaml,
            "\nProvide ONLY the YAML output block. No introductory text, explanations, or concluding remarks.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/abstraction_prompts.py
