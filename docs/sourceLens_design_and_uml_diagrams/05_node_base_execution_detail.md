
5. Detailed Node Execution (IdentifyAbstractions Example)
This diagram shows the internal prep -> exec -> post flow for a specific node, highlighting interaction with shared state and utilities.


```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator
    participant Identify as IdentifyAbstractions Node
    participant Shared as SharedState Dictionary
    participant Helpers as utils.helpers
    participant ApiUtil as LlmApi (utils.llm_api.py)
    participant Validation as utils.validation

    Flow->>Identify: prep(shared)
    activate Identify

    Identify->>Shared: Read required keys (files, project_name, llm_config, etc.)
    Note over Identify,Shared: Uses _get_required_shared

    Identify->>Helpers: get_content_for_indices(files_data, ...)
    activate Helpers
    Helpers-->>Identify: Relevant file content map
    deactivate Helpers

    Identify->>Identify: _format_prompt(...)
    Note right of Identify: Prepares prompt text

    Identify-->>Flow: prep_result (dict with context, prompt parts, etc.)
    deactivate Identify

    Flow->>Identify: exec(prep_result)
    activate Identify

    Identify->>ApiUtil: call_llm(prompt, llm_config, cache_config)
    activate ApiUtil
    %% Caching/Provider logic happens inside ApiUtil (see Diagram 4)
    ApiUtil-->>Identify: Raw LLM Response (string)
    deactivate ApiUtil

    Identify->>Validation: validate_yaml_list(raw_response, item_schema)
    activate Validation
    Validation-->>Identify: Parsed/Validated Abstractions List (or raises ValidationFailure)
    deactivate Validation

    Identify->>Identify: _parse_and_validate_indices(...)
    Note over Identify: Cleans up file indices

    Identify-->>Flow: exec_result (List of abstraction dicts)
    deactivate Identify

    Flow->>Identify: post(shared, prep_res, exec_res)
    activate Identify

    Identify->>Shared: Update shared['abstractions'] = exec_res
    Note right of Identify: Stores results

    Identify-->>Flow: done
    deactivate Identify