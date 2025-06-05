[Crawl4AI Documentation (v0.6.x)](https://docs.crawl4ai.com/)
  * [ Home ](https://docs.crawl4ai.com/)
  * [ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/)
  * [ LLM Context ](https://docs.crawl4ai.com/core/llmtxt/)
  * [ Quick Start ](https://docs.crawl4ai.com/core/quickstart/)
  * [ Code Examples ](https://docs.crawl4ai.com/core/examples/)
  * [ Search ](https://docs.crawl4ai.com/advanced/proxy-security/)


[ unclecode/crawl4ai 45.0k 4.2k ](https://github.com/unclecode/crawl4ai)
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
    * [Local Files & Raw HTML](https://docs.crawl4ai.com/core/local-files/)
    * [Link & Media](https://docs.crawl4ai.com/core/link-media/)
  * Advanced
    * [Overview](https://docs.crawl4ai.com/advanced/advanced-features/)
    * [File Downloading](https://docs.crawl4ai.com/advanced/file-downloading/)
    * [Lazy Loading](https://docs.crawl4ai.com/advanced/lazy-loading/)
    * [Hooks & Auth](https://docs.crawl4ai.com/advanced/hooks-auth/)
    * Proxy & Security
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


  * [Proxy](https://docs.crawl4ai.com/advanced/proxy-security/#proxy)
  * [Basic Proxy Setup](https://docs.crawl4ai.com/advanced/proxy-security/#basic-proxy-setup)
  * [Authenticated Proxy](https://docs.crawl4ai.com/advanced/proxy-security/#authenticated-proxy)
  * [Rotating Proxies](https://docs.crawl4ai.com/advanced/proxy-security/#rotating-proxies)


# Proxy
## Basic Proxy Setup
Simple proxy configuration with `BrowserConfig`:
```
from crawl4ai.async_configs import BrowserConfig
# Using proxy URL
browser_config = BrowserConfig(proxy="http://proxy.example.com:8080")
async with AsyncWebCrawler(config=browser_config) as crawler:
  result = await crawler.arun(url="https://example.com")
# Using SOCKS proxy
browser_config = BrowserConfig(proxy="socks5://proxy.example.com:1080")
async with AsyncWebCrawler(config=browser_config) as crawler:
  result = await crawler.arun(url="https://example.com")
Copy
```

## Authenticated Proxy
Use an authenticated proxy with `BrowserConfig`:
```
from crawl4ai.async_configs import BrowserConfig
proxy_config = {
  "server": "http://proxy.example.com:8080",
  "username": "user",
  "password": "pass"
}
browser_config = BrowserConfig(proxy_config=proxy_config)
async with AsyncWebCrawler(config=browser_config) as crawler:
  result = await crawler.arun(url="https://example.com")
Copy
```

Here's the corrected documentation:
## Rotating Proxies
Example using a proxy rotation service dynamically:
```
from crawl4ai import AsyncWebCrawler, BrowserConfig, CrawlerRunConfig
async def get_next_proxy():
  # Your proxy rotation logic here
  return {"server": "http://next.proxy.com:8080"}
async def main():
  browser_config = BrowserConfig()
  run_config = CrawlerRunConfig()
  async with AsyncWebCrawler(config=browser_config) as crawler:
    # For each URL, create a new run config with different proxy
    for url in urls:
      proxy = await get_next_proxy()
      # Clone the config and update proxy - this creates a new browser context
      current_config = run_config.clone(proxy_config=proxy)
      result = await crawler.arun(url=url, config=current_config)
if __name__ == "__main__":
  import asyncio
  asyncio.run(main())
Copy
```

#### On this page
  * [Basic Proxy Setup](https://docs.crawl4ai.com/advanced/proxy-security/#basic-proxy-setup)
  * [Authenticated Proxy](https://docs.crawl4ai.com/advanced/proxy-security/#authenticated-proxy)
  * [Rotating Proxies](https://docs.crawl4ai.com/advanced/proxy-security/#rotating-proxies)


> Feedback 
##### Search
xClose
Type to start searching
[ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/ "Ask Crawl4AI Assistant")
