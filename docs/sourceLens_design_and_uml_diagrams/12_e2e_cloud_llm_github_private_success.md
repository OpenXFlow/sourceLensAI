
**2. Scenario: Cloud LLM, Private GitHub Repo (Token Fetch), Success**

*   **Filename:** `20_e2e_cloud_llm_github_private_success.md`
*   **Description:** Shows the successful flow for a private GitHub repository, requiring a valid GitHub token for the API fetch, using a cloud LLM.


```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant GitHubCrawl as GitHubCrawler (utils/github)
    participant Identify as IdentifyAbstractions Node
    %% Other nodes omitted for brevity but follow Cloud LLM pattern
    participant Combine as CombineTutorial Node
    participant LlmApi as LlmApi (utils.llm_api.py)
    participant CloudImpl as CloudImpl (utils._cloud_llm_api.py)
    participant CloudLLM as Cloud LLM Service (e.g., Gemini API)
    participant GitHubAPI as GitHub API / Git
    participant FS as FileSystem
    participant Shared as SharedState (Conceptual)

    User->>CLI: Executes `sourcelens --repo https://github.com/private/...`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Note over Config: Finds active Cloud LLM & GitHub Token
    Config-->>CLI: Configuration data (Cloud LLM, GH Token)
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state with repo url & token)
    activate Flow

    %% --- FetchCode Node (GitHub API with Token) ---
    Flow->>Fetch: prep(shared)
    activate Fetch
    Fetch->>GitHubCrawl: crawl_github_repo(url, token=SHARED_TOKEN, filters...)
    activate GitHubCrawl
    Note over GitHubCrawl: Uses provided token for API calls
    GitHubCrawl->>GitHubAPI: API Requests (with Auth Header)
    activate GitHubAPI
    GitHubAPI-->>GitHubCrawl: API Responses (Private Repo Content)
    deactivate GitHubAPI
    GitHubCrawl-->>Fetch: files_dict
    deactivate GitHubCrawl
    Fetch-->>Flow: prep_result (files found)
    deactivate Fetch
    Flow->>Fetch: post(shared, ...) # Updates shared['files']
    activate Fetch
    Fetch-->>Flow: done
    deactivate Fetch

    %% --- Subsequent Nodes (Using Cloud LLM) ---
    Note over Flow, Identify: Identify Node calls Cloud LLM...
    Flow->>Identify: prep -> exec (calls LlmApi->CloudImpl->CloudLLM) -> post

    %% ... Analyze, Order, Write nodes follow ...

    Note over Flow, Combine: Combine Node writes output...
    Flow->>Combine: prep -> post (writes to FS)

    %% --- Finalization ---
    Flow-->>CLI: Flow finished successfully
    deactivate Flow
    CLI-->>User: Prints success message
    deactivate CLI