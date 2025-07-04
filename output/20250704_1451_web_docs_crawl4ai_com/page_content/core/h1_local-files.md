[Crawl4AI Documentation (v0.6.x)](https://docs.crawl4ai.com/)
  * [ Home ](https://docs.crawl4ai.com/)
  * [ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/)
  * [ LLM Context ](https://docs.crawl4ai.com/core/llmtxt/)
  * [ Quick Start ](https://docs.crawl4ai.com/core/quickstart/)
  * [ Code Examples ](https://docs.crawl4ai.com/core/examples/)
  * [ Search ](https://docs.crawl4ai.com/core/local-files/)


[ unclecode/crawl4ai 47.1k 4.5k ](https://github.com/unclecode/crawl4ai)
×
  * [Home](https://docs.crawl4ai.com/)
  * [Ask AI](https://docs.crawl4ai.com/core/ask-ai/)
  * [LLM Context](https://docs.crawl4ai.com/core/llmtxt/)
  * [Quick Start](https://docs.crawl4ai.com/core/quickstart/)
  * [Code Examples](https://docs.crawl4ai.com/core/examples/)
  * Setup & Installation
    * [Installation](https://docs.crawl4ai.com/core/installation/)
    * [Docker Deployment](https://docs.crawl4ai.com/core/docker-deployment/)
  * Blog & Changelog
    * [Blog Home](https://docs.crawl4ai.com/blog/)
    * [Changelog](https://github.com/unclecode/crawl4ai/blob/main/CHANGELOG.md)
  * Core
    * [Command Line Interface](https://docs.crawl4ai.com/core/cli/)
    * [Simple Crawling](https://docs.crawl4ai.com/core/simple-crawling/)
    * [Deep Crawling](https://docs.crawl4ai.com/core/deep-crawling/)
    * [Crawler Result](https://docs.crawl4ai.com/core/crawler-result/)
    * [Browser, Crawler & LLM Config](https://docs.crawl4ai.com/core/browser-crawler-config/)
    * [Markdown Generation](https://docs.crawl4ai.com/core/markdown-generation/)
    * [Fit Markdown](https://docs.crawl4ai.com/core/fit-markdown/)
    * [Page Interaction](https://docs.crawl4ai.com/core/page-interaction/)
    * [Content Selection](https://docs.crawl4ai.com/core/content-selection/)
    * [Cache Modes](https://docs.crawl4ai.com/core/cache-modes/)
    * Local Files & Raw HTML
    * [Link & Media](https://docs.crawl4ai.com/core/link-media/)
  * Advanced
    * [Overview](https://docs.crawl4ai.com/advanced/advanced-features/)
    * [File Downloading](https://docs.crawl4ai.com/advanced/file-downloading/)
    * [Lazy Loading](https://docs.crawl4ai.com/advanced/lazy-loading/)
    * [Hooks & Auth](https://docs.crawl4ai.com/advanced/hooks-auth/)
    * [Proxy & Security](https://docs.crawl4ai.com/advanced/proxy-security/)
    * [Session Management](https://docs.crawl4ai.com/advanced/session-management/)
    * [Multi-URL Crawling](https://docs.crawl4ai.com/advanced/multi-url-crawling/)
    * [Crawl Dispatcher](https://docs.crawl4ai.com/advanced/crawl-dispatcher/)
    * [Identity Based Crawling](https://docs.crawl4ai.com/advanced/identity-based-crawling/)
    * [SSL Certificate](https://docs.crawl4ai.com/advanced/ssl-certificate/)
    * [Network & Console Capture](https://docs.crawl4ai.com/advanced/network-console-capture/)
  * Extraction
    * [LLM-Free Strategies](https://docs.crawl4ai.com/extraction/no-llm-strategies/)
    * [LLM Strategies](https://docs.crawl4ai.com/extraction/llm-strategies/)
    * [Clustering Strategies](https://docs.crawl4ai.com/extraction/clustring-strategies/)
    * [Chunking](https://docs.crawl4ai.com/extraction/chunking/)
  * API Reference
    * [AsyncWebCrawler](https://docs.crawl4ai.com/api/async-webcrawler/)
    * [arun()](https://docs.crawl4ai.com/api/arun/)
    * [arun_many()](https://docs.crawl4ai.com/api/arun_many/)
    * [Browser, Crawler & LLM Config](https://docs.crawl4ai.com/api/parameters/)
    * [CrawlResult](https://docs.crawl4ai.com/api/crawl-result/)
    * [Strategies](https://docs.crawl4ai.com/api/strategies/)


  * [Prefix-Based Input Handling in Crawl4AI](https://docs.crawl4ai.com/core/local-files/#prefix-based-input-handling-in-crawl4ai)
  * [Crawling a Web URL](https://docs.crawl4ai.com/core/local-files/#crawling-a-web-url)
  * [Crawling a Local HTML File](https://docs.crawl4ai.com/core/local-files/#crawling-a-local-html-file)
  * [Crawling Raw HTML Content](https://docs.crawl4ai.com/core/local-files/#crawling-raw-html-content)
  * [Complete Example](https://docs.crawl4ai.com/core/local-files/#complete-example)
  * [Conclusion](https://docs.crawl4ai.com/core/local-files/#conclusion)


# Prefix-Based Input Handling in Crawl4AI
This guide will walk you through using the Crawl4AI library to crawl web pages, local HTML files, and raw HTML strings. We'll demonstrate these capabilities using a Wikipedia page as an example.
## Crawling a Web URL
To crawl a live web page, provide the URL starting with `http://` or `https://`, using a `CrawlerRunConfig` object:
```
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig
async def crawl_web():
  config = CrawlerRunConfig(bypass_cache=True)
  async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(
      url="https://en.wikipedia.org/wiki/apple", 
      config=config
    )
    if result.success:
      print("Markdown Content:")
      print(result.markdown)
    else:
      print(f"Failed to crawl: {result.error_message}")
asyncio.run(crawl_web())
Copy
```

## Crawling a Local HTML File
To crawl a local HTML file, prefix the file path with `file://`.
```
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig
async def crawl_local_file():
  local_file_path = "/path/to/apple.html" # Replace with your file path
  file_url = f"file://{local_file_path}"
  config = CrawlerRunConfig(bypass_cache=True)
  async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=file_url, config=config)
    if result.success:
      print("Markdown Content from Local File:")
      print(result.markdown)
    else:
      print(f"Failed to crawl local file: {result.error_message}")
asyncio.run(crawl_local_file())
Copy
```

## Crawling Raw HTML Content
To crawl raw HTML content, prefix the HTML string with `raw:`.
```
import asyncio
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig
async def crawl_raw_html():
  raw_html = "<html><body><h1>Hello, World!</h1></body></html>"
  raw_html_url = f"raw:{raw_html}"
  config = CrawlerRunConfig(bypass_cache=True)
  async with AsyncWebCrawler() as crawler:
    result = await crawler.arun(url=raw_html_url, config=config)
    if result.success:
      print("Markdown Content from Raw HTML:")
      print(result.markdown)
    else:
      print(f"Failed to crawl raw HTML: {result.error_message}")
asyncio.run(crawl_raw_html())
Copy
```

# Complete Example
Below is a comprehensive script that:
  1. Crawls the Wikipedia page for "Apple."
  2. Saves the HTML content to a local file (`apple.html`).
  3. Crawls the local HTML file and verifies the markdown length matches the original crawl.
  4. Crawls the raw HTML content from the saved file and verifies consistency.


```
import os
import sys
import asyncio
from pathlib import Path
from crawl4ai import AsyncWebCrawler
from crawl4ai.async_configs import CrawlerRunConfig
async def main():
  wikipedia_url = "https://en.wikipedia.org/wiki/apple"
  script_dir = Path(__file__).parent
  html_file_path = script_dir / "apple.html"
  async with AsyncWebCrawler() as crawler:
    # Step 1: Crawl the Web URL
    print("\n=== Step 1: Crawling the Wikipedia URL ===")
    web_config = CrawlerRunConfig(bypass_cache=True)
    result = await crawler.arun(url=wikipedia_url, config=web_config)
    if not result.success:
      print(f"Failed to crawl {wikipedia_url}: {result.error_message}")
      return
    with open(html_file_path, 'w', encoding='utf-8') as f:
      f.write(result.html)
    web_crawl_length = len(result.markdown)
    print(f"Length of markdown from web crawl: {web_crawl_length}\n")
    # Step 2: Crawl from the Local HTML File
    print("=== Step 2: Crawling from the Local HTML File ===")
    file_url = f"file://{html_file_path.resolve()}"
    file_config = CrawlerRunConfig(bypass_cache=True)
    local_result = await crawler.arun(url=file_url, config=file_config)
    if not local_result.success:
      print(f"Failed to crawl local file {file_url}: {local_result.error_message}")
      return
    local_crawl_length = len(local_result.markdown)
    assert web_crawl_length == local_crawl_length, "Markdown length mismatch"
    print("✅ Markdown length matches between web and local file crawl.\n")
    # Step 3: Crawl Using Raw HTML Content
    print("=== Step 3: Crawling Using Raw HTML Content ===")
    with open(html_file_path, 'r', encoding='utf-8') as f:
      raw_html_content = f.read()
    raw_html_url = f"raw:{raw_html_content}"
    raw_config = CrawlerRunConfig(bypass_cache=True)
    raw_result = await crawler.arun(url=raw_html_url, config=raw_config)
    if not raw_result.success:
      print(f"Failed to crawl raw HTML content: {raw_result.error_message}")
      return
    raw_crawl_length = len(raw_result.markdown)
    assert web_crawl_length == raw_crawl_length, "Markdown length mismatch"
    print("✅ Markdown length matches between web and raw HTML crawl.\n")
    print("All tests passed successfully!")
  if html_file_path.exists():
    os.remove(html_file_path)
if __name__ == "__main__":
  asyncio.run(main())
Copy
```

# Conclusion
With the unified `url` parameter and prefix-based handling in **Crawl4AI** , you can seamlessly handle web URLs, local HTML files, and raw HTML content. Use `CrawlerRunConfig` for flexible and consistent configuration in all scenarios.
#### On this page
  * [Crawling a Web URL](https://docs.crawl4ai.com/core/local-files/#crawling-a-web-url)
  * [Crawling a Local HTML File](https://docs.crawl4ai.com/core/local-files/#crawling-a-local-html-file)
  * [Crawling Raw HTML Content](https://docs.crawl4ai.com/core/local-files/#crawling-raw-html-content)


> Feedback 
##### Search
xClose
Type to start searching
[ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/ "Ask Crawl4AI Assistant")
