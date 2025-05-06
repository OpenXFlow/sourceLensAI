# src/sourcelens/prompts/scenario_prompts.py

"""Prompts related to identifying interaction scenarios for diagrams."""


class ScenarioPrompts:
    """Container for prompts related to identifying interaction scenarios."""

    @staticmethod
    def format_identify_scenarios_prompt(
        project_name: str, abstraction_listing: str, context_summary: str, max_scenarios: int
    ) -> str:
        """Format prompt for LLM to identify key interaction scenarios.

        Args:
            project_name: The name of the project.
            abstraction_listing: String listing identified abstractions (Index # Name).
            context_summary: String containing the project summary.
            max_scenarios: Maximum number of scenarios to suggest.

        Returns:
            Formatted string prompting for a YAML list of scenario descriptions.

        """
        # Reverted to simpler task description for scenario identification
        task_description = (
            f"**Task:**\nSuggest up to {max_scenarios} distinct and important "
            f"scenarios based on the abstractions and summary.\n"
            f"Focus on typical user interactions, core processing flows, "
            f"or significant error handling paths if applicable.\n"
            f"Describe each scenario concisely in one sentence, focusing on the interaction or goal."
        )
        example_yaml = """**Example Output:**
```yaml
- User logs in successfully and accesses their dashboard.
- Processing a new data entry including validation and storage.
- Handling a connection error when fetching external data.
- User updates their profile information.
- Generating a monthly report based on stored data.
```"""
        prompt_lines = [
            f"Analyze the provided project information for '{project_name}'. Your goal is to identify "
            f"{max_scenarios} key interaction scenarios that would be most useful to visualize "
            f"with sequence diagrams for a beginner understanding the project's flow.",
            f"\n**Identified Abstractions (Index # Name):**\n{abstraction_listing}",
            f"\n**Project Summary:**\n{context_summary}",
            f"\n{task_description}",
            "\n**Output Format:**",
            "Format your response STRICTLY as a YAML list of strings enclosed within a single ```yaml code block.",
            "Each string in the list should be a concise description of one scenario.",
            f"\n{example_yaml}",
            "\nProvide ONLY the YAML output block containing the list of scenario descriptions. "
            "Do not include any introductory text, explanations, or concluding remarks outside the ```yaml block.",
        ]
        return "\n".join(prompt_lines)


# End of src/sourcelens/prompts/scenario_prompts.py
