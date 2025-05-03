```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Fetch as FetchCode Node
    participant Identify as IdentifyAbstractions Node
    participant Analyze as AnalyzeRelationships Node
    participant Order as OrderChapters Node
    participant Write as WriteChapters Node
    participant Combine as CombineTutorial Node
    participant FS as FileSystem

    User->>CLI: Executes `sourcelens --repo <url>`
    activate CLI

    CLI->>Config: load_config()
    activate Config
    Config-->>CLI: Configuration data
    deactivate Config

    CLI->>Flow: create_tutorial_flow(config)
    activate Flow
    Flow-->>CLI: Flow instance
    deactivate Flow

    CLI->>Flow: run(initial_shared_state)
    activate Flow
    Note over Flow: Executes Nodes Sequentially

    Flow->>Fetch: prep(shared)
    activate Fetch
    %% Implies Fetch calls utils.github/local -> External/FS
    Fetch-->>Flow: prep_result (files fetched)
    deactivate Fetch

    Flow->>Fetch: post(shared, prep_res, None)
    activate Fetch
    Note right of Fetch: Updates shared['files']
    Fetch-->>Flow: done ## Added ": done"
    deactivate Fetch

    Flow->>Identify: prep(shared)
    activate Identify
    %% Reads shared['files']
    Identify-->>Flow: prep_result (context)
    deactivate Identify

    Flow->>Identify: exec(prep_res)
    activate Identify
    %% Implies Identify calls utils.llm_api -> External LLM
    Identify-->>Flow: exec_result (abstractions)
    deactivate Identify

    Flow->>Identify: post(shared, prep_res, exec_res)
    activate Identify
    Note right of Identify: Updates shared['abstractions']
    Identify-->>Flow: done ## Added ": done"
    deactivate Identify

    %% ... Similar prep/exec/post sequence for Analyze, Order, Write ...
    Flow->>Analyze: prep/exec/post(...)
    activate Analyze
    Note right of Analyze: Updates shared['relationships']
    deactivate Analyze

    Flow->>Order: prep/exec/post(...)
    activate Order
    Note right of Order: Updates shared['chapter_order']
    deactivate Order

    Flow->>Write: prep/exec/post(...)
    activate Write
    Note right of Write: Updates shared['chapters']
    deactivate Write

    Flow->>Combine: prep(shared)
    activate Combine
    %% Generates index, uses utils.helpers, writes to FS
    Combine->>FS: Write index.md
    Combine->>FS: Write chapter_01.md
    Combine->>FS: Write chapter_02.md
    %% ... etc ...
    Combine-->>Flow: prep_result (success/failure)
    deactivate Combine

    Flow->>Combine: post(shared, prep_res, None)
    activate Combine
    Note right of Combine: Updates shared['final_output_dir']
    Combine-->>Flow: done ## Added ": done"
    deactivate Combine

    Flow-->>CLI: Flow finished (returns None or raises Exception)
    deactivate Flow

    CLI-->>User: Prints success message (with output path)
    deactivate CLI

