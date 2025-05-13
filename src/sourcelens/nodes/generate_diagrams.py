# src/sourcelens/nodes/generate_diagrams.py

"""Node responsible for generating architectural diagrams using an LLM."""

import logging
from typing import Any, Final, Optional, Union  # TypeAlias removed from here

# Import TypeAlias from typing_extensions for broader compatibility
from typing_extensions import TypeAlias

from sourcelens.prompts import DiagramPrompts, SequenceDiagramContext
from sourcelens.utils.llm_api import LlmApiError, call_llm

# Import BaseNode
from .base_node import BaseNode, SharedState

# --- Type Aliases specific to this Node ---
PrepContext: TypeAlias = dict[str, Any]
"""Type alias for the dictionary containing preparation results for diagram generation."""
DiagramMarkup: TypeAlias = Optional[str]
"""Type alias for a string containing diagram markup, or None if generation failed."""
DiagramResultDict: TypeAlias = dict[str, Union[DiagramMarkup, list[DiagramMarkup]]]
"""Type alias for the dictionary returned by exec, holding generated diagram markups."""

# SLPrepResType for GenerateDiagramsNode
GenerateDiagramsPrepResult: TypeAlias = Optional[PrepContext]
# SLExecResType for GenerateDiagramsNode
GenerateDiagramsExecResult: TypeAlias = DiagramResultDict


# --- Other Type Aliases used within this module ---
AbstractionsList: TypeAlias = list[dict[str, Any]]
RelationshipsDict: TypeAlias = dict[str, Any]
FilesDataList: TypeAlias = list[tuple[str, str]]
IdentifiedScenarioList: TypeAlias = list[str]

# Module-level logger
module_logger: logging.Logger = logging.getLogger(__name__)

# --- Constants ---
MAX_FILES_FOR_STRUCTURE_CONTEXT: Final[int] = 50
SCENARIO_NAME_MAX_WORDS: Final[int] = 5
DEFAULT_DIAGRAM_FORMAT: Final[str] = "mermaid"


class GenerateDiagramsNode(BaseNode[GenerateDiagramsPrepResult, GenerateDiagramsExecResult]):
    """Generate architectural diagrams using an LLM.

    This node prompts an LLM to create various diagrams (Relationship Flowchart,
    Class Diagram, Package Diagram, and Sequence Diagrams) based on the project's
    analyzed context and configuration settings. The generated diagram markups
    are then stored in the shared state.
    """

    def _escape_mermaid_quotes(self: "GenerateDiagramsNode", text: Union[str, int, float]) -> str:
        """Convert input to string and escape double quotes for Mermaid.

        Args:
            text: The input text, number, or float to be escaped.

        Returns:
            A string with double quotes replaced by the Mermaid escape sequence.

        """
        return str(text).replace('"', "#quot;")

    def _get_structure_context(self: "GenerateDiagramsNode", files_data: Optional[FilesDataList]) -> str:
        """Prepare a string summarizing the project file structure.

        This context is used for diagrams that benefit from understanding the
        overall layout of files and directories, like package or class diagrams.

        Args:
            files_data: A list of (filepath, content) tuples, or None.

        Returns:
            A string describing the file structure, or a message if no data is available.

        """
        if not files_data:
            return "No file data available to generate structure context."

        file_list_parts: list[str] = [
            f"- {path.replace(chr(92), '/')}"
            for i, (path, _) in enumerate(files_data)
            if i < MAX_FILES_FOR_STRUCTURE_CONTEXT
        ]
        if len(files_data) > MAX_FILES_FOR_STRUCTURE_CONTEXT:
            additional_files_count = len(files_data) - MAX_FILES_FOR_STRUCTURE_CONTEXT
            file_list_parts.append(f"- ... ({additional_files_count} more files)")

        if not file_list_parts:
            return "Project structure context is empty (no files after filtering)."
        return f"Project File Structure Overview:\n{chr(10).join(file_list_parts)}"

    def _prepare_diagram_flags_and_configs(self: "GenerateDiagramsNode", shared: SharedState) -> dict[str, Any]:
        """Extract diagram generation flags and LLM/cache configurations from shared state.

        Args:
            shared: The shared state dictionary.

        Returns:
            A dictionary containing boolean flags for each diagram type,
            the diagram format, sequence diagram specific settings, and
            LLM/cache configurations.

        """
        config: dict[str, Any] = self._get_required_shared(shared, "config")
        output_config: dict[str, Any] = config.get("output", {})
        diagram_config_raw: Any = output_config.get("diagram_generation", {})
        diagram_config: dict[str, Any] = diagram_config_raw if isinstance(diagram_config_raw, dict) else {}

        llm_config: dict[str, Any] = self._get_required_shared(shared, "llm_config")
        cache_config: dict[str, Any] = self._get_required_shared(shared, "cache_config")

        flags_and_configs: dict[str, Any] = {
            "gen_flowchart": bool(diagram_config.get("include_relationship_flowchart", False)),
            "gen_class": bool(diagram_config.get("include_class_diagram", False)),
            "gen_pkg": bool(diagram_config.get("include_package_diagram", False)),
            "llm_config": llm_config,
            "cache_config": cache_config,
            "diagram_format": str(diagram_config.get("format", DEFAULT_DIAGRAM_FORMAT)),
        }

        seq_config_raw: Any = diagram_config.get("include_sequence_diagrams", {})
        seq_config: dict[str, Any] = seq_config_raw if isinstance(seq_config_raw, dict) else {}
        flags_and_configs["gen_seq"] = bool(seq_config.get("enabled", False))
        flags_and_configs["seq_max"] = int(seq_config.get("max_diagrams", 5))
        return flags_and_configs

    def _gather_diagram_context_data(
        self: "GenerateDiagramsNode", shared: SharedState, flags_configs: dict[str, Any]
    ) -> PrepContext:
        """Gather all core context data required for generating diagrams.

        Args:
            shared: The shared state dictionary.
            flags_configs: A dictionary of flags and configurations.

        Returns:
            A `PrepContext` dictionary containing all necessary data.

        """
        project_name: str = str(shared.get("project_name", "Unknown Project"))
        abstractions: AbstractionsList = []
        if flags_configs.get("gen_flowchart") or flags_configs.get("gen_seq"):
            abstractions = self._get_required_shared(shared, "abstractions")

        relationships: RelationshipsDict = {}
        if flags_configs.get("gen_flowchart"):
            relationships = self._get_required_shared(shared, "relationships")

        files_data_val: Any = shared.get("files")
        files_data_for_context: Optional[FilesDataList] = files_data_val if isinstance(files_data_val, list) else None

        structure_context_str: str = ""
        if files_data_for_context and (flags_configs.get("gen_pkg") or flags_configs.get("gen_class")):
            structure_context_str = self._get_structure_context(files_data_for_context)
        elif (flags_configs.get("gen_pkg") or flags_configs.get("gen_class")) and not files_data_for_context:
            self._log_warning("Cannot generate structure_context for diagrams: 'files' data missing.")
            structure_context_str = "File structure data was not available."

        scenarios_to_use: IdentifiedScenarioList = []
        if flags_configs.get("gen_seq"):
            identified_scenarios_raw: Any = shared.get("identified_scenarios")
            scenarios_to_use = (
                [str(s) for s in identified_scenarios_raw if isinstance(s, str) and s.strip()]
                if isinstance(identified_scenarios_raw, list)
                else []
            )
            if not scenarios_to_use:
                self._log_warning("Sequence diagrams enabled, but no valid scenarios found.")

        return {
            "project_name": project_name,
            "abstractions": abstractions,
            "relationships": relationships,
            "structure_context": structure_context_str,
            "files_data_for_class_pkg": files_data_for_context,
            "identified_scenarios": scenarios_to_use,
            "llm_config": flags_configs["llm_config"],
            "cache_config": flags_configs["cache_config"],
            "gen_flowchart": flags_configs["gen_flowchart"],
            "gen_class": flags_configs["gen_class"],
            "gen_pkg": flags_configs["gen_pkg"],
            "gen_seq": flags_configs["gen_seq"],
            "seq_max": flags_configs["seq_max"],
            "diagram_format": flags_configs["diagram_format"],
        }

    def prep(self, shared: SharedState) -> GenerateDiagramsPrepResult:
        """Prepare context and configuration flags for diagram generation.

        Args:
            shared: The shared state dictionary.

        Returns:
            A `PrepContext` dictionary if any diagrams are enabled, otherwise None.

        """
        self._log_info("Preparing for diagram generation...")
        try:
            flags_and_configs = self._prepare_diagram_flags_and_configs(shared)
            if not any(
                flags_and_configs.get(k) for k in flags_and_configs if isinstance(k, str) and k.startswith("gen_")
            ):
                self._log_info("All diagram types are disabled. Skipping diagram generation.")
                return None
            return self._gather_diagram_context_data(shared, flags_and_configs)
        except ValueError as e_val:
            self._log_error("Error preparing diagram context (missing shared data): %s", e_val, exc_info=True)
            raise
        except Exception as e_prep:  # noqa: BLE001 - Catch-all for unexpected prep errors
            self._log_error("Unexpected error during diagram preparation: %s", e_prep, exc_info=True)
            return None

    def _call_llm_for_diagram(
        self: "GenerateDiagramsNode",
        prompt: str,
        llm_config: dict[str, Any],
        cache_config: dict[str, Any],
        diagram_type: str,
        expected_keywords: Optional[list[str]] = None,
    ) -> DiagramMarkup:
        """Call LLM for diagram generation and validate the response.

        Args:
            prompt: The formatted prompt string for the LLM.
            llm_config: LLM API configuration.
            cache_config: LLM cache configuration.
            diagram_type: A string identifying the type of diagram for logging.
            expected_keywords: An optional list of keywords, one of which the
                               response should start with.

        Returns:
            The generated diagram markup as a string, or None on failure.

        """
        markup: DiagramMarkup = None
        try:
            markup_raw: str = call_llm(prompt, llm_config, cache_config)
            markup = str(markup_raw or "").strip()

            if not markup:
                self._log_warning("LLM returned empty response for %s diagram.", diagram_type)
                return None

            if expected_keywords and not any(markup.startswith(kw) for kw in expected_keywords):
                log_msg = (
                    f"LLM {diagram_type} diagram markup missing expected start. "
                    f"Expected one of: {expected_keywords}. Received: '{markup[:50]}...'"
                )
                self._log_warning(log_msg)
                return None

            self._log_info("Successfully generated %s diagram markup.", diagram_type)
            return markup
        except LlmApiError as e_llm:
            self._log_error("LLM API call failed for %s diagram: %s", diagram_type, e_llm, exc_info=True)
            return None
        except Exception as e_other:  # noqa: BLE001 - Catch-all for unexpected LLM processing errors
            self._log_error(
                "Unexpected error during LLM call or processing for %s diagram: %s",
                diagram_type,
                e_other,
                exc_info=True,
            )
            return None

    def _generate_relationship_flowchart(self: "GenerateDiagramsNode", prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the relationship flowchart diagram.

        Args:
            prep_res_context: The context dictionary from the prep phase.

        Returns:
            The Mermaid markup for the flowchart, or None on failure.

        """
        abstractions: AbstractionsList = prep_res_context.get("abstractions", [])
        relationships: RelationshipsDict = prep_res_context.get("relationships", {})

        return self._call_llm_for_diagram(
            prompt=DiagramPrompts.format_relationship_flowchart_prompt(
                project_name=str(prep_res_context.get("project_name")),
                abstractions=abstractions,
                relationships=relationships,
                diagram_format=str(prep_res_context.get("diagram_format")),
            ),
            llm_config=prep_res_context["llm_config"],
            cache_config=prep_res_context["cache_config"],
            diagram_type="relationship_flowchart",
            expected_keywords=["flowchart TD"],
        )

    def _generate_class_diagram(self: "GenerateDiagramsNode", prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the class hierarchy diagram.

        Args:
            prep_res_context: The context dictionary from the prep phase.

        Returns:
            The Mermaid markup for the class diagram, or None on failure.

        """
        code_context_str = str(prep_res_context.get("structure_context", "No code context available."))
        if not code_context_str or code_context_str == "No file data available to generate structure context.":
            self._log_warning("No proper code/structure context for class diagram. Diagram might be suboptimal.")

        return self._call_llm_for_diagram(
            prompt=DiagramPrompts.format_class_diagram_prompt(
                project_name=str(prep_res_context.get("project_name")),
                code_context=code_context_str,
                diagram_format=str(prep_res_context.get("diagram_format")),
            ),
            llm_config=prep_res_context["llm_config"],
            cache_config=prep_res_context["cache_config"],
            diagram_type="class",
            expected_keywords=["classDiagram"],
        )

    def _generate_package_diagram(self: "GenerateDiagramsNode", prep_res_context: PrepContext) -> DiagramMarkup:
        """Generate the package dependency diagram.

        Args:
            prep_res_context: The context dictionary from the prep phase.

        Returns:
            The Mermaid markup for the package diagram, or None if context is missing.

        """
        structure_context_str = str(prep_res_context.get("structure_context", ""))
        if (
            not structure_context_str
            or structure_context_str == "No file data available to generate structure context."
        ):
            self._log_warning("Cannot generate package diagram: structure_context is missing or empty.")
            return None

        return self._call_llm_for_diagram(
            prompt=DiagramPrompts.format_package_diagram_prompt(
                project_name=str(prep_res_context.get("project_name")),
                structure_context=structure_context_str,
                diagram_format=str(prep_res_context.get("diagram_format")),
            ),
            llm_config=prep_res_context["llm_config"],
            cache_config=prep_res_context["cache_config"],
            diagram_type="package",
            expected_keywords=["graph TD"],
        )

    def _generate_sequence_diagrams(self: "GenerateDiagramsNode", prep_res_context: PrepContext) -> list[DiagramMarkup]:
        """Generate sequence diagrams based on identified scenarios.

        Args:
            prep_res_context: The context dictionary from the prep phase.

        Returns:
            A list of Mermaid markup strings for sequence diagrams.

        """
        diagram_format: str = str(prep_res_context.get("diagram_format", DEFAULT_DIAGRAM_FORMAT))
        self._log_info("Generating Sequence diagrams (format: %s)...", diagram_format)
        generated_seq_diagrams: list[DiagramMarkup] = []

        scenarios: IdentifiedScenarioList = prep_res_context.get("identified_scenarios", [])
        max_diagrams_to_generate: int = prep_res_context.get("seq_max", 0)
        scenarios_to_process = scenarios[:max_diagrams_to_generate]

        if not scenarios_to_process:
            self._log_warning("No scenarios available or 'seq_max' is 0. No sequence diagrams generated.")
            return []

        self._log_info(
            "Attempting to generate up to %d sequence diagrams from %d scenarios.",
            max_diagrams_to_generate,
            len(scenarios),
        )

        for i, scenario_desc in enumerate(scenarios_to_process):
            words = scenario_desc.split()
            scenario_name_short = " ".join(words[:SCENARIO_NAME_MAX_WORDS])
            if len(words) > SCENARIO_NAME_MAX_WORDS:
                scenario_name_short += "..."
            self._log_info(
                "Generating sequence diagram %d/%d: '%s'", i + 1, len(scenarios_to_process), scenario_name_short
            )

            sequence_context_obj = SequenceDiagramContext(
                project_name=str(prep_res_context.get("project_name")),
                scenario_name=scenario_name_short,
                scenario_description=scenario_desc,
                diagram_format=diagram_format,
            )
            markup = self._call_llm_for_diagram(
                prompt=DiagramPrompts.format_sequence_diagram_prompt(sequence_context_obj),
                llm_config=prep_res_context["llm_config"],
                cache_config=prep_res_context["cache_config"],
                diagram_type=f"sequence (scenario: {scenario_name_short})",
                expected_keywords=["sequenceDiagram"],
            )
            generated_seq_diagrams.append(markup)

        valid_diagrams_count = sum(1 for d in generated_seq_diagrams if d is not None and d.strip())
        if valid_diagrams_count == 0 and scenarios_to_process:
            self._log_warning("No sequence diagrams were generated successfully despite available scenarios.")
        else:
            self._log_info("Generated %d valid sequence diagram(s).", valid_diagrams_count)
        return generated_seq_diagrams

    def exec(self, prep_res: GenerateDiagramsPrepResult) -> GenerateDiagramsExecResult:
        """Generate diagrams based on prepared context and configuration flags.

        Args:
            prep_res: The result from the `prep` method.

        Returns:
            A `DiagramResultDict` containing the markup for each generated diagram.

        """
        results: DiagramResultDict = {
            "relationship_flowchart_markup": None,
            "class_diagram_markup": None,
            "package_diagram_markup": None,
            "sequence_diagrams_markup": [],
        }
        if prep_res is None:
            self._log_info("Diagram generation skipped as per preparation step.")
            return results

        if prep_res.get("gen_flowchart"):
            results["relationship_flowchart_markup"] = self._generate_relationship_flowchart(prep_res)
        if prep_res.get("gen_class"):
            results["class_diagram_markup"] = self._generate_class_diagram(prep_res)
        if prep_res.get("gen_pkg"):
            results["package_diagram_markup"] = self._generate_package_diagram(prep_res)
        if prep_res.get("gen_seq"):
            results["sequence_diagrams_markup"] = self._generate_sequence_diagrams(prep_res)

        return results

    def post(
        self, shared: SharedState, prep_res: GenerateDiagramsPrepResult, exec_res: GenerateDiagramsExecResult
    ) -> None:
        """Update shared state with generated diagram markups.

        Args:
            shared: The shared state dictionary to update.
            prep_res: Result from the `prep` phase.
            exec_res: Dictionary of diagram markups from the `exec` phase.

        """
        del prep_res

        updated_keys: list[str] = []
        if isinstance(exec_res, dict):
            for key, value in exec_res.items():
                is_valid_str_markup = isinstance(value, str) and value.strip()
                is_valid_list_markup = isinstance(value, list) and any(
                    isinstance(item, str) and item.strip() for item in value
                )

                if is_valid_str_markup or is_valid_list_markup:
                    shared[key] = value
                    updated_keys.append(key)
                elif key in shared and value is None:
                    self._log_info(
                        "Diagram for '%s' was None, key in shared state set/remains None.", key
                    )  # Changed from _log_debug
                    shared[key] = None
                elif key == "sequence_diagrams_markup" and isinstance(value, list) and not value:
                    shared[key] = []
                    updated_keys.append(key)

            if updated_keys:
                self._log_info("Stored diagram generation results in shared state for keys: %s", sorted(updated_keys))
            else:
                self._log_info("No valid diagram markups were generated or updated in shared state.")
        else:
            self._log_warning(
                "No diagram results or unexpected type (%s) from exec. Shared state not updated for diagrams.",
                type(exec_res).__name__,
            )


# End of src/sourcelens/nodes/generate_diagrams.py
