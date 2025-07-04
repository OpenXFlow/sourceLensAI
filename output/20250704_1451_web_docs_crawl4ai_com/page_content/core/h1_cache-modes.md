[Crawl4AI Documentation (v0.6.x)](https://docs.crawl4ai.com/)
  * [ Home ](https://docs.crawl4ai.com/)
  * [ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/)
  * [ LLM Context ](https://docs.crawl4ai.com/core/llmtxt/)
  * [ Quick Start ](https://docs.crawl4ai.com/core/quickstart/)
  * [ Code Examples ](https://docs.crawl4ai.com/core/examples/)
  * [ Search ](https://docs.crawl4ai.com/core/cache-modes/)


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
    * Cache Modes
    * [Local Files & Raw HTML](https://docs.crawl4ai.com/core/local-files/)
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


  * [Crawl4AI Cache System and Migration Guide](https://docs.crawl4ai.com/core/cache-modes/#crawl4ai-cache-system-and-migration-guide)
  * [Overview](https://docs.crawl4ai.com/core/cache-modes/#overview)
  * [Old vs New Approach](https://docs.crawl4ai.com/core/cache-modes/#old-vs-new-approach)
  * [Migration Example](https://docs.crawl4ai.com/core/cache-modes/#migration-example)
  * [Common Migration Patterns](https://docs.crawl4ai.com/core/cache-modes/#common-migration-patterns)


# Crawl4AI Cache System and Migration Guide
## Overview
Starting from version 0.5.0, Crawl4AI introduces a new caching system that replaces the old boolean flags with a more intuitive `CacheMode` enum. This change simplifies cache control and makes the behavior more predictable.
## Old vs New Approach
### Old Way (Deprecated)
The old system used multiple boolean flags: - `bypass_cache`: Skip cache entirely - `disable_cache`: Disable all caching - `no_cache_read`: Don't read from cache - `no_cache_write`: Don't write to cache
### New Way (Recommended)
The new system uses a single `CacheMode` enum: - `CacheMode.ENABLED`: Normal caching (read/write) - `CacheMode.DISABLED`: No caching at all - `CacheMode.READ_ONLY`: Only read from cache - `CacheMode.WRITE_ONLY`: Only write to cache - `CacheMode.BYPASS`: Skip cache for this operation
## Migration Example
### Old Code (Deprecated)
```
import asyncio
from crawl4ai import AsyncWebCrawler
async def use_proxy():
  async with AsyncWebCrawler(verbose=True) as crawler:
    result = await crawler.arun(
      url="https://www.nbcnews.com/business",
      bypass_cache=True # Old way
    )
    print(len(result.markdown))
async def main():
  await use_proxy()
if __name__ == "__main__":
  asyncio.run(main())
Copy
```

### New Code (Recommended)
```
import asyncio
from crawl4ai import AsyncWebCrawler, CacheMode
from crawl4ai.async_configs import CrawlerRunConfig
async def use_proxy():
  # Use CacheMode in CrawlerRunConfig
  config = CrawlerRunConfig(cache_mode=CacheMode.BYPASS) 
  async with AsyncWebCrawler(verbose=True) as crawler:
    result = await crawler.arun(
      url="https://www.nbcnews.com/business",
      config=config # Pass the configuration object
    )
    print(len(result.markdown))
async def main():
  await use_proxy()
if __name__ == "__main__":
  asyncio.run(main())
Copy
```

## Common Migration Patterns
Old Flag | New Mode  
---|---  
`bypass_cache=True` | `cache_mode=CacheMode.BYPASS`  
`disable_cache=True` | `cache_mode=CacheMode.DISABLED`  
`no_cache_read=True` | `cache_mode=CacheMode.WRITE_ONLY`  
`no_cache_write=True` | `cache_mode=CacheMode.READ_ONLY`  
#### On this page
  * [Overview](https://docs.crawl4ai.com/core/cache-modes/#overview)
  * [Old vs New Approach](https://docs.crawl4ai.com/core/cache-modes/#old-vs-new-approach)
  * [Old Way (Deprecated)](https://docs.crawl4ai.com/core/cache-modes/#old-way-deprecated)
  * [New Way (Recommended)](https://docs.crawl4ai.com/core/cache-modes/#new-way-recommended)
  * [Migration Example](https://docs.crawl4ai.com/core/cache-modes/#migration-example)
  * [Old Code (Deprecated)](https://docs.crawl4ai.com/core/cache-modes/#old-code-deprecated)
  * [New Code (Recommended)](https://docs.crawl4ai.com/core/cache-modes/#new-code-recommended)
  * [Common Migration Patterns](https://docs.crawl4ai.com/core/cache-modes/#common-migration-patterns)


> Feedback 
##### Search
xClose
Type to start searching
[ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/ "Ask Crawl4AI Assistant")
