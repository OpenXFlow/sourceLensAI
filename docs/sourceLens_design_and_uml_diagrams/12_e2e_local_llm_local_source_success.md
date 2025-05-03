This combines elements from several previous diagrams into one end-to-end flow for this scenario. Due to the length, some repetitive details within nodes (like the exact prep/exec/post calls for every node after the first example) are slightly condensed with notes to maintain readability.

Filename: 18_e2e_local_llm_local_source_success.md
Breakdown:
18: The next sequential number.
e2e: Indicates an "End-to-End" scenario, covering the full process.
local_llm: Specifies the key variation - using a local LLM.
local_source: Specifies the other key variation - using a local directory as input.
success: Denotes this represents the successful execution path.


```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant LocalCrawl as LocalCrawler (utils/local)
    participant Identify as IdentifyAbstractions Node
    participant Analyze as AnalyzeRelationships Node
    participant Order as OrderChapters Node
    participant Write as WriteChapters Node (Batch)
    participant Combine as CombineTutorial Node
    participant LlmApi as LlmApi (utils.llm_api.py)
    participant LlmCache as LlmCache (utils.llm_api.py)
    participant LocalImpl as LocalImpl (utils._local_llm_api.py)
    participant LocalLLM as Local LLM Server
    participant Validation as Validation (utils.validation)
    participant Helpers as Helpers (utils.helpers)
    participant FS as FileSystem
    participant Shared as SharedState (Conceptual)

    User->>CLI: Executes `sourcelens --dir /path/to/project`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Note over Config: Finds active local LLM & Python profile
    Config-->>CLI: Configuration data (local LLM details)
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state with local dir)
    activate Flow
    Note over Flow: Executes Nodes Sequentially

    %% --- FetchCode Node ---
    Flow->>Fetch: prep(shared)
    activate Fetch
    Fetch->>Fetch: _derive_project_name()
    Fetch->>LocalCrawl: crawl_local_directory("/path/to/project", filters...)
    activate LocalCrawl
    LocalCrawl->>FS: os.walk / read_text files
    activate FS
    FS-->>LocalCrawl: File content
    deactivate FS
    LocalCrawl-->>Fetch: files_dict
    deactivate LocalCrawl
    Fetch-->>Flow: prep_result (files found)
    deactivate Fetch

    Flow->>Fetch: post(shared, ...)
    activate Fetch
    Fetch->>Shared: Update shared['files']
    Fetch-->>Flow: done
    deactivate Fetch

    %% --- IdentifyAbstractions Node ---
    Flow->>Identify: prep(shared)
    activate Identify
    Identify->>Shared: Read shared['files'], config
    Identify->>Helpers: get_content_for_indices(...)
    Identify->>Identify: _format_prompt(...)
    Identify-->>Flow: prep_result (context)
    deactivate Identify

    Flow->>Identify: exec(prep_result)
    activate Identify
    Identify->>LlmApi: call_llm(prompt, local_llm_config, cache_config)
    activate LlmApi
    LlmApi->>LlmCache: get(prompt) ## Assume Cache Miss ##
    LlmCache-->>LlmApi: None
    LlmApi->>LocalImpl: call_local_openai_compatible(prompt, local_llm_config)
    activate LocalImpl
    LocalImpl->>LocalLLM: POST /v1/chat/completions Request
    activate LocalLLM
    LocalLLM-->>LocalImpl: Success Response (JSON)
    deactivate LocalLLM
    LocalImpl-->>LlmApi: llm_response_text
    deactivate LocalImpl
    LlmApi->>LlmCache: put(prompt, response) ## Update Cache ##
    LlmCache-->>LlmApi: done
    LlmApi-->>Identify: llm_response_text
    deactivate LlmApi
    Identify->>Validation: validate_yaml_list(response, schema)
    activate Validation
    Validation-->>Identify: Parsed Abstractions List
    deactivate Validation
    Identify->>Identify: _parse_and_validate_indices(...)
    Identify-->>Flow: exec_result (abstractions)
    deactivate Identify

    Flow->>Identify: post(shared, ...)
    activate Identify
    Identify->>Shared: Update shared['abstractions']
    Identify-->>Flow: done
    deactivate Identify

    %% --- AnalyzeRelationships Node ---
    Note over Flow, Analyze: Analyze Node: prep -> exec -> post
    Flow->>Analyze: ... prep ...
    Flow->>Analyze: ... exec (calls LlmApi -> LocalLLM, Validation) ...
    Flow->>Analyze: ... post (Updates shared['relationships']) ...

    %% --- OrderChapters Node ---
    Note over Flow, Order: OrderChapters Node: prep -> exec -> post
    Flow->>Order: ... prep ...
    Flow->>Order: ... exec (calls LlmApi -> LocalLLM, Validation) ...
    Flow->>Order: ... post (Updates shared['chapter_order']) ...

    %% --- WriteChapters Node (Batch) ---
    Flow->>Write: prep(shared)
    activate Write
    Note over Write: Yields items for each chapter
    loop For Each Chapter
        Write->>Helpers: get_content_for_indices(...)
    end
    Write-->>Flow: Iterable of chapter items
    deactivate Write

    Note over Flow, Write: PocketFlow calls Write.exec() in loop
    loop For Each Chapter Item
        Flow->>Write: exec(item)
        activate Write
        Write->>Write: _format_prompt...()
        Write->>LlmApi: call_llm(prompt, ...) ## Calls Local LLM via ApiUtil ##
        LlmApi-->>Write: chapter_content (Markdown)
        Write-->>Flow: exec_result
        deactivate Write
    end

    Flow->>Write: post(shared, ...)
    activate Write
    Write->>Shared: Update shared['chapters']
    Write-->>Flow: done
    deactivate Write

    %% --- CombineTutorial Node ---
    Flow->>Combine: prep(shared)
    activate Combine
    Combine->>Shared: Read all generated data
    Combine->>Helpers: sanitize_filename(...)
    Combine->>Combine: Generate Mermaid, Index Content
    Combine->>FS: Create output dir
    activate FS
    FS-->>Combine: done
    deactivate FS
    Combine->>FS: Write index.md
    activate FS
    FS-->>Combine: done
    deactivate FS
    loop Write Chapter Files
        Combine->>FS: Write chapter_N.md
        activate FS
        FS-->>Combine: done
        deactivate FS
    end
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