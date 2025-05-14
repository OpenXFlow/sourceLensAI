# Copyright (C) 2025 Jozef Darida (Find me on LinkedIn/Xing)
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


"""Defines the main processing pipeline (Flow) for SourceLens.

Instantiates and connects the various processing nodes using the internal
SourceLens flow engine to generate tutorials from source code. Includes
dynamic scenario identification for sequence diagrams and optional source
code index generation.
"""

import logging
from typing import TYPE_CHECKING, Any

from typing_extensions import TypeAlias

# Import Flow class from the integrated flow engine
if TYPE_CHECKING:
    from sourcelens.core.flow_engine_sync import Flow as SourceLensFlow
else:
    SourceLensFlow: Any = None


# Use absolute imports for nodes within the sourcelens package
from sourcelens.nodes.analyze import AnalyzeRelationships, IdentifyAbstractions
from sourcelens.nodes.combine import CombineTutorial
from sourcelens.nodes.fetch import FetchCode
from sourcelens.nodes.generate_diagrams import GenerateDiagramsNode
from sourcelens.nodes.generate_source_index import GenerateSourceIndexNode
from sourcelens.nodes.identify_scenarios import IdentifyScenariosNode
from sourcelens.nodes.structure import OrderChapters
from sourcelens.nodes.write import WriteChapters

# Type alias for Configuration Dictionary
ConfigDict: TypeAlias = dict[str, Any]  # Generic config dict
LlmConfigDict: TypeAlias = dict[str, Any]
CacheConfigDict: TypeAlias = dict[str, Any]

logger: logging.Logger = logging.getLogger(__name__)


def create_tutorial_flow(llm_config: LlmConfigDict, cache_config: CacheConfigDict) -> "SourceLensFlow":
    """Create and configure the SourceLens tutorial generation flow.

    Instantiates all processing nodes (fetching, analyzing, ordering, scenario
    identification, diagram generation, writing chapters, source index generation,
    combining output), passing necessary configurations. Defines the execution
    sequence of these nodes using the internal SourceLens flow engine.

    Args:
        llm_config: Processed configuration dictionary for the active LLM provider.
        cache_config: Configuration dictionary related to LLM response caching.

    Returns:
        An instance of the configured `SourceLensFlow` ready for execution.

    Raises:
        ImportError: If a required node cannot be imported.

    """
    logger.info("Creating tutorial generation flow...")

    # --- Node Instantiation ---
    max_retries_llm_any: Any = llm_config.get("max_retries", 3)
    retry_wait_llm_any: Any = llm_config.get("retry_wait_seconds", 10)

    max_retries_llm: int = max_retries_llm_any if isinstance(max_retries_llm_any, int) else 3
    retry_wait_llm: int = retry_wait_llm_any if isinstance(retry_wait_llm_any, int) else 10

    logger.info("Initializing LLM-based nodes with max_retries=%d, retry_wait=%d", max_retries_llm, retry_wait_llm)

    fetch_code = FetchCode()
    identify_abstractions = IdentifyAbstractions(max_retries=max_retries_llm, wait=retry_wait_llm)
    analyze_relationships = AnalyzeRelationships(max_retries=max_retries_llm, wait=retry_wait_llm)
    order_chapters = OrderChapters(max_retries=max_retries_llm, wait=retry_wait_llm)
    identify_scenarios = IdentifyScenariosNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    generate_diagrams = GenerateDiagramsNode(max_retries=max_retries_llm, wait=retry_wait_llm)
    write_chapters = WriteChapters(max_retries=max_retries_llm, wait=retry_wait_llm)
    generate_source_index = GenerateSourceIndexNode(max_retries=1, wait=0)
    logger.info("Initialized GenerateSourceIndexNode with max_retries=1, wait=0.")
    combine_tutorial = CombineTutorial()

    # --- Flow Definition ---
    (
        fetch_code
        >> identify_abstractions
        >> analyze_relationships
        >> order_chapters
        >> identify_scenarios
        >> generate_diagrams
        >> write_chapters
        >> generate_source_index
        >> combine_tutorial
    )
    logger.info(
        "Flow sequence defined: Fetch -> IdentifyAbs -> AnalyzeRel -> OrderChap -> "
        "IdentifyScen -> GenDiag -> WriteChap -> GenSourceIndex -> Combine"
    )

    # --- Flow Creation ---
    if TYPE_CHECKING:
        # This path is for MyPy and other type checkers
        from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow
    else:
        # This path is for runtime
        from sourcelens.core.flow_engine_sync import Flow as ActualSourceLensFlow

    flow_instance: SourceLensFlow = ActualSourceLensFlow(start=fetch_code)  # type: ignore[assignment, misc]
    # Ignorujeme `assignment` pre prípad, že `ActualSourceLensFlow` by bolo `Any` kvôli problémom s `py.typed`.
    # Ignorujeme `misc` pre prípad, že by `start` argument nebol presne `BaseNode`, ale kompatibilný podtyp.

    logger.info("Flow instance created successfully using SourceLensFlow.")

    return flow_instance


# End of src/sourcelens/flow.py
