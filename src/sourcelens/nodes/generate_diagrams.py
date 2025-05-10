# src/sourcelens/nodes/generate_diagrams.py

"""Node responsible for generating architectural diagrams using an LLM."""

import logging  # Keep for module-level logger if needed
from typing import Any, Final, Optional, TypeAlias, Union

# BaseNode now relies on exec_res parameter in post
from sourcelens.nodes.base_node import BaseNode, SharedState
from sourcelens.prompts import DiagramPrompts, SequenceDiagramContext
from sourcelens.utils.llm_api import LlmApiError, call_llm

# Type Aliases and Constants
DiagramMarkup: TypeAlias = Optional[str]
DiagramResultDict: TypeAlias = dict[str, DiagramMarkup | list[DiagramMarkup]]
PrepContext: TypeAlias = dict[str, Any]
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
FilesData: TypeAlias = list[tuple[str, str]]
IdentifiedScenarioList: TypeAlias = list[str]

# Module-level logger for utility functions if not part of a class instance
module_logger = logging.getLogger(__name__)


MAX_FILES_FOR_STRUCTURE_CONTEXT: Final[int] = 50
SCENARIO_NAME_MAX_WORDS: Final[int] = 5


class GenerateDiagramsNode(BaseNode):
    """Generate architectural diagrams using an LLM.

    This node is responsible for prompting an LLM to create various
    diagrams (Relationship Flowchart, Class Diagram, Package Diagram, and
    Sequence Diagrams) based on the project's analyzed context and
    configuration settings. The generated diagram markups are then stored
    in the shared state for later use in the tutorial.
    """

    # ... (Metódy _escape_quotes, _get_structure_context,
    #      _format_simple_relationship_flowchart_prompt_internal,
    #      _prepare_diagram_flags_and_configs, _gather_diagram_context_data,
    #      prep, _call_llm_for_diagram, a všetky _generate_... metódy
    #      zostávajú nezmenené, používajú self._logger alebo module_logger)
    def _escape_quotes(self, text: Union[str, int, float]) -> str:
        """Convert input to string and escape double quotes for Mermaid."""
        return str(text).replace('"', "#quot;")

    def _get_structure_context(self, files_data: Optional[FilesData]) -> str:
        """Prepare a string summarizing the project file structure."""
        if not files_data:
            return "No file data available."
        file_list_parts: list[str] = [
            f"- {path.replace(chr(92), '/')}"
            for i, (path, _) in enumerate(files_data)
            if i < MAX_FILES_FOR_STRUCTURE_CONTEXT
        ]
        if len(files_data) > MAX_FILES_FOR_STRUCTURE_CONTEXT:
            file_list_parts.append(f"- ... ({len(files_data) - MAX_FILES_FOR_STRUCTURE_CONTEXT} more files)")
        if not file_list_parts:
            return "Project structure context is empty."
        return f"Project File Structure Overview:\n{chr(10).join(file_list_parts)}"

    def _format_simple_relationship_flowchart_prompt_internal(
        self,
        project_name: str,
        abstractions: AbstractionsList,
        relationships: RelationshipsDict,
        diagram_format: str = "mermaid",
    ) -> str:
        """Format prompt for a SIMPLE abstraction relationship flowchart."""
        return DiagramPrompts.format_relationship_flowchart_prompt(
            project_name=project_name,
            abstractions=abstractions,
            relationships=relationships,
            diagram_format=diagram_format,
            structure_context=None,
        )

    def _prepare_diagram_flags_and_configs(self, shared: SharedState) -> dict[str, Any]:
        """Extract diagram flags and LLM/cache configs from shared state."""
        config: dict[str, Any] = self._get_required_shared(shared, "config")
        output_config = config.get("output", {})
        diagram_config_raw = output_config.get("diagram_generation", {})
        diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}
        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")
        flags_and_configs = {
            "gen_flowchart": diagram_config.get("include_relationship_flowchart", False),
            "gen_class": diagram_config.get("include_class_diagram", False),
            "gen_pkg": diagram_config.get("include_package_diagram", False),
            "llm_config": llm_config,
            "cache_config": cache_config,
            "diagram_format": diagram_config.get("format", "mermaid"),
        }
        seq_config_raw = diagram_config.get("include_sequence_diagrams", {})
        seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}
        flags_and_configs["gen_seq"] = seq_config.get("enabled", False)
        flags_and_configs["seq_max"] = seq_config.get("max_diagrams", 5)
        return flags_and_configs

    def _gather_diagram_context_data(self, shared: SharedState, flags_configs: dict[str, Any]) -> dict[str, Any]:
        """Gather core context data for diagram generation."""
        project_name: str = str(shared.get("project_name", "Unknown Project"))
        abstractions: AbstractionsList = []
        if flags_configs["gen_flowchart"] or flags_configs["gen_seq"]:
            abstractions = self._get_required_shared(shared, "abstractions")
        relationships: RelationshipsDict = {}
        if flags_configs["gen_flowchart"]:
            relationships = self._get_required_shared(shared, "relationships")
        files_data: Optional[FilesData] = None
        if flags_configs["gen_class"] or flags_configs["gen_pkg"]:
            files_data = shared.get("files")
        structure_context_str = ""
        if files_data and (flags_configs["gen_pkg"] or flags_configs["gen_class"]):
            structure_context_str = self._get_structure_context(files_data)
        elif (flags_configs["gen_pkg"] or flags_configs["gen_class"]) and not files_data:
            self._logger.warning("Cannot generate structure_context: files_data missing.")
        scenarios_to_use: IdentifiedScenarioList = []
        if flags_configs["gen_seq"]:
            identified_scenarios_raw = shared.get("identified_scenarios")
            scenarios_to_use = (
                [str(s) for s in identified_scenarios_raw if isinstance(s, str) and s.strip()]
                if isinstance(identified_scenarios_raw, list)
                else []
            )
        if flags_configs["gen_seq"] and not scenarios_to_use:
            self._logger.warning("Sequence diagrams enabled, but no valid scenarios found in shared state.")
        return {
            "project_name": project_name,
            "abstractions": abstractions,
            "relationships": relationships,
            "structure_context": structure_context_str,
            "files_data_for_class_pkg": files_data,
            "identified_scenarios": scenarios_to_use,
            "llm_config": flags_configs["llm_config"],
            "cache_config": flags_configs["cache_config"],
        }

    def prep(self, shared: SharedState) -> Optional[PrepContext]:
        """Prepare context and configuration flags for diagram generation."""
        self._logger.info("Preparing for diagram generation...")
        try:
            flags_and_configs = self._prepare_diagram_flags_and_configs(shared)
            if not any(flags_and_configs[k] for k in flags_and_configs if k.startswith("gen_")):
                self._logger.info("All diagram types are disabled in configuration.")
                return None
            context_data = self._gather_diagram_context_data(shared, flags_and_configs)
            return {
                "gen_flowchart": flags_and_configs["gen_flowchart"],
                "gen_class": flags_and_configs["gen_class"],
                "gen_pkg": flags_and_configs["gen_pkg"],
                "gen_seq": flags_and_configs["gen_seq"],
                "seq_max": flags_and_configs["seq_max"],
                "diagram_format": flags_and_configs["diagram_format"],
                "context": context_data,
            }
        except ValueError as e_val:
            self._logger.error("Error preparing diagram context: %s", e_val, exc_info=True)
            raise
        except Exception as e_prep:
            self._logger.error("Unexpected error during diagram prep: %s", e_prep, exc_info=True)
            return None

    def _call_llm_for_diagram(
        self,
        prompt: str,
        llm_config: dict[str, Any],
        cache_config: dict[str, Any],
        diagram_type: str,
        expected_keywords: list[str],
    ) -> DiagramMarkup:
        """Call LLM for diagram generation and validate the response."""
        markup: DiagramMarkup = None
        try:
            markup_raw = call_llm(prompt, llm_config, cache_config)
            markup = str(markup_raw or "").strip()
            if not markup:
                self._logger.warning("LLM returned empty response for %s diagram.", diagram_type)
                return None
            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                log_msg = (
                    f"LLM {diagram_type} diagram markup missing expected start. Expected one of: {expected_keywords}."
                )
                self._logger.warning(log_msg)
                self._logger.debug("Received markup snippet: %s", markup[:200] + "...")
                return None
            self._logger.info("Successfully generated %s diagram markup.", diagram_type)
            return markup
        except LlmApiError as e_llm:
            self._logger.error("LLM API call failed for %s diagram: %s", diagram_type, e_llm, exc_info=True)
            return None
        except Exception as e_other:
            self._logger.error(
                "Unexpected error during LLM call for %s diagram: %s", diagram_type, e_other, exc_info=True
            )
            return None

    def _generate_simple_flowchart(self, prep_res: PrepContext) -> DiagramMarkup:
        """Generate the simple relationship flowchart."""
        context_data = prep_res["context"]
        return self._call_llm_for_diagram(
            prompt=self._format_simple_relationship_flowchart_prompt_internal(
                project_name=context_data["project_name"],
                abstractions=context_data["abstractions"],
                relationships=context_data["relationships"],
                diagram_format=prep_res["diagram_format"],
            ),
            llm_config=context_data["llm_config"],
            cache_config=context_data["cache_config"],
            diagram_type="simple_flowchart",
            expected_keywords=["flowchart TD"],
        )

    def _generate_class_diagram(self, prep_res: PrepContext) -> DiagramMarkup:
        """Generate the class hierarchy diagram."""
        context_data = prep_res["context"]
        files_data_for_context = context_data.get("files_data_for_class_pkg")
        code_context_str = (
            self._get_structure_context(files_data_for_context)
            if files_data_for_context
            else context_data.get("structure_context", "")
        )
        if not code_context_str:
            self._logger.warning("No code context provided for class diagram generation.")
        return self._call_llm_for_diagram(
            prompt=DiagramPrompts.format_class_diagram_prompt(
                project_name=context_data["project_name"],
                code_context=code_context_str or "No code context available.",
                diagram_format=prep_res["diagram_format"],
            ),
            llm_config=context_data["llm_config"],
            cache_config=context_data["cache_config"],
            diagram_type="class",
            expected_keywords=["classDiagram"],
        )

    def _generate_package_diagram(self, prep_res: PrepContext) -> DiagramMarkup:
        """Generate the package dependency diagram."""
        context_data = prep_res["context"]
        structure_context_str = context_data.get("structure_context", "")
        if not structure_context_str or structure_context_str == "No file data available.":
            self._logger.warning("Cannot generate package diagram: structure_context missing or empty.")
            return None
        return self._call_llm_for_diagram(
            prompt=DiagramPrompts.format_package_diagram_prompt(
                project_name=context_data["project_name"],
                structure_context=structure_context_str,
                diagram_format=prep_res["diagram_format"],
            ),
            llm_config=context_data["llm_config"],
            cache_config=context_data["cache_config"],
            diagram_type="package",
            expected_keywords=["graph TD"],
        )

    def _generate_sequence_diagrams(self, prep_res: PrepContext) -> list[DiagramMarkup]:
        """Generate sequence diagrams based on identified scenarios."""
        context_data = prep_res["context"]
        diagram_format = prep_res["diagram_format"]
        self._logger.info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: list[DiagramMarkup] = []
        scenarios = context_data.get("identified_scenarios", [])
        max_diagrams = prep_res.get("seq_max", 0)
        scenarios_to_generate = scenarios[:max_diagrams]
        if not scenarios_to_generate:
            self._logger.warning("No identified scenarios provided for sequence diagrams.")
            return []
        self._logger.info("Attempting to generate %d sequence diagrams.", len(scenarios_to_generate))
        for i, scenario_desc in enumerate(scenarios_to_generate):
            words = scenario_desc.split()
            scenario_name_short = " ".join(words[:SCENARIO_NAME_MAX_WORDS])
            if len(words) > SCENARIO_NAME_MAX_WORDS:
                scenario_name_short += "..."
            self._logger.info("Generating sequence diagram %d: '%s'", i + 1, scenario_name_short)
            sequence_context_obj = SequenceDiagramContext(
                project_name=context_data["project_name"],
                scenario_name=scenario_name_short,
                scenario_description=scenario_desc,
                diagram_format=diagram_format,
            )
            markup = self._call_llm_for_diagram(
                prompt=DiagramPrompts.format_sequence_diagram_prompt(sequence_context_obj),
                llm_config=context_data["llm_config"],
                cache_config=context_data["cache_config"],
                diagram_type="sequence",
                expected_keywords=["sequenceDiagram"],
            )
            generated_seq_diagrams.append(markup)
        valid_diagrams = [d for d in generated_seq_diagrams if d]
        if not valid_diagrams:
            self._logger.warning("No sequence diagrams generated successfully.")
        else:
            self._logger.info("Generated %d valid sequence diagram(s).", len(valid_diagrams))
        return valid_diagrams

    def exec(self, prep_res: Optional[PrepContext]) -> DiagramResultDict:
        """Generate diagrams based on prepared context and configuration flags."""
        if prep_res is None:
            self._logger.info("Diagram generation skipped as per prep_res.")
            return {}
        results: DiagramResultDict = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],
        }
        if prep_res.get("gen_flowchart"):
            results["relationship_flowchart_markup"] = self._generate_simple_flowchart(prep_res)
        if prep_res.get("gen_class"):
            results["class_diagram_markup"] = self._generate_class_diagram(prep_res)
        if prep_res.get("gen_pkg"):
            results["package_diagram_markup"] = self._generate_package_diagram(prep_res)
        if prep_res.get("gen_seq"):
            results["sequence_diagrams_markup"] = self._generate_sequence_diagrams(prep_res)
        return results

    # --- UPDATED post method ---
    def post(self, shared: SharedState, prep_res: Optional[PrepContext], exec_res: DiagramResultDict) -> None:
        """Update shared state with generated diagram markups.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from `prep` (unused).
            exec_res: Result from `exec` (dictionary of diagram markups), passed by
                      the flow runner.

        """
        if isinstance(exec_res, dict):  # Check if exec_res is a dictionary as expected
            updated_keys: list[str] = []
            for key, value in exec_res.items():
                is_valid_str = isinstance(value, str) and value.strip()
                # Check for list and if it contains at least one non-empty string
                is_valid_list = isinstance(value, list) and any(
                    item for item in value if isinstance(item, str) and item.strip()
                )

                if is_valid_str or is_valid_list:
                    shared[key] = value
                    updated_keys.append(key)
                elif key in shared and value is None:
                    self._logger.debug("Diagram '%s' was None, key in shared state remains/set to None.", key)
                    shared[key] = None  # Explicitly set to None if LLM failed for this diagram
                elif key == "sequence_diagrams_markup" and isinstance(value, list) and not value:
                    # If it's specifically sequence_diagrams_markup and it's an empty list
                    shared[key] = []  # Store empty list if no sequence diagrams were generated
                    updated_keys.append(key)  # Still consider it "updated" to an empty list

            if updated_keys:
                self._logger.info("Stored diagram results for keys: %s", updated_keys)
            else:
                # This can happen if all diagrams were disabled or all failed to generate
                self._logger.info("No valid diagram markup was generated or updated in shared state.")
        else:
            self._logger.warning(
                "No diagram results or unexpected type (%s) from exec. Shared state not updated for diagrams.",
                type(exec_res).__name__,
            )


# End of src/sourcelens/nodes/generate_diagrams.py
