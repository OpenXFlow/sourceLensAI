
**10. Configuration Profile Selection (`config.py`)**

This diagram shows the internal logic within `config.py` responsible for finding the single active LLM provider and source language profile from the lists provided in `config.json`.


```mermaid
sequenceDiagram
    participant ConfigLoader as config.py Function (e.g., _process_llm_config)
    participant RawConfig as Raw Config Dict (from JSON)
    participant ProcessedConfig as Output Config Dict

    ConfigLoader->>RawConfig: Get "llm.providers" list
    activate ConfigLoader

    loop For Each provider_config in providers list
        alt provider_config["is_active"] is true
            Note over ConfigLoader: Found an active provider
            ConfigLoader->>ConfigLoader: Increment active_count
            opt active_count > 1
                 ConfigLoader-->>x ConfigLoader: raises ConfigError("Multiple active providers")
            end
            Note over ConfigLoader: Store this config as active_provider_config
        end
    end

    opt active_count == 0
        ConfigLoader-->>x ConfigLoader: raises ConfigError("No active provider found")
    end
    opt active_count == 1
        ConfigLoader->>RawConfig: Get common LLM settings (retries, wait, use_cache)
        ConfigLoader->>ProcessedConfig: Merge common settings + active_provider_config
        Note over ConfigLoader: Continues with validation...
    end
    deactivate ConfigLoader

    %% Similar loop logic applies for finding active source.language_profiles