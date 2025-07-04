## Configuration

Configuration is managed through `config.json` (for user overrides and secrets) and default configurations within each flow's directory.

1.  **Copy Example Global Configuration:**
    ```bash
    cp config.example.json config.json
    ```

2.  **Set API Keys and Tokens (Secrets):**
    It's **highly recommended** to use environment variables for API keys and tokens.
    *   In `config.json`, find the `llm_profiles` array under `profiles`. For each cloud LLM provider you intend to use, set its `"api_key": null`.
    *   Similarly, for GitHub analysis from private repositories, set `"github_token": null` under `FL01_code_analysis`.
    *   Before running `sourcelens`, set the corresponding environment variables in your shell. The specific variable names (e.g., `GEMINI_API_KEY`, `OPENAI_API_KEY`, `GITHUB_TOKEN`) are usually defined in `config.json` within each profile's `api_key_env_var` field.
        ```bash
        # Example for Linux/macOS
        export GEMINI_API_KEY="your_gemini_key_here"
        export GITHUB_TOKEN="your_github_token_here"
        # ... other keys as needed ...

        sourcelens ...
        ```
    *   Alternatively (less secure), you can edit `config.json` directly and paste your keys/tokens into the respective `"api_key": "..."` or `"github_token": "..."` fields.
        **WARNING:** If you use this method, ensure `config.json` is **NEVER** committed to version control. The `.gitignore` file is set up to ignore `config.json`.

3.  **Review and Adjust Other Settings:**
    *   Open `config.json` and customize:
        *   `common.common_output_settings.generated_text_language`: e.g., "slovak", "english".
        *   `common.logging.log_level`: e.g., "INFO", "DEBUG".
        *   Active LLM provider (`active_llm_provider_id`) for each flow (`FL01_code_analysis`, `FL02_web_crawling`).
        *   Flow-specific options (e.g., `source_options` for code, `crawler_options` for web).

