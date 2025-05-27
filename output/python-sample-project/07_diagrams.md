Previously, we looked at [Main Application Pipeline](06_main-application-pipeline.md).

# Architecture Diagrams
## Class Diagram
Key classes and their relationships in **python_sample_project**.
```mermaid
classDiagram
    class Config {
        +data_path: str
        +log_level: str
    }
    class DataHandler {
        -config: Config
        +load_data() : list
    }
    class ItemProcessor {
        +process_item(item: object) : object
    }
    class Model {
    }
    class Main {
        -config: Config
        -data_handler: DataHandler
        -item_processor: ItemProcessor
        +run() : void
    }
    DataHandler *-- Config : Uses
    Main *-- Config : Uses
    Main *-- DataHandler : Uses
    Main *-- ItemProcessor : Uses
```
## Package Dependencies
High-level module and package structure of **python_sample_project**.
```mermaid
graph TD
    M(main.py)
    C["config.py"]
    D(data_handler.py)
    I(item_processor.py)
    MO(models.py)
    I_init(__init__.py)
    M -->|"imports"| C
    M -->|"imports"| D
    M -->|"imports"| I
    M -->|"imports"| MO
    D -->|"imports"| MO
    I -->|"imports"| MO
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios within the application, showcasing the sequence of operations between different components for specific use cases.
### Loading data items from a file based on a configuration specified in a configuration file.
```mermaid
sequenceDiagram
    participant MainApp as "Main Application"
    participant ConfigManager as "Configuration Manager"
    participant DataFile as "Data File"
    participant DataLoader as "Data Loader"
    participant DataItem as "Data Item"
    MainApp->>ConfigManager: Load configuration file
    activate ConfigManager
    ConfigManager-->>MainApp: File path, delimiter, ...
    deactivate ConfigManager
    MainApp->>DataLoader: Load data using configuration
    activate DataLoader
    DataLoader->>DataFile: Open file
    activate DataFile
    DataFile-->>DataLoader: File stream
    deactivate DataFile
    loop Read each line in file
        DataLoader->>DataFile: Read line
        activate DataFile
        DataFile-->>DataLoader: Data line
        deactivate DataFile
        alt Data line is valid
            DataLoader->>DataItem: Create DataItem from line
            activate DataItem
            DataItem-->>DataLoader: DataItem object
            deactivate DataItem
            DataLoader-->>MainApp: DataItem object
        else Data line is invalid
            DataLoader->>MainApp: Log error
        end
    end
    DataLoader->>DataFile: Close file
    activate DataFile
    DataFile-->>DataLoader: Confirmation
    deactivate DataFile
    deactivate DataLoader
```
### Processing a single data item through the entire pipeline, including transformation and logging.
```mermaid
sequenceDiagram
    participant MainApp as "Main Application"
    participant DataProcessor as "Data Processor"
    participant Transformer as "Data Transformer"
    participant Logger as "Logger"
    MainApp->>DataProcessor: Receive data item
    activate DataProcessor
    DataProcessor->>Transformer: Transform data item
    activate Transformer
    Transformer-->>DataProcessor: Transformed data
    deactivate Transformer
    DataProcessor->>Logger: Log data processing
    activate Logger
    Logger-->>DataProcessor: Log entry created
    deactivate Logger
    DataProcessor-->>MainApp: Processed data
    deactivate DataProcessor
```
### Saving processed data items to a database using Data Handling.
```mermaid
sequenceDiagram
    participant MainApp as "Main Application"
    participant DataHandler
    participant Database
    MainApp->>DataHandler: Process data items
    activate DataHandler
    DataHandler->>DataHandler: Validate data
    alt Data valid
        DataHandler->>Database: Save data items
        activate Database
        Database-->>DataHandler: Confirmation
        deactivate Database
        DataHandler-->>MainApp: Data saved successfully
    else Data invalid
        DataHandler-->>MainApp: Error: Invalid data
    end
    deactivate DataHandler
```
### Handling a data validation error during Item Processing and logging the error.
```mermaid
sequenceDiagram
    participant MainApp as "Main Application"
    participant ItemProc as "Item Processor"
    participant Validator as "Data Validator"
    participant Logger
    MainApp->>ItemProc: Process item data
    activate ItemProc
    ItemProc->>Validator: Validate item data
    activate Validator
    alt Data is invalid
        Validator-->>ItemProc: Validation error
        deactivate Validator
        ItemProc->>Logger: Log validation error
        activate Logger
        Logger-->>ItemProc: Error logged
        deactivate Logger
        ItemProc-->>MainApp: Error: Data validation failed
        deactivate ItemProc
    else Data is valid
        Validator-->>ItemProc: Validated data
        deactivate Validator
        ItemProc-->>MainApp: Item processed successfully
        deactivate ItemProc
    end
```
### Restarting the Main Application Pipeline after a recoverable error, triggered by Configuration Management.
```mermaid
sequenceDiagram
    participant ConfigMgr as "Configuration Manager"
    participant MainApp as "Main Application"
    participant ErrorHandler as "Error Handler"
    participant TaskScheduler as "Task Scheduler"
    participant Pipeline as "Main Pipeline"
    participant Logger as "Logger"
    ConfigMgr->>MainApp: Detects configuration change (e.g., restart flag)
    activate MainApp
    MainApp->>ErrorHandler: Check for recoverable error
    activate ErrorHandler
    ErrorHandler-->>MainApp: Error Status (Recoverable)
    deactivate ErrorHandler
    MainApp->>Logger: Log: "Recoverable error detected, initiating pipeline restart."
    activate Logger
    Logger-->>MainApp: Log confirmation
    deactivate Logger
    MainApp->>TaskScheduler: Stop Main Pipeline
    activate TaskScheduler
    TaskScheduler-->>MainApp: Pipeline stopped
    deactivate TaskScheduler
    MainApp->>Pipeline: Shutdown Processes
    activate Pipeline
    Pipeline-->>MainApp: Processes Shutdown
    deactivate Pipeline
    MainApp->>Pipeline: Initialize new Pipeline instance
    activate Pipeline
    Pipeline-->>MainApp: Pipeline initialized
    deactivate Pipeline
    MainApp->>TaskScheduler: Schedule Main Pipeline
    activate TaskScheduler
    TaskScheduler-->>MainApp: Pipeline scheduled
    deactivate TaskScheduler
    MainApp->>Logger: Log: "Pipeline restart complete."
    activate Logger
    Logger-->>MainApp: Log confirmation
    deactivate Logger
    deactivate MainApp
```

Next, we will examine [Code Inventory](08_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/darijo2yahoocom/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `python`*