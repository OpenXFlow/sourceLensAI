# How to Use Web Crawling Processing Modes (`FL02`)

The `sourceLens` web crawling flow (`FL02`) offers two distinct operational modes, controlled by the **`processing_mode`** setting in your `config.json`. Understanding the difference between these modes is crucial for controlling costs, managing time, and achieving your desired outcome.

## Table of Contents
1.  [Locating the `processing_mode` Setting](#1-locating-the-processing_mode-setting)
2.  [Mode 1: `minimalistic` (Default)](#2-mode-1-minimalistic-default)
3.  [Mode 2: `llm_extended` (Full AI Analysis)](#3-mode-2-llm_extended-full-ai-analysis)
4.  [Which Mode Should You Choose?](#4-which-mode-should-you-choose)

---

### 1. Locating the `processing_mode` Setting

You can configure the processing mode inside your `config.json` file, within the `FL02_web_crawling` block.

```json
{
  // ... other sections ...
  "FL02_web_crawling": {
    "enabled": true,
    "active_llm_provider_id": "gemini_flash_main",
    "crawler_options": {
      "processing_mode": "minimalistic", // <-- CHANGE THIS VALUE
      // ... other crawler options ...
    },
    // ... other sections ...
  }
}
```

**Accepted Values:** `"minimalistic"` or `"llm_extended"`.

---

### 2. Mode 1: `minimalistic` (Default)

This is the default mode. It is designed for one primary purpose: **content archiving**.

#### What It Does:
*   It runs only the initial `FetchWebPage` node.
*   This node crawls the target URL(s) based on your `max_depth_recursive` setting.
*   For each crawled page, it converts the HTML content into clean, readable Markdown.
*   It saves these Markdown files to a `page_content/` subdirectory within your run's output folder, preserving the original URL path structure.

#### What It Does **NOT** Do:
*   **It makes ZERO calls to any LLM API.**
*   It does not segment content into chunks.
*   It does not identify concepts, analyze relationships, write chapters, or generate a review.

#### When to Use `minimalistic` Mode:
*   **Archiving:** You need to quickly save the content of a website for offline reading or record-keeping.
*   **Cost-Saving:** You want to avoid all LLM-related API costs.
*   **Pre-processing:** You want to prepare a clean Markdown version of a website to feed into another tool or a later `llm_extended` run.

**Expected Output:** A `page_content/` directory full of `.md` files. There will be **no** `web_summary_index.md` or numbered chapter files.

---

### 3. Mode 2: `llm_extended` (Full AI Analysis)

This mode activates the entire AI-powered pipeline for web content.

#### What It Does:
1.  **Crawls & Archives:** It performs the same initial crawling as `minimalistic` mode.
2.  **AI Pipeline:** It then passes the crawled content through the full sequence of LLM-driven nodes:
    *   `SegmentWebContent`: Breaks the Markdown content into smaller, analyzable "chunks."
    *   `IdentifyWebConcepts`: Uses an LLM to find key topics and themes within the chunks.
    *   `AnalyzeWebRelationships`: Asks an LLM to determine how these concepts relate to each other.
    *   `OrderWebChapters`: Determines a logical flow for presenting the concepts.
    *   `WriteWebChapters`: Uses an LLM to write a detailed chapter for each concept.
    *   `GenerateWebInventory` & `GenerateWebReview`: Creates summary and review documents.
    *   `CombineWebSummary`: Assembles everything into a final, structured output.

#### When to Use `llm_extended` Mode:
*   **Content Summarization:** You need a deep, AI-generated summary of a large website or a complex set of documents.
*   **Knowledge Extraction:** Your goal is to distill the core concepts and themes from unstructured text.
*   **Automated Documentation:** You want to create a tutorial-like document from a knowledge base or documentation site.

**Expected Output:** A full set of documentation files, including `web_summary_index.md`, numbered chapter files (`01_...md`), `content_inventory.md`, and `web_content_review.md`.

---

### 4. Which Mode Should You Choose?

| Goal                                      | Recommended Mode     | Reason                                                                    |
| :---------------------------------------- | :------------------- | :------------------------------------------------------------------------ |
| I want to save a website for offline use. | **`minimalistic`**   | Fast, no API cost, directly archives content.                             |
| I want a deep AI summary of a website.    | **`llm_extended`**   | Activates the full analysis pipeline required for generating summaries.   |
| I want to avoid all API costs.            | **`minimalistic`**   | This mode is designed to be "offline" and does not call any LLMs.         |
| The tool is failing on LLM calls.         | **`minimalistic`**   | Use this to test if the basic web crawling is working correctly.          |

By choosing the right mode, you can tailor `sourceLens`'s behavior to fit your specific needs, whether it's simple content archiving or sophisticated AI-driven analysis.

