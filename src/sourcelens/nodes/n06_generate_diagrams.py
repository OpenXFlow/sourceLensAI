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
from sourcelens.utils.llm_api import LlmApiError, call_llm

from .base_node import BaseNode, SLSharedState

DiagramMarkup: TypeAlias = Optional[str]
SequenceDiagramsListInternal: TypeAlias = list[DiagramMarkup]
DiagramResultDict: TypeAlias = dict[str, Union[DiagramMarkup, SequenceDiagramsListInternal]]
PrepContext: TypeAlias = dict[str, Any]
GenerateDiagramsPrepResult: TypeAlias = Optional[PrepContext]
GenerateDiagramsExecResult: TypeAlias = DiagramResultDict

AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]
RelationshipDetail: TypeAlias = dict[str, Any]
RelationshipsDict: TypeAlias = dict[str, Union[str, list[RelationshipDetail]]]
FilesDataList: TypeAlias = list[tuple[str, str]]
IdentifiedScenarioList: TypeAlias = list[str]
LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]


module_logger: logging.Logger = logging.getLogger(__name__)

MAX_FILES_FOR_STRUCTURE_CONTEXT: Final[int] = 50
SCENARIO_NAME_MAX_WORDS: Final[int] = 5
DEFAULT_DIAGRAM_FORMAT: Final[str] = "mermaid"
EXPECTED_FILE_DATA_TUPLE_LENGTH: Final[int] = 2
CODE_FENCE_REGEX: Final[re.Pattern[str]] = re.compile(r"^\s*```(?:\w+)?\s*\n|\n\s*```\s*$", re.MULTILINE)
LOG_MARKUP_SNIPPET_LEN: Final[int] = 150


class GenerateDiagramsNode(BaseNode[GenerateDiagramsPrepResult, GenerateDiagramsExecResult]):
    """Generate architectural diagrams using an LLM."""

    def _get_structure_context(self, files_data: Optional[FilesDataList]) -> str:
        """Prepare a string summarizing the project file structure."""
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

    def _prepare_diagram_flags_and_configs(self, shared: SLSharedState) -> dict[str, Any]:
        """Extract diagram generation flags and LLM/cache configurations."""
        config_any: Any = self._get_required_shared(shared, "config")
        config: dict[str, Any] = config_any if isinstance(config_any, dict) else {}
        output_config_any: Any = config.get("output", {})
        output_config: dict[str, Any] = output_config_any if isinstance(output_config_any, dict) else {}
        diagram_config_raw: Any = output_config.get("diagram_generation", {})
        diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}

        llm_config_val: Any = self._get_required_shared(shared, "llm_config")
        cache_config_val: Any = self._get_required_shared(shared, "cache_config")
        llm_config: LlmConfigDict = llm_config_val if isinstance(llm_config_val, dict) else {}
        cache_config: CacheConfigDict = cache_config_val if isinstance(cache_config_val, dict) else {}

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

    def _gather_diagram_context_data(self, shared: SLSharedState, flags_configs: dict[str, Any]) -> PrepContext:
        """Gather all core context data required for generating diagrams."""
        project_name_any: Any = shared.get("project_name", "Unknown Project")
        project_name: str = str(project_name_any)

        abstractions: AbstractionsList = []
        if flags_configs.get("gen_flowchart") or flags_configs.get("gen_seq"):
            abstractions_any: Any = self._get_required_shared(shared, "abstractions")
            abstractions = abstractions_any if isinstance(abstractions_any, list) else []

        relationships: RelationshipsDict = {}
        if flags_configs.get("gen_flowchart"):
            relationships_any: Any = self._get_required_shared(shared, "relationships")
            relationships = relationships_any if isinstance(relationships_any, dict) else {}

        files_data_val: Any = shared.get("files")
        files_data_for_context: Optional[FilesDataList] = None
        if isinstance(files_data_val, list) and all(
            isinstance(t, tuple)
            and len(t) == EXPECTED_FILE_DATA_TUPLE_LENGTH
            and isinstance(t[0], str)
            and isinstance(t[1], str)
            for t in files_data_val
        ):
            files_data_for_context = files_data_val  # type: ignore[assignment]
        elif files_data_val is not None:
            self._log_warning("Invalid 'files' data structure in shared state. Expected list of (str, str) tuples.")

        structure_context_str: str = ""
        if files_data_for_context and (flags_configs.get("gen_pkg") or flags_configs.get("gen_class")):
            structure_context_str = self._get_structure_context(files_data_for_context)
        elif (flags_configs.get("gen_pkg") or flags_configs.get("gen_class")) and not files_data_for_context:
            self._log_warning("Cannot generate structure_context for diagrams: 'files' data missing or invalid.")
            structure_context_str = "File structure data was not available."

        scenarios_to_use: IdentifiedScenarioList = []
        if flags_configs.get("gen_seq"):
            identified_scenarios_raw_any: Any = shared.get("identified_scenarios")
            identified_scenarios_raw: list[Any] = (
                identified_scenarios_raw_any if isinstance(identified_scenarios_raw_any, list) else []
            )
            scenarios_to_use = [str(s) for s in identified_scenarios_raw if isinstance(s, str) and s.strip()]

            if not scenarios_to_use:
                self._log_warning("Sequence diagrams enabled, but no valid scenarios found.")

        prep_context: PrepContext = {
            "project_name": project_name,
            "abstractions": abstractions,
            "relationships": relationships,
            "structure_context": structure_context_str,
            "files_data_for_class_pkg": files_data_for_context,
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
        return prep_context

    def prep(self, shared: SLSharedState) -> GenerateDiagramsPrepResult:
        """Prepare context and configuration flags for diagram generation."""
        self._log_info("Preparing for diagram generation...")
        try:
            flags_and_configs = self._prepare_diagram_flags_and_configs(shared)
            if not any(
                flags_and_configs.get(k) for k in flags_and_configs if isinstance(k, str) and k.startswith("gen_")
            ):
                self._log_info("All diagram types are disabled. Skipping diagram generation.")
                return None
            return self._gather_diagram_context_data(shared, flags_and_configs)
        except ValueError as e_val:
            self._log_error("Error preparing diagram context (missing shared data): %s", e_val, exc_info=True)
            raise
        except (OSError, TypeError, KeyError) as e_prep:
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
            self._logger.debug(
                "Raw LLM response for %s diagram (len %d): '%.*s...'",
                diagram_type,
                len(markup_raw),
                LOG_MARKUP_SNIPPET_LEN,
                markup_raw.replace("\n", " "),
            )
            markup = self._clean_llm_diagram_output(markup_raw)
            self._logger.debug(
                "Cleaned markup for %s diagram (len %d): '%.*s...'",
                diagram_type,
                len(markup),
                LOG_MARKUP_SNIPPET_LEN,
                markup.replace("\n", " "),
            )

            if not markup:
                self._log_warning("LLM returned empty response for %s diagram after cleaning.", diagram_type)
                return None

            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                log_msg = (
                    f"LLM {diagram_type} diagram markup missing expected start. "
                    f"Expected one of: {expected_keywords}. Received: '%.*s...'"
                )
                self._log_warning(log_msg, LOG_MARKUP_SNIPPET_LEN, markup.replace("\n", " "))

            self._log_info("Successfully generated %s diagram markup.", diagram_type)
            return markup
        except LlmApiError as e_llm:
            self._log_error("LLM API call failed for %s diagram: %s", diagram_type, e_llm, exc_info=True)
            return None
        except (ValueError, TypeError, AttributeError, IndexError) as e_other:  # More specific processing errors
            self._log_error("Error processing LLM response for %s diagram: %s", diagram_type, e_other, exc_info=True)
            return None

    def _generate_relationship_flowchart(self, prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the relationship flowchart diagram."""
        abstractions_any: Any = prep_res_context.get("abstractions", [])
        relationships_any: Any = prep_res_context.get("relationships", {})
        structure_context_any: Any = prep_res_context.get("structure_context")

        abstractions: AbstractionsList = abstractions_any if isinstance(abstractions_any, list) else []
        relationships: RelationshipsDict = relationships_any if isinstance(relationships_any, dict) else {}
        structure_context: Optional[str] = (
            str(structure_context_any) if isinstance(structure_context_any, str) else None
        )

        llm_cfg: LlmConfigDict = prep_res_context.get("llm_config", {})
        cache_cfg: CacheConfigDict = prep_res_context.get("cache_config", {})
        diagram_format_str: str = str(prep_res_context.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_relationship_flowchart_prompt(
                project_name=str(prep_res_context.get("project_name")),
                abstractions=abstractions,
                relationships=relationships,
                diagram_format=diagram_format_str,
                structure_context=structure_context,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="relationship_flowchart",
            expected_keywords=["flowchart TD", "graph TD"],
        )

    def _generate_class_diagram(self, prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the class hierarchy diagram."""
        code_context_str = str(prep_res_context.get("structure_context", "No code context available."))
        if not code_context_str or code_context_str == "No file data available to generate structure context.":
            self._log_warning("No proper code/structure context for class diagram. Diagram might be suboptimal.")
        llm_cfg: LlmConfigDict = prep_res_context.get("llm_config", {})
        cache_cfg: CacheConfigDict = prep_res_context.get("cache_config", {})
        diagram_format_str: str = str(prep_res_context.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_class_diagram_prompt(
                project_name=str(prep_res_context.get("project_name")),
                code_context=code_context_str,
                diagram_format=diagram_format_str,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="class",
            expected_keywords=["classDiagram"],
        )

    def _generate_package_diagram(self, prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the package dependency diagram."""
        structure_context_str = str(prep_res_context.get("structure_context", ""))
        if (
            not structure_context_str
            or structure_context_str == "No file data available to generate structure context."
        ):
            self._log_warning("Cannot generate package diagram: structure_context is missing or empty.")
            return None
        llm_cfg: LlmConfigDict = prep_res_context.get("llm_config", {})
        cache_cfg: CacheConfigDict = prep_res_context.get("cache_config", {})
        diagram_format_str: str = str(prep_res_context.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))

        return self._call_llm_for_diagram(
            prompt=format_package_diagram_prompt(
                project_name=str(prep_res_context.get("project_name")),
                structure_context=structure_context_str,
                diagram_format=diagram_format_str,
            ),
            llm_config=llm_cfg,
            cache_config=cache_cfg,
            diagram_type="package",
            expected_keywords=["graph TD"],
        )

    def _generate_sequence_diagrams(self, prep_res_context: PrepContext) -> SequenceDiagramsListInternal:
        """Generate sequence diagrams based on identified scenarios."""
        diagram_format: str = str(prep_res_context.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))
        self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: SequenceDiagramsListInternal = []

        scenarios_any: Any = prep_res_context.get("identified_scenarios", [])
        max_diagrams_any: Any = prep_res_context.get("seq_max", 0)
        scenarios: IdentifiedScenarioList = scenarios_any if isinstance(scenarios_any, list) else []
        max_diagrams_to_generate: int = max_diagrams_any if isinstance(max_diagrams_any, int) else 0
        llm_cfg: LlmConfigDict = prep_res_context.get("llm_config", {})
        cache_cfg: CacheConfigDict = prep_res_context.get("cache_config", {})

        scenarios_to_process = scenarios[:max_diagrams_to_generate]

        if not scenarios_to_process:
            self._log_warning("No scenarios available or 'seq_max' is 0. No sequence diagrams generated.")
            return []

        self._log_info(
            "Attempting to generate up to %d sequence diagrams from %d scenarios.",
            max_diagrams_to_generate,
            len(scenarios),
        )

        for i, scenario_desc in enumerate(scenarios_to_process):
            words = scenario_desc.split()
            scenario_name_short = " ".join(words[:SCENARIO_NAME_MAX_WORDS])
            if len(words) > SCENARIO_NAME_MAX_WORDS:
                scenario_name_short += "..."
            self._log_info(
                "Generating sequence diagram %d/%d: '%s'", i + 1, len(scenarios_to_process), scenario_name_short
            )
            sequence_context_obj = SequenceDiagramContext(
                project_name=str(prep_res_context.get("project_name")),
                scenario_name=scenario_name_short,
                scenario_description=scenario_desc,
                diagram_format=diagram_format,
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

    def exec(self, prep_res: GenerateDiagramsPrepResult) -> GenerateDiagramsExecResult:
        """Generate diagrams based on prepared context and configuration flags."""
        results: DiagramResultDict = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],
        }
        if prep_res is None:
            self._log_info("Diagram generation skipped as per preparation step.")
            return results

        if prep_res.get("gen_flowchart"):
            results["relationship_flowchart_markup"] = self._generate_relationship_flowchart(prep_res)
        if prep_res.get("gen_class"):
            results["class_diagram_markup"] = self._generate_class_diagram(prep_res)
        if prep_res.get("gen_pkg"):
            results["package_diagram_markup"] = self._generate_package_diagram(prep_res)
        if prep_res.get("gen_seq"):
            results["sequence_diagrams_markup"] = self._generate_sequence_diagrams(prep_res)
        return results

    def post(
        self, shared: SLSharedState, prep_res: GenerateDiagramsPrepResult, exec_res: GenerateDiagramsExecResult
    ) -> None:
        """Update shared state with generated diagram markups."""
        del prep_res
        updated_keys: list[str] = []
        if not isinstance(exec_res, dict):
            self._log_warning(
                "No diagram results or unexpected type (%s) from exec. Shared state not updated for diagrams.",
                type(exec_res).__name__,
            )
            return

        for key, value in exec_res.items():
            is_valid_str_markup = isinstance(value, str) and value.strip()
            seq_markup_list = value if key == "sequence_diagrams_markup" and isinstance(value, list) else None
            is_valid_list_markup = (
                seq_markup_list is not None
                and all(isinstance(item, (str, type(None))) for item in seq_markup_list)
                and any(isinstance(item, str) and item.strip() for item in seq_markup_list)
            )

            if is_valid_str_markup or is_valid_list_markup:
                shared[key] = value
                updated_keys.append(key)
            elif key in shared:
                current_val = shared[key]
                new_val_for_key = [] if key == "sequence_diagrams_markup" and value is None else value
                if current_val != new_val_for_key:  # Only update if value actually changes to None/empty
                    shared[key] = new_val_for_key
                    self._log_info("Diagram for '%s' was None or empty, key in shared state updated.", key)
            elif value is None or (isinstance(value, list) and not value):  # Key not in shared, but value is None/empty
                shared[key] = [] if key == "sequence_diagrams_markup" and value is None else value
                self._log_info("Diagram for '%s' was None or empty, setting key in shared state.", key)

        if updated_keys:
            self._log_info("Stored diagram generation results in shared state for keys: %s", sorted(updated_keys))
        else:
            # Check if any generation was attempted (based on exec_res keys) but failed
            attempted_diagram_keys = {
                "relationship_flowchart_markup",
                "class_diagram_markup",
                "package_diagram_markup",
                "sequence_diagrams_markup",
            }
            any_attempt_failed = False
            for k in attempted_diagram_keys:
                if k in exec_res:  # Diagram generation was part of exec_res
                    val = exec_res[k]
                    if val is None or (
                        isinstance(val, list) and not any(v for v in val if isinstance(v, str) and v.strip())
                    ):
                        any_attempt_failed = True
                        break
            if any_attempt_failed:
                self._log_info(
                    "Some diagram generation was attempted but resulted in no valid markup. Shared state reflects this."
                )
            else:
                self._log_info("No diagram generation was attempted or no valid markups produced to update state.")


# End of src/sourcelens/nodes/n06_generate_diagrams.py
