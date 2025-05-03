
**11. `get_content_for_indices` Helper Usage**

This diagram shows how a node (like `AnalyzeRelationships` or `WriteChapters`) uses the `utils.helpers.get_content_for_indices` function during its `prep` phase to gather specific file contents needed for its LLM prompt.

```mermaid
sequenceDiagram
    participant Node as Node needing specific files (e.g., Analyze)
    participant Shared as SharedState Dictionary
    participant Helpers as utils.helpers

    activate Node
    Note over Node: In prep phase

    Node->>Shared: Read `shared['files']` (List of all files)
    Node->>Shared: Read abstraction details containing needed indices (e.g., `shared['abstractions'][i]['files']`)

    Node->>Helpers: get_content_for_indices(all_files_data, required_indices)
    activate Helpers

    loop For index, (path, content) in all_files_data
        alt index is in required_indices
            Helpers->>Helpers: Add "{index} # {path}": content to result map
        else Index is out of bounds or not required
            %% Skip or Log Warning
        end
    end

    Helpers-->>Node: content_map (Dict["idx # path" -> content])
    deactivate Helpers

    Node->>Node: Use content_map to build LLM prompt context
    Note over Node: Continues prep...
    deactivate Node