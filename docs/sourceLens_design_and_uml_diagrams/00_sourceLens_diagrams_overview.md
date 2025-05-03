# sourcelens UML Diagram Summary

This document summarizes the generated UML diagrams (Sequence, Class, Package) for the `sourceLens` project, explaining the focus and coverage of each diagram group based on the final filenames.

## Sequence Diagrams

These diagrams illustrate the dynamic behavior and interaction sequences between different components of the application under various scenarios.

| Group Prefix        | Primary File(s)/Focus           | Diagram Role/Focus                                      | Key Interactions Shown                                                                                                                                                           |
| :------------------ | :------------------------------ | :------------------------------------------------------ | :------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `01_main_...`       | `main.py`                       | App Lifecycle & Top-Level Orchestration                 | User command execution, core success flow, CLI argument parsing (failure), config loading (failure), logging setup (failure/fallback), initial state creation (overrides), flow errors. |
| `02_config_...`     | `config.py`                     | Configuration Loading & Processing                      | Reading `config.json`, schema validation, resolving secrets (env var fallback), selecting active LLM/source profiles.                                                              |
| `03_flow_...`       | `flow.py`, `PocketFlow` library | Flow Orchestration Error Handling                       | How PocketFlow handles node-level retries upon encountering specific errors (e.g., `LlmApiError`).                                                                               |
| `04_node_...`       | `nodes/fetch.py`                | Code Fetching Logic                                     | Branching based on source type (GitHub/local), choice between GitHub API vs. Git clone, interaction with crawler utilities.                                                        |
| `05_node_...`       | `nodes/base_node.py` (Concept)  | Generic Node Execution Pattern                          | Standard `prep` -> `exec` -> `post` lifecycle, shared state usage, calling common utilities (helpers, llm_api, validation). Uses `IdentifyAbstractions` as example.                |
| `06_node_...`       | `nodes/write.py`                | Batch Node Execution Pattern                            | `prep` yielding multiple items, `exec` processing each item individually (calling LLM API), `post` collecting results.                                                          |
| `07_node_...`       | `nodes/combine.py`              | Final Output Generation                                 | Gathering processed data, generating index/Mermaid content, writing output files to the filesystem.                                                                                |
| `08_util_...`       | `utils/llm_api.py`              | Central LLM API Interaction                             | Cache checking (`LlmCache`), dispatching to provider implementations (`_cloud`/`_local`), cache updates.                                                                           |
| `09_util_...`       | `utils/validation.py`           | LLM Output Validation Failure                           | Scenario where LLM response fails validation (type/schema check) using `utils.validation`, raising `ValidationFailure`.                                                            |
| `10_util_...`      | `utils/helpers.py`              | Helper Function Usage                                   | Example of a node using a utility function from `utils.helpers` (e.g., `get_content_for_indices`).                                                                              |
| `11_util_...`      | `utils/github.py`               | Specific Utility Error Handling                         | GitHub API rate limit response handling (waiting logic) within `utils.github.py`.                                                                                                  |
| `12_e2e_...`        | End-to-End Scenarios            | Complete Use Case Flows                                 | Illustrates full application runs for specific configurations: Local LLM/Local Source (Success), Cloud LLM/GitHub API (Success), Cloud LLM/Private GitHub (Success), Key Failure, Fetch Failure. |

## Class Diagram

*   **Filename:** `14_class_diagram_hierarchy.md`
*   **Role/Focus:** Shows the static structure, focusing on the inheritance hierarchy of Node classes (`BaseNode`, `BaseBatchNode`, specific nodes) and key utility/exception classes (`CacheProtocol`, `LlmCache`, `LlmApiError`, etc.).
*   **Key Interactions Shown:** Inheritance (`<|--`), Interface Implementation (`<|..`).

## Package Diagrams

*   **Filename:** `13_package_diagram_module_dependencies.md`
    *   **Role/Focus:** Detailed view of dependencies between individual `.py` modules and sub-packages (`nodes`, `utils`) within `sourcelens`.
    *   **Key Interactions Shown:** Import dependencies (`-->`) between modules/packages.
*   **Filename:** `15_package_diagram_high_level.md` (Optional, generated previously if needed)
    *   **Role/Focus:** Simplified overview of dependencies between major architectural layers (`main`, `config`, `flow`, `nodes` package, `utils` package).
    *   **Key Interactions Shown:** High-level import dependencies (`-->`) between packages/top-level modules.

## Reasoning for Files Without Dedicated Sequence Diagrams

Dedicated sequence diagrams were *not* generated for the following files as their roles and interactions are effectively represented within the diagrams above, avoiding redundancy:

*   **`nodes/analyze.py` & `nodes/structure.py`:** These follow the generic node pattern (`05_node_...`), LLM call pattern (`08_util_...`), and validation pattern (`09_util_...`).
*   **`utils/_exceptions.py`:** Only defines exception types; raising/handling shown elsewhere.
*   **`utils/_cloud_llm_api.py` & `utils/_local_llm_api.py`:** Contain implementation details called by `llm_api.py`; the core interaction pattern is shown in `08_util_...`.
*   **`utils/local.py`:** Its interaction (`Fetch` -> `LocalUtil` -> `FS`) is shown within `04_node_...`.

This summary provides a reference point for understanding the scope and purpose of each generated UML diagram based on the final naming convention.