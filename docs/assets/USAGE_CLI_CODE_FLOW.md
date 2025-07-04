# SourceLens: Code Analysis Flow Usage (`code` / `code_analysis`)

This document details the command-line options and usage examples specific to the **Code Analysis Flow** in `sourceLens`. This flow is designed to analyze source code from local directories or GitHub repositories and generate a tutorial-like documentation structure.

For general CLI options applicable to all flows, refer to [General CLI Usage](./USAGE_CLI_GENERAL.md).

## Command Syntax

To initiate a code analysis, use the `code` subcommand (or its alias `code_analysis`):

```bash
sourcelens [GLOBAL_OPTIONS] code (--dir LOCAL_DIR | --repo REPO_URL) [CODE_SPECIFIC_OPTIONS]
```
or
```bash
sourcelens [GLOBAL_OPTIONS] code_analysis (--dir LOCAL_DIR | --repo REPO_URL) [CODE_SPECIFIC_OPTIONS]
```

## Source Options (Required - Choose One)

You must specify one of the following options to provide the source code:

*   **`--dir LOCAL_DIR`**
    *   Specifies the path to a local directory containing the codebase you want to analyze.
    *   The path can be relative (e.g., `../my_project/src`) or absolute.
    *   Example: `sourcelens code --dir ./my_app_source`

*   **`--repo REPO_URL`**
    *   Specifies the URL of a GitHub repository to clone and analyze.
    *   The URL can point to the main repository page, a specific branch, tag, or even a subdirectory within the repository.
        *   Example (main branch): `https://github.com/user/repository`
        *   Example (specific branch): `https://github.com/user/repository/tree/develop`
        *   Example (specific tag): `https://github.com/user/repository/tree/v1.0.0`
        *   Example (subdirectory): `https://github.com/user/repository/tree/main/src/app`
    *   If analyzing private repositories, ensure your GitHub token is configured (see [Configuration](../README.md#configuration)).
    *   Example: `sourcelens code --repo https://github.com/pallets/flask`

## Code-Specific Options

These options allow you to fine-tune the code analysis process and override settings defined in your `config.json` for the `FL01_code_analysis` flow.

*   **`-h, --help`**
    *   Shows the help message specific to the `code` subcommand and exits.

*   **`-i PATTERN [PATTERN ...]`, `--include PATTERN [PATTERN ...]`**
    *   Overrides the `include_patterns` defined in the active language profile in your `config.json`.
    *   Specifies one or more glob-style patterns for files to **include** in the analysis.
    *   If used, only files matching these patterns (and not matching exclude patterns) will be processed.
    *   Can be specified multiple times or with multiple patterns separated by spaces.
    *   Example: `sourcelens code --dir . --include "*.py" "*.md"`

*   **`-e PATTERN [PATTERN ...]`, `--exclude PATTERN [PATTERN ...]`**
    *   Overrides the `default_exclude_patterns` defined in `source_options` (or language profile) in your `config.json`.
    *   Specifies one or more glob-style patterns for files or directories to **exclude** from the analysis.
    *   Patterns are matched against paths relative to the scan root.
    *   Example: `sourcelens code --dir . --exclude "*.log" "temp/*" "**/__pycache__"`

*   **`-s BYTES`, `--max-size BYTES`**
    *   Overrides the `max_file_size_bytes` setting from `source_options` in your `config.json`.
    *   Sets the maximum size (in bytes) for individual files to be included in the analysis. Files larger than this will be skipped.
    *   Example: `sourcelens code --dir . --max-size 100000` (for 100KB)

## Examples

1.  **Analyze a local Python project directory:**
    ```bash
    sourcelens code --dir /path/to/my/python_project
    ```

2.  **Analyze a specific branch of a public GitHub repository and generate output in Slovak:**
    ```bash
    sourcelens --language slovak code --repo https://github.com/tiangolo/fastapi/tree/master
    ```

3.  **Analyze a local Java project, overriding the output directory name and including only `.java` and `pom.xml` files:**
    ```bash
    sourcelens -n "MyJavaAppDoc" code --dir ./my-java-app --include "*.java" "pom.xml"
    ```

4.  **Analyze a C++ project from GitHub, excluding build directories and using a specific LLM provider:**
    ```bash
    sourcelens --llm-provider local_ollama_llama3_8b code --repo https://github.com/nlohmann/json --exclude "build/*" "tests/*"
    ```

5.  **Analyze a local directory with verbose logging for debugging:**
    ```bash
    sourcelens --log-level DEBUG code --dir ./project_to_debug
    ```

---

The generated tutorial, including an `index.md` and chapter files, will be placed in a subdirectory within your main output directory (e.g., `output/YYYYMMDD_HHMM_code-projectname/`).
