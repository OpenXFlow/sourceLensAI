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
import math
import re
from typing import Any, Final, Optional, Union

from typing_extensions import TypeAlias

from sourcelens.nodes.base_node import BaseNode, SLSharedContext
from sourcelens.prompts.code._common import SequenceDiagramContext
from sourcelens.prompts.code.diagrams import (
    format_class_diagram_prompt,
    format_package_diagram_prompt,
    format_relationship_flowchart_prompt,
    format_sequence_diagram_prompt,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm

DiagramMarkup: TypeAlias = Optional[str]
SequenceDiagramsListInternal: TypeAlias = list[DiagramMarkup]

GenerateDiagramsPreparedInputs: TypeAlias = Optional[dict[str, Any]]
GenerateDiagramsExecutionResult: TypeAlias = dict[str, Union[DiagramMarkup, SequenceDiagramsListInternal]]

AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
RelationshipDetailInternal: TypeAlias = dict[str, Any]
RelationshipsDictInternal: TypeAlias = dict[str, Union[str, list[RelationshipDetailInternal]]]
FilesDataListInternal: TypeAlias = list[tuple[str, str]]
IdentifiedScenarioListInternal: TypeAlias = list[str]

LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]
DiagramGenerationConfigDict: TypeAlias = dict[str, Any]


module_logger: logging.Logger = logging.getLogger(__name__)

MAX_FILES_FOR_STRUCTURE_CONTEXT: Final[int] = 50
SCENARIO_NAME_MAX_WORDS: Final[int] = 5
DEFAULT_DIAGRAM_FORMAT_NODE: Final[str] = "mermaid"
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2
CODE_FENCE_REGEX: Final[re.Pattern[str]] = re.compile(r"^\s*```(?:\w+)?\s*\n|\n\s*```\s*$", re.MULTILINE)
LOG_MARKUP_SNIPPET_LEN: Final[int] = 150
DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5


class GenerateDiagramsNode(BaseNode[GenerateDiagramsPreparedInputs, GenerateDiagramsExecutionResult]):
    """Generate architectural diagrams using an LLM based on analyzed project data.

    This node takes various pieces of information from the `shared_context`
    (like abstractions, relationships, file structure, and identified scenarios)
    along with LLM and diagram configurations to generate different types of
    diagrams (e.g., relationship flowchart, class diagram, sequence diagrams).
    The generated diagram markups are then stored back into the `shared_context`.
    """

    def _get_structure_context(self, files_data: Optional[FilesDataListInternal]) -> str:
        """Prepare a string summarizing the project file structure for prompts.

        Args:
            files_data: A list of (filepath, content) tuples. Only filepaths are used.
                        Content is not used in this specific helper.

        Returns:
            A string summarizing the project file structure, suitable for inclusion
            in LLM prompts. Returns a placeholder if no file data is available.
        """
        if not files_data:
            return "No file data available to generate structure context."

        file_list_parts: list[str] = [
            f"- {path.replace(chr(92), '/')}"
            for i, (path, _) in enumerate(files_data)
            if i < MAX_FILES_FOR_STRUCTURE_CONTEXT
        ]
        if len(files_data) > MAX_FILES_FOR_STRUCTURE_CONTEXT:
            additional_files_count = len(files_data) - MAX_FILES_FOR_STRUCTURE_CONTEXT
            file_list_parts.append(f"- ... ({additional_files_count} more files)")

        if not file_list_parts:
            return "Project structure context is empty (no files after filtering)."
        return f"Project File Structure Overview:\n{chr(10).join(file_list_parts)}"

    def _prepare_diagram_flags_and_configs(
        self, shared_context: SLSharedContext
    ) -> tuple[DiagramGenerationConfigDict, LlmConfigDict, CacheConfigDict]:
        """Extract diagram generation flags and LLM/cache configurations from shared context.

        Args:
            shared_context: The shared context dictionary, expected to contain the
                            fully resolved configuration under the "config" key.

        Returns:
            A tuple containing:
                - diagram_generation_config (dict): The specific diagram generation settings.
                - llm_config (dict): The resolved LLM configuration for the current mode.
                - cache_config (dict): The common cache settings.

        Raises:
            ValueError: If the "config" key or essential sub-keys for diagram/LLM/cache
                        configuration are missing from `shared_context`.
        """
        resolved_config_val: Any = self._get_required_shared(shared_context, "config")
        resolved_config: dict[str, Any] = resolved_config_val if isinstance(resolved_config_val, dict) else {}

        current_operation_mode = str(shared_context.get("current_operation_mode", "code"))
        analysis_config_key = f"{current_operation_mode}_analysis"
        mode_specific_config_val: Any = resolved_config.get(analysis_config_key, {})
        mode_specific_config: dict[str, Any] = (
            mode_specific_config_val if isinstance(mode_specific_config_val, dict) else {}
        )

        diagram_gen_config_val: Any = mode_specific_config.get("diagram_generation", {})
        diagram_gen_config: DiagramGenerationConfigDict = (
            diagram_gen_config_val if isinstance(diagram_gen_config_val, dict) else {}
        )
        self._log_debug("Diagram generation config in _prepare_diagram_flags_and_configs: %s", diagram_gen_config)

        llm_config_val: Any = mode_specific_config.get("llm_config", {})
        llm_config: LlmConfigDict = llm_config_val if isinstance(llm_config_val, dict) else {}

        common_config_val: Any = resolved_config.get("common", {})
        common_config: dict[str, Any] = common_config_val if isinstance(common_config_val, dict) else {}
        cache_config_val: Any = common_config.get("cache_settings", {})
        cache_config: CacheConfigDict = cache_config_val if isinstance(cache_config_val, dict) else {}

        if not diagram_gen_config:
            self._log_warning(
                "Diagram generation configuration section not found in '%s'. Using defaults.", analysis_config_key
            )
        if not llm_config:
            raise ValueError(f"LLM configuration missing under '{analysis_config_key}.llm_config'.")
        if not cache_config:
            raise ValueError("Cache configuration missing under 'common.cache_settings'.")

        return diagram_gen_config, llm_config, cache_config

    def _gather_diagram_context_data(
        self,
        shared_context: SLSharedContext,
        diagram_gen_cfg: DiagramGenerationConfigDict,
        llm_cfg: LlmConfigDict,
        cache_cfg: CacheConfigDict,
    ) -> GenerateDiagramsPreparedInputs:
        """Gather all core context data required for generating diagrams.

        Args:
            shared_context: The shared context dictionary.
            diagram_gen_cfg: The resolved diagram generation configuration.
            llm_cfg: The resolved LLM configuration.
            cache_cfg: The resolved cache configuration.

        Returns:
            A dictionary suitable for `prepared_inputs` in the `execution` phase,
            or None if no diagrams are enabled according to `diagram_gen_cfg`.

        Raises:
            ValueError: If required shared data (like abstractions for enabled diagrams)
                        is missing from `shared_context`.
        """
        gen_flowchart = bool(diagram_gen_cfg.get("include_relationship_flowchart", False))
        gen_class = bool(diagram_gen_cfg.get("include_class_diagram", False))
        gen_pkg = bool(diagram_gen_cfg.get("include_package_diagram", False))

        seq_config_val: Any = diagram_gen_cfg.get("sequence_diagrams", {})
        seq_config: dict[str, Any] = seq_config_val if isinstance(seq_config_val, dict) else {}
        gen_seq = bool(seq_config.get("enabled", False))
        seq_max = int(seq_config.get("max_diagrams_to_generate", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY))
        diagram_format = str(diagram_gen_cfg.get("format", DEFAULT_DIAGRAM_FORMAT_NODE))

        self._log_debug(
            "Diagram flags: Flowchart=%s, Class=%s, Package=%s, Sequence=%s (Max=%d)",
            gen_flowchart,
            gen_class,
            gen_pkg,
            gen_seq,
            seq_max,
        )

        if not (gen_flowchart or gen_class or gen_pkg or gen_seq):
            self._log_info("All specific diagram types are disabled in resolved 'diagram_generation' config. Skipping.")
            return None

        project_name_any: Any = shared_context.get("project_name", "Unknown Project")
        project_name: str = str(project_name_any)

        abstractions: AbstractionsListInternal = []
        if gen_flowchart or gen_seq:
            abstractions_any_val: Any = self._get_required_shared(shared_context, "abstractions")
            abstractions = abstractions_any_val if isinstance(abstractions_any_val, list) else []

        relationships: RelationshipsDictInternal = {}
        if gen_flowchart:
            relationships_any_val: Any = self._get_required_shared(shared_context, "relationships")
            relationships = relationships_any_val if isinstance(relationships_any_val, dict) else {}

        files_data_for_context: Optional[FilesDataListInternal] = None
        structure_context_str: str = "File structure data was not available for diagram context."
        if gen_class or gen_pkg:
            files_data_val: Any = shared_context.get("files")
            if isinstance(files_data_val, list) and all(
                isinstance(t, tuple)
                and len(t) == EXPECTED_FILE_DATA_TUPLE_LENGTH
                and isinstance(t[0], str)
                and isinstance(t[1], str)
                for t in files_data_val
            ):
                files_data_for_context = files_data_val  # type: ignore[assignment]
                structure_context_str = self._get_structure_context(files_data_for_context)
            else:
                self._log_warning("Cannot generate structure_context: 'files' data missing or invalid.")

        scenarios_to_use: IdentifiedScenarioListInternal = []
        if gen_seq:
            scenarios_raw_any: Any = shared_context.get("identified_scenarios")
            raw_list: list[Any] = scenarios_raw_any if isinstance(scenarios_raw_any, list) else []
            scenarios_to_use = [str(s) for s in raw_list if isinstance(s, str) and s.strip()]
            if not scenarios_to_use:
                self._log_warning("Sequence diagrams enabled, but no valid scenarios found in shared_context.")

        prepared_inputs: dict[str, Any] = {
            "project_name": project_name,
            "abstractions": abstractions,
            "relationships": relationships,
            "structure_context": structure_context_str,
            "identified_scenarios": scenarios_to_use,
            "llm_config": llm_cfg,
            "cache_config": cache_cfg,
            "gen_flowchart": gen_flowchart,
            "gen_class": gen_class,
            "gen_pkg": gen_pkg,
            "gen_seq": gen_seq,
            "seq_max": seq_max,
            "diagram_format": diagram_format,
        }
        return prepared_inputs

    def pre_execution(self, shared_context: SLSharedContext) -> GenerateDiagramsPreparedInputs:
        """Prepare context and configuration flags for diagram generation.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary with prepared inputs if any diagram is to be generated,
            otherwise None to indicate skipping the execution phase.

        Raises:
            ValueError: If critical configuration or shared data is missing.
        """
        self._log_info("Preparing for diagram generation...")
        try:
            diagram_gen_cfg, llm_cfg, cache_cfg = self._prepare_diagram_flags_and_configs(shared_context)

            if not diagram_gen_cfg.get("enabled", False):
                self._log_info("Diagram generation is disabled via 'diagram_generation.enabled=false'. Skipping.")
                return None

            return self._gather_diagram_context_data(shared_context, diagram_gen_cfg, llm_cfg, cache_cfg)
        except ValueError as e_val:
            self._log_error("Error preparing diagram context (missing shared data or config): %s", e_val, exc_info=True)
            if "LLM configuration missing" in str(e_val) or "Cache configuration missing" in str(e_val):
                raise
            return None
        except (OSError, TypeError, KeyError) as e_prep:
            self._log_error("Error during diagram preparation: %s", e_prep, exc_info=True)
            return None

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
        llm_config: LlmConfigDict,
        cache_config: CacheConfigDict,
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

            if not markup:  # Check after cleaning
                self._log_warning("LLM returned empty response for %s diagram after cleaning.", diagram_type)
                return None

            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                log_msg_l1 = f"LLM {diagram_type} diagram markup missing expected start. "
                log_msg_l2 = f"Expected one of: {expected_keywords}. Received: '%.*s...'"
                self._log_warning(log_msg_l1 + log_msg_l2, LOG_MARKUP_SNIPPET_LEN, markup.replace("\n", " "))

            # Log final state of markup before returning
            if markup and markup.strip():
                self._logger.debug(
                    "Final valid markup for %s diagram (len %d): '%.*s...'",
                    diagram_type,
                    len(markup),
                    LOG_MARKUP_SNIPPET_LEN,
                    markup.replace("\n", " "),
                )
            else:
                self._logger.warning("Final markup for %s diagram is None or empty after all checks.", diagram_type)
                return None  # Ensure None is returned if it became empty after keywords check or was empty

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
            The diagram markup string, or None if generation fails.
        """
        abstractions: AbstractionsListInternal = prepared_inputs.get("abstractions", [])
        relationships: RelationshipsDictInternal = prepared_inputs.get("relationships", {})
        structure_ctx_val: Any = prepared_inputs.get("structure_context")
        structure_ctx: Optional[str] = str(structure_ctx_val) if isinstance(structure_ctx_val, str) else None

        llm_cfg: LlmConfigDict = prepared_inputs.get("llm_config", {})
        cache_cfg: CacheConfigDict = prepared_inputs.get("cache_config", {})
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT_NODE))

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
            The diagram markup string, or None if generation fails.
        """
        code_context_str = str(prepared_inputs.get("structure_context", "No code context available."))
        if not code_context_str or code_context_str == "File structure data was not available for diagram context.":
            self._log_warning("No proper code/structure context for class diagram. Diagram might be suboptimal.")

        llm_cfg: LlmConfigDict = prepared_inputs.get("llm_config", {})
        cache_cfg: CacheConfigDict = prepared_inputs.get("cache_config", {})
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT_NODE))

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
            The diagram markup string, or None if generation fails.
        """
        structure_context_str = str(prepared_inputs.get("structure_context", ""))
        if (
            not structure_context_str
            or structure_context_str == "File structure data was not available for diagram context."
            or structure_context_str == "No file data available to generate structure context."
        ):
            self._log_warning("Cannot generate package diagram: structure_context is missing or effectively empty.")
            return None

        llm_cfg: LlmConfigDict = prepared_inputs.get("llm_config", {})
        cache_cfg: CacheConfigDict = prepared_inputs.get("cache_config", {})
        diag_fmt: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT_NODE))

        return self._call_llm_for_diagram(
            prompt=format_package_diagram_prompt(
                project_name=str(prepared_inputs.get("project_name")),
                structure_context=structure_context_str,
                diagram_format=diag_fmt,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="package",
            expected_keywords=["graph TD", "graph LR"],
        )

    def _generate_sequence_diagrams(self, prepared_inputs: dict[str, Any]) -> SequenceDiagramsListInternal:
        """Generate sequence diagrams based on identified scenarios.

        Implements logic to attempt generating a minimum number of diagrams
        based on `ceil(max_diagrams_to_generate / 2.0)`.

        Args:
            prepared_inputs: The dictionary from the pre_execution phase.
                             Expected keys: "diagram_format", "identified_scenarios",
                             "seq_max", "llm_config", "cache_config", "project_name",
                             "abstractions", "relationships".

        Returns:
            A list of diagram markup strings (DiagramMarkup), where each element
            can be a string (successful generation) or None (failed generation).
            The list will contain entries for each scenario attempted up to "seq_max".
        """
        diagram_format: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT_NODE))
        self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: SequenceDiagramsListInternal = []

        scenarios: IdentifiedScenarioListInternal = prepared_inputs.get("identified_scenarios", [])
        config_max_diagrams: int = prepared_inputs.get("seq_max", 0)

        if config_max_diagrams <= 0:
            self._log_warning(
                "Max sequence diagrams is configured to %d in 'seq_max'. No sequence diagrams will be generated.",
                config_max_diagrams,
            )
            return []

        min_diagrams_to_attempt: int = math.ceil(config_max_diagrams / 2.0) if config_max_diagrams > 0 else 0

        llm_cfg: LlmConfigDict = prepared_inputs.get("llm_config", {})
        cache_cfg: CacheConfigDict = prepared_inputs.get("cache_config", {})
        scenarios_to_process = scenarios[:config_max_diagrams]

        if not scenarios_to_process:
            self._log_warning(
                "No scenarios available to generate sequence diagrams, though config allows for %d.",
                config_max_diagrams,
            )
            return []

        self._log_info(
            "Attempting to generate up to %d sequence diagrams from %d identified scenarios (aiming for at least %d).",
            config_max_diagrams,
            len(scenarios),
            min_diagrams_to_attempt,
        )

        num_successfully_generated = 0
        for i, scenario_desc in enumerate(scenarios_to_process):
            words = scenario_desc.split()
            scenario_name_short = " ".join(words[:SCENARIO_NAME_MAX_WORDS])
            if len(words) > SCENARIO_NAME_MAX_WORDS:
                scenario_name_short += "..."
            self._log_info(
                "Generating sequence diagram %d/%d: '%s'", i + 1, len(scenarios_to_process), scenario_name_short
            )
            abstractions_for_ctx: AbstractionsListInternal = prepared_inputs.get("abstractions", [])
            relationships_for_ctx: RelationshipsDictInternal = prepared_inputs.get("relationships", {})

            sequence_context_obj = SequenceDiagramContext(
                project_name=str(prepared_inputs.get("project_name")),
                scenario_name=scenario_name_short,
                scenario_description=scenario_desc,
                diagram_format=diagram_format,
                abstractions=abstractions_for_ctx,
                relationships=relationships_for_ctx,
            )
            markup: DiagramMarkup = self._call_llm_for_diagram(
                prompt=format_sequence_diagram_prompt(sequence_context_obj),
                llm_config=llm_cfg,
                cache_config=cache_cfg,
                diagram_type=f"sequence (scenario: {scenario_name_short})",
                expected_keywords=["sequenceDiagram"],
            )
            self._logger.debug(
                "Markup generated for scenario '%s': %s (is_empty_after_strip: %s)",
                scenario_name_short,
                "Exists" if markup else "None",
                not bool(markup.strip()) if markup else "N/A",
            )
            generated_seq_diagrams.append(markup)
            if markup and markup.strip():
                num_successfully_generated += 1
            elif i < min_diagrams_to_attempt:
                self._log_warning(
                    "Failed to generate a 'required' sequence diagram (attempt %d/%d for scenario: '%s'). "
                    "Minimum target: %d.",
                    i + 1,
                    len(scenarios_to_process),
                    scenario_name_short,
                    min_diagrams_to_attempt,
                )

        if num_successfully_generated < min_diagrams_to_attempt and scenarios_to_process:
            self._log_warning(
                "Generated only %d valid sequence diagram(s), which is less than the target minimum of %d.",
                num_successfully_generated,
                min_diagrams_to_attempt,
            )
        elif scenarios_to_process:
            self._log_info(
                "Generated %d valid sequence diagram(s) out of %d attempted (min target: %d).",
                num_successfully_generated,
                len(scenarios_to_process),
                min_diagrams_to_attempt,
            )
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
        if prepared_inputs is None:
            self._log_info("Diagram generation skipped as per preparation step.")
            return results

        prep_dict: dict[str, Any] = prepared_inputs

        if prep_dict.get("gen_flowchart"):
            results["relationship_flowchart_markup"] = self._generate_relationship_flowchart(prep_dict)
        if prep_dict.get("gen_class"):
            results["class_diagram_markup"] = self._generate_class_diagram(prep_dict)
        if prep_dict.get("gen_pkg"):
            results["package_diagram_markup"] = self._generate_package_diagram(prep_dict)
        if prep_dict.get("gen_seq"):
            seq_diagrams_result = self._generate_sequence_diagrams(prep_dict)
            results["sequence_diagrams_markup"] = seq_diagrams_result if isinstance(seq_diagrams_result, list) else []
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
            prepared_inputs: Result from `pre_execution` (used to check if skipped).
            execution_outputs: Dictionary of diagram markups from `execution`.
        """
        if prepared_inputs is None:
            self._log_info("Diagram generation was skipped; no updates to shared_context for diagrams.")
            shared_context.setdefault("relationship_flowchart_markup", None)
            shared_context.setdefault("class_diagram_markup", None)
            shared_context.setdefault("package_diagram_markup", None)
            shared_context.setdefault("sequence_diagrams_markup", [])
            return

        updated_keys: list[str] = []
        if not isinstance(execution_outputs, dict):
            msg = (
                f"No diagram results or unexpected type ({type(execution_outputs).__name__}) from execution. "
                "Shared context not updated for diagrams."
            )
            self._log_warning(msg)
            return

        for key, value in execution_outputs.items():
            shared_context[key] = value
            is_valid_str_markup = isinstance(value, str) and value.strip()
            seq_markup_list = value if key == "sequence_diagrams_markup" and isinstance(value, list) else None
            is_valid_list_markup = (
                seq_markup_list is not None
                and all(isinstance(item, (str, type(None))) for item in seq_markup_list)
                and any(isinstance(item, str) and item.strip() for item in seq_markup_list)
            )

            if is_valid_str_markup or is_valid_list_markup:
                updated_keys.append(key)
            elif key in execution_outputs:
                self._log_info("Diagram markup for '%s' was None or empty. Shared context updated accordingly.", key)

        if updated_keys:
            self._log_info("Stored diagram generation results in shared context for keys: %s", sorted(updated_keys))
        else:
            self._log_info(
                "No valid diagram markups were produced to significantly update shared context, "
                "or all diagram types were disabled."
            )


# End of src/sourcelens/nodes/code/n06_generate_diagrams.py
