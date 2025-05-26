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

"""Node responsible for generating architectural diagrams using an LLM."""

import logging
import re
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

from sourcelens.prompts._common import SequenceDiagramContext
from sourcelens.prompts.diagrams import (
    format_class_diagram_prompt,
    format_package_diagram_prompt,
    format_relationship_flowchart_prompt,
    format_sequence_diagram_prompt,
)

# generate_file_structure_mermaid is used by GenerateSourceIndexNode, not directly here
from sourcelens.utils.llm_api import LlmApiError, call_llm

from .base_node import BaseNode, SLSharedContext  # Updated import

# Renamed Type Aliases
DiagramMarkup: TypeAlias = Optional[str]
SequenceDiagramsListInternal: TypeAlias = list[DiagramMarkup]  # Internal list of markups

GenerateDiagramsPreparedInputs: TypeAlias = Optional[dict[str, Any]]  # Can be None if skipped
"""Type alias for prepared inputs; None if diagram generation is skipped."""
GenerateDiagramsExecutionResult: TypeAlias = dict[str, Union[DiagramMarkup, SequenceDiagramsListInternal]]
"""Type alias for execution result: dict of diagram markups."""


# Internal type consistency
AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
RelationshipDetailInternal: TypeAlias = dict[str, Any]
RelationshipsDictInternal: TypeAlias = dict[str, Union[str, list[RelationshipDetailInternal]]]
FilesDataListInternal: TypeAlias = list[tuple[str, str]]  # Assumes content is always str
IdentifiedScenarioListInternal: TypeAlias = list[str]
LlmConfigDictInternal: TypeAlias = dict[str, Any]
CacheConfigDictInternal: TypeAlias = dict[str, Any]


module_logger: logging.Logger = logging.getLogger(__name__)

MAX_FILES_FOR_STRUCTURE_CONTEXT: Final[int] = 50
SCENARIO_NAME_MAX_WORDS: Final[int] = 5
DEFAULT_DIAGRAM_FORMAT: Final[str] = "mermaid"
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2
CODE_FENCE_REGEX: Final[re.Pattern[str]] = re.compile(r"^\s*```(?:\w+)?\s*\n|\n\s*```\s*$", re.MULTILINE)
LOG_MARKUP_SNIPPET_LEN: Final[int] = 150


class GenerateDiagramsNode(BaseNode[GenerateDiagramsPreparedInputs, GenerateDiagramsExecutionResult]):
    """Generate architectural diagrams using an LLM based on analyzed project data."""

    def _get_structure_context(self, files_data: Optional[FilesDataListInternal]) -> str:
        """Prepare a string summarizing the project file structure.

        Args:
            files_data: List of (filepath, content) tuples. Content is not used.

        Returns:
            A string summarizing the project file structure for prompts.
        """
        if not files_data:
            return "No file data available to generate structure context."

        file_list_parts: list[str] = [
            f"- {path.replace(chr(92), '/')}"  # Normalize path separators
            for i, (path, _) in enumerate(files_data)
            if i < MAX_FILES_FOR_STRUCTURE_CONTEXT
        ]
        if len(files_data) > MAX_FILES_FOR_STRUCTURE_CONTEXT:
            additional_files_count = len(files_data) - MAX_FILES_FOR_STRUCTURE_CONTEXT
            file_list_parts.append(f"- ... ({additional_files_count} more files)")

        if not file_list_parts:
            return "Project structure context is empty (no files after filtering)."
        return f"Project File Structure Overview:\n{chr(10).join(file_list_parts)}"

    def _prepare_diagram_flags_and_configs(self, shared_context: SLSharedContext) -> dict[str, Any]:
        """Extract diagram generation flags and LLM/cache configurations from shared context.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing boolean flags for each diagram type and LLM/cache configs.
        """
        config_any: Any = self._get_required_shared(shared_context, "config")
        config: dict[str, Any] = config_any if isinstance(config_any, dict) else {}
        output_config_any: Any = config.get("output", {})
        output_config: dict[str, Any] = output_config_any if isinstance(output_config_any, dict) else {}
        diagram_config_raw: Any = output_config.get("diagram_generation", {})
        diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}

        llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
        cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")
        llm_config: LlmConfigDictInternal = llm_config_val if isinstance(llm_config_val, dict) else {}
        cache_config: CacheConfigDictInternal = cache_config_val if isinstance(cache_config_val, dict) else {}

        flags_and_configs: dict[str, Any] = {
            "gen_flowchart": bool(diagram_config.get("include_relationship_flowchart", False)),
            "gen_class": bool(diagram_config.get("include_class_diagram", False)),
            "gen_pkg": bool(diagram_config.get("include_package_diagram", False)),
            "llm_config": llm_config,
            "cache_config": cache_config,
            "diagram_format": str(diagram_config.get("format", DEFAULT_DIAGRAM_FORMAT)),
        }

        seq_config_raw: Any = diagram_config.get("include_sequence_diagrams", {})
        seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}
        flags_and_configs["gen_seq"] = bool(seq_config.get("enabled", False))
        flags_and_configs["seq_max"] = int(seq_config.get("max_diagrams", 5))
        return flags_and_configs

    def _gather_diagram_context_data(
        self, shared_context: SLSharedContext, flags_configs: dict[str, Any]
    ) -> GenerateDiagramsPreparedInputs:  # Return type changed
        """Gather all core context data required for generating diagrams.

        Args:
            shared_context: The shared context dictionary.
            flags_configs: Dictionary of diagram flags and LLM/cache configurations.

        Returns:
            A dictionary suitable for `prepared_inputs` in the `execution` phase.
        """
        project_name_any: Any = shared_context.get("project_name", "Unknown Project")
        project_name: str = str(project_name_any)

        abstractions: AbstractionsListInternal = []
        if flags_configs.get("gen_flowchart") or flags_configs.get("gen_seq"):
            abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
            abstractions = abstractions_any if isinstance(abstractions_any, list) else []

        relationships: RelationshipsDictInternal = {}
        if flags_configs.get("gen_flowchart"):
            relationships_any: Any = self._get_required_shared(shared_context, "relationships")
            relationships = relationships_any if isinstance(relationships_any, dict) else {}

        files_data_val: Any = shared_context.get("files")
        files_data_for_context: Optional[FilesDataListInternal] = None
        if isinstance(files_data_val, list) and all(
            isinstance(t, tuple)
            and len(t) == EXPECTED_FILE_DATA_TUPLE_LENGTH
            and isinstance(t[0], str)
            and isinstance(t[1], str)  # Assuming content, if present, is string
            for t in files_data_val
        ):
            files_data_for_context = files_data_val  # type: ignore[assignment]
        elif files_data_val is not None:
            self._log_warning("Invalid 'files' data structure. Expected list of (str, str) tuples.")

        structure_context_str: str = ""
        needs_structure_context = flags_configs.get("gen_pkg") or flags_configs.get("gen_class")
        if files_data_for_context and needs_structure_context:
            structure_context_str = self._get_structure_context(files_data_for_context)
        elif needs_structure_context and not files_data_for_context:
            self._log_warning("Cannot generate structure_context: 'files' data missing or invalid.")
            structure_context_str = "File structure data was not available."

        scenarios_to_use: IdentifiedScenarioListInternal = []
        if flags_configs.get("gen_seq"):
            identified_scenarios_raw_any: Any = shared_context.get("identified_scenarios")
            raw_list: list[Any] = identified_scenarios_raw_any if isinstance(identified_scenarios_raw_any, list) else []
            scenarios_to_use = [str(s) for s in raw_list if isinstance(s, str) and s.strip()]

            if not scenarios_to_use:
                self._log_warning("Sequence diagrams enabled, but no valid scenarios found.")

        prepared_inputs: dict[str, Any] = {  # Explicit dict type for clarity
            "project_name": project_name,
            "abstractions": abstractions,
            "relationships": relationships,
            "structure_context": structure_context_str,
            # "files_data_for_class_pkg" was ambiguous, structure_context is what's used
            "identified_scenarios": scenarios_to_use,
            "llm_config": flags_configs["llm_config"],
            "cache_config": flags_configs["cache_config"],
            "gen_flowchart": flags_configs["gen_flowchart"],
            "gen_class": flags_configs["gen_class"],
            "gen_pkg": flags_configs["gen_pkg"],
            "gen_seq": flags_configs["gen_seq"],
            "seq_max": flags_configs["seq_max"],
            "diagram_format": flags_configs["diagram_format"],
        }
        return prepared_inputs

    def pre_execution(self, shared_context: SLSharedContext) -> GenerateDiagramsPreparedInputs:
        """Prepare context and configuration flags for diagram generation.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary with prepared inputs if any diagram is to be generated,
            otherwise None to indicate skipping the execution phase.
        """
        self._log_info("Preparing for diagram generation...")
        try:
            flags_and_configs = self._prepare_diagram_flags_and_configs(shared_context)
            # Check if any gen_ flag is true
            if not any(flags_and_configs.get(k) for k in flags_and_configs if k.startswith("gen_")):
                self._log_info("All diagram types are disabled. Skipping diagram generation.")
                return None  # Indicate skip
            return self._gather_diagram_context_data(shared_context, flags_and_configs)
        except ValueError as e_val:  # From _get_required_shared
            self._log_error("Error preparing diagram context (missing shared data): %s", e_val, exc_info=True)
            raise  # Propagate critical error
        except (OSError, TypeError, KeyError) as e_prep:  # Other prep errors
            self._log_error("Error during diagram preparation: %s", e_prep, exc_info=True)
            return None  # Indicate skip due to non-critical prep error

    def _clean_llm_diagram_output(self, raw_markup: str) -> str:
        """Clean the raw markup from LLM, removing potential code fences.

        Args:
            raw_markup: The raw string output from the LLM.

        Returns:
            Cleaned markup string.
        """
        return CODE_FENCE_REGEX.sub("", raw_markup).strip()

    def _call_llm_for_diagram(
        self,
        prompt: str,
        llm_config: LlmConfigDictInternal,
        cache_config: CacheConfigDictInternal,
        diagram_type: str,
        expected_keywords: Optional[list[str]] = None,
    ) -> DiagramMarkup:
        """Call LLM for diagram generation and validate the response.

        Args:
            prompt: The formatted prompt string for the LLM.
            llm_config: LLM API configuration.
            cache_config: LLM cache configuration.
            diagram_type: A string identifying the type of diagram for logging.
            expected_keywords: Optional list of keywords the markup should start with.

        Returns:
            The generated diagram markup as a string, or None on failure.
        """
        markup: DiagramMarkup = None
        try:
            markup_raw: str = call_llm(prompt, llm_config, cache_config)
            log_snippet_raw = markup_raw[:LOG_MARKUP_SNIPPET_LEN].replace("\n", " ")
            self._logger.debug(
                "Raw LLM response for %s diagram (len %d): '%.*s...'",
                diagram_type,
                len(markup_raw),
                LOG_MARKUP_SNIPPET_LEN,
                log_snippet_raw,
            )
            markup = self._clean_llm_diagram_output(markup_raw)
            log_snippet_clean = markup[:LOG_MARKUP_SNIPPET_LEN].replace("\n", " ")
            self._logger.debug(
                "Cleaned markup for %s diagram (len %d): '%.*s...'",
                diagram_type,
                len(markup),
                LOG_MARKUP_SNIPPET_LEN,
                log_snippet_clean,
            )

            if not markup:
                self._log_warning("LLM returned empty response for %s diagram after cleaning.", diagram_type)
                return None

            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                log_msg_l1 = f"LLM {diagram_type} diagram markup missing expected start. "
                log_msg_l2 = f"Expected one of: {expected_keywords}. Received: '%.*s...'"
                self._log_warning(log_msg_l1 + log_msg_l2, LOG_MARKUP_SNIPPET_LEN, markup.replace("\n", " "))

            self._log_info("Successfully generated %s diagram markup.", diagram_type)
            return markup
        except LlmApiError as e_llm:
            self._log_error("LLM API call failed for %s diagram: %s", diagram_type, e_llm, exc_info=True)
            return None
        except (ValueError, TypeError, AttributeError, IndexError) as e_other:
            self._log_error("Error processing LLM response for %s diagram: %s", diagram_type, e_other, exc_info=True)
            return None

    def _generate_relationship_flowchart(self, prepared_inputs: dict[str, Any]) -> DiagramMarkup:
        """Generate the relationship flowchart diagram.

        Args:
            prepared_inputs: The dictionary from the pre_execution phase.

        Returns:
            The diagram markup string, or None.
        """
        # Ensure type safety when accessing dictionary
        abstractions: AbstractionsListInternal = prepared_inputs.get("abstractions", [])  # type: ignore[assignment]
        relationships: RelationshipsDictInternal = prepared_inputs.get("relationships", {})  # type: ignore[assignment]
        structure_ctx: Optional[str] = str(prepared_inputs.get("structure_context")) or None

        llm_cfg: LlmConfigDictInternal = prepared_inputs.get("llm_config", {})  # type: ignore[assignment]
        cache_cfg: CacheConfigDictInternal = prepared_inputs.get("cache_config", {})  # type: ignore[assignment]
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_relationship_flowchart_prompt(
                project_name=str(prepared_inputs.get("project_name")),
                abstractions=abstractions,
                relationships=relationships,
                diagram_format=diag_fmt,
                structure_context=structure_ctx,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="relationship_flowchart",
            expected_keywords=["flowchart TD", "graph TD"],
        )

    def _generate_class_diagram(self, prepared_inputs: dict[str, Any]) -> DiagramMarkup:
        """Generate the class hierarchy diagram.

        Args:
            prepared_inputs: The dictionary from the pre_execution phase.

        Returns:
            The diagram markup string, or None.
        """
        code_context_str = str(prepared_inputs.get("structure_context", "No code context available."))
        if not code_context_str or code_context_str == "No file data available to generate structure context.":
            self._log_warning("No proper code/structure context for class diagram. Diagram might be suboptimal.")

        llm_cfg: LlmConfigDictInternal = prepared_inputs.get("llm_config", {})  # type: ignore[assignment]
        cache_cfg: CacheConfigDictInternal = prepared_inputs.get("cache_config", {})  # type: ignore[assignment]
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_class_diagram_prompt(
                project_name=str(prepared_inputs.get("project_name")),
                code_context=code_context_str,
                diagram_format=diag_fmt,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="class",
            expected_keywords=["classDiagram"],
        )

    def _generate_package_diagram(self, prepared_inputs: dict[str, Any]) -> DiagramMarkup:
        """Generate the package dependency diagram.

        Args:
            prepared_inputs: The dictionary from the pre_execution phase.

        Returns:
            The diagram markup string, or None.
        """
        structure_context_str = str(prepared_inputs.get("structure_context", ""))
        if (
            not structure_context_str
            or structure_context_str == "No file data available to generate structure context."
        ):
            self._log_warning("Cannot generate package diagram: structure_context is missing or empty.")
            return None

        llm_cfg: LlmConfigDictInternal = prepared_inputs.get("llm_config", {})  # type: ignore[assignment]
        cache_cfg: CacheConfigDictInternal = prepared_inputs.get("cache_config", {})  # type: ignore[assignment]
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_package_diagram_prompt(
                project_name=str(prepared_inputs.get("project_name")),
                structure_context=structure_context_str,
                diagram_format=diag_fmt,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="package",
            expected_keywords=["graph TD"],  # Mermaid package typically uses graph
        )

    def _generate_sequence_diagrams(self, prepared_inputs: dict[str, Any]) -> SequenceDiagramsListInternal:
        """Generate sequence diagrams based on identified scenarios.

        Args:
            prepared_inputs: The dictionary from the pre_execution phase.

        Returns:
            A list of diagram markup strings, with None for failed diagrams.
        """
        diagram_format: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))
        self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: SequenceDiagramsListInternal = []

        scenarios: IdentifiedScenarioListInternal = prepared_inputs.get("identified_scenarios", [])  # type: ignore[assignment]
        max_diagrams_to_generate: int = prepared_inputs.get("seq_max", 0)  # type: ignore[assignment]
        llm_cfg: LlmConfigDictInternal = prepared_inputs.get("llm_config", {})  # type: ignore[assignment]
        cache_cfg: CacheConfigDictInternal = prepared_inputs.get("cache_config", {})  # type: ignore[assignment]

        scenarios_to_process = scenarios[:max_diagrams_to_generate]

        if not scenarios_to_process:
            self._log_warning("No scenarios available or 'seq_max' is 0. No sequence diagrams generated.")
            return []

        log_msg = (
            f"Attempting to generate up to {max_diagrams_to_generate} sequence diagrams "
            f"from {len(scenarios)} scenarios."
        )
        self._log_info(log_msg)

        for i, scenario_desc in enumerate(scenarios_to_process):
            words = scenario_desc.split()
            scenario_name_short = " ".join(words[:SCENARIO_NAME_MAX_WORDS])
            if len(words) > SCENARIO_NAME_MAX_WORDS:
                scenario_name_short += "..."
            self._log_info(
                "Generating sequence diagram %d/%d: '%s'", i + 1, len(scenarios_to_process), scenario_name_short
            )
            # Abstractions and relationships from prepared_inputs can be passed if needed by SequenceDiagramContext
            abstractions_for_ctx: AbstractionsListInternal = prepared_inputs.get("abstractions", [])  # type: ignore[assignment]
            relationships_for_ctx: RelationshipsDictInternal = prepared_inputs.get("relationships", {})  # type: ignore[assignment]

            sequence_context_obj = SequenceDiagramContext(
                project_name=str(prepared_inputs.get("project_name")),
                scenario_name=scenario_name_short,
                scenario_description=scenario_desc,
                diagram_format=diagram_format,
                abstractions=abstractions_for_ctx,  # Pass if needed
                relationships=relationships_for_ctx,  # Pass if needed
            )
            markup: DiagramMarkup = self._call_llm_for_diagram(
                prompt=format_sequence_diagram_prompt(sequence_context_obj),
                llm_config=llm_cfg,
                cache_config=cache_cfg,
                diagram_type=f"sequence (scenario: {scenario_name_short})",
                expected_keywords=["sequenceDiagram"],
            )
            generated_seq_diagrams.append(markup)

        valid_diagrams_count = sum(1 for d in generated_seq_diagrams if d is not None and d.strip())
        if valid_diagrams_count == 0 and scenarios_to_process:
            self._log_warning("No sequence diagrams were generated successfully despite available scenarios.")
        else:
            self._log_info("Generated %d valid sequence diagram(s).", valid_diagrams_count)
        return generated_seq_diagrams

    def execution(self, prepared_inputs: GenerateDiagramsPreparedInputs) -> GenerateDiagramsExecutionResult:
        """Generate diagrams based on prepared context and configuration flags.

        Args:
            prepared_inputs: The dictionary from `pre_execution`, or None if skipped.

        Returns:
            A dictionary containing the markup for each generated diagram type.
            Values will be None if a diagram was not generated or failed.
        """
        results: GenerateDiagramsExecutionResult = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],
        }
        if prepared_inputs is None:  # Indicates skipping
            self._log_info("Diagram generation skipped as per preparation step.")
            return results

        # Type assertion: prepared_inputs is now known to be a dict
        prep_dict: dict[str, Any] = prepared_inputs

        if prep_dict.get("gen_flowchart"):
            results["relationship_flowchart_markup"] = self._generate_relationship_flowchart(prep_dict)
        if prep_dict.get("gen_class"):
            results["class_diagram_markup"] = self._generate_class_diagram(prep_dict)
        if prep_dict.get("gen_pkg"):
            results["package_diagram_markup"] = self._generate_package_diagram(prep_dict)
        if prep_dict.get("gen_seq"):
            results["sequence_diagrams_markup"] = self._generate_sequence_diagrams(prep_dict)
        return results

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: GenerateDiagramsPreparedInputs,
        execution_outputs: GenerateDiagramsExecutionResult,
    ) -> None:
        """Update shared context with generated diagram markups.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from `pre_execution` (unused here).
            execution_outputs: Dictionary of diagram markups from `execution`.
        """
        del prepared_inputs  # Mark as unused
        updated_keys: list[str] = []
        if not isinstance(execution_outputs, dict):
            msg = (
                f"No diagram results or unexpected type ({type(execution_outputs).__name__}) from execution. "
                "Shared context not updated for diagrams."
            )
            self._log_warning(msg)
            return

        for key, value in execution_outputs.items():
            is_valid_str_markup = isinstance(value, str) and value.strip()
            # Ensure value is treated as list only if it's the specific key and actually a list
            seq_markup_list = value if key == "sequence_diagrams_markup" and isinstance(value, list) else None
            is_valid_list_markup = (
                seq_markup_list is not None
                and all(isinstance(item, (str, type(None))) for item in seq_markup_list)
                and any(isinstance(item, str) and item.strip() for item in seq_markup_list)
            )

            if is_valid_str_markup or is_valid_list_markup:
                shared_context[key] = value
                updated_keys.append(key)
            # Handle cases where a diagram type was meant to be generated but failed (value is None or empty list)
            # Ensure the key exists in shared_context with a default empty value if it was attempted.
            elif key in execution_outputs:  # Key was attempted by exec phase
                shared_context[key] = [] if key == "sequence_diagrams_markup" else None
                self._log_info("Diagram for '%s' was None or empty, key set/updated in shared context.", key)

        if updated_keys:
            self._log_info("Stored diagram generation results in shared context for keys: %s", sorted(updated_keys))
        else:
            attempted_diagram_keys = {
                "relationship_flowchart_markup",
                "class_diagram_markup",
                "package_diagram_markup",
                "sequence_diagrams_markup",
            }
            any_attempt_failed_or_empty = False
            for k_diag in attempted_diagram_keys:
                if k_diag in execution_outputs:  # Diagram generation was part of exec_res
                    val_diag = execution_outputs[k_diag]
                    is_empty_list = isinstance(val_diag, list) and not any(
                        v for v in val_diag if isinstance(v, str) and v.strip()
                    )
                    if val_diag is None or is_empty_list:
                        any_attempt_failed_or_empty = True
                        break
            if any_attempt_failed_or_empty:
                self._log_info(
                    "Some diagram generation was attempted but resulted in no valid markup. "
                    "Shared context reflects this."
                )
            else:  # This case means no diagram generation was attempted (all gen_ flags were false in prep_res)
                # or an unexpected structure of execution_outputs.
                self._log_info("No diagram generation attempted or no valid markups produced to update context.")


# End of src/sourcelens/nodes/n06_generate_diagrams.py
