# src/sourcelens/nodes/identify_scenarios.py

"""Node responsible for identifying relevant interaction scenarios based on code analysis."""

import logging
from typing import Any, Final, TypeAlias  # Added Final

from sourcelens.nodes.base_node import BaseNode, SharedState

# Corrected import to use the ScenarioPrompts class
from sourcelens.prompts import ScenarioPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]
IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
IdentifyScenariosExecResult: TypeAlias = ScenarioList

logger = logging.getLogger(__name__)

# --- Constants ---
DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode):
    """Identify key interaction scenarios within the analyzed codebase using an LLM.

    Takes identified abstractions and relationships as input, prompts the LLM
    to suggest relevant scenarios (e.g., typical user flows, error handling paths),
    validates the response, and stores the identified scenarios in the shared state.
    Handles potential LLM API errors and YAML validation failures gracefully by
    returning an empty list of scenarios, allowing the main flow to continue.
    """

    def prep(self, shared: SharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt.

        Gathers abstractions, relationships, project name, and LLM configuration
        from the shared state. Skips processing if sequence diagrams are disabled
        or if no abstractions are available.

        Args:
            shared: The shared state dictionary containing analysis results and config.

        Returns:
            A dictionary containing context data needed for the `exec` step,
            or a dictionary with `skip: True` if conditions are not met.

        Raises:
            ValueError: If essential keys like 'config', 'llm_config', or 'cache_config'
                        are missing from the shared state.

        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config = config.get("output", {})
            diagram_config_raw = output_config.get("diagram_generation", {})
            diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
            seq_config_raw = diagram_config.get("include_sequence_diagrams", {})
            seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}

            if not seq_config.get("enabled", False):
                self._log_info("Sequence diagram generation is disabled. Skipping scenario identification.")
                return {"skip": True, "reason": "Sequence diagrams disabled in config"}

            # Abstractions and relationships are crucial context.
            # If IdentifyAbstractions failed and returned empty, this node should skip.
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            if not abstractions:
                self._log_warning("No abstractions available from previous step. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            max_scenarios: int = seq_config.get("max_diagrams", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)

            abstraction_listing = "\n".join(
                f"- {i} # {str(a.get('name', f'Unnamed Abstraction {i}'))}" for i, a in enumerate(abstractions)
            )
            context_summary = str(relationships.get("summary", "No project summary available."))

            return {
                "skip": False,
                "project_name": project_name,
                "abstraction_listing": abstraction_listing,
                "context_summary": context_summary,
                "num_abstractions": len(abstractions),
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
        except ValueError as e_val:  # Raised by _get_required_shared
            self._log_error("Missing required shared data for scenario identification prep: %s", e_val, exc=e_val)
            raise  # Re-raise critical config/data errors
        except (KeyError, TypeError) as e_struct:  # Should be less likely now
            self._log_error("Error accessing config structure during scenario ID prep: %s", e_struct, exc=e_struct)
            return {"skip": True, "reason": f"Config structure error: {e_struct}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A list of identified scenario description strings. Returns an empty
            list if skipping, if the LLM call fails, or if validation/parsing
            of the LLM response fails.

        """
        if prep_res.get("skip", False):
            self._log_info("Skipping scenario identification execution (reason: '%s').", prep_res.get("reason", "N/A"))
            return []

        # Ensure all required keys from prep_res are present
        try:
            project_name: str = prep_res["project_name"]
            abstraction_listing: str = prep_res["abstraction_listing"]
            context_summary: str = prep_res["context_summary"]
            max_scenarios: int = prep_res["max_scenarios"]
            llm_config: dict[str, Any] = prep_res["llm_config"]
            cache_config: dict[str, Any] = prep_res["cache_config"]
        except KeyError as e_key:
            self._log_error("Missing essential key from prep_res in exec: %s. Skipping.", e_key, exc_info=True)
            return []

        self._log_info(f"Identifying up to {max_scenarios} key scenarios for '{project_name}' using LLM...")
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
            self._log_error("LLM API call failed during scenario identification: %s", e_llm, exc=e_llm)
            return []

        try:
            scenario_list_raw = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": {"type": "string", "minLength": 5}},
            )
            # Filter for non-empty strings after stripping
            validated_scenarios = [s.strip() for s in scenario_list_raw if isinstance(s, str) and s.strip()]

            if not validated_scenarios and scenario_list_raw:  # If parsing gave a list but all items were invalid/empty
                self._log_warning("LLM response parsed as list, but yielded no valid non-empty scenario strings.")
            elif not validated_scenarios:  # If validate_yaml_list itself returned empty
                self._log_warning("LLM response did not contain any valid scenarios matching schema.")
            # No else needed, will proceed if validated_scenarios has items

            self._log_info(f"Identified and validated {len(validated_scenarios)} scenarios.")
            return validated_scenarios[:max_scenarios]

        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS] + (
                    "..." if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS else ""
                )
                logger.warning("Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet)
            return []
        except (TypeError, ValueError) as e_proc:
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc=e_proc)
            return []

    def post(
        self, shared: SharedState, prep_res: IdentifyScenariosPrepResult, exec_res: IdentifyScenariosExecResult
    ) -> None:
        """Update the shared state with the list of identified scenarios.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by the `prep` method.
            exec_res: The list of scenario description strings from `exec`.

        """
        shared.setdefault("identified_scenarios", [])  # Ensure key exists
        if not prep_res.get("skip", False):
            if isinstance(exec_res, list):
                shared["identified_scenarios"] = exec_res
                self._log_info("Stored %d identified scenarios in shared state.", len(exec_res))
            else:
                self._log_error(
                    "Invalid result type from scenario identification exec: %s. Expected list. "
                    "Shared state 'identified_scenarios' remains as default (empty list).",
                    type(exec_res).__name__,
                )
        else:
            self._log_info("Scenario identification was skipped. 'identified_scenarios' remains empty.")


# End of src/sourcelens/nodes/identify_scenarios.py
