    
**14. Configuration Loading Failure (`main.py`)**

This diagram details the error handling path within `main.py` if `config.py` fails to load or validate the configuration file.

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant System as Operating System / Shell

    User->>CLI: Executes `sourcelens --config non_existent.json ...`
    activate CLI

    CLI->>CLI: parse_arguments()
    Note over CLI: Args parsed successfully

    CLI->>Config: load_config("non_existent.json")
    activate Config
    alt Config File Not Found
        Config-->>CLI: raises FileNotFoundError
    else Invalid JSON or Schema Error
        Config-->>CLI: raises ConfigError(...)
    end
    deactivate Config

    Note over CLI: Catches FileNotFoundError or ConfigError
    CLI->>System: Logs critical error message
    CLI->>System: Prints error message to stderr

    CLI-->>User: Exits with non-zero status code (sys.exit(1))
    deactivate CLI