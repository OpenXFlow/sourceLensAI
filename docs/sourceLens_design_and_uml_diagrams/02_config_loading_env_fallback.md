```mermaid
sequenceDiagram
    participant CLI as CLI (main.py)
    participant Config as ConfigLoader (config.py)
    participant FS as FileSystem
    participant Env as OS Environment

    CLI->>Config: load_config("config.json")
    activate Config

    Config->>FS: readFile("config.json")
    activate FS
    FS-->>Config: Raw JSON content
    deactivate FS

    Config->>Config: validateSchema(json_content)
    Note over Config: Uses jsonschema

    Config->>Config: _process_llm_config(llm_section)
    activate Config # self-call processing

    Config->>Config: _validate_active_llm_config(active_llm_cfg)
    activate Config # self-call validation

    alt API Key missing in active_llm_cfg
        Config->>Config: _resolve_api_key(provider, null)
        activate Config # self-call resolve
        Config->>Env: getenv("PROVIDER_API_KEY")
        activate Env
        Env-->>Config: API Key value (or None)
        deactivate Env
        Config-->>Config: Resolved API Key
        deactivate Config # end resolve
    end
    %% Similar validation for other keys/settings...

    Config-->>Config: Processed LLM Config ## Changed comment to explicit text
    deactivate Config # end validation
    deactivate Config # end processing


    %% Similar processing for source config, github token validation etc.
    Config->>Config: _process_source_config(...)
    Config->>Config: _validate_github_token(...)
    Note right of Config: Checks GITHUB_TOKEN env var if needed

    Config-->>CLI: Fully validated config dictionary
    deactivate Config