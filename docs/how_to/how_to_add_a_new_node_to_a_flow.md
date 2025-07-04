# How to Add a New Node to a Flow

This guide provides a developer-focused walkthrough on how to extend a `sourceLens` pipeline by creating and integrating a new processing node. The modular architecture is designed to make this process straightforward for both the code analysis (`FL01`) and web crawling (`FL02`) flows.

## 1. The Principle of a Node

In `sourceLens`, a `Node` is a self-contained processing step that inherits from `BaseNode`. It operates on the `shared_context` dictionary and follows a clear lifecycle:

1.  **`pre_execution`**: Gathers and validates necessary data from `shared_context`.
2.  **`execution`**: Performs its core logic on the prepared data.
3.  **`post_execution`**: Stores its results back into `shared_context` for subsequent nodes.

This pattern is identical for both `FL01` and `FL02`. The only difference is the data (keys in `shared_context`) that each node consumes and produces.

---

## 2. Example for `FL01_code_analysis`: `CalculateCodeStatsNode`

Let's create a node that calculates basic statistics (total files, total lines of code) for the code analysis flow.

### Step 1: Create the Node File

*   **New File:** `src/FL01_code_analysis/nodes/n11_calculate_stats.py`

### Step 2: Define the Node Class

```python
# In src/FL01_code_analysis/nodes/n11_calculate_stats.py

# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
# ... (Add the full GPL license header here) ...

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import FilePathContentList

class CalculateCodeStatsNode(BaseNode):
    """A node to calculate simple statistics about the fetched source code."""

    def pre_execution(self, shared_context: SLSharedContext) -> FilePathContentList:
        self._log_info("Preparing to calculate code statistics...")
        files_data = self._get_required_shared(shared_context, "files")
        
        if not isinstance(files_data, list):
            self._log_warning("'files' data is not a list; returning empty for calculation.")
            return []
            
        return files_data

    def execution(self, prepared_inputs: FilePathContentList) -> dict:
        self._log_info(f"Calculating stats for {len(prepared_inputs)} files...")
        if not prepared_inputs:
            return {"file_count": 0, "total_lines": 0}

        total_lines = sum(len(content.splitlines()) for _, content in prepared_inputs if content)
        return {"file_count": len(prepared_inputs), "total_lines": total_lines}

    def post_execution(self, shared_context: SLSharedContext, prepared_inputs: FilePathContentList, execution_outputs: dict) -> None:
        shared_context["project_code_stats"] = execution_outputs
        self._log_info(f"Stored project code stats in shared context: {execution_outputs}")
```

### Step 3: Integrate the Node into the Code Flow

1.  **Export from `nodes/__init__.py`**:
    *   In `src/FL01_code_analysis/nodes/__init__.py`, add:
        ```python
        from .n11_calculate_stats import CalculateCodeStatsNode
        __all__.append("CalculateCodeStatsNode")
        ```
2.  **Add to `flow.py`**:
    *   In `src/FL01_code_analysis/flow.py`, import and chain the node, ideally after `FetchCode`.
        ```python
        # In create_code_analysis_flow function
        from .nodes import ..., CalculateCodeStatsNode

        # ... (instantiate other nodes)
        calc_stats = CalculateCodeStatsNode()

        # Chain it into the flow
        (fetch_code >> calc_stats >> id_abstr >> ...)
        ```

---

## 3. Example for `FL02_web_crawling`: `SummarizeAllChunksNode`

Now let's create a simpler node for the web flow. This node will create a single, combined summary of all web content chunks.

### Step 1: Create the Node File

*   **New File:** `src/FL02_web_crawling/nodes/n09_summarize_all_chunks.py`

### Step 2: Define the Node Class

This node will consume `web_content_chunks` and produce `overall_chunks_summary`.

```python
# In src/FL02_web_crawling/nodes/n09_summarize_all_chunks.py

# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
# ... (Add the full GPL license header here) ...

from sourcelens.core import BaseNode, SLSharedContext
from sourcelens.core.common_types import WebContentChunkList, LlmConfigDict, CacheConfigDict
from sourcelens.utils.llm_api import call_llm, LlmApiError

class SummarizeAllChunksNode(BaseNode):
    """A node to create a single summary of all web content."""

    def pre_execution(self, shared_context: SLSharedContext) -> dict:
        self._log_info("Preparing to summarize all web chunks...")
        chunks = self._get_required_shared(shared_context, "web_content_chunks")
        return {
            "chunks": chunks,
            "llm_config": self._get_required_shared(shared_context, "llm_config"),
            "cache_config": self._get_required_shared(shared_context, "cache_config")
        }

    def execution(self, prepared_inputs: dict) -> str:
        chunks: WebContentChunkList = prepared_inputs["chunks"]
        if not chunks:
            return "No content chunks were available to summarize."
            
        # Create a condensed context for the LLM
        context = "\\n\\n---\\n\\n".join([c.get("content", "") for c in chunks])
        prompt = f"Summarize the following collection of text chunks into a single, coherent paragraph:\n\n{context}"

        try:
            summary = call_llm(prompt, prepared_inputs["llm_config"], prepared_inputs["cache_config"])
            return summary
        except LlmApiError as e:
            self._log_error("LLM call failed during chunk summarization: %s", e)
            return f"Error: Could not generate overall summary. {e}"

    def post_execution(self, shared_context: SLSharedContext, prepared_inputs: dict, execution_outputs: str) -> None:
        shared_context["overall_chunks_summary"] = execution_outputs
        self._log_info("Stored overall chunk summary in shared context.")

```

### Step 3: Integrate the Node into the Web Flow

1.  **Export from `nodes/__init__.py`**:
    *   In `src/FL02_web_crawling/nodes/__init__.py`, add:
        ```python
        from .n09_summarize_all_chunks import SummarizeAllChunksNode
        __all__.append("SummarizeAllChunksNode")
        ```
2.  **Add to `flow.py`**:
    *   In `src/FL02_web_crawling/flow.py`, import and chain the node. A good place is after `SegmentWebContent` but before the other analysis nodes.
        ```python
        # In _build_llm_extended_pipeline_core function
        from .nodes import ..., SummarizeAllChunksNode

        # ...
        summarize_all = SummarizeAllChunksNode()

        llm_nodes_sequence: list[PipelineNodeType] = [
            cast(PipelineNodeType, SegmentWebContent()),
            cast(PipelineNodeType, summarize_all), # Add the new node here
            cast(PipelineNodeType, IdentifyWebConcepts(...)),
            #...
        ]
        # ...
        ```

By following these examples, you can extend either flow with custom logic while adhering to the project's established architecture.
