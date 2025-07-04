# SourceLens: Web Content Analysis Flow Usage (`web` / `web_crawling`)

This document details the command-line options and usage examples specific to the **Web Content Analysis Flow** in `sourceLens`. This flow is designed to crawl, process, and analyze content from web URLs, sitemaps, or local files (including YouTube video transcripts) to generate summaries, identify concepts, and provide insights.

For general CLI options applicable to all flows, refer to [General CLI Usage](./USAGE_CLI_GENERAL.md).

## Command Syntax

To initiate a web content analysis, use the `web` subcommand (or its alias `web_crawling`):

```bash
sourcelens [GLOBAL_OPTIONS] web (--crawl-url URL | --crawl-sitemap URL | --crawl-file PATH_OR_URL) [WEB_SPECIFIC_OPTIONS]
```
or
```bash
sourcelens [GLOBAL_OPTIONS] web_crawling (--crawl-url URL | --crawl-sitemap URL | --crawl-file PATH_OR_URL) [WEB_SPECIFIC_OPTIONS]
```

## Source Options (Required - Choose One)

You must specify one of the following options to provide the web content source:

*   **`--crawl-url WEB_URL`**
    *   Specifies the root URL of a website to start crawling from, or a direct URL to a single web page (including YouTube video URLs).
    *   Example (Rozumiem. Teraz vygenerujem obsah pre súbor **`USAGE_CLI_WEB_FLOW.md`**.

```markdown
# SourceLens: Web Content Analysis Flow Usage (`web` / `web_crawling`)

This document provides detailed command-line options and usage examples specific to the **Web Content Analysis Flow** in `sourceLens`. Thiswebsite): `https://docs.example.com/`
    *   Example (YouTube): `https://www.youtube.com/watch?v=VIDEO_ID`

*   **`--crawl-sitemap SITEMAP_URL`**
    *   Specifies the URL of a `sitemap.xml` file. `sourceLens` will fetch and process all URLs listed in the sitemap.
    *   Example: `https://www.example.com/sitemap.xml`

*   **`--crawl-file FILE_URL_OR_PATH`**
    *   Specifies a URL pointing to a single raw text, HTML, or Markdown file, or a path to a local text, HTML, or Markdown file.
    *   Example (remote): `https://raw.githubusercontent.com/user/repo/main/README.md`
    *   Example (local): `./my_documents/article.md`

## Web-Specific Options

These options allow you to fine-tune the web content analysis process and override settings defined in your `config.json` for the `FL02_web_crawling` flow.

*   **`-h, --help`**
    *   Shows the help message specific to the `web` flow is designed to crawl, process, and analyze content from web URLs, sitemaps, local files (including YouTube video transcripts), and generate summaries or insights.

For general CLI options applicable to all flows, refer to [General CLI Usage](./USAGE_CLI_GENERAL.md).

## Command Syntax

To initiate a web content analysis, use the `web` subcommand (or its alias `web_crawling`):

```bash
sourcelens [GLOBAL_OPTIONS] web (--crawl-url URL | --crawl-sitemap URL | --crawl-file PATH_OR_URL) [WEB_SPECIFIC_OPTIONS]
```
or
```bash
sourcelens [GLOBAL_OPTIONS] web_craw subcommand and exits.

*   **`--crawl-depth N`**
    *   Overrides the `max_depth_recursive` setting from `crawler_options` in your `config.json`.
    *   Sets the maximum recursion depth when crawling a website specified with `--crawl-url`.
    *   A depth of `0` means only the initial URL will be fetched. A depth of `1` means the initial URL and pages directly linked from it will be fetched, and so on.
    *   This option is ignored if `--crawl-sitemap` or `--crawl-file` is used.
    *   Example: `sourcelens web --crawl-url https://example.com --crawl-depth 2`

*   **`--processing-mode {minimalistic|llm_extended}`**
    *   Overrides the `processing_mode` setting from `crawler_options` in your `config.json`.
    *   `minimalistic`: Fetches and converts content to Markdown. For YouTube URLs, it extracts the transcript, performs basic cleaning and LLM-based deduplication, and saves it. Further LLM analysis (concept identification, chapter generation, review) is skipped.
    *   `llm_extended`: Performs full processing, including fetching, segmentation (for non-YouTube web content), LLM-based concept identification, relationship analysis, chapter generation, and content review generation. For YouTube, this mode processes the video description and the final (translated/reformatted) transcript for LLM analysis.
    *   Default is usually `minimalistic` if not set in config or overridden.
    *   Example: `sourcelens web --crawl-url https://example.com --processing-mode llm_extended`

*   **`--extract-audio`** (Hidden argument, primarily for YouTube via direct `FL02_web_crawling/cli.py` call)
    *   When processing YouTube URLs, this flag (if recognized by the specific CLI entry point) enables the download of the audio track as an MP3 file.
    *   Note: The main `sourcelens` command might not expose this directly unless explicitly added to its web subparser. Its primary use is via the standalone `src/FL02_web_crawling/cli.py`.
    *   Example (using standalone CLI):
        `python -m src.FL02_web_crawling.cli --crawl-url "ling (--crawl-url URL | --crawl-sitemap URL | --crawl-file PATH_OR_URL) [WEB_SPECIFIC_OPTIONS]
```

## Source Options (Required - Choose One)

You must specify one of the following options to provide the web content source:

*   **`--crawl-url WEB_URL`**
    *   Specifies the root URL of a website to crawl.
    *   If `crawl_depth` is greater than 0, `sourceLens` will attempt to follow links from this page.
    *   Can also be a direct URL to a YouTube video (e.g., `https://www.youtube.com/watch?v=VIDEO_ID`).
    *   Example (website): `sourcelens web --crawl-url https://example.com/documentation/`
    *   Example (YouTube): `sourcelens web --crawl-url https://www.youtube.com/watch?v=dQw4w9WgXcQ`

*   **`--crawl-sitemap SITEMAP_URL`**
    *   Specifies the URL of a `sitemap.xml` file.
    *   `sourceLens` will fetch and process all URLs listed in the sitemap. Deep crawling from sitemap URLs is typically not performed by default (equivalent to depth 0 for each sitemap entry).
    *   Example: `sourcelens web --crawl-sitemap https://www.markdownguide.org/sitemap.xml`

*   **`--crawl-file FILE_URL_OR_PATH`**
    *   Specifies a URL to a single remote file (e.g., raw text, HTML, Markdown on GitHub) or a path to a local file.
    *   The content of this single file will be processed.
    *   Example (remote file): `sourcelens web --crawl-file https://raw.githubusercontent.com/user/repo/main/INFO.md`
    *   Example (local file): `sourcelens web --crawl-file ./my_notes/article.txt`

## Web-Specific Options

These options allow you to customize the web crawling and analysis process, overriding settings from your `config.json` for the `FL02_web_crawling` flow.

*   **YOUTUBE_URL" --extract-audio`

## Examples

1.  **Crawl a documentation website up to depth 1 and generate a full LLM-based summary:**
    ```bash
    sourcelens web --crawl-url https://some-docs.com/ --crawl-depth 1 --processing-mode llm_extended
    ```

2.  **Process a YouTube video: extract transcript, translate/reformat it, and then perform full LLM analysis on description and final transcript (Slovak output):**
    ```bash
    sourcelens --language slovak web --crawl-url "https://www.youtube.com/watch?v=VIDEO_ID" --processing-mode llm_extended
    ```

3.  **Process a YouTube video in minimalistic mode (get cleaned original transcript only):**
    ```bash
    sourcelens web --crawl-url "https://www.youtube.com/watch?v=ANOTHER_VIDEO_ID" --processing-mode minimalistic
    ```

4.  **Analyze all URLs from a sitemap using full LLM processing:**
    ```bash
    sourcelens web --crawl-sitemap https://example.com/sitemap.xml --processing-mode llm_extended
    ```

5.  **Analyze a single local article (Markdown file) with LLM-extended processing:**
    ```bash
    sourcelens --name "MyArticleAnalysis" web --crawl-file ./articles/my_research.md --processing-mode llm_extended
    ```

6.  **Fetch a remote HTML page and get only its Markdown content (minimalistic):**
    ```bash
    sourcelens web --crawl-file https://example.com/some/page.html --processing-mode minimalistic
    ```

---

Generated summaries, inventories, and reviews will be placed in a subdirectory within your main output directory (e.g., `output/YYYYMMDD_HHMM_web-sitename/` or `output/YYYYMMDD_HHMM_yt-videotitle/`).
