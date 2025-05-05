# src/sourcelens/nodes/identify_scenarios.py

"""Node responsible for identifying relevant interaction scenarios based on code analysis."""

import logging
from typing import Any, TypeAlias

from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import format_identify_scenarios_prompt
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]  # List of scenario descriptions
# Type for the dictionary returned by the prep method
IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
# Type for the result returned by the exec method
IdentifyScenariosExecResult: TypeAlias = ScenarioList

logger = logging.getLogger(__name__)


class IdentifyScenariosNode(BaseNode):
    """Identifies key interaction scenarios within the analyzed codebase using an LLM.

    Takes the identified abstractions and relationships as input, prompts the LLM
    to suggest relevant scenarios (e.g., typical user flows, error handling paths),
    validates the response, and stores the identified scenarios in the shared state.
    """

    # Maximum number of scenarios to request from the LLM
    DEFAULT_MAX_SCENARIOS_TO_IDENTIFY = 5

    def prep(self, shared: SharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt.

        Gathers abstractions, relationships, project name, and LLM configuration
        from the shared state.

        Args:
            shared: The shared state dictionary containing analysis results and config.

        Returns:
            A dictionary containing context data needed for the `exec` step.
            Returns a dictionary indicating skip if diagram generation or sequence
            diagrams specifically are disabled, or if no abstractions were found.

        Raises:
            ValueError: If essential keys like 'abstractions' or 'relationships'
                        are missing from the shared state when sequence diagrams are enabled.

        """
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config = config.get("output", {})
            diagram_config = output_config.get("diagram_generation", {})
            seq_config = diagram_config.get("include_sequence_diagrams", {})

            # Check if sequence diagram generation is enabled
            if not seq_config.get("enabled", False):
                self._log_info("Sequence diagram generation is disabled. Skipping scenario identification.")
                return {"skip": True}

            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            # Get max scenarios from config, fallback to default
            max_scenarios = seq_config.get("max_diagrams", self.DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)

            if not abstractions:
                self._log_warning("No abstractions found. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions"}

            # Prepare context for prompt
            abstraction_listing = "\n".join(
                f"- {i} # {str(a.get('name', f'Unnamed {i}'))}" for i, a in enumerate(abstractions)
            )
            # Optionally add relationships summary or details if helpful for scenario generation
            # For now, keep it simple based on abstractions.
            context_summary = relationships.get("summary", "No project summary available.")

            return {
                "skip": False,
                "project_name": project_name,
                "abstraction_listing": abstraction_listing,
                "context_summary": str(context_summary),
                "num_abstractions": len(abstractions),
                "max_scenarios": max_scenarios,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }

        except ValueError as e:
            # Handle missing required shared data specifically
            self._log_error("Missing required shared data for scenario identification prep: %s", e, exc=e)
            raise  # Re-raise as prep cannot proceed without required data
        except KeyError as e:
            self._log_error("Missing key during scenario identification preparation: %s", e, exc=e)
            return {"skip": True, "reason": f"Missing key: {e}"}
        except TypeError as e:
            self._log_error("Type error during scenario identification preparation: %s", e, exc=e)
            return {"skip": True, "reason": f"Type error: {e}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call the LLM to identify relevant scenarios and validate the response.

        Args:
            prep_res: The dictionary returned by the `prep` method.

        Returns:
            A list of identified scenario description strings (ScenarioList).
            Returns an empty list if skipping or if validation fails.

        Raises:
            LlmApiError: If the LLM API call fails after configured retries.
            ValidationFailure: If the LLM response fails YAML parsing or basic validation.

        """
        if prep_res.get("skip", False):
            self._log_info(
                "Skipping scenario identification execution based on prep result (%s).",
                prep_res.get("reason", "config disabled"),
            )
            return []

        project_name: str = prep_res["project_name"]
        abstraction_listing: str = prep_res["abstraction_listing"]
        context_summary: str = prep_res["context_summary"]
        max_scenarios: int = prep_res["max_scenarios"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info(f"Identifying up to {max_scenarios} key scenarios for '{project_name}' using LLM...")

        # Format the prompt
        prompt = format_identify_scenarios_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing,
            context_summary=context_summary,
            max_scenarios=max_scenarios,
        )

        # Call LLM
        response_raw: str
        try:
            response_raw = call_llm(prompt, llm_config, cache_config)
        except LlmApiError:
            # Error already logged by call_llm or base node retry mechanism
            raise  # Re-raise for the flow runner

        # Validate and parse the LLM response
        try:
            # Expecting a simple list of strings
            scenario_list_raw = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": {"type": "string", "minLength": 5}},  # Basic schema
            )
            # Ensure items are actually strings and non-empty after validation
            validated_scenarios = [str(s).strip() for s in scenario_list_raw if isinstance(s, str) and str(s).strip()]

            if not validated_scenarios:
                raise ValidationFailure(
                    "LLM response parsed, but contained no valid scenario strings.", raw_output=response_raw
                )

            self._log_info(f"Successfully identified and validated {len(validated_scenarios)} scenarios.")
            # Return only up to max_scenarios requested
            return validated_scenarios[:max_scenarios]

        except ValidationFailure as e:
            # Log specific validation failure and return empty list
            self._log_error("Validation failed processing identified scenarios: %s", e)
            # Optionally re-raise if this should halt the flow: raise
            return []  # Return empty list on validation failure
        except (TypeError, ValueError) as e:
            # Catch specific errors during validation/parsing
            self._log_error("Error processing identified scenarios: %s", e, exc=e)
            return []  # Return empty list on specific error

    def post(
        self, shared: SharedState, prep_res: IdentifyScenariosPrepResult, exec_res: IdentifyScenariosExecResult
    ) -> None:
        """Update the shared state with the list of identified scenarios.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by `prep`.
            exec_res: The list of scenario description strings returned by `exec`.

        """
        if not prep_res.get("skip", False):
            if isinstance(exec_res, list):
                shared["identified_scenarios"] = exec_res
                self._log_info("Stored %d identified scenarios in shared state.", len(exec_res))
            else:
                # This case should ideally not happen if exec returns [] on failure
                self._log_error(
                    "Invalid result type from scenario identification exec: %s. Expected list.", type(exec_res).__name__
                )
                shared["identified_scenarios"] = []  # Store empty list to prevent downstream errors
        else:
            self._log_info("Scenario identification was skipped, 'identified_scenarios' not updated.")
            # Ensure the key exists but is empty if skipped
            if "identified_scenarios" not in shared:
                shared["identified_scenarios"] = []


# End of src/sourcelens/nodes/identify_scenarios.py
