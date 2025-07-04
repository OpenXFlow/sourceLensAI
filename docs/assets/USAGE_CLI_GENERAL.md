# SourceLens: General Command-Line Usage

This document outlines the general command-line interface (CLI) structure for `sourceLens`, including global options that apply to all analysis flows. For flow-specific commands and options, please refer to:

*   [Code Analysis Flow Usage](./USAGE_CLI_CODE_FLOW.md)
*   [Web Content Analysis Flow Usage](./USAGE_CLI_WEB_FLOW.md)

## Command-Line Structure

`sourceLens` is invoked from the command line, followed by a subcommand specifying the type of analysis, and then relevant options.

**General Syntax:**
```bash
sourcelens [GLOBAL_OPTIONS] <flow_command> [FLOW_SPECIFIC_OPTIONS]
```

*   **`sourcelens`**: The main executable command for the tool.
*   **`[GLOBAL_OPTIONS]`**: Arguments that can be applied to any flow command. These are typically specified *before* the `flow_command`.
*   **`<flow_command>`**: Specifies the type of analysis to perform. Currently supported:
    *   `code` (or alias `code_analysis`): For analyzing source code.
    *   `web` (or alias `web_crawling`): For analyzing web content.
*   **`[FLOW_SPECIFIC_OPTIONS]`**: Arguments that are specific to the chosen `flow_command`. These are specified *after* the `flow_command`.

## CLI Help Snippets

You can get help directly from the CLI:

*   **Main Help (`sourcelens -h` or `sourcelens --help`):**
    ```
    usage: sourcelens [-h] [--config FILE_PATH] [-n OUTPUT_NAME] [-o MAIN_OUTPUT_DIR] [--language LANG]
                      [--log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}] [--log-file PATH_OR_NONE]
                      [--llm-provider ID] [--llm-model NAME] [--api-key KEY] [--base-url URL]
                      {code,code_analysis,web,web_crawling} ...

    SourceLens: Generate tutorials from codebases or web content using AI.

    options:
      -h, --help            show this help message and exit
      --config FILE_PATH    Path to global config JSON file. (default: config.json)
      -n OUTPUT_NAME, --name OUTPUT_NAME
                            Override default output name for the tutorial/summary. (default: None)
      -o MAIN_OUTPUT_DIR, --output MAIN_OUTPUT_DIR
                            Override main output directory for generated files. (default: None)
      --language LANG       Override generated text language (e.g., 'english', 'slovak'). (default: None)
      --log-level {DEBUG,INFO,WARNING,ERROR,CRITICAL}
                            Override logging level from config. (default: None)
      --log-file PATH_OR_NONE
                            Path to log file. Use 'NONE' to disable file logging if enabled by config. (default: None)

    LLM Overrides (common to all flows):
      --llm-provider ID     Override active LLM provider ID from config. (default: None)
      --llm-model NAME      Override LLM model name. (default: None)
      --api-key KEY         Override LLM API key directly. (default: None)
      --base-url URL        Override LLM API base URL. (default: None)

    The type of analysis to perform.:
      {code,code_analysis,web,web_crawling}
        code (code_analysis)
                            Analyze source code from a repository or local directory.
        web (web_crawling)  Crawl and analyze content from web URLs, sitemaps, or files.
    ```
    *(For help on a specific flow command, use `sourcelens <flow_command> --help`, e.g., `sourcelens code --help`)*

## Global Options

These options can be used with any flow command (e.g., `sourcelens [GLOBAL_OPTION] code ...`).

*   **`--config FILE_PATH`**
    *   Specifies the path to your global `config.json` file.
    *   Default: `config.json` in the current working directory.

*   **`-n OUTPUT_NAME`, `--name OUTPUT_NAME`**
    *   Overrides the auto-generated name for the output directory (which is based on timestamp, source type, and source name).
    *   Example: `--name "MyFlaskProject_Analysis"`

*   **`-o MAIN_OUTPUT_DIR`, `--output MAIN_OUTPUT_DIR`**
    *   Overrides the `main_output_directory` setting from your `config.json` (default is usually "output").
    *   The final output for a specific run will be a subdirectory within this path (e.g., `MAIN_OUTPUT_DIR/YourProjectName`).
    *   Example: `--output /path/to/my/custom_outputs`

*   **`--language LANG`**
    *   Overrides the `generated_text_language` specified in your `config.json`.
    *   This affects the language in which LLM-generated content (summaries, chapters, reviews) will be produced.
    *   Example: `--language slovak`, `--language english`

*   **`--log-level {DEBUG|INFO|WARNING|ERROR|CRITICAL}`**
    *   Overrides the logging level set in your `config.json`.
    *   Useful for debugging (`DEBUG`) or quieter operation (`WARNING`).
    *   Example: `--log-level DEBUG`

*   **`--log-file PATH_OR_NONE`**
    *   Specifies a path for the log file for this specific run.
    *   If set to `"NONE"` (case-insensitive), file logging will be disabled for this run, even if enabled in `config.json`.
    *   If a path is provided, it overrides any default log file naming/location from `config.json`.
    *   Example: `--log-file ./run_specific.log`, `--log-file NONE`

### LLM Overrides (Global)

These options allow you to override specific LLM settings for the current run, affecting the chosen flow.

*   **`--llm-provider ID`**
    *   Overrides the `active_llm_provider_id` defined in `config.json` for the selected flow.
    *   The `ID` must correspond to one of the provider IDs defined in the `llm_profiles` section of your `config.json`.
    *   Example: `--llm-provider openai_gpt4o`

*   **`--llm-model NAME`**
    *   Overrides the specific `model` name for the LLM provider being used (either the default one for the flow or the one specified by `--llm-provider`).
    *   Example: `--llm-model gpt-4-turbo-preview` (if using an OpenAI provider)

*   **`--api-key KEY`**
    *   Allows you to directly provide the API key for the LLM provider.
    *   This will override any API key found in `config.json` or loaded from environment variables for this run.
    *   **Caution:** Be mindful of shell history if using this method.

*   **`--base-url URL`**
    *   Overrides the `api_base_url` for the LLM provider.
    *   Primarily used for local LLMs or services that use an OpenAI-compatible API but are hosted at a custom endpoint.
    *   Example: `--base-url http://localhost:11434/v1` (for a local Ollama instance)

---

Generated tutorials, summaries, and diagrams will appear in a subdirectory within your configured main output directory. The subdirectory name is typically auto-generated based on the current date/time, the type of analysis, and the name of the source (e.g., `output/YYYYMMDD_HHMM_type-project-name/`).
