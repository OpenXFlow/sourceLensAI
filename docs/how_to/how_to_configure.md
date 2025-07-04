## ⚙️ Configuration

After installation, `sourceLens` is ready to run with default settings (e.g., output in English). You can customize its behavior in two main ways:

#### A) Using Command-Line Arguments (Recommended for one-off changes)

You can override many settings directly from the command line. This is the easiest way to make temporary changes. For example, to change the output language to English:

```bash
sourcelens code --dir ./my-project --language english
```

Run `sourcelens --help` or `sourcelens code --help` to see all available flags.

#### B) Using a `config.json` File (For persistent settings)

For settings you want to use every time (like API keys and default language), create a `config.json` file in the directory **where you will run the `sourcelens` command**.

You only need to include the settings you want to change. For example, to set your Gemini API key and make English the default language:

```json
{
  "common": {
    "common_output_settings": {
      "generated_text_language": "english"
    }
  },
  "profiles": {
    "llm_profiles": [
      {
        "provider_id": "gemini_flash_main",
        "api_key": "your_gemini_api_key_here"
      }
    ]
  }
}
```

> **Note:** Command-line arguments will always override settings from `config.json`. You can see all possible configuration options in the [`config.example.json`](https://github.com/openXFlow/sourceLensAI/blob/main/config.example.json) file in the repository.
