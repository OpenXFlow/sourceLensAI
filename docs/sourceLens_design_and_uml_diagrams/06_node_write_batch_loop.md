
**6. WriteChapters Batch Node Process**

This diagram illustrates the batch processing nature of the `WriteChapters` node.

```mermaid
sequenceDiagram
    participant Flow as FlowOrchestrator
    participant Write as WriteChapters (Batch Node)
    participant Shared as SharedState Dictionary
    participant Helpers as utils.helpers
    participant ApiUtil as LlmApi (utils.llm_api.py)

    %% --- Prep Phase (Generates Items) ---
    Flow->>Write: prep(shared)
    activate Write
    Note over Write: Prepares metadata for *all* chapters

    loop For Each Chapter in Order
        Write->>Shared: Read abstractions, files_data, configs
        Write->>Helpers: get_content_for_indices(...)
        activate Helpers
        Helpers-->>Write: Content map for chapter files
        deactivate Helpers
        Write->>Write: Prepare chapter item dict (context, prompt parts)
        Note right of Write: Yields one item per chapter
    end

    Write-->>Flow: Iterable of chapter prep items
    deactivate Write


    %% --- Exec Phase (Processes Items Individually) ---
    Note over Flow, Write: PocketFlow calls exec for each yielded item

    loop For Each Chapter Item
        Flow->>Write: exec(chapter_item)
        activate Write

        Write->>Write: _format_prompt_for_chapter(chapter_item)
        Note over Write: Creates detailed prompt

        Write->>ApiUtil: call_llm(prompt, llm_config, cache_config)
        activate ApiUtil
        %% Internal LLM call logic
        ApiUtil-->>Write: Generated chapter content (Markdown string)
        deactivate ApiUtil

        Write->>Write: Add content to internal list (_chapters_written_this_run)

        Write-->>Flow: exec_result (Markdown string for one chapter)
        deactivate Write
    end


    %% --- Post Phase (Collects Results) ---
    Flow->>Write: post(shared, prep_iterable, list_of_exec_results)
    activate Write

    Write->>Shared: Update shared['chapters'] = list_of_exec_results
    Note right of Write: Stores all generated chapters

    Write->>Write: Clear internal list (_chapters_written_this_run)

    Write-->>Flow: done
    deactivate Write