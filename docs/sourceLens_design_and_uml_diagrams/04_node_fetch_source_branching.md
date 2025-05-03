```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator
    participant Fetch as FetchCode Node
    participant GitHubUtil as GitHubCrawler (utils/github)
    participant LocalUtil as LocalCrawler (utils/local)
    participant ExternalGitHub as GitHub API / Git
    participant FS as FileSystem
    participant Shared as SharedState

    Flow->>Fetch: prep(shared)
    activate Fetch

    Fetch->>Fetch: _derive_project_name(shared)
    Note right of Fetch: Updates shared['project_name'] if needed

    alt Repository URL Provided (shared['repo_url'])
        Fetch->>GitHubUtil: crawl_github_repo(url, token, filters...)
        activate GitHubUtil

        %% Inner choice: API vs Git Clone
        alt Use API Preferred (and possible)
            GitHubUtil->>ExternalGitHub: API Requests (/contents, /blobs)
            activate ExternalGitHub
            ExternalGitHub-->>GitHubUtil: API Responses (file list, content)
            deactivate ExternalGitHub
        else Use Git Clone (SSH URL or API fallback) ## Changed opt to alt/else here
            GitHubUtil->>ExternalGitHub: git clone <url>
            activate ExternalGitHub
            ExternalGitHub-->>GitHubUtil: Cloned repo locally (temp dir)
            deactivate ExternalGitHub
            GitHubUtil->>FS: Read files from temp dir
            activate FS
            FS-->>GitHubUtil: File content
            deactivate FS
            Note right of GitHubUtil: Cleans up temp dir
        end ## End inner alt

        GitHubUtil-->>Fetch: files_dict
        deactivate GitHubUtil

    else Local Directory Provided (shared['local_dir'])
        Fetch->>LocalUtil: crawl_local_directory(dir, filters...)
        activate LocalUtil
        LocalUtil->>FS: os.walk(dir) / pathlib.read_text()
        activate FS
        FS-->>LocalUtil: File content
        deactivate FS
        LocalUtil-->>Fetch: files_dict
        deactivate LocalUtil
    end ## End outer alt

    Fetch->>Shared: Update shared['files'] = files_list
    Fetch-->>Flow: prep_result (boolean success)
    deactivate Fetch

    %% post step is simple update, not detailed here
    %% Flow->>Fetch: post(...)