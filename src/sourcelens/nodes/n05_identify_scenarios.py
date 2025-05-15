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

"""Node responsible for identifying relevant interaction scenarios for diagrams.

This node uses an LLM to suggest key interaction scenarios within the analyzed
codebase, based on identified abstractions and their relationships. These
scenarios can then be used to generate sequence diagrams or other visualizations.
"""

import logging
from typing import Any, Final, Union

from typing_extensions import TypeAlias

from sourcelens.prompts import ScenarioPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from .base_node import BaseNode, SLSharedState

IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]
IdentifyScenariosExecResult: TypeAlias = ScenarioList

AbstractionItem: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[AbstractionItem]  # type: ignore[misc]

RelationshipDetail: TypeAlias = dict[str, Any]
RelationshipsDict: TypeAlias = dict[str, Union[str, list[RelationshipDetail]]]

ConfigDictTyped: TypeAlias = dict[str, Any]
OutputConfigDictTyped: TypeAlias = dict[str, Any]
DiagramConfigDictTyped: TypeAlias = dict[str, Any]
SeqConfigDictTyped: TypeAlias = dict[str, Any]
LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]


module_logger: logging.Logger = logging.getLogger(__name__)


DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode[IdentifyScenariosPrepResult, IdentifyScenariosExecResult]):
    """Identify key interaction scenarios within the analyzed codebase using an LLM."""

    def prep(self, shared: SLSharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt."""
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config_any: Any = self._get_required_shared(shared, "config")
            config: ConfigDictTyped = config_any if isinstance(config_any, dict) else {}
            output_config_any: Any = config.get("output", {})
            output_config: OutputConfigDictTyped = output_config_any if isinstance(output_config_any, dict) else {}
            diagram_config_raw: Any = output_config.get("diagram_generation", {})
            diagram_config: DiagramConfigDictTyped = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
            seq_config_raw: Any = diagram_config.get("include_sequence_diagrams", {})
            seq_config: SeqConfigDictTyped = seq_config_raw if isinstance(seq_config_raw, dict) else {}

            if not seq_config.get("enabled", False):
                self._log_info("Sequence diagram generation is disabled. Skipping scenario identification.")
                return {"skip": True, "reason": "Sequence diagrams disabled in config"}

            abstractions_any: Any = self._get_required_shared(shared, "abstractions")
            abstractions: AbstractionsList = abstractions_any if isinstance(abstractions_any, list) else []
            if not abstractions:
                self._log_warning("No abstractions available. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships_any: Any = self._get_required_shared(shared, "relationships")
            relationships: RelationshipsDict = relationships_any if isinstance(relationships_any, dict) else {}
            project_name_any: Any = self._get_required_shared(shared, "project_name")
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
            llm_config_any: Any = self._get_required_shared(shared, "llm_config")
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config_any: Any = self._get_required_shared(shared, "cache_config")
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}
            max_scenarios_any: Any = seq_config.get("max_diagrams", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)
            max_scenarios: int = (
                max_scenarios_any if isinstance(max_scenarios_any, int) else DEFAULT_MAX_SCENARIOS_TO_IDENTIFY
            )
            abstraction_listing_parts: list[str] = [
                f"- {i} # {str(abstr_item.get('name', f'Unnamed Abstraction {i}'))}"
                for i, abstr_item in enumerate(abstractions)
            ]
            abstraction_listing: str = "\n".join(abstraction_listing_parts)
            context_summary_val: Any = relationships.get("summary", "No project summary available.")
            context_summary: str = str(context_summary_val)
            prep_result: IdentifyScenariosPrepResult = {
                "skip": False,
                "project_name": project_name,
                "abstraction_listing": abstraction_listing,
                "context_summary": context_summary,
                "num_abstractions": len(abstractions),
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
            return prep_result
        except ValueError:  # Specific error for _get_required_shared
            self._log_error("Scenario ID prep failed due to missing essential shared data.", exc_info=True)
            return {"skip": True, "reason": "Missing essential shared data for scenario identification."}
        except (KeyError, TypeError) as e_struct:  # Errors in accessing config structure
            self._log_error("Error accessing config structure during scenario ID prep: %s", e_struct, exc_info=True)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call the LLM to identify relevant scenarios and validate the response."""
        if prep_res.get("skip", True):
            reason_any: Any = prep_res.get("reason", "N/A")
            self._log_info("Skipping scenario identification execution. Reason: '%s'", str(reason_any))
            return []

        project_name: str = prep_res["project_name"]  # type: ignore[assignment]
        abstraction_listing: str = prep_res["abstraction_listing"]  # type: ignore[assignment]
        context_summary: str = prep_res["context_summary"]  # type: ignore[assignment]
        max_scenarios: int = prep_res["max_scenarios"]  # type: ignore[assignment]
        llm_config: LlmConfigDictTyped = prep_res["llm_config"]  # type: ignore[assignment]
        cache_config: CacheConfigDictTyped = prep_res["cache_config"]  # type: ignore[assignment]

        self._log_info("Identifying up to %d key scenarios for '%s' using LLM...", max_scenarios, project_name)
        prompt = ScenarioPrompts.format_identify_scenarios_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing,
            context_summary=context_summary,
            max_scenarios=max_scenarios,
        )
        response_raw: str
        try:
            response_raw = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e_llm:
            self._log_error("LLM API call failed during scenario identification: %s", e_llm, exc_info=True)
            return []

        try:
            list_item_schema = {"type": "string", "minLength": 5}
            scenario_list_raw_any: list[Any] = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": list_item_schema},
            )
            validated_scenarios: ScenarioList = [
                s.strip() for s in scenario_list_raw_any if isinstance(s, str) and s.strip()
            ]
            if not validated_scenarios and scenario_list_raw_any:
                self._log_warning("LLM response for scenarios parsed as list, but yielded no valid non-empty strings.")
            elif not validated_scenarios:
                self._log_warning("LLM response did not contain any valid scenarios matching schema.")
            self._log_info("Identified and validated %d scenarios.", len(validated_scenarios))
            return validated_scenarios[:max_scenarios]
        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS:
                    snippet += "..."
                module_logger.warning("Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet)
            return []
        except (TypeError, ValueError) as e_proc:
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
            return []

    def post(
        self,
        shared: SLSharedState,
        prep_res: IdentifyScenariosPrepResult,
        exec_res: IdentifyScenariosExecResult,
    ) -> None:
        """Update the shared state with the list of identified scenarios."""
        self._logger.debug("--- IdentifyScenariosNode.post ---")
        self._logger.debug(
            "Shared state BEFORE update (abstractions count: %d, chapter_order count: %d, chapters count: %d)",
            len(shared.get("abstractions", [])),
            len(shared.get("chapter_order", [])),
            len(shared.get("chapters", [])),
        )

        shared.setdefault("identified_scenarios", [])
        if not prep_res.get("skip", True):
            shared["identified_scenarios"] = exec_res
            self._log_info("Stored %d identified scenarios in shared state.", len(exec_res))
        else:
            self._log_info(
                "Scenario identification was skipped in prep. 'identified_scenarios' remains default (empty list)."
            )
        self._logger.debug(
            "Shared state AFTER update (identified_scenarios count: %d)", len(shared.get("identified_scenarios", []))
        )
        self._logger.debug(
            "Shared state AFTER update (abstractions count: %d, chapter_order count: %d, chapters count: %d)",
            len(shared.get("abstractions", [])),
            len(shared.get("chapter_order", [])),
            len(shared.get("chapters", [])),
        )
        self._logger.debug("--- End IdentifyScenariosNode.post ---")


# End of src/sourcelens/nodes/n05_identify_scenarios.py
