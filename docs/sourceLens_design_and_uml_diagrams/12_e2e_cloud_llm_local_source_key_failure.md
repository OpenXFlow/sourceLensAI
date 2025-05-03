
**3. Scenario: Cloud LLM, Local Source, API Key Failure**

*   **Description:** Shows the flow failing when using a local directory as input and a cloud LLM, but the API key configuration is missing or invalid.


```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant LocalCrawl as LocalCrawler (utils/local)
    participant Identify as IdentifyAbstractions Node
    participant LlmApi as LlmApi (utils.llm_api.py)
    participant CloudImpl as CloudImpl (utils._cloud_llm_api.py)
    participant FS as FileSystem
    participant Shared as SharedState (Conceptual)
    participant System as OS/Shell

    User->>CLI: Executes `sourcelens --dir /path/to/project`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Note over Config: Finds active Cloud LLM, but API key is missing/null in config/env
    Config-->>CLI: Configuration data (Cloud LLM, key=None)
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state with local dir)
    activate Flow

    %% --- FetchCode Node (Local Path) ---
    Flow->>Fetch: prep(shared)
    activate Fetch
    Fetch->>LocalCrawl: crawl_local_directory(...)
    activate LocalCrawl
    LocalCrawl->>FS: Read files...
    FS-->>LocalCrawl: Content
    LocalCrawl-->>Fetch: files_dict
    deactivate LocalCrawl
    Fetch-->>Flow: prep_result (success)
    deactivate Fetch
    Flow->>Fetch: post(...) # Updates shared['files']
    activate Fetch
    Fetch-->>Flow: done
    deactivate Fetch

    %% --- IdentifyAbstractions Node (API Key Fails) ---
    Flow->>Identify: prep(shared)
    activate Identify
    %% ... setup ...
    Identify-->>Flow: prep_result (context)
    deactivate Identify

    Flow->>Identify: exec(prep_result)
    activate Identify
    Identify->>LlmApi: call_llm(prompt, cloud_llm_config_with_no_key, ...)
    activate LlmApi
    %% Cache Miss assumed
    LlmApi->>CloudImpl: call_cloud_provider(prompt, config_with_no_key)
    activate CloudImpl
    Note over CloudImpl: Checks config, finds api_key is None
    CloudImpl-->>LlmApi: raises ValueError("Missing 'api_key' for CloudProvider")
    %% Alternatively, SDK/HTTP call might fail with 401/403, raising LlmApiError
    deactivate CloudImpl
    LlmApi-->>Identify: raises LlmApiError / ValueError
    deactivate LlmApi
    Identify-->>Flow: raises LlmApiError / ValueError
    deactivate Identify

    %% --- Error Handling ---
    Note over Flow: Exception propagates up
    Flow-->>CLI: raises LlmApiError / ValueError
    deactivate Flow

    Note over CLI: Catches generic Exception
    CLI->>System: Logs exception
    CLI->>System: Prints error message to stderr
    CLI-->>User: Exits with non-zero status code
    deactivate CLI