
# How to Run `sourceLens`

This guide covers the command-line usage of `sourceLens` after you have completed the initial setup (cloning, virtual environment, and dependency installation).

## 1. Prerequisite Checklist

*   [ ] **Python 3.9+ and Git:** Both must be installed and accessible in your system's PATH.
*   [ ] **Virtual Environment Activated:** This is a **critical step**. Before running any commands, navigate to the project root and activate your virtual environment:
    *   **Linux/macOS:** `source venv/bin/activate`
    *   **Windows (CMD):** `.\venv\Scripts\activate`
    *   **Windows (PowerShell):** `.\venv\Scripts\Activate.ps1`
*   [ ] **Dependencies Installed:** You have successfully run `pip install -e .[dev,all]`.
*   [ ] **Configuration File Ready:** You have a `config.json` file in the project root, created from `config.example.json`.

## 2. Configuration: API Keys and Tokens

`sourceLens` requires API credentials to function. The most secure way to provide them is via environment variables.

### Step 2.1: Configure API Keys (LLM)
Your chosen LLM provider requires an API key.

*   **(Recommended) Use Environment Variables:**
    *   Find the `api_key_env_var` for your chosen provider in `config.json` (e.g., `GEMINI_API_KEY`, `OPENAI_API_KEY`).
    *   Set this environment variable in your terminal session **before** running the tool.

    ```bash
    # Example for Linux/macOS
    export GEMINI_API_KEY="your_actual_gemini_api_key_here"

    # Example for Windows (PowerShell)
    $env:GEMINI_API_KEY="your_actual_gemini_api_key_here"
    ```

*   **(Less Secure) Direct `config.json` Edit:**
    *   Paste your key directly into the `"api_key": "..."` field for your active LLM profile.
    *   **Warning:** Ensure this `config.json` file is **never** committed to version control.

### Step 2.2: Configure GitHub Token (for Code Analysis)
For analyzing GitHub repositories (especially private ones or to avoid rate limits), a GitHub Personal Access Token (PAT) is required.

*   **(Recommended) Use Environment Variables:**
    *   The tool looks for the `GITHUB_TOKEN` environment variable by default.

    ```bash
    # Example for Linux/macOS
    export GITHUB_TOKEN="ghp_your_github_personal_access_token"
    ```

*   **(Less Secure) Direct `config.json` Edit:**
    *   Paste your token into the `"github_token": "..."` field under the `FL01_code_analysis` section.

## 3. Command-Line Usage

The `sourcelens` command uses subcommands to distinguish between analysis types: `code` and `web`.

### 3.1. Analyzing Source Code (`code` command)

**Syntax:**
`sourcelens code [SOURCE] [OPTIONS]`

*   **`[SOURCE]` (Required):** You must specify one source.
    *   `--repo <URL>`: To analyze a public or private GitHub repository.
    *   `--dir <PATH>`: To analyze a local directory on your machine.

**Examples:**
```bash
# Analyze a local project directory
sourcelens code --dir ./tests/python_sample_project

# Analyze a public GitHub repository
sourcelens code --repo https://github.com/The-Pocket/pocketflow

# Analyze a private repo (requires a valid GitHub token)
sourcelens code --repo https://github.com/your-org/your-private-project
```

### 3.2. Analyzing Web Content (`web` command)

**Syntax:**
`sourcelens web [SOURCE] [OPTIONS]`

*   **`[SOURCE]` (Required):** You must specify one source.
    *   `--crawl-url <URL>`: To crawl a website starting from a root URL.
    *   `--crawl-sitemap <URL>`: To fetch and analyze all URLs listed in a sitemap.
    *   `--crawl-file <URL or PATH>`: To analyze a single online document or a local text/markdown file. Can also be a YouTube video URL.

**Examples:**
```bash
# Crawl a single web page (with default depth)
sourcelens web --crawl-url https://example.com/blog/my-article

# Crawl a website recursively (override crawl depth)
sourcelens web --crawl-url https://docs.python.org/3/ --crawl-depth 2

# Analyze content from a YouTube video
sourcelens web --crawl-file "https://www.youtube.com/watch?v=some_video_id"
```

### 3.3. Common Command-Line Options

These options can be used with both `code` and `web` commands to override settings in `config.json` for a single run.

*   `--name <NAME>`: Specify a custom name for the output folder.
*   `--output <DIR>`: Set a different base output directory.
*   `--language <LANG>`: Generate documentation in a different language (e.g., `slovak`).
*   `--log-level <LEVEL>`: Set logging verbosity (e.g., `DEBUG`, `INFO`).
*   `--llm-provider <ID>`: Temporarily use a different LLM provider profile from your config.

**Example with Overrides:**
```bash
sourcelens code --repo https://github.com/astral-sh/ruff --language "slovak" --name "Ruff_Analysis_SK"
```

## 4. Finding and Viewing the Output

*   **Console:** Monitor the terminal for real-time progress and INFO-level logs.
*   **Log File:** For detailed debugging, check the log file (default: `logs/sourcelens.log`).
*   **Generated Files:** The final output is created in a subdirectory inside your configured `main_output_directory` (default: `output/`). The subdirectory name is based on the project name (e.g., `output/20250626_2122_code-sourcelensai/`).
*   **Viewing Diagrams:** The generated Markdown files contain Mermaid diagrams. To view them visually, use an editor with Mermaid support like **VS Code with the "Markdown Preview Mermaid Support" extension**.

## 5. Common Troubleshooting

*   **`sourcelens: command not found`**: Your virtual environment is not activated. Run the activation script.
*   **`ConfigError`**: Your `config.json` is missing, malformed (not valid JSON), or missing required sections. Validate it against `config.example.json`.
*   **`LlmApiError` / `429 ResourceExhausted`**: Your API key is invalid, or you have exceeded the rate limits/quota of your LLM provider plan. Check your provider's dashboard and the log file for details.
*   **`GithubApiError` / `Authentication failed`**: The GitHub repository URL is incorrect, or your GitHub token is invalid, expired, or lacks the necessary permissions (`repo` scope).
*   **`ValidationFailure`**: The LLM returned data in an unexpected format (e.g., malformed YAML). This may require prompt engineering adjustments in the source code for the specific LLM being used.
