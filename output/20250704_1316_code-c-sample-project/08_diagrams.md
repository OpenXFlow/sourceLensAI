> Previously, we looked at [Traitement des Items (ItemProcessor)](07_traitement-des-items-itemprocessor.md).

# Architecture Diagrams
## Class Diagram
Key classes and their relationships in **20250704_1316_code-c-sample-project**.
```mermaid
classDiagram
    class Config {
        +load_config()
    }
    class DataHandler {
        +load_data()
        +save_data()
    }
    class Item {
        +id: int
        +name: string
    }
    class ItemProcessor {
        +process_item(item: Item)
    }
    DataHandler ..> Item : Manages
    ItemProcessor ..> Item : Uses
```
## Package Dependencies
High-level module and package structure of **20250704_1316_code-c-sample-project**.
```mermaid
graph TD
    M(main.c)
    DH(data_handler.h)
    DC(data_handler.c)
    C(config.h)
    CF(config.c)
    I(item.h)
    IT(item.c)
    IPH(item_processor.h)
    IPC(item_processor.c)
    M --> C
    M --> DH
    M --> I
    M --> IPH
    DC --> DH
    DC --> I
    CF --> C
    IT --> I
    IPC --> IPH
    IPC --> I
    IPC --> DH
```
## Sequence Diagrams
These diagrams illustrate various interaction scenarios, showcasing operations between components for specific use cases.
### The main function initiates project configuration, loads data, and starts item processing.
```mermaid
sequenceDiagram
    participant Main
    participant Config
    participant Data
    participant Processor
    Main->>Config: Initiate project configuration
    activate Main
    activate Config
    Config-->>Main: Configuration complete
    deactivate Config
    Main->>Data: Load data
    activate Data
    Data-->>Main: Data loaded
    deactivate Data
    Main->>Processor: Start item processing
    activate Processor
    Processor-->>Main: Processing complete
    deactivate Processor
    deactivate Main
```
### A new Item is created, validated by the DataHandler, and added to the processing queue.
```mermaid
sequenceDiagram
    participant User
    participant API
    participant DataHandler
    participant ProcessingQueue
    User->>API: Create new Item
    activate API
    API->>DataHandler: Validate Item
    activate DataHandler
    DataHandler-->>API: Validation Result
    deactivate DataHandler
    alt Validation Success
        API->>ProcessingQueue: Add Item to Queue
        activate ProcessingQueue
        ProcessingQueue-->>API: Item Queued
        deactivate ProcessingQueue
        API-->>User: Item Creation Success
    else Validation Failure
        API-->>User: Item Creation Failure
    end
    deactivate API
```
### The ItemProcessor retrieves an Item, processes it according to project configuration, and updates its state.
```mermaid
sequenceDiagram
    participant ItemProcessor
    participant ItemSource
    participant Configuration
    participant ItemState
    ItemProcessor->>ItemSource: Retrieve Item
    activate ItemSource
    ItemSource-->>ItemProcessor: Item
    deactivate ItemSource
    ItemProcessor->>Configuration: Get Processing Configuration
    activate Configuration
    Configuration-->>ItemProcessor: Configuration Data
    deactivate Configuration
    ItemProcessor->>ItemProcessor: Process Item
    activate ItemProcessor
    ItemProcessor->>ItemState: Update Item State
    activate ItemState
    ItemState-->>ItemProcessor: State Updated
    deactivate ItemState
    ItemProcessor-->>ItemProcessor: Item Processed
    deactivate ItemProcessor
```
### An error occurs during Item processing, triggering logging and potential error recovery by the Main function.
```mermaid
sequenceDiagram
    participant User
    participant Main
    participant ItemProcessor
    participant Logger
    User->>Main: Start Processing
    activate Main
    Main->>ItemProcessor: Process Item
    activate ItemProcessor
    alt Error Occurs
        ItemProcessor-->>Main: Error during processing
        deactivate ItemProcessor
        Main->>Logger: Log Error
        activate Logger
        Logger-->>Main: Logged
        deactivate Logger
        Main-->>User: Error Response
    else Item Processed Successfully
        ItemProcessor-->>Main: Item Processed
        deactivate ItemProcessor
        Main-->>User: Item Processed Successfully
    end
    deactivate Main
```
### The DataHandler persists processed Item data, ensuring data integrity and enabling future retrieval.
```mermaid
sequenceDiagram
    participant DataHandler
    participant Item
    participant Database
    participant Logger
    DataHandler->>Item: Receive processed Item data
    activate DataHandler
    DataHandler->>Database: Persist Item data
    activate Database
    alt Success
        Database-->>DataHandler: Persistence successful
        DataHandler-->>DataHandler: Update internal state (if needed)
    else Failure
        Database-->>DataHandler: Persistence failed
        DataHandler->>Logger: Log persistence error
        Logger-->>DataHandler: Logged
        DataHandler-->>DataHandler: Handle error/retry (if applicable)
    end
    deactivate Database
    deactivate DataHandler
```

> Next, we will examine [Code Inventory](09_code_inventory.md).


---

*Generated by [SourceLens AI](https://github.com/openXFlow/sourceLensAI) using LLM: `gemini` (cloud) - model: `gemini-2.0-flash` | Language Profile: `Python`*