### `how_to_configure_code_analysis.md`

# How to Configure the Code Analysis Flow (`FL01`)

This guide is for users who want to customize the `FL01_code_analysis` flow. By editing `config.json`, you can analyze projects written in different programming languages, switch LLM providers, and optimize runs to save time and API costs.

## Table of Contents
1.  [Core Configuration File: `config.json`](#1-core-configuration-file-configjson)
2.  [Switching the Active LLM Provider](#2-switching-the-active-llm-provider)
3.  [Managing Language Profiles](#3-managing-language-profiles)
4.  [Optimizing Code Analysis Runs](#4-optimizing-code-analysis-runs)

---

### 1. Core Configuration File: `config.json`

All customizations are done in your `config.json` file. You will primarily be editing two sections:
*   `profiles`: Where you define available LLM and Language profiles.
*   `FL01_code_analysis`: The block that controls the code analysis flow specifically.

### 2. Switching the Active LLM Provider

You can easily switch which LLM is used for the analysis. First, ensure the provider you want to use is defined in the `profiles.llm_profiles` array (see `how_to_add_new_LLM_provider_to_sourceLens.md` for adding new ones).

To activate a different LLM for code analysis, update the `active_llm_provider_id` in the `FL01_code_analysis` block:

```json
"FL01_code_analysis": {
  "active_llm_provider_id": "local_llama3_ollama", // Switched from "gemini_flash_main"
  // ... other settings ...
}
```

### 3. Managing Language Profiles

Language profiles are the most important configuration for code analysis. They tell `sourceLens`:
*   Which files to include in the analysis (`include_patterns`).
*   How to parse the source code (`parser_type`).
*   What to name the language when talking to the LLM (`language_name_for_llm`).

#### How to Add a Profile for a New Language

Let's say you want to add support for `Rust`.

1.  Navigate to the `profiles.language_profiles` array in your `config.json`.
2.  Add a new profile object based on the existing examples:

    ```json
    {
      "profiles": {
        "language_profiles": [
          // ... existing profiles like python_ast_default ...
          {
            "profile_id": "rust_llm_default",    // 1. A unique ID for this profile
            "language_name_for_llm": "Rust",       // 2. The name for the LLM
            "parser_type": "llm",                  // 3. Use "llm" for non-Python languages
            "include_patterns": [                  // 4. File patterns for Rust projects
              "*.rs",
              "Cargo.toml",
              "Cargo.lock",
              "README.md"
            ]
          }
        ]
      }
    }
    ```
*   **`parser_type`**: This is crucial. Use `"ast"` only for Python, as it's fast and doesn't require LLM calls for structural analysis. For all other languages, set this to `"llm"`, which instructs `sourceLens` to use an LLM to parse the structure of each file.

#### How to Use Your New Language Profile

Update the `active_language_profile_id` in the `FL01_code_analysis` configuration block to activate your new profile for the next run.

```json
"FL01_code_analysis": {
  "active_language_profile_id": "rust_llm_default", // Activate the new Rust profile
  // ... other settings ...
}
```

### 4. Optimizing Code Analysis Runs

You can significantly reduce API calls and speed up execution by disabling parts of the flow you don't currently need. This is done inside the `FL01_code_analysis` block.

**Example: A "Review-Only" Run**

If you only want the `project_review.md` file and don't need diagrams or individual chapters, use this configuration:

```json
"FL01_code_analysis": {
  // ...
  "diagram_generation": {
    "enabled": false // This disables ALL diagram-related LLM calls
  },
  "output_options": {
    "include_source_index": false, // Disables the code inventory to save AST parsing time
    "include_project_review": true  // Keeps our target output enabled
  }
}
```
This configuration reduces the number of LLM calls from over 20 to just 4, while still producing a high-quality project review because all its necessary inputs (abstractions, relationships) are still generated.

