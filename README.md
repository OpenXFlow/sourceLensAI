<h1 align="center">sourceLens: AI-Powered Source Code Tutorials</h1>

<p align="center">
  <a href="https://www.gnu.org/licenses/gpl-3.0"><img src="https://img.shields.io/badge/License-GPLv3-blue.svg" alt="License: GPL v3"></a>
</p>

*Feeling lost in a new codebase? `sourceLens` uses AI to analyze code repositories (GitHub/local) and automatically generate beginner-friendly tutorials explaining how it works.*

<p align="center">
  <img src="./docs/assets/banner.png" alt="sourceLens Banner" width="800"/>
</p>

`sourceLens` is an AI-powered command-line tool that analyzes source code (GitHub/local) and generates beginner-friendly Markdown tutorials explaining its structure and concepts.

## Key Features

*   **Code Input:** Fetches code from GitHub repositories (public/private) or local directories.
*   **AI Analysis:** Uses configurable Large Language Models (LLMs like Gemini, etc.) to identify core concepts, map their relationships, and determine a logical learning path.
*   **Tutorial Generation:** Creates structured Markdown tutorials with an index, individual chapters, and explanations in potentially multiple languages.
*   **Filtering:** Supports include/exclude patterns and file size limits for focused analysis.
*   **Configurable:** Operation is controlled via a `config.json` file, with support for environment variables for secrets.

## Installation

**Prerequisites:**

*   Python 3.9 or higher
*   Git

**Steps:**

1.  **Clone:**
    ```bash
    git clone https://github.com/darijo2yahoocom/sourceLensAI
    cd sourceLensAI
    ```

2.  **Set up Virtual Environment:**
    *   Linux/macOS: `python3 -m venv venv && source venv/bin/activate`
    *   Windows: `python -m venv venv && .\venv\Scripts\activate`
    *(Your prompt should show `(venv)`)*

3.  **Install Dependencies:**
    ```bash
    pip install -e .[dev]
    ```

## Configuration

Configuration is primarily handled via `config.json`.

1.  **Copy Example:** `cp config.example.json config.json`

2.  **Set Secrets (API Keys/Tokens):** You have two options:
    *   **(Recommended) Use Environment Variables:**
        *   In `config.json`, set the relevant `api_key` (under `llm.providers`) and `token` (under `github`) fields to `null`.
        *   Before running `sourcelens`, set the corresponding environment variables in your shell:
            ```bash
            # Example for Linux/macOS
            export GEMINI_API_KEY="your_gemini_key_here" # Or OPENAI_API_KEY, ANTHROPIC_API_KEY, etc.
            export GITHUB_TOKEN="your_github_token_here"
            sourcelens ...
            ```
        *   The tool checks for standard variables like `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `GITHUB_TOKEN`, etc., if the config value is `null`.
    *   **(Less Secure) Edit `config.json` Directly:**
        *   Place your API key directly into the `"api_key": "..."` field for the active LLM provider.
        *   Place your GitHub Token directly into the `"token": "..."` field under `github`.
        *   **WARNING:** If you use this method, ensure `config.json` is never committed to Git.

3.  **Adjust Other Settings:** Review `config.json` and modify other settings (LLM model, active language profile, file filters, output directory) as needed.

    **IMPORTANT:** `config.json` is ignored by Git (`.gitignore`). Even if using environment variables, **do NOT commit `config.json`** as it might contain other configuration details or accidentally hold secrets later.

## Usage

Run from the command line, providing a source:

```bash
sourcelens [OPTIONS] (--repo REPO_URL | --dir LOCAL_DIR)
```

**Common Options:**

*   `--repo REPO_URL`: URL of the GitHub repository.
*   `--dir LOCAL_DIR`: Path to the local codebase directory.
*   `--config FILE_PATH`: Path to config file (default: `config.json`).
*   `--name NAME`: Override the project name for the tutorial.
*   `--output DIR`: Override the base output directory.
*   `--include PATTERN`: Add an include file pattern (can use multiple).
*   `--exclude PATTERN`: Add an exclude file pattern (can use multiple).
*   `--language LANG`: Override the output tutorial language.

**Examples:**

```bash
# Analyze a GitHub repo (assuming keys are in environment variables or config.json)
sourcelens --repo https://github.com/darijo2yahoocom/sourceLensAI

# Analyze a local directory
sourcelens --dir ../my-local-project/src

# Analyze with overrides
sourcelens --repo https://github.com/some/repo --name "My Tutorial" --language spanish
```

Generated tutorials appear in the configured output directory (e.g., `output/your-project-name/`).

## License

This project is licensed under the GNU GPL v3 License - see the LICENSE file for details.
```