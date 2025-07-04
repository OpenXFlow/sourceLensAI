### `how_to_analyze_and_understand_logs.md`

# How to Analyze and Understand SourceLens Logs

The log file (`logs/sourcelens.log` by default) is the most powerful tool for understanding what `sourceLens` is doing and for diagnosing problems. This guide explains the structure of the logs, how to trace a successful run, and how to identify and interpret common errors.

## Table of Contents
1.  [Log File Structure and Verbosity](#1-log-file-structure-and-verbosity)
2.  [Anatomy of a Successful Run: Tracing the Flow](#2-anatomy-of-a-successful-run-tracing-the-flow)
3.  [Common Error Patterns and How to Interpret Them](#3-common-error-patterns-and-how-to-interpret-them)
    *   [Group A: Configuration & Setup Errors](#group-a-configuration--setup-errors)
    *   [Group B: Data Fetching Errors](#group-b-data-fetching-errors)
    *   [Group C: LLM-Related Errors](#group-c-llm-related-errors)
    *   [Group D: Internal Processing Errors](#group-d-internal-processing-errors)

---

### 1. Log File Structure and Verbosity

Each log entry has a standard format:
`{Timestamp} - {Module:Function} - {LogLevel} - {Message}`

*   **Timestamp:** When the event occurred.
*   **Module:Function:** Where in the code the log message originated (e.g., `FetchCode:pre_execution`). This is key for tracing.
*   **LogLevel:** `INFO` (normal progress), `DEBUG` (detailed info), `WARNING` (potential issue), `ERROR` (a specific operation failed), `CRITICAL` (application-halting issue).
*   **Message:** The description of the event.

To get the most detailed logs for debugging, set the `log_level` in your `config.json` to `"DEBUG"`.

### 2. Anatomy of a Successful Run: Tracing the Flow

A healthy log file will show a clear, sequential progression through the nodes defined in the active flow. For `FL01_code_analysis`, look for this sequence:

1.  **`sourcelens.main`**: Logs initialization, argument parsing, and config loading.
2.  **`FetchCode:pre_execution`**: Signals the start of fetching source files.
3.  **`sourcelens.utils.github` / `local`**: Shows details of the crawling process.
4.  **`FetchCode:post_execution`**: Confirms how many files were successfully fetched.
5.  **`IdentifyAbstractions:pre_execution` -> `execution` -> `post_execution`**: Shows the start, execution (including LLM calls), and completion of abstraction identification.
6.  **This P-E-P pattern repeats for each node in the chain:**
    *   `AnalyzeRelationships`
    *   `OrderChapters`
    *   `IdentifyScenariosNode`
    *   `GenerateDiagramsNode`
    *   `WriteChapters` (will show logs for each individual chapter being written)
    *   `GenerateSourceIndexNode`
    *   `GenerateProjectReview`
7.  **`CombineTutorial:pre_execution`**: This is the final major step where all generated content is assembled and written to disk. Look for "Wrote index file" and "Wrote chapter file" messages.
8.  **`sourcelens.main:_handle_flow_completion`**: The final log message confirming the successful completion and the output path.

If the log follows this sequence without any `ERROR` or `CRITICAL` entries, your run was successful.

### 3. Common Error Patterns and How to Interpret Them

Errors in the log can be grouped into several categories, helping you quickly identify the root cause.

#### Group A: Configuration & Setup Errors

These errors occur at the very start of the application, usually before any processing begins.

*   **Log Signature:** `ConfigError: ...` or `FileNotFoundError: config.json`
*   **Example Log:** `ERROR: Configuration setup failed: ConfigError: ...`
*   **Meaning:** Your `config.json` file is missing, malformed (not valid JSON), or is missing a required section or key.
*   **Action:**
    1.  Ensure `config.json` exists in the project root.
    2.  Use a JSON validator to check its syntax.
    3.  Compare its structure to `config.example.json` to find the missing part.

#### Group B: Data Fetching Errors

These occur in the `FetchCode` (FL01) or `FetchWebPage` / `FetchYouTubeContent` (FL02) nodes.

*   **Log Signature:** `GithubApiError`, `NoFilesFetchedError`, errors from `sourcelens.utils.github` or `crawl4ai`.
*   **Example Log (FL01):** `ERROR: API Error processing path '': Path not found via API... (Status: 404)`
*   **Meaning (Code):** The GitHub repository URL is incorrect, the repo is private and your token is invalid/missing, or the branch/path within the repo doesn't exist.
*   **Example Log (FL02):** `ERROR: yt-dlp error during info extraction...` or `WARNING: CrawlResult for '...' missing data.`
*   **Meaning (Web):** The target URL is invalid, blocked, or returned an error. For YouTube, a transcript might not be available.
*   **Action:**
    1.  Double-check the provided URL or directory path.
    2.  For private GitHub repos, verify your `GITHUB_TOKEN` is correct and has `repo` permissions.
    3.  For web crawling, check the website's availability and `robots.txt` file.

#### Group C: LLM-Related Errors

These are the most common errors during the main processing phase.

*   **Log Signature:** `LlmApiError`, `ValidationFailure`.
*   **Example 1 (API Limit):** `LlmApiError: ... 429 You exceeded your current quota...`
    *   **Meaning:** You have hit the daily or per-minute limit of your LLM provider's plan (especially the free tier).
    *   **Action:** Wait for the quota to reset, upgrade your plan, or switch to a different LLM provider (like a local model) in `config.json`.
*   **Example 2 (Authentication):** `LlmApiError: ... 401 Unauthorized` or `API key is invalid`.
    *   **Meaning:** The API key for your active LLM provider is incorrect, expired, or missing.
    *   **Action:** Verify the API key in your environment variables or `config.json`.
*   **Example 3 (Validation Failure):** `ERROR: YAML validation failed for ...: ValidationFailure: ...`
    *   **Meaning:** The LLM returned a response, but its format was incorrect (e.g., malformed YAML). The pipeline stopped because it couldn't parse the data.
    *   **Action:** This requires developer intervention. Follow the steps in "Debugging LLM Output and Prompts" in `how_to_debug_and_troubleshoot_the_pipeline.md` to fix the prompt.

#### Group D: Internal Processing Errors

These errors suggest a potential bug or unexpected data state within the application itself.

*   **Log Signature:** `KeyError`, `AttributeError`, `TypeError`, `IndexError`.
*   **Example Log:** `ERROR: All attempts to generate project review ... failed. Last error: KeyError: 'some_missing_key'`
*   **Meaning:** A node expected a certain key in `shared_context` (e.g., `abstractions`) but it was not found. This is often a knock-on effect of an earlier failure (like an LLM error).
*   **Action:**
    1.  Trace the log backwards from the error message.
    2.  Find the *first* `ERROR` or `WARNING` that occurred. The `KeyError` is likely a symptom, not the root cause.
    3.  For example, if `GenerateProjectReview` fails with a `KeyError` on `abstractions`, look for an earlier error in the `IdentifyAbstractions` node logs.

By understanding these patterns, you can quickly move from identifying an error in the logs to diagnosing its root cause.

