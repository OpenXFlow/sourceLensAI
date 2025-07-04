# How to Configure the Web Crawling Flow (`FL02`)

This guide is for users who want to customize the `FL02_web_crawling` flow. By editing `config.json`, you can control crawling behavior, fine-tune content processing, and manage outputs for web pages, sitemaps, and YouTube videos.

## Table of Contents
1.  [Core Configuration Block: `FL02_web_crawling`](#1-core-configuration-block-fl02_web_crawling)
2.  [Controlling the Crawler: `crawler_options`](#2-controlling-the-crawler-crawler_options)
3.  [Tuning Content Segmentation: `segmentation_options`](#3-tuning-content-segmentation-segmentation_options)
4.  [Configuring YouTube Processing](#4-configuring-youtube-processing)
5.  [Managing Flow Outputs](#5-managing-flow-outputs)

---

### 1. Core Configuration Block: `FL02_web_crawling`

All settings specific to the web flow are located within the `FL02_web_crawling` object in your `config.json`.

```json
"FL02_web_crawling": {
  "enabled": true,
  "active_llm_provider_id": "gemini_flash_main",
  "crawler_options": { ... },
  "segmentation_options": { ... },
  "youtube_processing": { ... },
  "output_options": { ... }
}
```

### 2. Controlling the Crawler: `crawler_options`

This section lets you define how `sourceLens` fetches content from the web.

*   **`"processing_mode"`**: The most important setting.
    *   `"minimalistic"`: **(Default & Low Cost)** Simply crawls the web pages and saves their content as clean Markdown. **No LLM calls are made.** Use this for archiving or pre-processing.
    *   `"llm_extended"`: **(High Cost)** Performs a full AI analysis pipeline on the crawled content: identifies concepts, analyzes relationships, writes chapters, and generates a review.

*   **`"max_depth_recursive"`**: Controls how deep the crawler goes from the starting URL.
    *   `0`: Crawls only the single starting URL.
    *   `1`: Crawls the starting URL and all pages it links to (on the same domain).
    *   `2`: Crawls one level deeper, and so on.
    *   **Note:** This is automatically set to `0` when a YouTube URL is provided to prevent crawling external links in the video description.

*   **`"user_agent"`**: Sets the User-Agent string for the crawler. It's good practice to identify your bot.

*   **`"respect_robots_txt"`**: If `true`, the crawler will respect the rules defined in a website's `robots.txt` file.

### 3. Tuning Content Segmentation: `segmentation_options`

This section is only relevant for the `"llm_extended"` processing mode. It defines how large web pages are broken down into smaller, manageable "chunks" for the LLM to analyze.

*   **`"enabled"`**: A master switch to turn segmentation on or off.

*   **`"min_chunk_char_length"`**: The minimum number of characters a piece of text must have to be considered a valid chunk. This prevents very short, meaningless sections (like a lone heading) from being processed.

*   **`"heading_levels_to_split_on"`**: A list of Markdown heading levels (e.g., `[1, 2, 3]` for `<h1>`, `<h2>`, `<h3>`) that will be used as delimiters to split the content.

### 4. Configuring YouTube Processing

The `youtube_processing` block controls how transcripts are handled when a YouTube URL is provided.

*   **`"expected_transcript_languages_on_yt"`**: This is a **prioritized list** of language codes (e.g., `"en"`, `"sk"`, `"de"`). `sourceLens` will search for an available transcript in this exact order. For example, with `["en", "sk"]`, it will first look for an English transcript. If found, it will use it. If not, it will then look for a Slovak one.

### 5. Managing Flow Outputs

The `output_options` block lets you enable or disable the creation of the final AI-generated summary files (only used in `"llm_extended"` mode).

```json
"output_options": {
  "include_content_inventory": true, // Set to false to skip generating the inventory of all chunks
  "include_content_review": true     // Set to false to skip generating the final AI review
}
```
Disabling these can save a few LLM calls if you are only interested in the generated chapters.
