
**9. YAML Validation Failure**

This diagram illustrates what happens when the LLM returns syntactically valid YAML, but it doesn't conform to the expected structure (schema) or type.


```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator
    participant Node as Node Parsing YAML (e.g., Identify)
    participant ApiUtil as LlmApi (utils.llm_api.py)
    participant Validation as utils.validation
    participant ExternalLLM

    Flow->>Node: exec(prep_result)
    activate Node

    Node->>ApiUtil: call_llm(prompt, ...)
    activate ApiUtil
    ApiUtil->>ExternalLLM: Request
    ExternalLLM-->>ApiUtil: Raw Response (string with invalid YAML structure)
    ApiUtil-->>Node: llm_response_text
    deactivate ApiUtil

    Node->>Validation: validate_yaml_list(llm_response_text, schema)
    activate Validation
    Note over Validation: Extracts YAML block, PyYAML parses successfully

    alt Schema Validation Fails (jsonschema)
        Validation-->>Node: raises ValidationFailure("Schema error at 'path': Expected string, got int")
    else Type Validation Fails
        Note over Validation: Expecting list, got dict
        Validation-->>Node: raises ValidationFailure("Expected YAML list, got dict")
    end
    deactivate Validation

    Node-->>Flow: raises ValidationFailure(...)
    deactivate Node

    Note over Flow: Catches ValidationFailure, likely stops the flow