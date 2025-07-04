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

"""Node responsible for generating an AI-powered project review."""

import logging
from typing import TYPE_CHECKING, Any, Final, Optional, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext

if TYPE_CHECKING:  # pragma: no cover
    from sourcelens.core.common_types import (
        CodeAbstractionsList,
        CodeRelationshipsDict,
        FilePathContentList,
    )
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_dict

from ..prompts.project_review_prompts import (
    PROJECT_REVIEW_SCHEMA,
    ProjectReviewPrompts,
)

if TYPE_CHECKING:  # pragma: no cover
    ResolvedLlmConfigDict: TypeAlias = dict[str, Any]
    ResolvedCacheConfigDict: TypeAlias = dict[str, Any]


ProjectReviewPreparedInputs: TypeAlias = dict[str, Any]
ProjectReviewExecutionResult: TypeAlias = Optional[str]


MAX_REVIEW_SNIPPET_LEN_LOG: Final[int] = 200
EXPECTED_FILE_DATA_ITEM_LENGTH: Final[int] = 2

module_logger: logging.Logger = logging.getLogger(__name__)


class GenerateProjectReview(BaseNode[ProjectReviewPreparedInputs, ProjectReviewExecutionResult]):
    """Generate an AI-powered project review based on analyzed project data.

    This node takes identified abstractions, their relationships, and file data
    to prompt an LLM for a structured project review. The review includes key
    characteristics, areas for discussion, observed patterns, an overall
    summary, and an experimental AI-generated rating. The LLM's YAML output
    is validated and then formatted into Markdown.
    """

    def _format_list_section(self, title: str, items: list[str]) -> list[str]:
        """Format a list section for the Markdown review.

        Args:
            title: The title of the section (e.g., "Key Architectural Characteristics").
            items: A list of strings, where each string is an item in the list.

        Returns:
            A list of Markdown strings for this section. Returns an empty list
            if items is empty.
        """
        if not items:
            return []
        section_parts: list[str] = [f"## {title}\n"]
        for item_text in items:
            section_parts.append(f"- {item_text}")
        section_parts.append("\n")
        return section_parts

    def _format_rating_section(self, review_data: dict[str, Any], project_name: str) -> list[str]:
        """Format the AI-Generated Expert Rating section.

        Args:
            review_data: The validated dictionary parsed from LLM's YAML response.
            project_name: The name of the project.

        Returns:
            A list of Markdown strings for the rating section.
        """
        rating_parts: list[str] = []
        rating_score_any: Any = review_data.get("overall_rating_score")
        rating_level_name_any: Any = review_data.get("rating_level_name")
        rating_justification_any: Any = review_data.get("rating_justification")

        rating_score: Optional[int] = (
            cast(Optional[int], rating_score_any) if isinstance(rating_score_any, int) else None
        )
        rating_level_name: Optional[str] = (
            cast(Optional[str], rating_level_name_any) if isinstance(rating_level_name_any, str) else None
        )
        rating_justification: Optional[str] = (
            cast(Optional[str], rating_justification_any) if isinstance(rating_justification_any, str) else None
        )

        if rating_score is not None and rating_level_name and rating_justification:
            rating_parts.append("## AI-Generated Expert Rating\n")
            disclaimer_l1: str = (
                "> ⚠️ **Important Disclaimer:** The following rating is an experimental feature generated by a Large "
                "Language Model (LLM). It is based SOLELY on the textual analysis of the project's identified "
                "abstractions, their relationships, and the provided file structure information."
            )
            disclaimer_l2: str = (
                "> **This AI rating CANNOT and DOES NOT assess:** actual code quality, correctness, efficiency, "
                "runtime behavior, performance, stability, security vulnerabilities, test coverage, usability, "
                "adherence to specific coding standards not evident in the provided text, real-world maintainability "
                "or scalability beyond structural observations, or business logic validity."
            )
            disclaimer_l3: str = (
                "> The rating scale and descriptions were provided to the LLM as a guideline. "
                "The LLM's interpretation is inherently subjective and may not align with a human expert's assessment."
            )
            disclaimer_l4: str = (
                "> **Please use this rating as a high-level, AI-driven perspective for stimulating discussion "
                "and further investigation, NOT as a definitive measure of project quality or maturity.**"
            )
            rating_parts.extend([disclaimer_l1, disclaimer_l2, disclaimer_l3, disclaimer_l4, "\n"])
            rating_parts.append(
                f"**Rating Scale (1-100) provided to the AI:**\n{ProjectReviewPrompts._RATING_SCALE_TEXT}\n\n---\n"
            )
            rating_parts.append(f"**AI Rating for {project_name}:**\n\n")
            rating_parts.append(f"*   **Score:** {rating_score}/100\n")
            rating_parts.append(f"*   **Level:** {rating_level_name}\n")
            rating_parts.append(f"*   **Justification (AI's perspective):**\n    > {rating_justification}\n")
        else:
            self._log_warning("AI Expert Rating fields missing or invalid in LLM response. Skipping rating section.")
        return rating_parts

    def _format_review_yaml_to_markdown(self, review_data: dict[str, Any], project_name: str) -> str:
        """Format the structured YAML data from LLM into Markdown.

        Args:
            review_data: The validated dictionary parsed from LLM's YAML response.
                         Expected to conform to `PROJECT_REVIEW_SCHEMA`.
            project_name: The name of the project, used in the review title.

        Returns:
            A string containing the formatted Markdown for the project review chapter.
        """
        markdown_parts: list[str] = [f"# Project Review: {project_name}\n"]
        warning_text_l1: str = (
            "> **Note:** This review is automatically generated by an AI (Large Language Model) "
            "based on an analysis of the project's abstractions, "
        )
        warning_text_l2: str = (
            "relationships, and file structure. "
            "It is intended to provide high-level insights and stimulate discussion, "
            "not as a definitive expert assessment. "
            "Always use critical judgment when interpreting AI-generated content."
        )
        markdown_parts.append(f"{warning_text_l1}{warning_text_l2}\n")

        summary: str = str(review_data.get("overall_summary", "No overall summary provided."))
        markdown_parts.append(f"## AI-Generated Overall Summary\n\n{summary}\n")

        sections_map: dict[str, str] = {
            "Key Architectural Characteristics (AI-Observed)": "key_characteristics",
            "Potential Areas for Discussion (AI-Suggested)": "areas_for_discussion",
            "Observed Patterns & Structural Notes (AI-Identified)": "observed_patterns",
            "Coding Practice Observations (AI-Noted)": "coding_practice_observations",
        }

        for title, key in sections_map.items():
            items_any: Any = review_data.get(key, [])
            items: list[str] = (
                items_any if isinstance(items_any, list) and all(isinstance(i, str) for i in items_any) else []
            )
            if items or key == "coding_practice_observations":  # Always add header for optional coding_practice
                markdown_parts.extend(self._format_list_section(title, items))

        markdown_parts.extend(self._format_rating_section(review_data, project_name))

        return "\n".join(markdown_parts)

    def pre_execution(self, shared_context: SLSharedContext) -> ProjectReviewPreparedInputs:
        """Prepare necessary data and context for generating the project review.

        Retrieves abstractions, relationships, file data, project details, and
        relevant LLM/cache configurations from `shared_context`.
        Determines if project review generation should be skipped based on config.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing data for the `execution` method, or
            `{"skip": True, "reason": ...}` if prerequisites are not met
            or review generation is disabled.

        Raises:
            ValueError: If essential data like 'config' or specific sub-keys are
                        missing or of an unexpected type in `shared_context`.
        """
        self._log_info("Preparing for project review generation.")
        try:
            current_mode_opts_any: Any = shared_context.get("current_mode_output_options", {})
            current_mode_opts: dict[str, Any] = current_mode_opts_any if isinstance(current_mode_opts_any, dict) else {}

            include_review_val: Any = current_mode_opts.get("include_project_review")
            include_review: bool = include_review_val if isinstance(include_review_val, bool) else False

            if not include_review:
                self._log_info("Project review generation is disabled in configuration. Skipping.")
                return {"skip": True, "reason": "Disabled via 'output_options.include_project_review'"}

            abstractions_data_any: Any = self._get_required_shared(shared_context, "abstractions")
            relationships_data_any: Any = self._get_required_shared(shared_context, "relationships")
            files_data_any: Any = self._get_required_shared(shared_context, "files")
            project_name_val: Any = self._get_required_shared(shared_context, "project_name")
            language_val: Any = shared_context.get("language", "unknown")
            llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
            cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")

            abstractions_data: "CodeAbstractionsList" = []
            if isinstance(abstractions_data_any, list):
                abstractions_data = [item for item in abstractions_data_any if isinstance(item, dict)]
            if len(abstractions_data) != len(abstractions_data_any or []):
                self._log_warning(
                    "Some items in 'abstractions' were not dictionaries or did not match expected structure."
                )

            relationships_data: "CodeRelationshipsDict" = (
                relationships_data_any if isinstance(relationships_data_any, dict) else {}
            )
            files_data_raw: list[Any] = files_data_any if isinstance(files_data_any, list) else []
            files_data: "FilePathContentList" = []
            for item in files_data_raw:
                if (
                    isinstance(item, tuple)
                    and len(item) == EXPECTED_FILE_DATA_ITEM_LENGTH
                    and isinstance(item[0], str)
                    and isinstance(item[1], str)
                ):
                    files_data.append(item)
                else:
                    self._log_warning("Skipping invalid item in files_data for project review context: %s", item)

            prepared_inputs: ProjectReviewPreparedInputs = {
                "skip": False,
                "project_name": str(project_name_val),
                "abstractions_data": abstractions_data,
                "relationships_data": relationships_data,
                "files_data": files_data,
                "language": str(language_val),
                "llm_config": llm_config_val if isinstance(llm_config_val, dict) else {},
                "cache_config": cache_config_val if isinstance(cache_config_val, dict) else {},
            }
            return prepared_inputs
        except ValueError as e_prep_val:
            self._log_error("Preparation for project review failed due to missing/invalid data: %s", e_prep_val)
            return {"skip": True, "reason": f"Data preparation error: {e_prep_val!s}"}
        except (KeyError, TypeError) as e_struct:
            self._log_error("Error accessing config structure during project review pre_execution: %s", e_struct)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct!s}"}

    def execution(self, prepared_inputs: ProjectReviewPreparedInputs) -> ProjectReviewExecutionResult:
        """Generate the project review using an LLM.

        If an `LlmApiError` occurs, it is re-raised to be handled by the `Node`'s
        retry logic (if configured). Other errors during validation or processing
        result in a fallback Markdown message being returned.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.
                             Expected to contain all necessary data for prompting the LLM.

        Returns:
            A string containing the Markdown content for the project review,
            or None if execution was skipped.

        Raises:
            LlmApiError: If the LLM API call fails, to allow for retries.
        """
        if prepared_inputs.get("skip", True):
            reason_val: Any = prepared_inputs.get("reason", "N/A")
            self._log_info("Skipping project review execution. Reason: %s", str(reason_val))
            return None

        project_name: str = prepared_inputs["project_name"]
        self._log_info("Generating project review for '%s' using LLM...", project_name)

        abstractions_data: "CodeAbstractionsList" = prepared_inputs["abstractions_data"]
        relationships_data: "CodeRelationshipsDict" = prepared_inputs["relationships_data"]
        files_data: "FilePathContentList" = prepared_inputs["files_data"]
        language: str = prepared_inputs["language"]
        llm_config: "ResolvedLlmConfigDict" = prepared_inputs["llm_config"]
        cache_config: "ResolvedCacheConfigDict" = prepared_inputs["cache_config"]

        prompt = ProjectReviewPrompts.format_project_review_prompt(
            project_name=project_name,
            abstractions_data=abstractions_data,
            relationships_data=relationships_data,
            files_data=files_data,
            language=language,
        )

        try:
            response_text = call_llm(prompt, llm_config, cache_config)
            validated_yaml_data = validate_yaml_dict(response_text, PROJECT_REVIEW_SCHEMA)
            markdown_content = self._format_review_yaml_to_markdown(validated_yaml_data, project_name)
            self._log_info("Successfully generated project review content.")
            return markdown_content
        except LlmApiError:
            self._log_error(
                "LLM call failed during project review generation. This error will be re-raised for retry/fallback."
            )
            raise
        except ValidationFailure as e_val:
            self._log_error("YAML validation failed for project review: %s", e_val)
            return f"# Project Review: {project_name}\n\n> AI-generated review validation failed: {e_val!s}"
        except (ValueError, TypeError, KeyError, AttributeError) as e_proc:  # More specific exceptions
            self._log_error("Unexpected error processing project review: %s", e_proc, exc_info=True)
            return f"# Project Review: {project_name}\n\n> Unexpected error generating review: {e_proc!s}"

    def execution_fallback(
        self, prepared_inputs: ProjectReviewPreparedInputs, exc: Exception
    ) -> ProjectReviewExecutionResult:
        """Handle fallback if all execution attempts for project review fail.

        This method is called by the parent `Node` class's retry mechanism if all
        attempts to call `self.execution()` (which internally calls the LLM) fail
        due to recoverable errors (like `LlmApiError`).

        Args:
            prepared_inputs: The data from the `pre_execution` phase, which was
                             passed to the failed `execution` attempts.
            exc: The exception that occurred during the final execution attempt
                 (typically an `LlmApiError`).

        Returns:
            A Markdown string indicating the failure to generate the project review.
        """
        project_name_val: Any = prepared_inputs.get("project_name", "Unknown Project")
        project_name: str = str(project_name_val)
        self._log_error(
            "All attempts to generate project review for '%s' failed. Last error: %s", project_name, exc, exc_info=True
        )
        return (
            f"# Project Review: {project_name}\n\n"
            f"> AI-generated review could not be created after multiple attempts. Error: {exc!s}"
        )

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: ProjectReviewPreparedInputs,
        execution_outputs: ProjectReviewExecutionResult,
    ) -> None:
        """Store the generated project review content in shared context.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from the `pre_execution` phase. Used here to
                             check if execution was skipped.
            execution_outputs: Markdown content of the project review, or None if
                               skipped, or an error string if generation failed.
        """
        if prepared_inputs.get("skip", True):
            shared_context["project_review_content"] = None
            self._log_info("Project review was skipped, 'project_review_content' set to None.")
            return

        shared_context["project_review_content"] = execution_outputs
        project_name_val: Any = prepared_inputs.get("project_name", "Unknown Project")
        project_name: str = str(project_name_val)
        error_message_start_heuristic = f"# Project Review: {project_name}\n\n> AI-generated review"

        if (
            execution_outputs
            and execution_outputs.strip()
            and not execution_outputs.startswith(error_message_start_heuristic)
        ):
            snippet = execution_outputs[:MAX_REVIEW_SNIPPET_LEN_LOG].replace("\n", " ")
            if len(execution_outputs) > MAX_REVIEW_SNIPPET_LEN_LOG:
                snippet += "..."
            self._log_info("Stored project review content in shared context (snippet: '%s').", snippet)
        elif execution_outputs:
            self._log_warning("Project review content from execution was an error message or empty. Stored as is.")
        else:
            self._log_warning("Project review content from execution was None. Stored None.")


# End of src/FL01_code_analysis/nodes/n09_generate_project_review.py
