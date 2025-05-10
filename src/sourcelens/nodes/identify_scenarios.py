# src/sourcelens/nodes/identify_scenarios.py

"""Node responsible for identifying relevant interaction scenarios based on code analysis."""

import logging  # Keep for module-level logger if needed
from typing import Any, Final, TypeAlias

# BaseNode now relies on exec_res parameter in post
from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import ScenarioPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]
IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
IdentifyScenariosExecResult: TypeAlias = ScenarioList

# Module-level logger (can be used if needed outside class instance)
module_logger = logging.getLogger(__name__)


# --- Constants ---
DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500


class IdentifyScenariosNode(BaseNode):
    """Identify key interaction scenarios within the analyzed codebase using an LLM.

    This node takes identified code abstractions and their relationships as input.
    It then prompts a Large Language Model (LLM) to suggest relevant interaction
    scenarios (e.g., typical user flows, core system operations, error handling
    paths) that would be suitable for visualization with sequence diagrams.
    The LLM's response, expected in YAML format, is validated. Successfully
    identified scenarios are stored in the shared state for later use by the
    diagram generation node. The node handles potential LLM API errors and
    YAML validation failures gracefully by returning an empty list of scenarios,
    allowing the main processing flow to continue.
    """

    def prep(self, shared: SharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt.

        Gathers abstractions, relationships, project name, LLM configuration,
        and sequence diagram settings (max scenarios) from the shared state.
        Determines if scenario identification should be skipped based on whether
        sequence diagrams are enabled in the configuration or if no abstractions
        are available from previous analysis steps.

        Args:
            shared: The shared state dictionary containing analysis
                    results and application configuration.

        Returns:
            A dictionary containing context data needed for the `exec` step,
            or a dictionary with `skip: True` if conditions are not met.

        Raises:
            ValueError: If essential keys (e.g., 'config', 'llm_config',
                        'cache_config', 'abstractions', 'relationships',
                        'project_name') are missing from the shared state when
                        scenario identification is active.

        """
        self._logger.info("Preparing context for identifying interaction scenarios...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config = config.get("output", {})
            diagram_config_raw = output_config.get("diagram_generation", {})
            diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
            seq_config_raw = diagram_config.get("include_sequence_diagrams", {})
            seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}

            if not seq_config.get("enabled", False):
                self._logger.info("Sequence diagram generation is disabled. Skipping scenario identification.")
                return {"skip": True, "reason": "Sequence diagrams disabled in config"}

            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            if not abstractions:
                self._logger.warning("No abstractions available from previous step. Cannot identify scenarios.")
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
        except ValueError as e_val:
            self._logger.error(
                "Missing required shared data for scenario identification prep: %s", e_val, exc_info=True
            )
            raise
        except (KeyError, TypeError) as e_struct:
            self._logger.error("Error accessing config structure during scenario ID prep: %s", e_struct, exc_info=True)
            return {"skip": True, "reason": f"Config structure error: {e_struct}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Constructs a prompt using `ScenarioPrompts`, sends it to the LLM,
        and then parses and validates the YAML response. The number of returned
        scenarios is limited by `max_scenarios` from the configuration.

        Args:
            prep_res: The dictionary returned by the `prep` method containing
                      context for the LLM and configuration settings.

        Returns:
            A list of identified scenario description strings. Returns an empty
            list if skipping, if the LLM call fails, or if validation/parsing
            of the LLM response fails.

        Raises:
            ValueError: If essential keys are missing from `prep_res` (programming error).

        """
        if prep_res.get("skip", False):
            self._logger.info(
                "Skipping scenario identification execution (reason: '%s').", prep_res.get("reason", "N/A")
            )
            return []

        try:
            project_name: str = prep_res["project_name"]
            abstraction_listing: str = prep_res["abstraction_listing"]
            context_summary: str = prep_res["context_summary"]
            max_scenarios: int = prep_res["max_scenarios"]
            llm_config: dict[str, Any] = prep_res["llm_config"]
            cache_config: dict[str, Any] = prep_res["cache_config"]
        except KeyError as e_key:
            self._logger.error("Missing essential key from prep_res in exec: %s. Skipping.", e_key, exc_info=True)
            raise ValueError(f"Missing data from prep for scenario identification: {e_key}") from e_key

        self._logger.info(f"Identifying up to {max_scenarios} key scenarios for '{project_name}' using LLM...")
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
            self._logger.error("LLM API call failed during scenario identification: %s", e_llm, exc_info=True)
            return []

        try:
            scenario_list_raw = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": {"type": "string", "minLength": 5}},
            )
            validated_scenarios = [s.strip() for s in scenario_list_raw if isinstance(s, str) and s.strip()]

            if not validated_scenarios and scenario_list_raw:
                self._logger.warning("LLM response parsed as list, but yielded no valid non-empty scenario strings.")
            elif not validated_scenarios:
                self._logger.warning("LLM response did not contain any valid scenarios matching schema.")

            self._logger.info(f"Identified and validated {len(validated_scenarios)} scenarios.")
            return validated_scenarios[:max_scenarios]

        except ValidationFailure as e_val:
            self._logger.error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS] + (
                    "..." if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS else ""
                )
                module_logger.warning(  # Use module_logger for potentially large output
                    "Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet
                )
            return []
        except (TypeError, ValueError) as e_proc:
            self._logger.error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
            return []

    # --- UPDATED post method ---
    def post(
        self,
        shared: SharedState,
        prep_res: IdentifyScenariosPrepResult,
        exec_res: IdentifyScenariosExecResult,  # Parameter from PocketFlow
    ) -> None:
        """Update the shared state with the list of identified scenarios.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by the `prep` method.
            exec_res: The list of scenario description strings from `exec`,
                      passed by the flow runner.

        """
        shared.setdefault("identified_scenarios", [])

        if not prep_res.get("skip", False):
            # Use exec_res directly, as _run override was removed from BaseNode
            if isinstance(exec_res, list):
                shared["identified_scenarios"] = exec_res
                self._logger.info("Stored %d identified scenarios in shared state.", len(exec_res))
            else:
                self._logger.error(
                    "Invalid result type from scenario identification exec: %s. Expected list. "
                    "Shared state 'identified_scenarios' remains as default.",
                    type(exec_res).__name__,
                )
        else:
            self._logger.info("Scenario identification was skipped in prep. 'identified_scenarios' remains as default.")


# End of src/sourcelens/nodes/identify_scenarios.py
