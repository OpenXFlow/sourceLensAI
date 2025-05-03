```mermaid
sequenceDiagram
    participant Node as Calling Node (e.g., Identify)
    participant ApiUtil as LlmApi (utils/llm_api.py)
    participant Cache as LlmCache (utils/llm_api.py)
    participant ProviderImpl as Provider Impl (_cloud/_local)
    participant LLMService as External LLM Service / Local Server

    Node->>ApiUtil: call_llm(prompt, llm_config, cache_config)
    activate ApiUtil

    ApiUtil->>Cache: get(prompt)
    %% Removed activate Cache

    alt Cache Hit
        Cache-->>ApiUtil: cached_response
        %% Removed deactivate Cache
        ApiUtil-->>Node: cached_response
        deactivate ApiUtil
    else Cache Miss
        Cache-->>ApiUtil: None
        %% Removed deactivate Cache

        ApiUtil->>ProviderImpl: call_provider_specific(prompt, llm_config)
        activate ProviderImpl
        ProviderImpl->>LLMService: API Request (HTTP/SDK call)
        activate LLMService
        LLMService-->>ProviderImpl: API Response
        deactivate LLMService
        ProviderImpl-->>ApiUtil: llm_response_text
        deactivate ProviderImpl

        ApiUtil->>Cache: put(prompt, llm_response_text)
        %% Removed activate Cache
        %% Cache saves to file implicitly
        Cache-->>ApiUtil: done
        %% Removed deactivate Cache

        ApiUtil-->>Node: llm_response_text
    end