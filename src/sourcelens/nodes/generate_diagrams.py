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

logger = logging.getLogger(__name__)

# --- Constants ---
MAX_FILES_TO_LIST_FOR_CONTEXT = 20


class GenerateDiagramsNode(BaseNode):
    """Generates architectural diagrams (Flowchart, Class, Package, Sequence)
    using an LLM based on configuration settings and project context.
    """

    def prep(self, shared: SharedState) -> Optional[PrepContext]:
        """Check config flags and gather context needed for diagram generation prompts.

        Args:
            shared: The shared state dictionary containing configuration and analysis results.

        Returns:
            A dictionary containing configuration flags (which diagrams to generate, format),
            LLM/cache configurations, and necessary project context (name, abstractions,
            relationships, files data if needed) for the `exec` method. Returns None if
            all diagram generation types are disabled in the configuration.

        """
        self._log_info("Preparing for diagram generation...")
        try:
            config: dict[str, Any] = self._get_required_shared(shared, "config")
            # Safely get nested diagram config with defaults
            output_config = config.get("output", {})
            diagram_config: dict[str, Any] = output_config.get("diagram_generation", {})
            llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
            cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

            # Determine which diagrams to generate based on config
            gen_flowchart: bool = diagram_config.get("include_relationship_flowchart", False)
            gen_class: bool = diagram_config.get("include_class_diagram", False)
            gen_pkg: bool = diagram_config.get("include_package_diagram", False)
            # Safely get nested sequence diagram config
            seq_config: dict[str, Any] = diagram_config.get("include_sequence_diagrams", {})
            gen_seq: bool = seq_config.get("enabled", False)

            # If no diagrams are enabled, skip preparation
            if not (gen_flowchart or gen_class or gen_pkg or gen_seq):
                self._log_info("All diagram generation types are disabled in configuration.")
                return None

            # Gather necessary context from shared state
            project_name: str = shared.get("project_name", "Unknown Project")
            abstractions: AbstractionsList = shared.get("abstractions", [])
            relationships: RelationshipsDict = shared.get("relationships", {})
            # Only fetch files_data if class or package diagrams are needed
            files_data: Optional[FilesData] = shared.get("files") if gen_class or gen_pkg else None

            # Store context needed by exec
            context_data: dict[str, Any] = {
                "project_name": project_name,
                "abstractions": abstractions,
                "relationships": relationships,
                "files_data": files_data,  # Will be None if not needed
                "config": config,  # Pass full config if needed later
                "llm_config": llm_config,
                "cache_config": cache_config,
            }

            # Return combined prep data
            return {
                "gen_flowchart": gen_flowchart,
                "gen_class": gen_class,
                "gen_pkg": gen_pkg,
                "gen_seq": gen_seq,
                "seq_scenarios": seq_config.get("scenarios", []),
                "seq_max": seq_config.get("max_diagrams", 5),
                "format": diagram_config.get("format", "mermaid"),
                "context": context_data,
            }
        except (ValueError, KeyError) as e:
            # Handle missing required shared state keys
            self._log_error("Error preparing diagram context due to missing shared state key: %s", e, exc=e)
            return None
        except Exception as e:
            # Catch any other unexpected errors during preparation
            self._log_error("Unexpected error during diagram generation preparation: %s", e, exc=e)
            return None

    def _call_llm_for_diagram(
        self,
        prompt: str,
        prep_res: PrepContext,
        diagram_type: str,
    ) -> Optional[DiagramMarkup]:
        """Helper function to call the LLM for diagram generation with validation.

        Calls the LLM using the provided prompt and configuration. Validates that
        the response is not empty and starts with the expected Mermaid keyword
        (e.g., 'flowchart TD', 'classDiagram').

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
        context: dict[str, Any] = prep_res["context"]
        llm_config: dict[str, Any] = context["llm_config"]
        cache_config: dict[str, Any] = context["cache_config"]

        # Map internal type name to expected Mermaid start keywords
        diagram_type_keywords: dict[str, list[str]] = {
            "flowchart": ["flowchart TD"],
            "class": ["classDiagram"],
            "package": ["graph TD"],  # Using graph TD for package dependencies
            "sequence": ["sequenceDiagram"],
        }
        expected_keywords: list[str] = diagram_type_keywords.get(diagram_type, [])
        if not expected_keywords:
            self._log_warning(
                "No expected start keywords defined for diagram type '%s'. Cannot validate start keyword.", diagram_type
            )
            # Proceed without keyword validation if none are defined

        try:
            markup_raw = call_llm(prompt, llm_config, cache_config)
            markup = str(markup_raw or "").strip()  # Ensure string and strip whitespace

            if not markup:
                self._log_warning("LLM returned empty response for %s diagram.", diagram_type)
                return None

            # Basic validation: check if it starts with expected keywords (if defined)
            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                self._log_warning(
                    "LLM %s diagram markup missing expected start keyword(s) for format '%s': %s. "
                    "LLM likely failed to follow format instructions.",
                    diagram_type,
                    fmt,
                    expected_keywords,
                )
                logger.debug("Received markup snippet: %s", markup[:200] + "...")  # Log snippet for debugging
                return None  # Failed validation

            # If validation passes (or wasn't required)
            self._log_info("Successfully generated and validated %s diagram markup.", diagram_type)
            return markup

        except LlmApiError as e:
            self._log_error("LLM API call failed while generating %s diagram: %s", diagram_type, e, exc=e)
            return None
        except (ValueError, KeyError, TypeError) as e:
            # Errors related to config or processing before/after LLM call
            self._log_error("Error processing LLM call configuration for %s diagram: %s", diagram_type, e, exc=e)
            return None
        except Exception as e:
            # Catch-all for other unexpected errors
            self._log_error("Unexpected error calling LLM for %s diagram: %s", diagram_type, e, exc=e)
            return None

    def _get_code_context_for_diagrams(self, prep_context: PrepContext) -> str:
        """Prepare a concise summary of code structure for diagram prompts.

        Currently provides a simple list of file paths. Can be enhanced to
        extract class/function definitions or import statements for better context.

        Args:
            prep_context: The dictionary returned by `prep`, containing project context.

        Returns:
            A string summarizing the code structure relevant for diagram generation.

        """
        files_data: Optional[FilesData] = prep_context["context"].get("files_data")
        if not files_data:
            return "No specific file data available for context."

        # Create a list of file paths, limited for brevity
        file_list_str_parts: list[str] = []
        for i, (path, _) in enumerate(files_data):
            if i >= MAX_FILES_TO_LIST_FOR_CONTEXT:
                file_list_str_parts.append("- ... (more files)")
                break
            # Normalize path separators for consistency
            normalized_path = path.replace("\\", "/")
            file_list_str_parts.append(f"- {normalized_path}")

        return f"Project File Structure Overview:\n{chr(10).join(file_list_str_parts)}"

    def exec(self, prep_res: Optional[PrepContext]) -> DiagramResultDict:
        """Generate the configured diagrams by calling the LLM with specific prompts.

        Iterates through the diagram types enabled in the configuration (`prep_res`),
        formats the appropriate prompt using data from the context, calls the LLM
        via the `_call_llm_for_diagram` helper, and collects the resulting markup.

        Args:
            prep_res: The dictionary returned by the `prep` method, containing configuration
                      flags and context, or None if diagram generation was skipped in prep.

        Returns:
            A dictionary containing the generated markup for each requested diagram type.
            Keys correspond to diagram types (e.g., 'relationship_flowchart_markup') and
            values are the markup strings or None if generation failed or was skipped.
            'sequence_diagrams_markup' holds a list of markups.

        """
        if prep_res is None:
            self._log_info("Diagram generation skipped as per prep result.")
            return {}

        results: DiagramResultDict = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],  # Initialize as empty list
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

        # --- Generate Sequence Diagrams ---
        if prep_res["gen_seq"]:
            self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
            generated_seq_diagrams: list[DiagramMarkup] = []
            # Limit scenarios based on max_diagrams config
            scenarios_to_generate = prep_res["seq_scenarios"][: prep_res["seq_max"]]

            for scenario in scenarios_to_generate:
                self._log_info("Generating sequence diagram for scenario: %s", scenario)
                # Use revised method to get potentially more descriptive text
                scenario_desc = self._get_scenario_description(scenario)
                # Create context object, NOTE: abstractions/relationships removed from prompt formatting
                sequence_context = SequenceDiagramContext(
                    project_name=context_data["project_name"],
                    scenario_name=scenario,
                    scenario_description=scenario_desc,
                    diagram_format=diagram_format,
                )
                prompt = format_sequence_diagram_prompt(sequence_context)
                markup = self._call_llm_for_diagram(prompt, prep_res, "sequence")
                if markup:
                    generated_seq_diagrams.append(markup)
                else:
                    # Log failure for specific scenario
                    self._log_warning("Failed to generate sequence diagram for scenario: %s", scenario)

            if generated_seq_diagrams:
                results["sequence_diagrams_markup"] = generated_seq_diagrams
                self._log_info("Generated %d sequence diagram(s).", len(generated_seq_diagrams))
            else:
                self._log_warning("No sequence diagrams were successfully generated for the requested scenarios.")

        return results

    def _get_scenario_description(self, scenario_name: str) -> str:
        """Provide descriptive text for predefined sequence diagram scenario prompts. (REVISED)

        Provides slightly more detailed descriptions hinting at potential components
        or key steps involved in each scenario.

        Args:
            scenario_name: The key name of the scenario (e.g., 'main_success_flow').

        Returns:
            A short descriptive string explaining the scenario.

        """
        # Revised descriptions to potentially guide the LLM better
        descriptions: dict[str, str] = {
            "main_success_flow": (
                "Illustrate the main success path: User runs CLI -> Flow orchestrates Nodes "
                "(Fetch, Analyze, Order, Write, Combine) -> Final tutorial output is generated."
            ),
            "node_llm_interaction_success": (
                "Show a generic Node calling the central LLM utility (`call_llm`) with a prompt, "
                "receiving a successful response, and processing it."
            ),
            "output_generation": (
                "Detail the final stage: The CombineTutorial Node receives processed data "
                "(chapters, index info) and writes the final Markdown files to the FileSystem."
            ),
            "fetch_code_local_source": (
                "Depict the FetchCode Node being triggered for a local directory source. Show it "
                "interacting with the FileSystem to read and filter files based on configuration."
            ),
            "fetch_code_github_source": (
                "Show the FetchCode Node interacting with the GitHub utility (`crawl_github_repo`) "
                "to fetch code from a repository URL, potentially involving API calls or Git clone."
            ),
            "config_loading_failure": (
                "Illustrate an early application exit: The `main` function attempts to load "
                "configuration (`load_config`), validation fails, an error is logged, and the process terminates."
            ),
            "llm_api_error_retry": (
                "Show a Node calling the LLM (`call_llm`), receiving an `LlmApiError` (e.g., rate limit). "
                "Illustrate the Flow's retry mechanism attempting the Node's execution again after a delay."
            ),
            "fetch_code_github_failure": (
                "Depict the FetchCode Node calling the GitHub utility (`crawl_github_repo`), which fails "
                "(e.g., repo not found, auth error), raises `GithubApiError`, and the flow handles the error."
            ),
            "llm_response_validation_failure": (
                "Illustrate a Node (e.g., AnalyzeRelationships) receiving a response from `call_llm`, "
                "but the subsequent validation step (`validate_yaml_dict`) fails, raising `ValidationFailure`."
            ),
        }
        # Fallback for unknown scenarios
        return descriptions.get(scenario_name, f"A sequence illustrating the specific scenario: '{scenario_name}'.")

    def post(self, shared: SharedState, prep_res: Optional[PrepContext], exec_res: DiagramResultDict) -> None:
        """Update shared state with generated diagram markups.

        Takes the results from the `exec` phase and updates the corresponding keys
        in the `shared` state dictionary (e.g., `shared['class_diagram_markup']`).

        Args:
            shared: The shared state dictionary to update.
            prep_res: The dictionary returned by `prep` (unused in this method).
            exec_res: The dictionary containing generated diagram markups from `exec`.

        """
        if exec_res:
            updated_keys: list[str] = []
            # Explicitly update shared state with results, checking if they exist and are valid
            for key, value in exec_res.items():
                # Only update if the value is a non-empty string or a non-empty list
                if (isinstance(value, str) and value) or (isinstance(value, list) and value):
                    shared[key] = value
                    updated_keys.append(key)
                elif key in shared and value is None:
                    # If exec returns None for a key that might exist, log it but don't clear
                    logger.debug(
                        "Diagram generation for '%s' resulted in None, key remains unchanged in shared state.", key
                    )

            if updated_keys:
                self._log_info("Updated shared state with generated diagram results for keys: %s", updated_keys)
            else:
                self._log_info("No valid diagram markup was generated to update shared state.")
        else:
            # This case means exec returned an empty dictionary or None
            self._log_info("No diagram results dictionary returned from exec step. Shared state unchanged.")


# End of src/sourcelens/nodes/generate_diagrams.py
