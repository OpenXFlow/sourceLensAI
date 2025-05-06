# src/sourcelens/nodes/identify_scenarios.py

"""Node responsible for identifying relevant interaction scenarios."""

import logging
from typing import Any, TypeAlias

from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import format_identify_scenarios_prompt
from sourcelens.utils.llm_api import LlmApiError, call_llm
from sourcelens.utils.validation import ValidationFailure, validate_yaml_list

# --- Type Aliases ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
ScenarioList: TypeAlias = list[str]
IdentifyScenariosPrepResult: TypeAlias = dict[str, Any]
IdentifyScenariosExecResult: TypeAlias = ScenarioList

logger = logging.getLogger(__name__)


class IdentifyScenariosNode(BaseNode):
    """Identify key interaction scenarios within the codebase using an LLM."""

    DEFAULT_MAX_SCENARIOS_TO_IDENTIFY = 5

    def prep(self, shared: SharedState) -> IdentifyScenariosPrepResult:
        """Prepare context for the scenario identification LLM prompt."""
        # ... (Implementation remains the same as previous fix) ...
        self._log_info("Preparing context for identifying interaction scenarios...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config = config.get("output", {})
            diagram_config = output_config.get("diagram_generation", {})
            seq_config = diagram_config.get("include_sequence_diagrams", {})
            if not seq_config.get("enabled", False):
                self._log_info("Sequence diagrams disabled. Skipping scenario identification.")
                return {"skip": True}
            abstractions: AbstractionsList = self._get_required_shared(shared, "abstractions")
            relationships: RelationshipsDict = self._get_required_shared(shared, "relationships")
            project_name: str = self._get_required_shared(shared, "project_name")
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
            max_scenarios = seq_config.get("max_diagrams", self.DEFAULT_MAX_SCENARIOS_TO_IDENTIFY)
            # --- Handle case where abstractions might be empty due to previous node failure ---
            if not abstractions:
                self._log_warning("No abstractions available from previous step. Cannot identify scenarios.")
                return {"skip": True, "reason": "No abstractions available"}
            # --- End Handle empty abstractions ---
            abstraction_listing = "\n".join(
                f"- {i} # {str(a.get('name', f'Unnamed {i}'))}" for i, a in enumerate(abstractions)
            )
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
            self._log_error("Missing required shared data for scenario ID prep: %s", e, exc=e)
            raise
        except KeyError as e:
            self._log_error("Missing key during scenario ID prep: %s", e, exc=e)
            return {"skip": True, "reason": f"Missing key: {e}"}
        except TypeError as e:
            self._log_error("Type error during scenario ID prep: %s", e, exc=e)
            return {"skip": True, "reason": f"Type error: {e}"}

    def exec(self, prep_res: IdentifyScenariosPrepResult) -> IdentifyScenariosExecResult:
        """Call LLM to identify relevant scenarios and validate the response."""
        if prep_res.get("skip", False):
            self._log_info("Skipping scenario identification exec (%s).", prep_res.get("reason", "config disabled"))
            return []

        project_name: str = prep_res["project_name"]
        abstraction_listing: str = prep_res["abstraction_listing"]
        context_summary: str = prep_res["context_summary"]
        max_scenarios: int = prep_res["max_scenarios"]
        llm_config: dict[str, Any] = prep_res["llm_config"]
        cache_config: dict[str, Any] = prep_res["cache_config"]

        self._log_info(f"Identifying up to {max_scenarios} key scenarios for '{project_name}' using LLM...")
        prompt = format_identify_scenarios_prompt(
            project_name=project_name,
            abstraction_listing=abstraction_listing,
            context_summary=context_summary,
            max_scenarios=max_scenarios,
        )

        response_raw: str
        try:
            response_raw = call_llm(prompt, llm_config, cache_config)
        except LlmApiError as e:
            # Allow flow continuation if LLM call fails after retries
            self._log_error("LLM call failed for scenarios: %s", e, exc=e)
            return []  # Return empty on API failure

        # --- MODIFIED: Wrap validation/parsing in try/except ---
        try:
            scenario_list_raw = validate_yaml_list(
                raw_llm_output=response_raw,
                list_schema={"type": "array", "items": {"type": "string", "minLength": 5}},
            )
            validated_scenarios = [str(s).strip() for s in scenario_list_raw if isinstance(s, str) and str(s).strip()]

            if not validated_scenarios:
                # Don't raise, just log if parsing succeeded but list is empty/invalid
                self._log_warning("LLM response parsed, but yielded no valid scenario strings.")
                return []

            self._log_info(f"Successfully identified and validated {len(validated_scenarios)} scenarios.")
            return validated_scenarios[:max_scenarios]

        except ValidationFailure as e_val:
            self._log_error("YAML validation/parsing failed for scenarios: %s", e_val)
            if e_val.raw_output:
                MAX_SNIPPET_LENGTH = 500
                snippet = e_val.raw_output[:MAX_SNIPPET_LENGTH] + (
                    "..." if len(e_val.raw_output) > MAX_SNIPPET_LENGTH else ""
                )
                logger.warning("Problematic raw LLM output snippet:\n---\n%s\n---", snippet)
            return []  # Return empty list instead of raising
        except (TypeError, ValueError) as e_proc:  # Catch other potential parsing errors
            self._log_error("Error processing identified scenarios: %s", e_proc, exc=e_proc)
            return []  # Return empty list on specific error

    def post(
        self, shared: SharedState, prep_res: IdentifyScenariosPrepResult, exec_res: IdentifyScenariosExecResult
    ) -> None:
        """Update the shared state with the list of identified scenarios."""
        # Ensure the key always exists, even if exec failed or was skipped
        shared.setdefault("identified_scenarios", [])

        if not prep_res.get("skip", False):
            if isinstance(exec_res, list):
                shared["identified_scenarios"] = exec_res  # Overwrite if exec succeeded
                self._log_info("Stored %d identified scenarios.", len(exec_res))
            else:
                self._log_error("Invalid result type from scenario ID exec: %s.", type(exec_res).__name__)
                # Keep the default empty list set by setdefault
        else:
            self._log_info("Scenario ID skipped, 'identified_scenarios' remains empty.")


# End of src/sourcelens/nodes/identify_scenarios.py
