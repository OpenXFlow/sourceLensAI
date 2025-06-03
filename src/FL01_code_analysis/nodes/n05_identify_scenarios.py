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
from typing import TYPE_CHECKING, Any, Final, Union, cast

from typing_extensions import TypeAlias

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

from ..prompts.scenario_prompts import ScenarioPrompts

if TYPE_CHECKING:  # pragma: no cover
    ResolvedConfigDict: TypeAlias = dict[str, Any]
    ResolvedLlmConfigDict: TypeAlias = dict[str, Any]
    ResolvedCacheConfigDict: TypeAlias = dict[str, Any]
    ResolvedDiagramGenerationConfig: TypeAlias = dict[str, Any]
    ResolvedSequenceDiagramConfig: TypeAlias = dict[str, Any]


IdentifyScenariosPreparedInputs: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]
IdentifyScenariosExecutionResult: TypeAlias = ScenarioList

AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
RelationshipDetailInternal: TypeAlias = dict[str, Any]
RelationshipsDictInternal: TypeAlias = dict[str, Union[str, list[RelationshipDetailInternal]]]


module_logger: logging.Logger = logging.getLogger(__name__)

DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode[IdentifyScenariosPreparedInputs, IdentifyScenariosExecutionResult]):
    """Identify key interaction scenarios within the analyzed codebase using an LLM.

    This node prompts an LLM to suggest interaction scenarios based on identified
    abstractions and their relationships. These scenarios are intended for
    generating sequence diagrams. The node checks configuration to see if
    sequence diagram generation is enabled and what the maximum number of
    scenarios to identify is.
    """

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyScenariosPreparedInputs:
        """Prepare context for the scenario identification LLM prompt.

        Retrieves configurations for diagram generation (specifically sequence
        diagrams), identified abstractions, relationships, project details,
        and LLM/cache settings from the `shared_context`. If sequence diagrams
        are disabled or essential data like abstractions is missing, this method
        prepares to skip the execution phase.

        Args:
            shared_context: The shared context dictionary. Expected to contain:
                            "config" (the fully resolved application configuration),
                            "abstractions", "relationships", "project_name",
                            "llm_config" (resolved for the current mode),
                            "cache_config", and "current_operation_mode".

        Returns:
            A dictionary containing data for the `execution` method.
            If conditions for scenario identification are not met (e.g., sequence
            diagrams disabled, no abstractions), it returns a dictionary
            with `{"skip": True, "reason": ...}`.

        Raises:
            ValueError: If essential base data (like "config", "abstractions", "llm_config",
                        "cache_config", "project_name", or "current_operation_mode")
                        is missing from `shared_context`.
        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            resolved_config_val: Any = self._get_required_shared(shared_context, "config")
            resolved_config: "ResolvedConfigDict" = cast("ResolvedConfigDict", resolved_config_val)

            current_operation_mode: str = str(self._get_required_shared(shared_context, "current_operation_mode"))

            # Correctly access flow-specific settings
            flow_specific_config_val: Any = resolved_config.get(current_operation_mode, {})
            flow_specific_config: dict[str, Any] = cast(dict[str, Any], flow_specific_config_val)

            diagram_config_raw: Any = flow_specific_config.get("diagram_generation", {})
            diagram_config: "ResolvedDiagramGenerationConfig" = cast(
                "ResolvedDiagramGenerationConfig", diagram_config_raw
            )
            self._log_debug("Diagram config received by IdentifyScenariosNode: %s", diagram_config)

            seq_config_raw: Any = diagram_config.get("sequence_diagrams", {})
            seq_config: "ResolvedSequenceDiagramConfig" = cast("ResolvedSequenceDiagramConfig", seq_config_raw)
            self._log_debug("Sequence diagram specific config in IdentifyScenariosNode: %s", seq_config)

            if not seq_config.get("enabled", False):
                self._log_info(
                    "Sequence diagram generation is disabled per resolved config. Skipping scenario identification."
                )
                return {"skip": True, "reason": "Sequence diagrams disabled in resolved config"}

            abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
            abstractions: AbstractionsListInternal = cast(AbstractionsListInternal, abstractions_any)
            if not abstractions:  # pragma: no cover
                self._log_warning("No abstractions available. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships_any: Any = self._get_required_shared(shared_context, "relationships")
            relationships: RelationshipsDictInternal = cast(RelationshipsDictInternal, relationships_any)
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            project_name: str = str(project_name_any)

            llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
            llm_config: "ResolvedLlmConfigDict" = cast("ResolvedLlmConfigDict", llm_config_val)
            cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")
            cache_config: "ResolvedCacheConfigDict" = cast("ResolvedCacheConfigDict", cache_config_val)

            max_scenarios_cfg_val: Any = seq_config.get("max_diagrams_to_generate", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)
            max_scenarios: int = (
                int(max_scenarios_cfg_val)
                if isinstance(max_scenarios_cfg_val, (int, float)) and max_scenarios_cfg_val >= 0
                else DEFAULT_MAX_SCENARIOS_TO_IDENTIFY
            )
            if max_scenarios <= 0:  # pragma: no cover
                self._log_info("Max scenarios is configured to %d. Skipping scenario identification.", max_scenarios)
                return {"skip": True, "reason": f"Max scenarios for sequence diagrams set to {max_scenarios}"}

            abstraction_listing_parts: list[str] = [
                f"- {i} # {str(abstr_item.get('name', f'Unnamed Abstraction {i}'))}"
                for i, abstr_item in enumerate(abstractions)
            ]
            abstraction_listing: str = "\n".join(abstraction_listing_parts)
            context_summary_val: Any = relationships.get("summary", "No project summary available.")
            context_summary: str = str(context_summary_val)

            prepared_inputs: IdentifyScenariosPreparedInputs = {
                "skip": False,
                "project_name": project_name,
                "abstraction_listing": abstraction_listing,
                "context_summary": context_summary,
                "num_abstractions": len(abstractions),
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
            return prepared_inputs
        except ValueError as e_val:  # pragma: no cover
            self._log_error("Scenario ID pre_execution failed due to missing essential shared data: %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {e_val!s}"}
        except (KeyError, TypeError) as e_struct:  # pragma: no cover
            self._log_error("Error accessing config structure during scenario ID pre_execution: %s", e_struct)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct!s}"}

    def execution(self, prepared_inputs: IdentifyScenariosPreparedInputs) -> IdentifyScenariosExecutionResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.
                             It contains data for prompting the LLM, including a "skip" flag.

        Returns:
            A list of scenario description strings. Returns an empty list if
            execution was skipped or if the LLM call or validation fails.

        Raises:
            LlmApiError: If the LLM API call itself fails after retries.
        """
        if prepared_inputs.get("skip", True):
            reason_any: Any = prepared_inputs.get("reason", "N/A")
            self._log_info("Skipping scenario identification execution. Reason: '%s'", str(reason_any))
            return []

        project_name: str = prepared_inputs["project_name"]
        abstraction_listing: str = prepared_inputs["abstraction_listing"]
        context_summary: str = prepared_inputs["context_summary"]
        max_scenarios: int = prepared_inputs["max_scenarios"]
        llm_config: "ResolvedLlmConfigDict" = cast("ResolvedLlmConfigDict", prepared_inputs["llm_config"])
        cache_config: "ResolvedCacheConfigDict" = cast("ResolvedCacheConfigDict", prepared_inputs["cache_config"])

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
        except LlmApiError:
            self._log_error("LLM API call failed during scenario identification. Error will be re-raised.")
            raise

        try:
            list_item_schema = {"type": "string", "minLength": 5}
            # Validate the entire list structure and item types
            scenario_list_raw_any: list[Any] = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": list_item_schema},
            )
            # Further ensure items are strings and strip whitespace
            validated_scenarios: ScenarioList = [
                s.strip() for s in scenario_list_raw_any if isinstance(s, str) and s.strip()
            ]
            if not validated_scenarios and scenario_list_raw_any:  # pragma: no cover
                log_msg = "LLM response for scenarios parsed as list, but yielded no valid non-empty strings."
                self._log_warning(log_msg)
            elif not validated_scenarios:  # pragma: no cover
                self._log_warning("LLM response did not contain any valid scenarios matching schema.")
            self._log_info("Identified and validated %d scenarios.", len(validated_scenarios))
            return validated_scenarios[:max_scenarios]  # Ensure not to exceed max_scenarios
        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:  # pragma: no cover
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS:
                    snippet += "..."
                module_logger.warning("Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet)
            return []
        except (TypeError, ValueError) as e_proc:  # pragma: no cover
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
            return []

    def execution_fallback(
        self, prepared_inputs: IdentifyScenariosPreparedInputs, exc: Exception
    ) -> IdentifyScenariosExecutionResult:
        """Handle fallback if all LLM execution attempts fail for scenario identification.

        Args:
            prepared_inputs: The data from the `pre_execution` phase.
            exc: The final exception (typically `LlmApiError`) from `execution`.

        Returns:
            An empty list, as no scenarios could be identified.
        """
        project_name = str(prepared_inputs.get("project_name", "Unknown Project"))
        self._log_error(
            "All LLM attempts to identify scenarios for '%s' failed. Last error: %s. Returning empty list.",
            project_name,
            exc,
            exc_info=True,
        )
        return []

    def post_execution(
        self,
        shared_context: SLSharedContext,
        prepared_inputs: IdentifyScenariosPreparedInputs,
        execution_outputs: IdentifyScenariosExecutionResult,
    ) -> None:
        """Update the shared context with the list of identified scenarios.

        Args:
            shared_context: The shared context dictionary to update.
            prepared_inputs: Result from the `pre_execution` phase.
            execution_outputs: List of scenario strings from the `execution` phase.
        """
        self._logger.debug("--- IdentifyScenariosNode.post_execution ---")
        # Log state before update for easier debugging if needed
        abstractions_count_before = len(cast(list, shared_context.get("abstractions", [])))
        order_count_before = len(cast(list, shared_context.get("chapter_order", [])))
        chapters_count_before = len(cast(list, shared_context.get("chapters", [])))
        log_msg_before_parts = [
            f"Shared context BEFORE update (abstractions: {abstractions_count_before}, ",
            f"chapter_order: {order_count_before}, chapters: {chapters_count_before})",
        ]
        self._logger.debug("".join(log_msg_before_parts))

        shared_context.setdefault("identified_scenarios", [])  # Ensure key exists
        if not prepared_inputs.get("skip", True):
            scenarios_to_store = execution_outputs if isinstance(execution_outputs, list) else []
            shared_context["identified_scenarios"] = scenarios_to_store
            self._log_info("Stored %d identified scenarios in shared context.", len(scenarios_to_store))
        else:
            reason = str(prepared_inputs.get("reason", "N/A"))
            log_msg_skip_part1 = "Scenario identification was skipped in pre_execution "
            log_msg_skip_part2 = f"(Reason: {reason}). 'identified_scenarios' remains default or unchanged "
            log_msg_skip_part3 = f"(currently: {len(cast(list, shared_context.get('identified_scenarios', [])))})."
            self._log_info(log_msg_skip_part1 + log_msg_skip_part2 + log_msg_skip_part3)

        # Log state after update
        scenarios_len_after = len(cast(list, shared_context.get("identified_scenarios", [])))
        self._logger.debug("Shared context AFTER update (identified_scenarios count: %d)", scenarios_len_after)
        self._logger.debug("--- End IdentifyScenariosNode.post_execution ---")


# End of src/FL01_code_analysis/nodes/n05_identify_scenarios.py
