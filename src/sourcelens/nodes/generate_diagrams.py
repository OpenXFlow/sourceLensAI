# src/sourcelens/nodes/generate_diagrams.py

"""Node responsible for generating architectural diagrams using an LLM."""

import logging
from typing import Any, Optional, TypeAlias

from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import (
    SequenceDiagramContext,
    format_class_diagram_prompt,
    format_package_diagram_prompt,
    format_relationship_flowchart_prompt,
    format_sequence_diagram_prompt,
)
from sourcelens.utils.llm_api import LlmApiError, call_llm

# --- Type Aliases ---
DiagramMarkup: TypeAlias = str
DiagramResultDict: TypeAlias = dict[str, Optional[DiagramMarkup | list[DiagramMarkup]]]
PrepContext: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
FilesData: TypeAlias = list[tuple[str, str]]  # List of (path, content) tuples
IdentifiedScenarioList: TypeAlias = list[str]  # List of scenario descriptions

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_FILES_TO_LIST_FOR_CONTEXT = 20


class GenerateDiagramsNode(BaseNode):
    """Generates architectural diagrams (Flowchart, Class, Package, Sequence)
    using an LLM based on configuration settings and project context.

    For sequence diagrams, it now uses dynamically identified scenarios if available,
    falling back to predefined ones only if dynamic identification fails or is skipped.
    """

    def prep(self, shared: SharedState) -> Optional[PrepContext]:
        """Check config flags and gather context needed for diagram generation prompts.

        Args:
            shared: The shared state dictionary containing configuration and analysis results.

        Returns:
            A dictionary containing configuration flags, LLM/cache configurations,
            and necessary project context (name, abstractions, relationships, files data,
            dynamically identified scenarios if applicable). Returns None if all diagram
            generation types are disabled.

        """
        self._log_info("Preparing for diagram generation...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            output_config = config.get("output", {})
            diagram_config: dict[str, Any] = output_config.get("diagram_generation", {})
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

            # Determine which diagrams to generate
            gen_flowchart: bool = diagram_config.get("include_relationship_flowchart", False)
            gen_class: bool = diagram_config.get("include_class_diagram", False)
            gen_pkg: bool = diagram_config.get("include_package_diagram", False)
            seq_config: dict[str, Any] = diagram_config.get("include_sequence_diagrams", {})
            gen_seq: bool = seq_config.get("enabled", False)

            if not (gen_flowchart or gen_class or gen_pkg or gen_seq):
                self._log_info("All diagram generation types are disabled.")
                return None

            # Gather common context
            project_name: str = shared.get("project_name", "Unknown Project")
            abstractions: AbstractionsList = shared.get("abstractions", [])
            relationships: RelationshipsDict = shared.get("relationships", {})
            files_data: Optional[FilesData] = shared.get("files") if gen_class or gen_pkg else None

            # Prepare scenarios for sequence diagrams
            scenarios_to_use: IdentifiedScenarioList = []
            if gen_seq:
                # Prioritize dynamically identified scenarios
                identified_scenarios = shared.get("identified_scenarios")
                if isinstance(identified_scenarios, list) and identified_scenarios:
                    scenarios_to_use = identified_scenarios
                    self._log_info(
                        "Using %d dynamically identified scenarios for sequence diagrams.", len(scenarios_to_use)
                    )
                else:
                    self._log_warning(
                        "Dynamic scenarios not found or empty in shared state. Sequence diagram generation might be limited or fail."
                    )
                    # Optionally fall back to config scenarios if needed, but current logic assumes dynamic is primary
                    # fallback_scenarios = seq_config.get("scenarios", [])
                    # if fallback_scenarios:
                    #    self._log_info("Falling back to %d scenarios defined in config.", len(fallback_scenarios))
                    #    scenarios_to_use = fallback_scenarios # This would require _get_scenario_description back

            context_data: dict[str, Any] = {
                "project_name": project_name,
                "abstractions": abstractions,
                "relationships": relationships,
                "files_data": files_data,
                "config": config,
                "llm_config": llm_config,
                "cache_config": cache_config,
            }

            return {
                "gen_flowchart": gen_flowchart,
                "gen_class": gen_class,
                "gen_pkg": gen_pkg,
                "gen_seq": gen_seq,
                "identified_scenarios": scenarios_to_use,  # Use dynamically identified scenarios
                "seq_max": seq_config.get("max_diagrams", 5),  # Still respect max limit
                "format": diagram_config.get("format", "mermaid"),
                "context": context_data,
            }
        except (ValueError, KeyError) as e:
            self._log_error("Error preparing diagram context due to missing shared state key: %s", e, exc=e)
            return None
        except Exception as e:
            self._log_error("Unexpected error during diagram generation preparation: %s", e, exc=e)
            return None

    def _call_llm_for_diagram(
        self,
        prompt: str,
        prep_res: PrepContext,
        diagram_type: str,
    ) -> Optional[DiagramMarkup]:
        """Helper function to call the LLM for diagram generation with validation.

        Args:
            prompt: The formatted prompt string for the specific diagram type.
            prep_res: The dictionary returned by `prep`, containing configs and context.
            diagram_type: A string identifying the diagram type (e.g., "flowchart", "class")
                          used for logging and validation keywords.

        Returns:
            The generated diagram markup string if successful and basic validation passes,
            otherwise None.

        """
        fmt: str = prep_res.get("format", "mermaid")
        # Access context correctly
        context_data: dict[str, Any] = prep_res["context"]
        llm_config: dict[str, Any] = context_data["llm_config"]
        cache_config: dict[str, Any] = context_data["cache_config"]

        diagram_type_keywords: dict[str, list[str]] = {
            "flowchart": ["flowchart TD"],
            "class": ["classDiagram"],
            "package": ["graph TD"],
            "sequence": ["sequenceDiagram"],
        }
        expected_keywords: list[str] = diagram_type_keywords.get(diagram_type, [])
        if not expected_keywords:
            self._log_warning(
                "No expected start keywords defined for diagram type '%s'. Cannot validate start keyword.", diagram_type
            )

        try:
            markup_raw = call_llm(prompt, llm_config, cache_config)
            markup = str(markup_raw or "").strip()

            if not markup:
                self._log_warning("LLM returned empty response for %s diagram.", diagram_type)
                return None

            # Validation: check start keyword (if defined)
            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                self._log_warning(
                    "LLM %s diagram markup missing expected start keyword(s) for format '%s': %s.",
                    diagram_type,
                    fmt,
                    expected_keywords,
                )
                logger.debug("Received markup snippet: %s", markup[:200] + "...")
                return None

            self._log_info("Successfully generated and validated %s diagram markup.", diagram_type)
            return markup

        except LlmApiError as e:
            self._log_error("LLM API call failed while generating %s diagram: %s", diagram_type, e, exc=e)
            return None
        except Exception as e:
            # Catch other errors like JSON parsing if call_llm changes
            self._log_error("Unexpected error processing LLM call for %s diagram: %s", diagram_type, e, exc=e)
            return None

    def _get_code_context_for_diagrams(self, prep_context: PrepContext) -> str:
        """Prepare a concise summary of code structure for class/package diagrams.

        Args:
            prep_context: The dictionary returned by `prep`, containing project context.

        Returns:
            A string summarizing the code structure.

        """
        # Access context correctly
        context_data: dict[str, Any] = prep_context["context"]
        files_data: Optional[FilesData] = context_data.get("files_data")
        if not files_data:
            return "No specific file data available for context."

        file_list_str_parts: list[str] = []
        for i, (path, _) in enumerate(files_data):
            if i >= MAX_FILES_TO_LIST_FOR_CONTEXT:
                file_list_str_parts.append("- ... (more files)")
                break
            normalized_path = path.replace("\\", "/")
            file_list_str_parts.append(f"- {normalized_path}")

        return f"Project File Structure Overview:\n{chr(10).join(file_list_str_parts)}"

    def exec(self, prep_res: Optional[PrepContext]) -> DiagramResultDict:
        """Generate the configured diagrams by calling the LLM with specific prompts.

        Args:
            prep_res: The dictionary returned by the `prep` method, or None if skipped.

        Returns:
            A dictionary containing generated diagram markups.

        """
        if prep_res is None:
            self._log_info("Diagram generation skipped as per prep result.")
            return {}

        results: DiagramResultDict = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],
        }
        context_data: dict[str, Any] = prep_res["context"]
        diagram_format: str = prep_res["format"]

        # --- Generate Relationship Flowchart ---
        if prep_res["gen_flowchart"]:
            self._log_info("Generating Relationship Flowchart (format: %s)...", diagram_format)
            prompt = format_relationship_flowchart_prompt(
                project_name=context_data["project_name"],
                abstractions=context_data["abstractions"],
                relationships=context_data["relationships"],
                diagram_format=diagram_format,
            )
            # Pass full prep_res which includes context for helper call
            markup = self._call_llm_for_diagram(prompt, prep_res, "flowchart")
            if markup:
                results["relationship_flowchart_markup"] = markup

        # --- Generate Class Hierarchy Diagram ---
        if prep_res["gen_class"]:
            self._log_info("Generating Class Hierarchy diagram (format: %s)...", diagram_format)
            if context_data["files_data"] is None:
                self._log_warning("Cannot generate class diagram: files_data is missing from context.")
            else:
                code_context_str = self._get_code_context_for_diagrams(prep_res)
                prompt = format_class_diagram_prompt(
                    project_name=context_data["project_name"],
                    code_context=code_context_str,
                    diagram_format=diagram_format,
                )
                markup = self._call_llm_for_diagram(prompt, prep_res, "class")
                if markup:
                    results["class_diagram_markup"] = markup

        # --- Generate Package Dependency Diagram ---
        if prep_res["gen_pkg"]:
            self._log_info("Generating Package Dependency diagram (format: %s)...", diagram_format)
            if context_data["files_data"] is None:
                self._log_warning("Cannot generate package diagram: files_data is missing from context.")
            else:
                structure_context_str = self._get_code_context_for_diagrams(prep_res)
                prompt = format_package_diagram_prompt(
                    project_name=context_data["project_name"],
                    structure_context=structure_context_str,
                    diagram_format=diagram_format,
                )
                markup = self._call_llm_for_diagram(prompt, prep_res, "package")
                if markup:
                    results["package_diagram_markup"] = markup

        # --- Generate Sequence Diagrams (Using Identified Scenarios) ---
        if prep_res["gen_seq"]:
            self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
            generated_seq_diagrams: list[DiagramMarkup] = []
            # Get identified scenarios from prep_res and limit by seq_max
            scenarios_to_generate = prep_res["identified_scenarios"][: prep_res["seq_max"]]

            if not scenarios_to_generate:
                self._log_warning("No identified scenarios provided to generate sequence diagrams.")
            else:
                self._log_info("Attempting to generate %d sequence diagrams.", len(scenarios_to_generate))

                for i, scenario_desc in enumerate(scenarios_to_generate):
                    # Use the scenario description directly. Create a simple name for context/logging.
                    # Example: use first few words + ellipsis as name
                    words = scenario_desc.split()
                    scenario_name = " ".join(words[:5]) + ("..." if len(words) > 5 else "")
                    self._log_info("Generating sequence diagram for scenario %d: '%s'", i + 1, scenario_name)

                    # Create context, pass only necessary info to prompt formatter
                    sequence_context = SequenceDiagramContext(
                        project_name=context_data["project_name"],
                        scenario_name=scenario_name,  # Use derived name
                        scenario_description=scenario_desc,  # Full identified description
                        diagram_format=diagram_format,
                        # abstractions/relationships not directly used by revised prompt
                    )
                    prompt = format_sequence_diagram_prompt(sequence_context)
                    markup = self._call_llm_for_diagram(prompt, prep_res, "sequence")
                    if markup:
                        generated_seq_diagrams.append(markup)
                    else:
                        self._log_warning("Failed to generate sequence diagram for scenario: %s", scenario_name)

                if generated_seq_diagrams:
                    results["sequence_diagrams_markup"] = generated_seq_diagrams
                    self._log_info("Generated %d sequence diagram(s).", len(generated_seq_diagrams))
                else:
                    self._log_warning("No sequence diagrams were successfully generated.")

        return results

    # Remove _get_scenario_description as it's no longer used for fixed keys
    # def _get_scenario_description(self, scenario_name: str) -> str: ...

    def post(self, shared: SharedState, prep_res: Optional[PrepContext], exec_res: DiagramResultDict) -> None:
        """Update shared state with generated diagram markups.

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by `prep` (unused here).
            exec_res: The dictionary containing generated diagram markups from `exec`.

        """
        if exec_res:
            updated_keys: list[str] = []
            for key, value in exec_res.items():
                if (isinstance(value, str) and value) or (isinstance(value, list) and value):
                    shared[key] = value
                    updated_keys.append(key)
                elif key in shared and value is None:
                    logger.debug(
                        "Diagram generation for '%s' resulted in None, key remains unchanged in shared state.", key
                    )

            if updated_keys:
                self._log_info("Updated shared state with generated diagram results for keys: %s", updated_keys)
            else:
                self._log_info("No valid diagram markup was generated to update shared state.")
        else:
            self._log_info("No diagram results dictionary returned from exec step. Shared state unchanged.")


# End of src/sourcelens/nodes/generate_diagrams.py
