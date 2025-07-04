# How to Add a New LLM Provider to SourceLens

This guide outlines the steps required to integrate a new Large Language Model (LLM) provider into the `sourceLens` tool. The modular design aims to make this process straightforward by focusing on configuration and specific API implementation.

## Table of Contents
1.  [Implement the API Call Logic](#1-implement-the-api-call-logic)
2.  [Register the Provider in the Dispatcher](#2-register-the-provider-in-the-dispatcher)
3.  [Add a Profile for the New Provider](#3-add-a-profile-for-the-new-provider)
4.  [Define Environment Variable Constants (Optional)](#4-define-environment-variable-constants-optional)
5.  [Add Dependencies (If Required)](#5-add-dependencies-if-required)
6.  [Test the Integration](#6-test-the-integration)
7.  [Update Documentation](#7-update-documentation)

---

### 1. Implement the API Call Logic

First, you need to write the function that handles the actual communication with the new provider's API.

*   **Location:** `src/sourcelens/utils/_cloud_llm_api.py` (for cloud services) or `src/sourcelens/utils/_local_llm_api.py` (for local servers).
*   **Action:**
    1.  Create a new function, for example: `call_new_provider(prompt: str, llm_config: LlmConfigDict) -> str`.
    2.  **Safe Imports:** If a new SDK is needed, import it safely at the top of the file with a check, similar to how `requests` or `google.generativeai` are handled.
    3.  **Configuration:** Extract necessary parameters (`api_key`, `model`, `api_base_url`, etc.) from the `llm_config` dictionary. Raise a `ValueError` if a required key is missing.
    4.  **Request:** Construct the API request payload and headers according to the provider's documentation.
    5.  **Error Handling:** Make the API call within a `try...except` block. Catch specific network or API exceptions (e.g., `requests.exceptions.RequestException` or an SDK-specific error). On failure, you **must** raise `LlmApiError` (from `._exceptions`) with a descriptive message, status code (if available), and the provider's name. This is crucial for the application's retry mechanism.
    6.  **Response:** Parse the successful response and return the generated text content as a string.

### 2. Register the Provider in the Dispatcher

Next, tell SourceLens's central LLM dispatcher how to call your new function.

*   **Location:** `src/sourcelens/utils/llm_api.py`
*   **Action:**
    1.  Find the internal function `_get_llm_response`.
    2.  Add a new `elif` condition to the `if/elif` block that dispatches based on the `provider` string.

    **Example:**
    ```python
    # Inside _get_llm_response function in llm_api.py
    
    provider: str = provider_any.lower()

    if provider == "gemini":
        response_text = _cloud_llm_api.call_gemini(prompt, llm_config)
    elif provider == "perplexity":
        response_text = _cloud_llm_api.call_perplexity(prompt, llm_config)
    
    # ADD YOUR NEW PROVIDER HERE
    elif provider == "new_provider_name": 
        response_text = _cloud_llm_api.call_new_provider(prompt, llm_config)

    elif provider in ("openai_compatible_local", "openai_compatible"):
        # ... existing code ...
    else:
        raise ValueError(f"Unsupported LLM provider configured: {provider}")
    ```
    *   Make sure `"new_provider_name"` matches the `provider` value you will use in the configuration profiles.

### 3. Add a Profile for the New Provider

The application learns about providers and their settings through profiles defined in the configuration. You don't need to modify Python schema files.

*   **Location:** `config.example.json` (and your local `config.json` for testing).
*   **Action:**
    1.  Navigate to the `profiles.llm_profiles` array.
    2.  Add a new JSON object for your provider. This object defines the default settings and tells the `ConfigLoader` how to handle it.

    **Example Profile:**
    ```json
    {
      "provider_id": "new_provider_main", // A unique ID for this specific configuration
      "is_local_llm": false, // Is it a local or cloud service?
      "provider": "new_provider_name", // MUST match the string used in the dispatcher (Step 2)
      "model": "model-name-v1", // Default model for this provider
      "api_key_env_var": "NEW_PROVIDER_API_KEY", // Env variable for the API key (see Step 4)
      "api_key": null, // Keep null to prioritize env variable
      "api_base_url": "https://api.newprovider.com/v1" // If needed
    }
    ```
    *   **`provider_id`**: A unique name you choose for this profile (e.g., `anthropic_opus`, `my_local_llama`).
    *   **`provider`**: The string that the dispatcher in `llm_api.py` uses to select the correct `call_*` function.

### 4. Define Environment Variable Constants (Optional)

To maintain consistency, it's good practice to define the environment variable name as a constant.

*   **Location:** `src/sourcelens/config_loader.py`
*   **Action:**
    1.  At the top of the file, add a new constant for your API key's environment variable.

    **Example:**
    ```python
    # ... existing ENV_VAR constants ...
    ENV_VAR_PERPLEXITY_KEY: Final[str] = "PERPLEXITY_API_KEY"
    ENV_VAR_NEW_PROVIDER_KEY: Final[str] = "NEW_PROVIDER_API_KEY" // Add your new constant
    ```

### 5. Add Dependencies (If Required)

If your new provider's API requires a specific Python SDK, you must add it to the project's dependencies.

*   **Location:** `pyproject.toml`
*   **Action:**
    1.  Add the SDK package (e.g., `new-provider-sdk>=1.0.0`) to the `[project.dependencies]` list.
    2.  Re-install dependencies in your virtual environment by running:
        ```bash
        pip install -e .[dev,all]
        ```
    3.  If you maintain `requirements.txt`, regenerate it from `pyproject.toml`.

### 6. Test the Integration

Thoroughly test the new provider to ensure it works correctly within the `sourceLens` flows.

1.  **Configure:** In your local `config.json`, find the flow you want to test with (e.g., `FL01_code_analysis`) and set its `active_llm_provider_id` to the `provider_id` you created in Step 3.
    ```json
    "FL01_code_analysis": {
      "active_llm_provider_id": "new_provider_main",
      // ... other settings
    }
    ```
2.  **Authenticate:** Make sure your API key is available, either by setting the environment variable (`export NEW_PROVIDER_API_KEY=...`) or by temporarily putting it in `config.json`.
3.  **Run:** Execute a `sourceLens` command, preferably on a small test project.
    ```bash
    sourcelens code --dir /path/to/small/project
    ```
4.  **Verify:**
    *   Check `logs/sourcelens.log` for any errors, especially `LlmApiError`.
    *   Examine the generated output files in the `output/` directory to ensure they are high-quality.
    *   Test edge cases, such as providing an invalid API key, to see if your error handling works as expected.

### 7. Update Documentation

If the new provider is a permanent addition, update the project's documentation.

*   **Location:** `README.md` and any other relevant docs.
*   **Action:**
    *   Add the new provider to the list of supported LLMs.
    *   Explain any specific configuration required for it.

By following these updated steps, you can cleanly and effectively integrate new LLM capabilities into SourceLens.