
**7. CombineTutorial Node Detail**

This diagram focuses on how the `CombineTutorial` node gathers information and writes the final output.

```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator
    participant Combine as CombineTutorial Node
    participant Shared as SharedState Dictionary
    participant Helpers as utils.helpers
    participant FS as FileSystem

    %% Combine often does work in Prep as workaround
    Flow->>Combine: prep(shared)
    activate Combine

    Combine->>Shared: Read project_name, output_dir, relationships, chapter_order, abstractions, chapters
    Note over Combine,Shared: Gets all necessary data

    Combine->>Helpers: sanitize_filename(project_name)
    activate Helpers
    Helpers-->>Combine: safe_project_dir_name
    deactivate Helpers

    Combine->>Combine: _prepare_chapter_file_data(...)
    Note over Combine: Creates list of {filename, content, name, ...} dicts

    Combine->>Combine: _generate_mermaid_diagram(...)
    Note over Combine: Creates Mermaid graph definition string

    Combine->>Combine: _prepare_index_content(...)
    Note over Combine: Assembles content for index.md

    Combine->>Combine: _write_output_files(...)
    activate Combine # Internal processing for writing

    Combine->>FS: Create output directory (e.g., output/project-name/)
    activate FS
    FS-->>Combine: done
    deactivate FS

    Combine->>FS: Write index.md (with Mermaid diagram)
    activate FS
    FS-->>Combine: done
    deactivate FS

    loop For Each Chapter File Data
        Combine->>FS: Write chapter_XX_name.md
        activate FS
        FS-->>Combine: done
        deactivate FS
    end

    Combine->>Shared: Update shared['final_output_dir'] = output_path_str

    Combine-->>Combine: writing_result (boolean success)
    deactivate Combine # End internal writing process

    Combine-->>Flow: prep_result (boolean success)
    deactivate Combine

    %% Post step mainly logs based on shared state
    %% Flow->>Combine: post(...)