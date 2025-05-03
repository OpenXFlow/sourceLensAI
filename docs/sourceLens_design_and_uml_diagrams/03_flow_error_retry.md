8. LLM API Error Handling and Retry (PocketFlow)
This diagram shows how PocketFlow (as the orchestrator) handles a transient error from the LLM API during a node's execution phase and retries the node.

```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator (PocketFlow)
    participant Node as Any Node using LLM (e.g., Analyze)
    participant ApiUtil as LlmApi (utils.llm_api.py)
    participant ProviderImpl as Provider Impl (_cloud/_local)
    participant LLMService as External LLM Service

    Note over Flow: Executes Node (Attempt 1)
    Flow->>Node: exec(prep_result)
    activate Node

    Node->>ApiUtil: call_llm(prompt, ...)
    activate ApiUtil
    %% Assuming Cache Miss
    ApiUtil->>ProviderImpl: call_provider_specific(...)
    activate ProviderImpl
    ProviderImpl->>LLMService: API Request
    activate LLMService
    LLMService-->>ProviderImpl: Error Response (e.g., 503 Service Unavailable)
    deactivate LLMService
    ProviderImpl-->>ApiUtil: raises LlmApiError("Service Unavailable")
    deactivate ProviderImpl
    ApiUtil-->>Node: raises LlmApiError("Service Unavailable")
    deactivate ApiUtil
    Node-->>Flow: raises LlmApiError("Service Unavailable")
    deactivate Node

    Note over Flow: Catches LlmApiError, Checks Retry Policy
    Note over Flow: Waits (retry_wait_seconds)

    Note over Flow: Executes Node (Attempt 2 - Retry)
    Flow->>Node: exec(prep_result) ## Retry Call
    activate Node

    Node->>ApiUtil: call_llm(prompt, ...)
    activate ApiUtil
    %% Assuming Cache Miss Again
    ApiUtil->>ProviderImpl: call_provider_specific(...)
    activate ProviderImpl
    ProviderImpl->>LLMService: API Request
    activate LLMService
    LLMService-->>ProviderImpl: Success Response
    deactivate LLMService
    ProviderImpl-->>ApiUtil: llm_response_text
    deactivate ProviderImpl
    ApiUtil-->>Node: llm_response_text
    deactivate ApiUtil

    %% Node continues processing... validates YAML etc.

    Node-->>Flow: exec_result (Successful)
    deactivate Node

    Note over Flow: Continues to Node Post-processing