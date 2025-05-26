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

from .base_node import BaseNode, SLSharedContext  # Updated import

# Renamed Type Aliases
IdentifyScenariosPreparedInputs: TypeAlias = dict[str, Any]
"""Type alias for the prepared inputs for this node."""
ScenarioList: TypeAlias = list[str]
"""Type alias for a list of scenario description strings."""
IdentifyScenariosExecutionResult: TypeAlias = ScenarioList
"""Type alias for the execution result, which is a list of scenarios."""


# Internal type consistency for data from shared_context
AbstractionItemInternal: TypeAlias = dict[str, Any]
AbstractionsListInternal: TypeAlias = list[AbstractionItemInternal]
RelationshipDetailInternal: TypeAlias = dict[str, Any]
RelationshipsDictInternal: TypeAlias = dict[str, Union[str, list[RelationshipDetailInternal]]]

ConfigDictTyped: TypeAlias = dict[str, Any]
OutputConfigDictTyped: TypeAlias = dict[str, Any]
DiagramConfigDictTyped: TypeAlias = dict[str, Any]
SeqConfigDictTyped: TypeAlias = dict[str, Any]
LlmConfigDictTyped: TypeAlias = dict[str, Any]
CacheConfigDictTyped: TypeAlias = dict[str, Any]


module_logger: logging.Logger = logging.getLogger(__name__)


DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode[IdentifyScenariosPreparedInputs, IdentifyScenariosExecutionResult]):
    """Identify key interaction scenarios within the analyzed codebase using an LLM."""

    def pre_execution(self, shared_context: SLSharedContext) -> IdentifyScenariosPreparedInputs:
        """Prepare context for the scenario identification LLM prompt.

        Args:
            shared_context: The shared context dictionary.

        Returns:
            A dictionary containing data for the `execution` method, or an
            indicator to skip execution if prerequisites are not met.
        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config_any: Any = self._get_required_shared(shared_context, "config")
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

            abstractions_any: Any = self._get_required_shared(shared_context, "abstractions")
            abstractions: AbstractionsListInternal = abstractions_any if isinstance(abstractions_any, list) else []
            if not abstractions:
                self._log_warning("No abstractions available. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships_any: Any = self._get_required_shared(shared_context, "relationships")
            relationships: RelationshipsDictInternal = relationships_any if isinstance(relationships_any, dict) else {}
            project_name_any: Any = self._get_required_shared(shared_context, "project_name")
            project_name: str = str(project_name_any) if isinstance(project_name_any, str) else "Unknown Project"
            llm_config_any: Any = self._get_required_shared(shared_context, "llm_config")
            llm_config: LlmConfigDictTyped = llm_config_any if isinstance(llm_config_any, dict) else {}
            cache_config_any: Any = self._get_required_shared(shared_context, "cache_config")
            cache_config: CacheConfigDictTyped = cache_config_any if isinstance(cache_config_any, dict) else {}

            max_scenarios_cfg: Any = seq_config.get("max_diagrams", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)
            max_scenarios: int = (
                int(max_scenarios_cfg)
                if isinstance(max_scenarios_cfg, (int, float)) and max_scenarios_cfg >= 0  # Allow float if whole number
                else DEFAULT_MAX_SCENARIOS_TO_IDENTIFY
            )
            if max_scenarios <= 0:
                self._log_info("Max scenarios is configured to %d. Skipping scenario identification.", max_scenarios)
                return {"skip": True, "reason": f"Max scenarios set to {max_scenarios}"}

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
                "num_abstractions": len(abstractions),  # Though not directly used in prompt, useful for context
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
            return prepared_inputs
        except ValueError as e_val:  # Specific error for _get_required_shared
            self._log_error("Scenario ID pre_execution failed due to missing essential shared data: %s", e_val)
            return {"skip": True, "reason": f"Missing essential shared data: {e_val!s}"}
        except (KeyError, TypeError) as e_struct:
            self._log_error("Error accessing config structure during scenario ID pre_execution: %s", e_struct)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct!s}"}

    def execution(self, prepared_inputs: IdentifyScenariosPreparedInputs) -> IdentifyScenariosExecutionResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Args:
            prepared_inputs: The dictionary returned by the `pre_execution` method.

        Returns:
            A list of scenario description strings. Returns an empty list if
            skipped, or if LLM call or validation fails.
        """
        if prepared_inputs.get("skip", True):
            reason_any: Any = prepared_inputs.get("reason", "N/A")
            self._log_info("Skipping scenario identification execution. Reason: '%s'", str(reason_any))
            return []

        project_name: str = prepared_inputs["project_name"]
        abstraction_listing: str = prepared_inputs["abstraction_listing"]
        context_summary: str = prepared_inputs["context_summary"]
        max_scenarios: int = prepared_inputs["max_scenarios"]
        llm_config: LlmConfigDictTyped = prepared_inputs["llm_config"]  # type: ignore[assignment]
        cache_config: CacheConfigDictTyped = prepared_inputs["cache_config"]  # type: ignore[assignment]

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
            list_item_schema = {"type": "string", "minLength": 5}  # Scenarios should have some length
            # The list itself doesn't need minItems/maxItems from LLM, we'll cap it later.
            scenario_list_raw_any: list[Any] = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": list_item_schema},
            )
            # Ensure all items are strings and stripped
            validated_scenarios: ScenarioList = [
                s.strip() for s in scenario_list_raw_any if isinstance(s, str) and s.strip()
            ]
            if not validated_scenarios and scenario_list_raw_any:
                log_msg = "LLM response for scenarios parsed as list, but yielded no valid non-empty strings."
                self._log_warning(log_msg)
            elif not validated_scenarios:
                self._log_warning("LLM response did not contain any valid scenarios matching schema.")
            self._log_info("Identified and validated %d scenarios.", len(validated_scenarios))
            return validated_scenarios[:max_scenarios]  # Cap the number of scenarios
        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS:
                    snippet += "..."
                module_logger.warning("Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet)
            return []
        except (TypeError, ValueError) as e_proc:  # Catch specific processing errors
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
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
        # Example of logging existing state before update for debugging complex flows
        abstractions_count = len(shared_context.get("abstractions", []))
        order_count = len(shared_context.get("chapter_order", []))
        chapters_count = len(shared_context.get("chapters", []))
        log_msg_before = (
            f"Shared context BEFORE update (abstractions: {abstractions_count}, "
            f"chapter_order: {order_count}, chapters: {chapters_count})"
        )
        self._logger.debug(log_msg_before)

        shared_context.setdefault("identified_scenarios", [])  # Ensure key exists
        if not prepared_inputs.get("skip", True):
            shared_context["identified_scenarios"] = execution_outputs
            self._log_info("Stored %d identified scenarios in shared context.", len(execution_outputs))
        else:
            reason = str(prepared_inputs.get("reason", "N/A"))
            log_msg = (
                f"Scenario identification was skipped in pre_execution (Reason: {reason}). "
                "'identified_scenarios' remains default or unchanged."
            )
            self._log_info(log_msg)

        scenarios_len_after = len(shared_context.get("identified_scenarios", []))
        self._logger.debug("Shared context AFTER update (identified_scenarios count: %d)", scenarios_len_after)
        # Log other key states again if useful for tracing issues
        self._logger.debug(
            "Shared context AFTER update (abstractions: %d, chapter_order: %d, chapters: %d)",
            len(shared_context.get("abstractions", [])),  # Re-fetch in case they changed (unlikely here)
            len(shared_context.get("chapter_order", [])),
            len(shared_context.get("chapters", [])),
        )
        self._logger.debug("--- End IdentifyScenariosNode.post_execution ---")


# End of src/sourcelens/nodes/n05_identify_scenarios.py
