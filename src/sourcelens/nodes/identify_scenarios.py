# src/sourcelens/nodes/identify_scenarios.py

"""Node responsible for identifying relevant interaction scenarios for diagrams.

This node uses an LLM to suggest key interaction scenarios within the analyzed
codebase, based on identified abstractions and their relationships. These
scenarios can then be used to generate sequence diagrams or other visualizations.
"""

import logging
from typing import Any, Final  # TypeAlias removed

from typing_extensions import TypeAlias  # Using typing_extensions

from sourcelens.prompts import ScenarioPrompts
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# Import BaseNode and generic TypeVars
from .base_node import BaseNode, SharedState

# --- Type Aliases specific to this Node ---
IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
"""Result of the prep phase: context for LLM or a skip flag."""
ScenarioList: TypeAlias = list[str]
"""Type alias for a list of scenario description strings."""
IdentifyScenariosExecResult: TypeAlias = ScenarioList
"""Result of the exec phase: a list of identified scenarios."""

# --- Other Type Aliases used within this module ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]

# Module-level logger (can be used if needed outside class instance)
# Node-specific logging will use self._logger from BaseNode
module_logger: logging.Logger = logging.getLogger(__name__)


# --- Constants ---
DEFAULT_MAX_SCENARIOS_TO_IDENTIFY: Final[int] = 5
"""Default maximum number of scenarios to identify if not specified in config."""
MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS: Final[int] = 500
"""Max length of LLM raw output snippet to log on validation failure."""


class IdentifyScenariosNode(BaseNode[IdentifyScenariosPrepResult, IdentifyScenariosExecResult]):
    """Identify key interaction scenarios within the analyzed codebase using an LLM.

    This node takes identified code abstractions and their relationships as input.
    It then prompts a Large Language Model (LLM) to suggest relevant interaction
    scenarios (e.g., typical user flows, core system operations) suitable for
    visualization. The LLM's YAML response is validated, and successfully
    identified scenarios are stored in the shared state.
    """

    def prep(self, shared: SharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt.

        Gathers abstractions, relationships, project name, LLM configuration,
        and sequence diagram settings from the shared state. Determines if
        scenario identification should be skipped based on configuration or
        availability of abstractions.

        Args:
            shared: The shared state dictionary, expected to contain 'config',
                    'llm_config', 'cache_config', 'abstractions',
                    'relationships', and 'project_name'.

        Returns:
            A dictionary (`IdentifyScenariosPrepResult`) containing context data
            for the `exec` step, or a dictionary with `skip: True` if conditions
            for scenario identification are not met.

        Raises:
            ValueError: If essential keys are missing from `shared_state` when
                        scenario identification is active and required data is absent.

        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config: dict[str, Any] = config.get("output", {})
            diagram_config_raw: Any = output_config.get("diagram_generation", {})
            diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
            seq_config_raw: Any = diagram_config.get("include_sequence_diagrams", {})
            seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}

            if not seq_config.get("enabled", False):
                self._log_info("Sequence diagram generation is disabled. Skipping scenario identification.")
                return {"skip": True, "reason": "Sequence diagrams disabled in config"}

            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            if not abstractions:
                self._log_warning("No abstractions available. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}

            relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            max_scenarios: int = seq_config.get("max_diagrams", DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)

            abstraction_listing_parts: list[str] = []
            for i, abstr_item in enumerate(abstractions):
                name_val: Any = abstr_item.get("name", f"Unnamed Abstraction {i}")
                abstraction_listing_parts.append(f"- {i} # {str(name_val)}")
            abstraction_listing: str = "\n".join(abstraction_listing_parts)

            context_summary_val: Any = relationships.get("summary", "No project summary available.")
            context_summary: str = str(context_summary_val)

            return {
                "skip": False,
                "project_name": project_name,
                "abstraction_listing": abstraction_listing,
                "context_summary": context_summary,
                "num_abstractions": len(
                    abstractions
                ),  # Retained for prompt, though not directly used by LLM in current prompt
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }
        except ValueError:  # From _get_required_shared
            # Error already logged by _get_required_shared
            self._log_error("Scenario ID prep failed due to missing essential shared data.", exc_info=True)
            # Re-raise to be handled by flow engine if necessary, or return skip
            # For robustness, return skip to allow flow to potentially continue if designed for it
            return {"skip": True, "reason": "Missing essential shared data for scenario identification."}
        except (KeyError, TypeError) as e_struct:  # More specific than general Exception
            self._log_error("Error accessing config structure during scenario ID prep: %s", e_struct, exc_info=True)
            return {"skip": True, "reason": f"Configuration structure error: {e_struct}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Constructs a prompt using `ScenarioPrompts`, sends it to the LLM,
        and then parses and validates the YAML response. The number of returned
        scenarios is limited by `max_scenarios` from the configuration.

        Args:
            prep_res: The dictionary returned by the `prep` method, containing
                      context for the LLM and configuration settings.

        Returns:
            A list of identified scenario description strings (`ScenarioList`).
            Returns an empty list if skipping, if the LLM call fails, or if
            validation/parsing of the LLM response fails.

        """
        if prep_res.get("skip", True):
            self._log_info("Skipping scenario identification execution. Reason: '%s'", prep_res.get("reason", "N/A"))
            return []

        # All keys below are expected if skip is False
        project_name: str = prep_res["project_name"]
        abstraction_listing: str = prep_res["abstraction_listing"]
        context_summary: str = prep_res["context_summary"]
        max_scenarios: int = prep_res["max_scenarios"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

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
            # Schema for a list of strings, each with minLength 5
            list_item_schema = {"type": "string", "minLength": 5}  # PLR2004 fix for 5
            scenario_list_raw: list[Any] = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": list_item_schema},
            )
            # Ensure items are strings and strip whitespace
            validated_scenarios: ScenarioList = [
                s.strip() for s in scenario_list_raw if isinstance(s, str) and s.strip()
            ]

            if not validated_scenarios and scenario_list_raw:  # If list was not empty but became empty after validation
                self._log_warning("LLM response for scenarios parsed as list, but yielded no valid non-empty strings.")
            elif not validated_scenarios:  # If list was empty to begin with
                self._log_warning("LLM response did not contain any valid scenarios matching schema.")

            self._log_info("Identified and validated %d scenarios.", len(validated_scenarios))
            return validated_scenarios[:max_scenarios]  # Ensure we don't exceed max_scenarios

        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                snippet = e_val.raw_output[:MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS]
                if len(e_val.raw_output) > MAX_RAW_OUTPUT_SNIPPET_LEN_SCENARIOS:
                    snippet += "..."
                module_logger.warning("Problematic raw LLM output snippet for scenarios:\n---\n%s\n---", snippet)
            return []
        except (TypeError, ValueError) as e_proc:  # For issues during list comprehension or stripping
            self._log_error("Error processing identified scenarios from LLM response: %s", e_proc, exc_info=True)
            return []

    def post(
        self,
        shared: SharedState,
        prep_res: IdentifyScenariosPrepResult,
        exec_res: IdentifyScenariosExecResult,
    ) -> None:
        """Update the shared state with the list of identified scenarios.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by the `prep` method (used here to
                      check if execution was skipped).
            exec_res: The list of scenario description strings from `exec`.
                      This will be an empty list if `prep` indicated skipping or
                      if `exec` failed.

        """
        shared.setdefault("identified_scenarios", [])  # Ensure key exists

        if not prep_res.get("skip", True):  # If not skipped in prep
            # exec_res is already ScenarioList (list[str]) or an empty list
            shared["identified_scenarios"] = exec_res
            self._log_info("Stored %d identified scenarios in shared state.", len(exec_res))
        else:
            self._log_info(
                "Scenario identification was skipped in prep. 'identified_scenarios' remains default (empty list)."
            )


# End of src/sourcelens/nodes/identify_scenarios.py
