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
from typing import Any, Final, Optional, Union, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.mermaid_diagrams.class_diagram_prompts import format_class_diagram_prompt
from sourcelens.mermaid_diagrams.package_diagram_prompts import format_package_diagram_prompt
from sourcelens.mermaid_diagrams.sequence_diagram_prompts import (
    format_sequence_diagram_prompt,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm

from ..prompts._common import (
    CodeAbstractionsList,
    CodeRelationshipsDict,
    SequenceDiagramContext,
)

DiagramMarkup: TypeAlias = Optional[str]
SequenceDiagramsListInternal: TypeAlias = list[DiagramMarkup]


GenerateDiagramsPreparedInputs: TypeAlias = Optional[dict[str, Any]]
GenerateDiagramsExecutionResult: TypeAlias = dict[str, Union[DiagramMarkup, SequenceDiagramsListInternal]]

FilesDataListInternal: TypeAlias = list[tuple[str, str]]
IdentifiedScenarioListInternal: TypeAlias = list[str]

LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]
DiagramGenerationConfigDict: TypeAlias = dict[str, Any]
SequenceDiagramConfigDict: TypeAlias = dict[str, Any]

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
            files_data (Optional[FilesDataListInternal]): A list of (filepath, content) tuples.
                                                          Only filepaths are used.

        Returns:
            str: A string summarizing the project file structure, suitable for inclusion
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
            shared_context (SLSharedContext): The shared context dictionary.

        Returns:
            tuple[DiagramGenerationConfigDict, LlmConfigDict, CacheConfigDict]:
                A tuple containing the diagram generation settings, resolved LLM configuration,
                and common cache settings.

        Raises:
            ValueError: If essential configuration is missing.
        """
        resolved_config_val: Any = self._get_required_shared(shared_context, "config")
        resolved_config: dict[str, Any] = cast(dict[str, Any], resolved_config_val)

        current_operation_mode = str(shared_context.get("current_operation_mode", "code"))
        flow_specific_config_val: Any = resolved_config.get(current_operation_mode, {})
        flow_specific_config: dict[str, Any] = cast(dict[str, Any], flow_specific_config_val)

        diagram_gen_config_val: Any = flow_specific_config.get("diagram_generation", {})
        diagram_gen_config: DiagramGenerationConfigDict = cast(DiagramGenerationConfigDict, diagram_gen_config_val)
        self._log_debug("Diagram generation config in _prepare_diagram_flags_and_configs: %s", diagram_gen_config)

        llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
        llm_config: LlmConfigDict = cast(LlmConfigDict, llm_config_val)

        cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")
        cache_config: CacheConfigDict = cast(CacheConfigDict, cache_config_val)

        if not diagram_gen_config:
            self._log_warning(
                "Diagram generation configuration section not found under flow config '%s'. "
                "Diagrams might be disabled or use defaults.",
                current_operation_mode,
            )
        if not llm_config:
            raise ValueError("Resolved 'llm_config' missing in shared_context.")
        if not cache_config:
            raise ValueError("Resolved 'cache_config' missing in shared_context.")

        return diagram_gen_config, llm_config, cache_config

    def _gather_diagram_context_data(
        self,
        shared_context: SLSharedContext,
        diagram_gen_cfg: DiagramGenerationConfigDict,
        llm_cfg: LlmConfigDict,
        cache_cfg: CacheConfigDict,
    ) -> GenerateDiagramsPreparedInputs:
        """Gather all core context data required for generating diagrams."""
        gen_flowchart = bool(diagram_gen_cfg.get("include_relationship_flowchart", False))
        gen_class = bool(diagram_gen_cfg.get("include_class_diagram", False))
        gen_pkg = bool(diagram_gen_cfg.get("include_package_diagram", False))

        seq_config_val: Any = diagram_gen_cfg.get("sequence_diagrams", {})
        seq_config: SequenceDiagramConfigDict = cast(SequenceDiagramConfigDict, seq_config_val)
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
            self._log_info("All specific diagram types are disabled in 'diagram_generation' config. Skipping.")
            return None

        project_name_any: Any = shared_context.get("project_name", "Unknown Project")
        project_name: str = str(project_name_any)

        abstractions_val: Any = self._get_required_shared(shared_context, "abstractions")
        abstractions: CodeAbstractionsList = cast(CodeAbstractionsList, abstractions_val)

        relationships_val: Any = self._get_required_shared(shared_context, "relationships")
        relationships: CodeRelationshipsDict = cast(CodeRelationshipsDict, relationships_val)

        files_data_for_context: Optional[FilesDataListInternal] = None
        structure_context_str: str = "File structure data was not available for diagram context."
        files_data_val: Any = shared_context.get("files")
        if isinstance(files_data_val, list) and all(
            isinstance(t, tuple)
            and len(t) == EXPECTED_FILE_DATA_TUPLE_LENGTH
            and isinstance(t[0], str)
            and (isinstance(t[1], str) or t[1] is None)
            for t in files_data_val
        ):
            valid_files_for_structure: FilesDataListInternal = [
                (path, content if content is not None else "") for path, content in files_data_val if path
            ]
            if valid_files_for_structure:
                files_data_for_context = valid_files_for_structure
                structure_context_str = self._get_structure_context(files_data_for_context)
        if not files_data_for_context:
            self._log_warning("Cannot generate structure_context: 'files' data missing, invalid, or empty.")

        scenarios_to_use: IdentifiedScenarioListInternal = []
        if gen_seq:
            scenarios_raw_any: Any = shared_context.get("identified_scenarios")
            raw_list: list[Any] = cast(list[Any], scenarios_raw_any) if isinstance(scenarios_raw_any, list) else []
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
        """Prepare context and configuration flags for diagram generation."""
        self._log_info("Preparing for diagram generation...")
        try:
            diagram_gen_cfg, llm_cfg, cache_cfg = self._prepare_diagram_flags_and_configs(shared_context)

            if not diagram_gen_cfg.get("enabled", False):
                self._log_info("Diagram generation is disabled via 'diagram_generation.enabled=false'. Skipping.")
                return None

            return self._gather_diagram_context_data(shared_context, diagram_gen_cfg, llm_cfg, cache_cfg)
        except ValueError as e_val:
            self._log_error("Error preparing diagram context (missing shared data or config): %s", e_val, exc_info=True)
            if "llm_config' missing" in str(e_val) or "'cache_config' missing" in str(e_val):
                raise
            return None
        except (OSError, TypeError, KeyError) as e_prep:  # pragma: no cover
            self._log_error("Error during diagram preparation: %s", e_prep, exc_info=True)
            return None

    def _clean_llm_diagram_output(self, raw_markup: str) -> str:
        """Clean the raw markup from LLM, removing potential code fences."""
        return CODE_FENCE_REGEX.sub("", raw_markup).strip()

    def _call_llm_for_diagram(
        self,
        prompt: str,
        llm_config: LlmConfigDict,
        cache_config: CacheConfigDict,
        diagram_type: str,
        expected_keywords: Optional[list[str]] = None,
    ) -> DiagramMarkup:
        """Call LLM for diagram generation and validate the response."""
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
                log_msg_l2_part1 = f"Expected one of: {expected_keywords}. "
                log_msg_l2_part2 = "Received: '%.*s...'"
                self._log_warning(
                    log_msg_l1 + log_msg_l2_part1 + log_msg_l2_part2, LOG_MARKUP_SNIPPET_LEN, markup.replace("\n", " ")
                )

            if markup and markup.strip():
                self._logger.debug(
                    "Final valid markup for %s diagram (len %d): '%.*s...'",
                    diagram_type,
                    len(markup),
                    LOG_MARKUP_SNIPPET_LEN,
                    markup.replace("\n", " "),
                )
            else:  # pragma: no cover
                self._logger.warning("Final markup for %s diagram is None or empty after all checks.", diagram_type)
                return None

            self._log_info("Successfully generated %s diagram markup.", diagram_type)
            return markup
        except LlmApiError as e_llm:  # pragma: no cover
            self._log_error("LLM API call failed for %s diagram: %s", diagram_type, e_llm, exc_info=True)
            return None
        except (ValueError, TypeError, AttributeError, IndexError) as e_other:  # pragma: no cover
            self._log_error("Error processing LLM response for %s diagram: %s", diagram_type, e_other, exc_info=True)
            return None

    def _generate_relationship_flowchart(self, prepared_inputs: dict[str, Any]) -> DiagramMarkup:
        """Generate the relationship flowchart diagram."""
        from sourcelens.mermaid_diagrams.relationship_flowchart_prompts import (
            format_relationship_flowchart_prompt,
        )

        abstractions: CodeAbstractionsList = cast(CodeAbstractionsList, prepared_inputs.get("abstractions", []))
        relationships: CodeRelationshipsDict = cast(CodeRelationshipsDict, prepared_inputs.get("relationships", {}))
        structure_ctx_val: Any = prepared_inputs.get("structure_context")
        structure_ctx: Optional[str] = str(structure_ctx_val) if isinstance(structure_ctx_val, str) else None

        llm_cfg: LlmConfigDict = cast(LlmConfigDict, prepared_inputs.get("llm_config", {}))
        cache_cfg: CacheConfigDict = cast(CacheConfigDict, prepared_inputs.get("cache_config", {}))
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
        """Generate the class hierarchy diagram."""
        code_context_str = str(prepared_inputs.get("structure_context", "No code context available."))
        if not code_context_str or code_context_str == "File structure data was not available for diagram context.":
            self._log_warning("No proper code/structure context for class diagram. Diagram might be suboptimal.")

        llm_cfg: LlmConfigDict = cast(LlmConfigDict, prepared_inputs.get("llm_config", {}))
        cache_cfg: CacheConfigDict = cast(CacheConfigDict, prepared_inputs.get("cache_config", {}))
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
        """Generate the package dependency diagram."""
        structure_context_str = str(prepared_inputs.get("structure_context", ""))
        empty_context_placeholders = {
            "File structure data was not available for diagram context.",
            "No file data available to generate structure context.",
            "Project structure context is empty (no files after filtering).",
        }
        if not structure_context_str or structure_context_str in empty_context_placeholders:
            self._log_warning("Cannot generate package diagram: structure_context is missing or effectively empty.")
            return None

        llm_cfg: LlmConfigDict = cast(LlmConfigDict, prepared_inputs.get("llm_config", {}))
        cache_cfg: CacheConfigDict = cast(CacheConfigDict, prepared_inputs.get("cache_config", {}))
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
        """Generate sequence diagrams based on identified scenarios."""
        diagram_format: str = str(prepared_inputs.get("diagram_format", DEFAULT_DIAGRAM_FORMAT_NODE))
        self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: SequenceDiagramsListInternal = []

        scenarios: IdentifiedScenarioListInternal = cast(
            IdentifiedScenarioListInternal, prepared_inputs.get("identified_scenarios", [])
        )
        config_max_diagrams: int = cast(int, prepared_inputs.get("seq_max", 0))

        if config_max_diagrams <= 0:
            self._log_warning(
                "Max sequence diagrams is %d. No sequence diagrams will be generated.", config_max_diagrams
            )
            return []

        min_diagrams_to_attempt: int = math.ceil(config_max_diagrams / 2.0) if config_max_diagrams > 0 else 0
        llm_cfg: LlmConfigDict = cast(LlmConfigDict, prepared_inputs.get("llm_config", {}))
        cache_cfg: CacheConfigDict = cast(CacheConfigDict, prepared_inputs.get("cache_config", {}))
        scenarios_to_process = scenarios[:config_max_diagrams]

        if not scenarios_to_process:
            self._log_warning("No scenarios to generate sequence diagrams (config allows %d).", config_max_diagrams)
            return []

        self._log_info(
            "Attempting up to %d sequence diagrams from %d scenarios (min target: %d).",
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
            abstractions_for_ctx: CodeAbstractionsList = cast(
                CodeAbstractionsList, prepared_inputs.get("abstractions", [])
            )
            relationships_for_ctx: CodeRelationshipsDict = cast(
                CodeRelationshipsDict, prepared_inputs.get("relationships", {})
            )

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
            generated_seq_diagrams.append(markup)
            if markup and markup.strip():
                num_successfully_generated += 1
            elif i < min_diagrams_to_attempt:  # pragma: no cover
                self._log_warning(
                    "Failed required sequence diagram %d/%d for '%s'. Min target: %d.",
                    i + 1,
                    len(scenarios_to_process),
                    scenario_name_short,
                    min_diagrams_to_attempt,
                )
        if num_successfully_generated < min_diagrams_to_attempt and scenarios_to_process:  # pragma: no cover
            self._log_warning(
                "Generated only %d valid sequence diagrams (min target: %d).",
                num_successfully_generated,
                min_diagrams_to_attempt,
            )
        elif scenarios_to_process:
            self._log_info(
                "Generated %d valid sequence diagrams out of %d attempted (min target: %d).",
                num_successfully_generated,
                len(scenarios_to_process),
                min_diagrams_to_attempt,
            )
        return generated_seq_diagrams

    def execution(self, prepared_inputs: GenerateDiagramsPreparedInputs) -> GenerateDiagramsExecutionResult:
        """Generate diagrams based on prepared context and configuration flags."""
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
        """Update shared context with generated diagram markups."""
        if prepared_inputs is None:
            self._log_info("Diagram generation was skipped; no updates to shared_context for diagrams.")
            shared_context.setdefault("relationship_flowchart_markup", None)
            shared_context.setdefault("class_diagram_markup", None)
            shared_context.setdefault("package_diagram_markup", None)
            shared_context.setdefault("sequence_diagrams_markup", [])
            return

        updated_keys: list[str] = []
        if not isinstance(execution_outputs, dict):  # pragma: no cover
            self._log_warning("No diagram results or unexpected type from execution. Shared context not updated.")
            return

        for key, value in execution_outputs.items():
            shared_context[key] = value
            is_valid_str_markup = isinstance(value, str) and value.strip()
            seq_markup_list_candidate = value if key == "sequence_diagrams_markup" and isinstance(value, list) else None
            is_valid_list_markup = False
            if seq_markup_list_candidate is not None:
                actual_strings_in_list = [item for item in seq_markup_list_candidate if isinstance(item, str)]
                if all(isinstance(item, (str, type(None))) for item in seq_markup_list_candidate) and any(
                    item.strip() for item in actual_strings_in_list
                ):
                    is_valid_list_markup = True

            if is_valid_str_markup or is_valid_list_markup:
                updated_keys.append(key)
            elif key in execution_outputs:  # pragma: no cover
                self._log_info("Diagram markup for '%s' was None or empty. Shared context updated accordingly.", key)

        if updated_keys:
            self._log_info("Stored diagram generation results in shared context for keys: %s", sorted(updated_keys))
        else:  # pragma: no cover
            self._log_info("No valid diagram markups produced or all diagram types were disabled.")


# End of src/FL01_code_analysis/nodes/n06_generate_diagrams.py
