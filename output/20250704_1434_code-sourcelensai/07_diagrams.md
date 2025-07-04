> Previously, we looked at [Markdown Output Generation](06_markdown-output-generation.md).

# Architecture Diagrams
## Class Diagram
Key classes and their relationships in **20250704_1434_code-sourcelensai**.
```mermaid
classDiagram
    class ConfigLoader {
        +load_config(path: str) dict
    }
    class Flow {
        +run()
    }
    class CLI {
        +main()
    }
    class _ASTPythonFormatter {
        +format_node() str
    }
    class _LLMDefaultFormatter {
        +format_node() str
    }
    CLI --|> Flow : Triggers
```
## Package Dependencies
High-level module and package structure of **20250704_1434_code-sourcelensai**.
```mermaid
graph TD
    A(".gitignore")
    B("config.json")
    C("config.example.json")
    D("README.md")
    E("requirements.txt")
    F("src/FL01_code_analysis/cli.py")
    G("src/FL01_code_analysis/config_loader.py")
    H("src/FL01_code_analysis/flow.py")
    I("src/FL01_code_analysis/nodes/n01_fetch_code.py")
    J("src/FL01_code_analysis/nodes/n02_identify_abstractions.py")
    K("src/FL01_code_analysis/nodes/n03_analyze_relationships.py")
    L("src/FL01_code_analysis/nodes/n04_order_chapters.py")
    M("src/FL01_code_analysis/nodes/n05_identify_scenarios.py")
    N("src/FL01_code_analysis/nodes/n06_generate_diagrams.py")
    O("src/FL01_code_analysis/nodes/n07_write_chapters.py")
    P("src/FL01_code_analysis/nodes/n08_generate_source_index.py")
    Q("src/FL01_code_analysis/nodes/n09_generate_project_review.py")
    R("src/FL01_code_analysis/nodes/n10_combine_tutorial.py")
    S("src/FL01_code_analysis/prompts/abstraction_prompts.py")
    T("src/FL01_code_analysis/prompts/chapter_prompts.py")
    U("src/FL01_code_analysis/prompts/project_review_prompts.py")
    V("src/FL01_code_analysis/prompts/scenario_prompts.py")
    W("src/FL01_code_analysis/prompts/source_index_prompts.py")
    X("src/FL01_code_analysis/prompts/_common.py")
    Y("src/FL02_web_crawling/cli.py")
    Z("src/FL02_web_crawling/flow.py")
    AA("src/FL02_web_crawling/nodes/n01b_segment_web_content.py")
    BB("src/FL02_web_crawling/nodes/n01c_youtube_content.py")
    CC("src/FL02_web_crawling/nodes/n01_fetch_web_page.py")
    DD("src/FL02_web_crawling/nodes/n02_identify_web_concepts.py")
    EE("src/FL02_web_crawling/nodes/n03_analyze_web_relationships.py")
    FF("src/FL02_web_crawling/nodes/n04_order_web_chapters.py")
    GG("src/FL02_web_crawling/nodes/n05_write_web_chapters.py")
    HH("src/FL02_web_crawling/nodes/n06_generate_web_inventory.py")
    F --> G
    H --> I
    H --> J
    H --> K
    H --> L
    H --> M
    H --> N
    H --> O
    H --> P
    H --> Q
    H --> R
    I --> S
    J --> S
    K --> X
    Q --> U
    P --> W
    Y --> Z
    Z --> AA
    Z --> BB
    Z --> CC
    Z --> DD
    Z --> EE
    Z --> FF
    Z --> GG
    Z --> HH
    G --> B
    F --> H
    Y --> Z
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios, showcasing operations between components for specific use cases.
### Fetching configuration settings at startup and applying them to the flow engine.
```mermaid
sequenceDiagram
    participant Application
    participant ConfigServer
    participant FlowEngine
    participant Logger
    Application->>ConfigServer: Request Configuration
    activate ConfigServer
    ConfigServer-->>Application: Configuration Data
    deactivate ConfigServer
    Application->>FlowEngine: Apply Configuration
    activate FlowEngine
    alt Configuration Successful
        FlowEngine-->>Application: Configuration Applied Successfully
    else Configuration Failed
        FlowEngine->>Logger: Log Configuration Error
        activate Logger
        Logger-->>FlowEngine: Logged
        deactivate Logger
        FlowEngine-->>Application: Configuration Failed
    end
    deactivate FlowEngine
```
### User initiates a process that involves fetching a markdown file, processing it using the LLM API, and generating output.
```mermaid
sequenceDiagram
    participant User
    participant App
    participant LLM_API
    User->>App: Request Markdown processing
    activate App
    App->>App: Fetch Markdown file
    App->>LLM_API: Send Markdown for processing
    activate LLM_API
    LLM_API-->>App: Processed output
    App-->>User: Display output
    deactivate LLM_API
    deactivate App
```
### The Flow Engine executes a task involving fetching a file and encountering a validation error, triggering error handling.
```mermaid
sequenceDiagram
    participant User
    participant FlowEngine
    participant FileSystem
    participant Validator
    participant ErrorHandler
    User->>FlowEngine: Start Task
    activate FlowEngine
    FlowEngine->>FileSystem: Fetch File
    activate FileSystem
    FileSystem-->>FlowEngine: File Content or Error
    deactivate FileSystem
    alt File Fetch Success
        FlowEngine->>Validator: Validate File Content
        activate Validator
        Validator-->>FlowEngine: Validation Result (Success/Error)
        deactivate Validator
        alt Validation Success
            FlowEngine-->>User: Task Complete (Success)
        else Validation Error
            FlowEngine->>ErrorHandler: Handle Validation Error
            activate ErrorHandler
            ErrorHandler-->>FlowEngine: Error Handling Complete
            deactivate ErrorHandler
            FlowEngine-->>User: Task Complete (Error)
        end
    else File Fetch Error
        FlowEngine->>ErrorHandler: Handle File Fetch Error
        activate ErrorHandler
        ErrorHandler-->>FlowEngine: Error Handling Complete
        deactivate ErrorHandler
        FlowEngine-->>User: Task Complete (Error)
    end
    deactivate FlowEngine
```
### User updates a configuration setting that triggers a re-initialization of the Flow Engine.
```mermaid
sequenceDiagram
    participant User
    participant ConfigurationManager
    participant FlowEngine
    participant MessageBus
    User->>ConfigurationManager: Update configuration setting
    activate ConfigurationManager
    ConfigurationManager->>ConfigurationManager: Validate setting
    alt Setting is valid
        ConfigurationManager->>MessageBus: Publish config change event
        MessageBus->>FlowEngine: Config change event
        activate FlowEngine
        FlowEngine->>FlowEngine: Stop existing flows
        FlowEngine->>FlowEngine: Re-initialize Flow Engine
        FlowEngine->>FlowEngine: Load new configuration
        FlowEngine->>FlowEngine: Start new flows
        FlowEngine-->>ConfigurationManager: Re-initialization complete
        deactivate FlowEngine
        ConfigurationManager-->>User: Configuration updated successfully
    else Setting is invalid
        ConfigurationManager-->>User: Error message
    end
    deactivate ConfigurationManager
```
### The LLM API returns an unexpected error during markdown processing, requiring error handling and reporting.
```mermaid
sequenceDiagram
    participant User
    participant ClientApp
    participant LLM_API
    participant ErrorLogger
    User->>ClientApp: Request Markdown Processing
    activate ClientApp
    ClientApp->>LLM_API: Send Markdown for Processing
    activate LLM_API
    alt Error occurred during processing
        LLM_API-->>ClientApp: Error Response
        ClientApp->>ErrorLogger: Log Error Details
        activate ErrorLogger
        ErrorLogger-->>ClientApp: Logged
        deactivate ErrorLogger
        ClientApp-->>User: Error Message
    else Successful processing
        LLM_API-->>ClientApp: Processed Markdown
        ClientApp-->>User: Display Processed Markdown
    end
    deactivate LLM_API
    deactivate ClientApp
```

> Next, we will examine [Code Inventory](08_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*