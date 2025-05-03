
**4. Scenario: Cloud LLM, GitHub Repo (API), Fetch Failure**

*   **Description:** Shows the flow failing during the `FetchCode` stage when using the GitHub API, perhaps due to an invalid repository URL, lack of permissions (missing token for private repo), or hitting rate limits without a token.

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant GitHubCrawl as GitHubCrawler (utils/github)
    participant GitHubAPI as GitHub API
    participant Shared as SharedState (Conceptual)
    participant System as OS/Shell

    User->>CLI: Executes `sourcelens --repo https://github.com/invalid/repo`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Config-->>CLI: Configuration data
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state with invalid repo url)
    activate Flow

    %% --- FetchCode Node (GitHub API Fails) ---
    Flow->>Fetch: prep(shared)
    activate Fetch
    Fetch->>GitHubCrawl: crawl_github_repo(url="invalid...", ...)
    activate GitHubCrawl
    GitHubCrawl->>GitHubAPI: API Request (e.g., /contents/invalid/repo)
    activate GitHubAPI
    alt Repo Not Found or Access Denied
        GitHubAPI-->>GitHubCrawl: HTTP 404 Not Found / 401 Unauthorized / 403 Forbidden
    else Rate Limit Exceeded (No Token)
        GitHubAPI-->>GitHubCrawl: HTTP 403/429 Rate Limit (with X-RateLimit-Reset)
        Note over GitHubCrawl: Calls _handle_rate_limit, waits...
        %% If retries also fail or wait is too long, may still raise error
    end
    deactivate GitHubAPI

    GitHubCrawl-->>Fetch: raises GithubApiError("Failed fetching path 'invalid/repo' (Status: 404)")
    deactivate GitHubCrawl
    Fetch-->>Flow: raises GithubApiError(...)
    deactivate Fetch

    %% --- Error Handling ---
    Note over Flow: Exception propagates up
    Flow-->>CLI: raises GithubApiError(...)
    deactivate Flow

    Note over CLI: Catches generic Exception
    CLI->>System: Logs exception
    CLI->>System: Prints error message to stderr ("ERROR: Tutorial generation failed: ...")
    CLI-->>User: Exits with non-zero status code
    deactivate CLI