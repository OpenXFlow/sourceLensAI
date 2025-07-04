# How to Debug and Troubleshoot the Pipeline

This guide is for developers working on the `sourceLens` codebase. It provides advanced techniques for debugging issues that go beyond simple syntax errors, such as problems with data flow, LLM response quality, or flow-specific logic.

## Table of Contents
1.  [General Debugging Techniques (For Both Flows)](#1-general-debugging-techniques-for-both-flows)
    *   [1.1 Inspecting the `shared_context`](#11-inspecting-the-shared_context)
    *   [1.2 Isolating and Testing a Single Flow](#12-isolating-and-testing-a-single-flow)
    *   [1.3 Debugging LLM Output and Prompts](#13-debugging-llm-output-and-prompts)
    *   [1.4 Working with the LLM Cache](#14-working-with-the-llm-cache)
2.  [Troubleshooting `FL01_code_analysis`](#2-troubleshooting-fl01_code_analysis)
    *   [Scenario: Not all expected files are being analyzed](#scenario-not-all-expected-files-are-being-analyzed)
    *   [Scenario: `parser_type: ast` fails or produces poor output](#scenario-parser_type-ast-fails-or-produces-poor-output)
3.  [Troubleshooting `FL02_web_crawling`](#3-troubleshooting-fl02_web_crawling)
    *   [Scenario: The crawler doesn't find expected pages](#scenario-the-crawler-doesnt-find-expected-pages)
    *   [Scenario: Content segmentation is not working as expected](#scenario-content-segmentation-is-not-working-as-expected)
    *   [Scenario: YouTube transcript processing fails](#scenario-youtube-transcript-processing-fails)

---

## 1. General Debugging Techniques (For Both Flows)

These techniques are fundamental for debugging any part of the `sourceLens` application.

### 1.1 Inspecting the `shared_context`

The `shared_context` dictionary is the "bloodstream" of the pipeline. Every piece of data is passed through it. Inspecting its contents is the most effective way to debug data flow issues.

*   **Technique:** Temporarily add `print` or `logger.debug` statements in the flow definition file (`src/FL01_code_analysis/flow.py` or `src/FL02_web_crawling/flow.py`) between node chains.

*   **Example:** To check the output of the `IdentifyWebConcepts` node:
    ```python
    # In src/FL02_web_crawling/flow.py, inside create_web_crawling_flow()
    
    # ... after chaining up to IdentifyWebConcepts ...
    ( ... >> segment_content >> id_concepts)
    
    # --- TEMPORARY DEBUGGING ---
    import json
    # Run the first few nodes to populate the context
    segment_content._run_node_lifecycle(initial_context)
    id_concepts._run_node_lifecycle(initial_context)
    
    print("--- DEBUG: Web Concepts in Context ---")
    print(json.dumps(initial_context.get("text_concepts"), indent=2))
    print("--- END DEBUG ---")
    
    # You might want to exit here during debugging
    # import sys; sys.exit()
    
    # Continue the chain for a normal run
    (id_concepts >> an_web_rels >> ...)
    ```

### 1.2 Isolating and Testing a Single Flow

Running the entire `sourcelens` command can be slow. Each flow has its own command-line interface for isolated testing, which is much faster.

*   **Code Analysis Flow:**
    ```bash
    python src/FL01_code_analysis/cli.py --dir ./tests/python_sample_project
    ```
*   **Web Crawling Flow:**
    ```bash
    python src/FL02_web_crawling/cli.py --crawl-file "https://www.youtube.com/watch?v=..."
    ```

### 1.3 Debugging LLM Output and Prompts

When generated content is low-quality or malformed (`ValidationFailure`), the issue is almost always the prompt sent to the LLM.

1.  **Check for `ValidationFailure` in Logs:** This error means the LLM returned data (e.g., YAML) that didn't match the expected structure. The log will often contain a snippet of the problematic raw output.
2.  **Inspect the Exact Prompt:** Set the `log_level` in `config.json` to `"DEBUG"`. This will log the **full prompt** sent to the LLM and the **full raw response** received.
3.  **Iterate in a Playground:**
    *   Copy the logged prompt.
    *   Paste it into an LLM playground (e.g., Google AI Studio, OpenAI Playground).
    *   Refine the prompt text until the LLM consistently produces the correct output.
    *   Update the corresponding prompt file in `src/FL01_code_analysis/prompts/` or `src/FL02_web_crawling/prompts/`.

### 1.4 Working with the LLM Cache

The cache at `.cache/llm_cache.json` saves API calls but can serve stale data if you're iterating on a prompt.

*   **To force a new LLM call:**
    1.  Open `.cache/llm_cache.json`.
    2.  Find the key-value pair corresponding to the prompt you are debugging. The key is the full prompt text.
    3.  **Delete that entire key-value pair** and save the file.
*   The next run will now perform a live API call for that specific prompt.

## 2. Troubleshooting `FL01_code_analysis`

### Scenario: Not all expected files are being analyzed
*   **Cause:** The file filtering logic in `FetchCode` is excluding them.
*   **Troubleshooting:**
    1.  **Check `include_patterns`:** In your active language profile in `config.json`, ensure the file extension or pattern (e.g., `*.java`, `pom.xml`) is listed.
    2.  **Check `default_exclude_patterns`:** In the `FL01_code_analysis.source_options` block, ensure a pattern like `tests/*` or `*test*` isn't accidentally excluding your desired files.
    3.  **Check `max_file_size_bytes`:** Make sure the files aren't larger than the configured limit.

### Scenario: `parser_type: ast` fails or produces poor output
*   **Cause:** The Python file being parsed might have syntax errors or use unusual constructs that the AST visitor doesn't handle perfectly.
*   **Troubleshooting:**
    1.  The logs should indicate which file caused the AST parsing error.
    2.  Check that file for syntax errors using a standard linter.
    3.  For debugging the visitor itself, add print statements inside the `visit_*` methods in `src/FL01_code_analysis/nodes/index_formatters/_ast_python_formatter.py`.

## 3. Troubleshooting `FL02_web_crawling`

### Scenario: The crawler doesn't find expected pages
*   **Cause:** Crawl depth is too low, or `robots.txt` is blocking access.
*   **Troubleshooting:**
    1.  **Check `max_depth_recursive`:** In `FL02_web_crawling.crawler_options`, increase the depth. A depth of `0` only fetches the single starting URL.
    2.  **Check `respect_robots_txt`:** Try setting this to `false` temporarily to see if a restrictive `robots.txt` file is the cause. Do not abuse this on public websites.
    3.  **Check for JavaScript-Rendered Links:** `crawl4ai` is powerful, but some complex JavaScript-based sites might hide links in ways it can't easily discover.

### Scenario: Content segmentation is not working as expected
*   **Cause:** The settings in `segmentation_options` don't match the HTML structure of the page.
*   **Troubleshooting:**
    1.  After a run, inspect the raw Markdown file in `output/your-run/page_content/`.
    2.  Check which heading levels (`#`, `##`, `###`) are actually used in the Markdown.
    3.  Adjust the `heading_levels_to_split_on` array in `config.json` to match the levels you want to use as delimiters.
    4.  Adjust `min_chunk_char_length` if small sections are being discarded.

### Scenario: YouTube transcript processing fails
*   **Cause:** No suitable transcript is available, or `yt-dlp` encountered an error.
*   **Troubleshooting:**
    1.  **Check Available Languages:** Manually open the YouTube video in your browser and check which subtitle languages are *actually* available (both manual and auto-generated).
    2.  **Configure `expected_transcript_languages_on_yt`:** In `config.json`, make sure the list contains the language codes you see on YouTube, in your preferred order.
    3.  **Check `yt-dlp` Logs:** Set log level to `DEBUG` and inspect the output prefixed with `yt-dlp-lib:` for specific errors (e.g., "video is unavailable").
