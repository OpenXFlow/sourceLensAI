
**15. Logging Setup Failure (`main.py`)**

This diagram shows the fallback mechanism if the logging setup fails (e.g., cannot create the log directory).

```mermaid
sequenceDiagram
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant Logging as logging module setup
    participant FS as FileSystem
    participant System as Operating System / Shell

    CLI->>Config: load_config()
    activate Config
    Config-->>CLI: config_data (successful)
    deactivate Config

    CLI->>Logging: setup_logging(config['logging'])
    activate Logging

    Logging->>FS: Attempt mkdir("logs/")
    activate FS
    alt Directory Creation Fails (e.g., permissions)
        FS-->>Logging: raises OSError
        %% deactivate FS ## REMOVED this line as it caused the error
        Note over Logging: Catches OSError
        Logging->>System: Prints error message to stderr
        Logging->>Logging: Configures basic logging to stdout only
        Note over Logging: File logging disabled
    else Directory Creation Succeeds
         FS-->>Logging: done
         %% FS Remains Active
         Logging->>FS: Attempt open("logs/sourcelens.log")
         %% Still interacting with FS implicitly or explicitly
         %% Assuming success for this path
         FS-->>Logging: done ## Reply from the open attempt
         Logging->>Logging: Configures file and stream handlers
         deactivate FS ## Deactivate FS *after* all interactions in this block (This one is needed)
    end

    Logging-->>CLI: done (setup complete, maybe only partially)
    deactivate Logging

    Note over CLI: Continues execution (with potentially limited logging)