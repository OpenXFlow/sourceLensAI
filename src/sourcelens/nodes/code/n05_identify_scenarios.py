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
from typing import TYPE_CHECKING, Any, Final, Union

from typing_extensions import TypeAlias

from sourcelens.nodes.base_node import BaseNode, SLSharedContext
from sourcelens.prompts import ScenarioPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

if TYPE_CHECKING:
    # Type aliases for resolved configurations from shared_context["config"]
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


module_logger: logging.Logger = logging.getLogger(__name__)  # Node-specific logger

DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode[IdentifyScenariosPreparedInputs, IdentifyScenariosExecutionResult]):
    """Identify key interaction scenarios within the analyzed codebase using an LLM."""

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyScenariosPreparedInputs:
        """Prepare context for the scenario identification LLM prompt.

        This method retrieves necessary configurations for diagram generation
        (especially sequence diagrams) and data about identified abstractions
        and relationships from the `shared_context`. If sequence diagrams are
        disabled or essential data is missing, it prepares to skip execution.

        Args:
            shared_context: The shared context dictionary. Expected to contain:
                            "config" (the fully resolved application configuration),
                            "abstractions", "relationships", "project_name",
                            "llm_config" (resolved for the current mode),
                            "cache_config".

        Returns:
            A dictionary containing data for the `execution` method. If conditions
            for scenario identification are not met (e.g., sequence diagrams disabled,
            no abstractions), it returns `{"skip": True, "reason": ...}`.

        Raises:
            ValueError: If essential data (like "config") is missing from `shared_context`.
        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            # Retrieve the fully resolved configuration
            resolved_config_val: Any = self._get_required_shared(shared_context, "config")
            resolved_config: "ResolvedConfigDict" = resolved_config_val if isinstance(resolved_config_val, dict) else {}  # type: ignore[assignment]

            # Determine current operation mode to correctly access diagram_generation settings
            current_operation_mode = str(shared_context.get("current_operation_mode", "code"))
            analysis_config_key = f"{current_operation_mode}_analysis"  # e.g. "code_analysis"
            mode_specific_config: dict[str, Any] = resolved_config.get(analysis_config_key, {})

            diagram_config_raw: Any = mode_specific_config.get("diagram_generation", {})
            diagram_config: "ResolvedDiagramGenerationConfig" = (
                diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
            )  # type: ignore[assignment]
            self._log_debug("Diagram config received by IdentifyScenariosNode: %s", diagram_config)

            seq_config_raw: Any = diagram_config.get("sequence_diagrams", {})
            seq_config: "ResolvedSequenceDiagramConfig" = seq_config_raw if isinstance(seq_config_raw, dict) else {}  # type: ignore[assignment]
            self._log_debug("Sequence diagram specific config in IdentifyScenariosNode: %s", seq_config)

            if not seq_config.get("enabled", False):  # Default to False if key missing
                self._log_info(
                    "Sequence diagram generation is disabled per resolved config. Skipping scenario identification."
                )
                return {"skip": True, "reason": "Sequence diagrams disabled in resolved config"}

            abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
            abstractions: AbstractionsListInternal = abstractions_any if isinstance(abstractions_any, list) else []
            if not abstractions:
                self._log_warning("No abstractions available. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships_any: Any = self._get_required_shared(shared_context, "relationships")
            relationships: RelationshipsDictInternal = relationships_any if isinstance(relationships_any, dict) else {}  # type: ignore[assignment]
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"

            # LLM and cache config are taken from shared_context, already resolved for the current mode
            llm_config_val: Any = self._get_required_shared(shared_context, "llm_config")
            llm_config: "ResolvedLlmConfigDict" = llm_config_val if isinstance(llm_config_val, dict) else {}  # type: ignore[assignment]
            cache_config_val: Any = self._get_required_shared(shared_context, "cache_config")
            cache_config: "ResolvedCacheConfigDict" = cache_config_val if isinstance(cache_config_val, dict) else {}  # type: ignore[assignment]

            max_scenarios_cfg_val: Any = seq_config.get("max_diagrams_to_generate", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)
            max_scenarios: int = (
                int(max_scenarios_cfg_val)
                if isinstance(max_scenarios_cfg_val, (int, float)) and max_scenarios_cfg_val >= 0
                else DEFAULT_MAX_SCENARIOS_TO_IDENTIFY
            )
            if max_scenarios <= 0:
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
        except ValueError as e_val:
            self._log_error("Scenario ID pre_execution failed due to missing essential shared data: %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {e_val!s}"}
        except (KeyError, TypeError) as e_struct:
            self._log_error("Error accessing config structure during scenario ID pre_execution: %s", e_struct)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct!s}"}

    def execution(self, prepared_inputs: IdentifyScenariosPreparedInputs) -> IdentifyScenariosExecutionResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.
                             It contains data for prompting the LLM, including a "skip" flag.

        Returns:
            A list of scenario description strings. Returns an empty list if
            execution was skipped (due to `prepared_inputs["skip"]` being True),
            or if the LLM call or subsequent YAML validation fails.

        Raises:
            LlmApiError: If the LLM API call itself fails after retries (to be
                         handled by the `Node`'s `execution_fallback`).
        """
        if prepared_inputs.get("skip", True):
            reason_any: Any = prepared_inputs.get("reason", "N/A")
            self._log_info("Skipping scenario identification execution. Reason: '%s'", str(reason_any))
            return []

        project_name: str = prepared_inputs["project_name"]
        abstraction_listing: str = prepared_inputs["abstraction_listing"]
        context_summary: str = prepared_inputs["context_summary"]
        max_scenarios: int = prepared_inputs["max_scenarios"]
        llm_config: "ResolvedLlmConfigDict" = prepared_inputs["llm_config"]  # type: ignore[assignment]
        cache_config: "ResolvedCacheConfigDict" = prepared_inputs["cache_config"]  # type: ignore[assignment]

        self._log_info("Identifying up to %d key scenarios for '%s' using LLM...", max_scenarios, project_name)
        prompt = ScenarioPrompts.format_identify_scenarios_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing,
            context_summary=context_summary,
            max_scenarios=max_scenarios,
        )
        response_raw: str
        try:
            response_raw = call_llm(prompt, llm_config, cache_config)  # Can raise LlmApiError
        except LlmApiError:  # Re-raise to be caught by Node's retry/fallback
            self._log_error("LLM API call failed during scenario identification. Error will be re-raised.")
            raise

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
                log_msg = "LLM response for scenarios parsed as list, but yielded no valid non-empty strings."
                self._log_warning(log_msg)
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
            return []  # Return empty on validation failure; Node's fallback won't help here.
        except (TypeError, ValueError) as e_proc:
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
            return []

    def execution_fallback(
        self, prepared_inputs: IdentifyScenariosPreparedInputs, exc: Exception
    ) -> IdentifyScenariosExecutionResult:
        """Handle fallback if all LLM execution attempts fail for scenario identification.

        This is called by the parent `Node` class if `execution` (which calls the LLM)
        repeatedly raises an `LlmApiError`.

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
            execution_outputs: List of scenario strings from the `execution` phase,
                               or an empty list if skipped or failed.
        """
        self._logger.debug("--- IdentifyScenariosNode.post_execution ---")
        abstractions_count = len(shared_context.get("abstractions", []))
        order_count = len(shared_context.get("chapter_order", []))
        chapters_count = len(shared_context.get("chapters", []))
        log_msg_before = (
            f"Shared context BEFORE update (abstractions: {abstractions_count}, "
            f"chapter_order: {order_count}, chapters: {chapters_count})"
        )
        self._logger.debug(log_msg_before)

        shared_context.setdefault("identified_scenarios", [])
        if not prepared_inputs.get("skip", True):
            # Ensure execution_outputs is a list, even if empty from fallback
            scenarios_to_store = execution_outputs if isinstance(execution_outputs, list) else []
            shared_context["identified_scenarios"] = scenarios_to_store
            self._log_info("Stored %d identified scenarios in shared context.", len(scenarios_to_store))
        else:
            reason = str(prepared_inputs.get("reason", "N/A"))
            log_msg = (
                f"Scenario identification was skipped in pre_execution (Reason: {reason}). "
                "'identified_scenarios' remains default or unchanged (currently: "
                f"{len(shared_context.get('identified_scenarios', []))})."
            )
            self._log_info(log_msg)

        scenarios_len_after = len(shared_context.get("identified_scenarios", []))
        self._logger.debug("Shared context AFTER update (identified_scenarios count: %d)", scenarios_len_after)
        self._logger.debug(
            "Shared context AFTER update (abstractions: %d, chapter_order: %d, chapters: %d)",
            len(shared_context.get("abstractions", [])),
            len(shared_context.get("chapter_order", [])),
            len(shared_context.get("chapters", [])),
        )
        self._logger.debug("--- End IdentifyScenariosNode.post_execution ---")


# End of src/sourcelens/nodes/code/n05_identify_scenarios.py
