1. Scenario: Cloud LLM, Public GitHub Repo (API Fetch), Success
Description: Shows the successful flow when analyzing a public GitHub repository using the API fetch method (preferred) and a configured cloud LLM provider like Gemini.


```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant GitHubCrawl as GitHubCrawler (utils/github)
    participant Identify as IdentifyAbstractions Node
    participant Analyze as AnalyzeRelationships Node
    participant Order as OrderChapters Node
    participant Write as WriteChapters Node (Batch)
    participant Combine as CombineTutorial Node
    participant LlmApi as LlmApi (utils.llm_api.py)
    participant LlmCache as LlmCache (utils.llm_api.py)
    participant CloudImpl as CloudImpl (utils._cloud_llm_api.py)
    participant CloudLLM as Cloud LLM Service (e.g., Gemini API)
    participant GitHubAPI as GitHub API / Git
    participant Validation as Validation (utils.validation)
    participant Helpers as Helpers (utils.helpers)
    participant FS as FileSystem
    participant Shared as SharedState (Conceptual)

    User->>CLI: Executes `sourcelens --repo https://github.com/...`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Note over Config: Finds active Cloud LLM & relevant profile
    Config-->>CLI: Configuration data (Cloud LLM details)
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state with repo url)
    activate Flow
    Note over Flow: Executes Nodes Sequentially

    %% --- FetchCode Node (GitHub API Path) ---
    Flow->>Fetch: prep(shared)
    activate Fetch
    Fetch->>Fetch: _derive_project_name()
    Fetch->>GitHubCrawl: crawl_github_repo(url, token, filters...)
    activate GitHubCrawl
    Note over GitHubCrawl: Prefers API Fetch for HTTPS URL
    GitHubCrawl->>GitHubAPI: API Requests (/contents, /blobs)
    activate GitHubAPI
    GitHubAPI-->>GitHubCrawl: API Responses (file list, content)
    deactivate GitHubAPI
    GitHubCrawl-->>Fetch: files_dict
    deactivate GitHubCrawl
    Fetch-->>Flow: prep_result (files found)
    deactivate Fetch

    Flow->>Fetch: post(shared, ...)
    activate Fetch
    Fetch->>Shared: Update shared['files']
    Fetch-->>Flow: done
    deactivate Fetch

    %% --- IdentifyAbstractions Node (Cloud LLM) ---
    Flow->>Identify: prep(shared)
    activate Identify
    %% ... setup using Helpers ...
    Identify-->>Flow: prep_result (context)
    deactivate Identify

    Flow->>Identify: exec(prep_result)
    activate Identify
    Identify->>LlmApi: call_llm(prompt, cloud_llm_config, cache_config)
    activate LlmApi
    LlmApi->>LlmCache: get(prompt) ## Assume Cache Miss ##
    LlmCache-->>LlmApi: None
    LlmApi->>CloudImpl: call_cloud_provider(prompt, cloud_llm_config)
    activate CloudImpl
    CloudImpl->>CloudLLM: API Request (SDK/HTTP)
    activate CloudLLM
    CloudLLM-->>CloudImpl: Success Response
    deactivate CloudLLM
    CloudImpl-->>LlmApi: llm_response_text
    deactivate CloudImpl
    LlmApi->>LlmCache: put(prompt, response) ## Update Cache ##
    LlmCache-->>LlmApi: done
    LlmApi-->>Identify: llm_response_text
    deactivate LlmApi
    Identify->>Validation: validate_yaml_list(response, schema)
    activate Validation
    Validation-->>Identify: Parsed Abstractions List
    deactivate Validation
    Identify-->>Flow: exec_result (abstractions)
    deactivate Identify

    Flow->>Identify: post(shared, ...)
    activate Identify
    Identify->>Shared: Update shared['abstractions']
    Identify-->>Flow: done
    deactivate Identify

    %% --- Analyze, Order, Write Nodes (Using Cloud LLM) ---
    Note over Flow, Analyze: Analyze Node uses Cloud LLM...
    Flow->>Analyze: ... (prep -> exec -> post) ...
    Note over Flow, Order: OrderChapters Node uses Cloud LLM...
    Flow->>Order: ... (prep -> exec -> post) ...
    Note over Flow, Write: WriteChapters Node uses Cloud LLM...
    Flow->>Write: ... (prep -> exec loop -> post) ...

    %% --- CombineTutorial Node ---
    Note over Flow, Combine: Combine Node gathers data...
    Flow->>Combine: prep(shared)
    activate Combine
    %% ... generates content ...
    Combine->>FS: Writes output files...
    Combine-->>Flow: prep_result (success)
    deactivate Combine
    Flow->>Combine: post(shared, ...)
    activate Combine
    Combine->>Shared: Update shared['final_output_dir']
    Combine-->>Flow: done
    deactivate Combine

    %% --- Finalization ---
    Flow-->>CLI: Flow finished successfully
    deactivate Flow

    CLI-->>User: Prints success message with output path
    deactivate CLI