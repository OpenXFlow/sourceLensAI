```markdown
# How to Run sourceLens

This guide explains how to run the `sourceLens` application after completing the initial setup (cloning, virtual environment, installation).

## 1. Prerequisites Check

*   **Python:** Python 3.9 or higher installed. (Note: While 3.13 might work, versions 3.10-3.12 are generally recommended for broader package compatibility. See Troubleshooting if you encounter version issues).
*   **Git:** Git must be installed and accessible in your PATH (used for cloning repositories if analyzing via `--repo`).
*   **Initial Setup:** You have cloned the repository, created a virtual environment, and installed dependencies (see `README.md`).

## 2. Virtual Environment Activation

*   **Crucial Step:** Before running any `sourcelens` commands, always activate the virtual environment you created during setup.
*   Navigate to the project's root directory (`sourceLensAI/`) in your terminal.
*   **Activation Commands:**
    *   **Linux/macOS:** `source venv/bin/activate` (or the name you gave your venv folder).
    *   **Windows:** `.\venv\Scripts\activate` (or the name you gave your venv folder, e.g., `.\venv_310\Scripts\activate`).
*   Your terminal prompt should now show the environment name (e.g., `(venv)` or `(venv_310)`) at the beginning.

## 3. Configuration (`config.json`)

*   Ensure you have copied `config.example.json` to `config.json` in the project root.
*   **Set Secrets (API Keys/Tokens):** You **must** provide API keys for the LLM(s) you intend to use and optionally a GitHub token.
    *   **(Recommended) Use Environment Variables:**
        *   In `config.json`, set the relevant `api_key` (under `llm.providers`) and `token` (under `github`) fields to `null`.
        *   Before running `sourcelens`, set the environment variables in your shell:
            ```bash
            # Example for Linux/macOS
            export GEMINI_API_KEY="your_gemini_key_here" # Or OPENAI_API_KEY, etc.
            export GITHUB_TOKEN="your_github_token_here"
            # Example for Windows Command Prompt
            # set GEMINI_API_KEY=your_gemini_key_here
            # Example for Windows PowerShell
            # $env:GEMINI_API_KEY = "your_gemini_key_here"

            sourcelens ... # Now run the command
            ```
        *   Supported variables include `GEMINI_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `PERPLEXITY_API_KEY`, `GITHUB_TOKEN`, etc. (Check `src/sourcelens/config.py` for the full map).
    *   **(Less Secure) Edit `config.json` Directly:**
        *   Place your keys/tokens directly into the corresponding fields (`"api_key": "..."`, `"token": "..."`).
        *   **WARNING:** Ensure `config.json` is **never** committed to Git if it contains secrets.
*   **Select Active Profiles:** Ensure `is_active: true` is set for *exactly one* provider under `llm.providers` and *exactly one* language profile under `source.language_profiles`. Set others to `false`.
*   **Adjust Other Settings:** Configure `output.base_dir`, `llm.model`, `source` filters, etc., as needed.

## 4. Running the `sourcelens` Command

*   With your virtual environment activated and `config.json` prepared, use the `sourcelens` command.
*   You **must** provide either `--repo` (for GitHub) or `--dir` (for local).

**Command Syntax:**

```bash
sourcelens [OPTIONS] (--repo REPO_URL | --dir LOCAL_DIR)
```

**Examples:**

*   **Analyze a Local Project:**
    ```bash
    # Analyze the sample project included in tests
    sourcelens --dir tests/sample_project

    # Analyze your own local project (replace path)
    sourcelens --dir /path/to/your/local/project/src
    sourcelens --dir ../my-other-project
    ```

*   **Analyze a GitHub Repository:**
    ```bash
    # Analyze a public repository
    sourcelens --repo https://github.com/The-Pocket/pocketflow

    # Analyze a larger public repository (may hit rate limits without token)
    sourcelens --repo https://github.com/astral-sh/ruff

    # Analyze a private repository (requires valid token)
    sourcelens --repo https://github.com/your-username/your-private-repo
    ```

*   **Using Overrides:** Command-line options temporarily override `config.json` settings.
    ```bash
    # Use a different config file
    sourcelens --config my_special_config.json --repo https://github.com/owner/repo

    # Override output directory and generated language
    sourcelens --repo https://github.com/owner/repo --output ./generated_tutorials --language spanish

    # Override include/exclude patterns for a local run
    sourcelens --dir ./my_code --include "*.js" "*.css" --exclude "node_modules/*" "dist/*"
    ```

## 5. Monitoring Output & Finding Results

*   **Console Output:** `sourceLens` prints progress messages and logs (INFO level by default) to the console.
*   **Log File:** Detailed logs (including DEBUG messages if configured) are written to the file specified in `config.json` (default: `logs/sourcelens.log`). **Check this file first for errors.**
*   **Duration:** Processing can take significant time depending on codebase size, LLM speed, and API calls.
*   **Generated Files:** Upon successful completion, find the Markdown tutorial files in a subdirectory within your configured `output.base_dir`. The subdirectory is named after the project (e.g., `output/ruff/`, `output/sample_project/`). Look for `index.md` and numbered chapter files (`01_...md`, `02_...md`).

## 6. Troubleshooting Common Issues

*   **`Command not found: sourcelens`**:
    *   **Fix:** Ensure your virtual environment is activated. Check the activation step (Section 2).
    *   **Fix:** Verify installation completed successfully (`pip install -e .[dev]` or `pip install -r requirements.txt`). If unsure, re-run the installation command within the activated venv.
    *   **Check:** Use `where sourcelens` (Windows) or `which sourcelens` (Linux/macOS) within the venv to see if the executable path exists.

*   **Configuration Errors (`ConfigError`)**:
    *   **Fix:** Check `config.json` exists in the project root.
    *   **Fix:** Ensure `config.json` is valid JSON (use an online validator).
    *   **Fix:** Verify all required fields are present and correctly formatted according to `config.example.json` and the schema in `src/sourcelens/config.py`. Check the error message in the console or log file for specifics.

*   **API Key / LLM Errors (`LlmApiError`)**:
    *   **Fix:** Double-check the API key (in `config.json` or environment variable) is correct for the *active* LLM provider.
    *   **Fix:** Ensure the key has necessary permissions and billing is enabled on the provider's platform.
    *   **Fix:** Check the specific error message in the log file (`LlmApiError: ...`).

*   **GitHub Errors (`GithubApiError`)**:
    *   **`Authentication failed` / `Could not read` / `Not found`**: Ensure `--repo` URL is correct. For private repos, verify your GitHub token (in `config.json` or `GITHUB_TOKEN` env var) is valid and has `repo` scope permissions.
    *   **`Rate limit exceeded`**: This is common when analyzing larger repos without a token.
        *   **Fix:** Generate a GitHub Personal Access Token (PAT):
            1. Go to GitHub Settings -> Developer settings -> Personal access tokens -> Tokens (classic).
            2. Generate a new token. Give it a name (e.g., `sourceLens`).
            3. Select expiration and scopes. The `repo` scope is generally needed. For public-only analysis, `public_repo` might suffice.
            4. **Copy the token immediately.**
        *   **Fix:** Provide the token to `sourceLens`:
            *   **Recommended:** Set the `GITHUB_TOKEN` environment variable before running.
            *   *Alternatively:* Paste the token string into the `token` field in `config.json` (less secure).
        *   **Fix:** Stop the running command (Ctrl+C) and restart it after providing the token.

*   **LLM Response Validation Errors (`ValidationFailure`)**:
    *   **Cause:** The LLM generated output (YAML) that doesn't match the expected format or schema.
    *   **Fix:** Check the log file for the error message and potentially the problematic LLM response snippet.
    *   **Fix (Advanced):** This might require modifying the prompt generation logic within the corresponding node file (`analyze.py`, `structure.py`, `write.py`) to be clearer or more robust for the specific LLM being used.

*   **Dependency / Installation / Python Version Issues**:
    *   **Symptom:** Errors during `pip install` or `ImportError` when running.
    *   **Check:** Verify your Python version (`python --version`). While 3.9+ is required, some dependencies might have stricter upper/lower bounds. Consider using Python 3.10, 3.11, or 3.12 if issues arise with newer versions like 3.13.
    *   **Fix:** Create the virtual environment using a specific, compatible Python version if needed: `C:\Path\To\Python311\python.exe -m venv venv` (Windows example).
    *   **Fix:** Try a clean install within the venv: `pip install --no-cache-dir -r requirements.txt` or `pip install --no-cache-dir -e .[dev]`.
    *   **Check:** Use `pip list` within the activated venv to see installed package versions. Ensure key packages (`google-generativeai`, `requests`, `PyYAML`, `GitPython`, etc.) are present.

*   **General Advice:**
    *   **Check the Logs:** `logs/sourcelens.log` often contains detailed error messages and tracebacks that pinpoint the problem. Increase log level to `DEBUG` in `config.json` for more verbose output if needed.

```