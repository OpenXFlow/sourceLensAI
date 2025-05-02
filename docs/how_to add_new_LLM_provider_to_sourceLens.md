```markdown
# How to Add Support for a New LLM Provider

This guide outlines the steps required to add support for a new Large Language Model (LLM) provider to the `sourceLens` tool. The modular design aims to make this process straightforward.

## Prerequisites

*   Familiarity with the `sourceLens` project structure, especially the `src/sourcelens/utils/` directory.
*   Access to the new LLM provider's API documentation.
*   An API key or necessary credentials for the new provider.

## Steps

1.  **Implement API Interaction (`src/sourcelens/utils/`)**

    *   **Determine Type:** Is the provider a cloud service requiring specific SDKs/HTTP calls, or a local server exposing an OpenAI-compatible API?
    *   **Cloud Provider:**
        *   Open `src/sourcelens/utils/_cloud_llm_api.py`.
        *   Add a new function, e.g., `call_new_provider(prompt: str, llm_config: LlmConfigDict) -> str`.
        *   Inside this function:
            *   Import any necessary SDKs or the `requests` library (ensure safe imports with checks like `SDK_AVAILABLE`).
            *   Retrieve the `api_key`, `model`, and any other required parameters (e.g., `api_base_url`) from the `llm_config` dictionary. Raise `ValueError` if essential keys are missing.
            *   Construct the API request (URL, headers, payload) according to the provider's documentation. Format the input `prompt` into the expected message structure.
            *   Make the API call using the SDK or `requests`.
            *   Handle the API response: Check for errors (status codes, error messages), parse the response JSON, and extract the generated text content.
            *   Implement robust error handling. Catch provider-specific exceptions or `requests.exceptions.RequestException`. Raise `LlmApiError` (imported from `._exceptions`) with relevant details (message, status code, provider name) on failure.
    *   **Local OpenAI-Compatible Provider:**
        *   Usually, no new function is needed in `_local_llm_api.py` if it truly follows the OpenAI standard `/v1/chat/completions` endpoint structure. The existing `call_local_openai_compatible` function should work if configured correctly.
        *   If the local provider has significant deviations, you might need to add a new function similar to the cloud provider steps.

2.  **Register Provider in Dispatcher (`src/sourcelens/utils/llm_api.py`)**

    *   Open `src/sourcelens/utils/llm_api.py`.
    *   Locate the `call_llm` function.
    *   Inside the `try...except` block where providers are dispatched, add a new `elif` condition:
        ```python
        # Inside call_llm function
        try:
            # ... existing providers ...
            elif provider == "new_provider_name": # Use the official name
                # Choose the correct implementation module (_cloud or _local)
                response_text = _cloud_llm_api.call_new_provider(prompt, llm_config)
                # OR if using the existing local compatible function:
                # response_text = _local_llm_api.call_local_openai_compatible(prompt, llm_config)
            # ... existing else block ...
        except ...
        ```
    *   Ensure you call the correct function implemented in Step 1.

3.  **Update Configuration Schema & Validation (`src/sourcelens/config.py`)**

    *   **Update Schema:**
        *   Find the `LLM_PROVIDER_SCHEMA` dictionary.
        *   Add your `"new_provider_name"` to the `enum` list within the `"provider"` property's definition.
    *   **Update API Key Resolution (Optional but Recommended):**
        *   Find the `_resolve_api_key` function.
        *   If the new provider uses a standard environment variable for its API key (e.g., `NEWPROVIDER_API_KEY`), add an entry to the `env_var_map` dictionary:
            ```python
            env_var_map = {
                # ... existing entries ...
                "new_provider_name": "NEWPROVIDER_API_KEY",
            }
            ```
    *   **Update Provider Validation:**
        *   Find the `_validate_active_llm_config` function.
        *   Determine if the new provider needs special validation logic (like Vertex AI needing project/location) or if it fits the standard cloud/local patterns.
        *   If special logic is needed, add an `elif provider == "new_provider_name":` block calling a new validation helper function (similar to `_validate_vertexai_config`).
        *   If it's a standard cloud provider needing only an API key, it should automatically be handled by the final `else:` block calling `_validate_standard_cloud_config`.
        *   If it's a standard local provider needing only a base URL, it should be handled by the `if is_local:` block calling `_validate_local_llm_config`. Adjust these standard validators if necessary.

4.  **Add Dependencies (`pyproject.toml`)**

    *   If the new provider requires a specific Python SDK, add it to the `[project.dependencies]` section in `pyproject.toml`.
    *   Run `pip install -e .[dev]` again to install the new dependency into your virtual environment.
    *   If you maintain `requirements.txt`, regenerate it.

5.  **Update Configuration Examples (`config.example.json`)**

    *   Add a new dictionary entry to the `llm.providers` list in `config.example.json` for your `"new_provider_name"`.
    *   Include all necessary configuration fields (`is_active`, `is_local_llm`, `provider`, `model`, `api_key`, `api_base_url`, etc.), setting `is_active: false` by default.
    *   Use placeholders like `YOUR_NEWPROVIDER_KEY_HERE` for secrets.

6.  **Test Thoroughly**

    *   Create or modify your local `config.json` to activate the new provider. Ensure `is_active: true` for its entry and `is_active: false` for all others.
    *   Provide necessary credentials (either in `config.json` or via environment variables, as configured).
    *   Run `sourcelens` against a small test repository or directory.
    *   Check the logs (`logs/sourcelens.log`) for any errors during the API calls.
    *   Verify that the output is generated correctly and makes sense.
    *   Test edge cases (e.g., invalid API key, network issues if possible).

7.  **(Optional) Update Documentation**

    *   Mention the newly supported provider in the main `README.md` file.
    *   Ensure any relevant documentation accurately reflects the added support.

By following these steps, you can integrate new LLM providers while maintaining the project's modular structure. Remember to prioritize security by handling API keys appropriately (preferably via environment variables).
```