This diagram focuses on the higher-level dependencies between the main modules (main.py, config.py, flow.py) and the sub-packages (nodes, utils), as well as key dependencies within and between those sub-packages.

```mermaid
graph TD
    subgraph "sourcelens"
        %% Top Level Modules
        M["sourcelens.main"]
        C["sourcelens.config"]
        F["sourcelens.flow"]

        %% Nodes Sub-Package
        subgraph "nodes"
            N_PKG["(package)"]
            N_BASE["nodes.base_node"]
            N_FETCH["nodes.fetch"]
            N_ANALYZE["nodes.analyze"]
            N_STRUCTURE["nodes.structure"]
            N_WRITE["nodes.write"]
            N_COMBINE["nodes.combine"]
        end

        %% Utils Sub-Package
        subgraph "utils"
            U_PKG["(package)"]
            U_LLM["utils.llm_api"]
            U_CLOUD["utils._cloud_llm_api"]
            U_LOCAL_LLM["utils._local_llm_api"]
            U_EX["utils._exceptions"]
            U_GITHUB["utils.github"]
            U_LOCAL["utils.local"]
            U_HELP["utils.helpers"]
            U_VALID["utils.validation"]
        end
    end

    %% Top-Level Dependencies
    M --> C
    M --> F

    %% Flow Dependencies
    %% Flow orchestrates nodes
    F --> N_PKG

    %% Config Dependencies
    %% Config uses validation utils/schema
    C --> U_VALID
    %% Config uses ConfigError (likely defined or related in exceptions)
    C --> U_EX

    %% Nodes Package Dependencies (Internal & External)
    N_PKG --> N_BASE
    N_PKG --> N_FETCH
    N_PKG --> N_ANALYZE
    N_PKG --> N_STRUCTURE
    N_PKG --> N_WRITE
    N_PKG --> N_COMBINE

    N_FETCH --> N_BASE
    N_ANALYZE --> N_BASE
    N_STRUCTURE --> N_BASE
    N_WRITE --> N_BASE
    N_COMBINE --> N_BASE

    N_FETCH --> U_GITHUB
    N_FETCH --> U_LOCAL

    N_ANALYZE --> U_LLM
    N_ANALYZE --> U_VALID
    N_ANALYZE --> U_HELP

    N_STRUCTURE --> U_LLM
    N_STRUCTURE --> U_VALID

    N_WRITE --> U_LLM
    N_WRITE --> U_HELP

    N_COMBINE --> U_HELP

    %% Utils Package Dependencies (Internal)
    U_LLM --> U_CLOUD
    U_LLM --> U_LOCAL_LLM
    U_LLM --> U_EX

    U_GITHUB --> U_EX
    U_VALID --> U_EX
    U_CLOUD --> U_EX
    U_LOCAL_LLM --> U_EX

    %% Local uses Github for _should_include_file helper
    U_LOCAL --> U_GITHUB

    %% Style Packages
    style N_PKG fill:#ddeeff,stroke:#333
    style U_PKG fill:#ddffdd,stroke:#333