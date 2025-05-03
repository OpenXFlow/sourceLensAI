
**17. Flow Execution Failure (`main.py`)**

This diagram shows the error handling in `main.py` if the `flow.run()` method itself raises an unhandled exception (one not caught and resolved by PocketFlow's retries).

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI (main.py)
    participant Flow as FlowOrchestrator (flow.py/PocketFlow)
    participant Node as Problematic Node
    participant System as Operating System / Shell

    Note over CLI: After successful setup and flow creation
    CLI->>Flow: run(shared_initial_state)
    activate Flow

    Note over Flow: Executes nodes...
    Flow->>Node: exec(...) or post(...)
    activate Node
    alt Unhandled Exception in Node/Utility
        Node-->>Flow: raises Exception (e.g., ValueError, TypeError, unexpected LlmApiError)
    end
    deactivate Node

    Note over Flow: Exception propagates up from flow.run()
    Flow-->>CLI: raises Exception
    deactivate Flow

    Note over CLI: Catches generic Exception during flow.run()
    CLI->>System: Logs exception details (logging.exception)
    CLI->>System: Prints error message to stderr

    CLI-->>User: Exits with non-zero status code (sys.exit(1))
     %%deactivate CLI