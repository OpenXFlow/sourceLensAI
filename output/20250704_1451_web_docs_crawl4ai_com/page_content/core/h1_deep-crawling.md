[Crawl4AI Documentation (v0.6.x)](https://docs.crawl4ai.com/)
  * [ Home ](https://docs.crawl4ai.com/)
  * [ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/)
  * [ LLM Context ](https://docs.crawl4ai.com/core/llmtxt/)
  * [ Quick Start ](https://docs.crawl4ai.com/core/quickstart/)
  * [ Code Examples ](https://docs.crawl4ai.com/core/examples/)
  * [ Search ](https://docs.crawl4ai.com/core/deep-crawling/)


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
    * Deep Crawling
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


  * [Deep Crawling](https://docs.crawl4ai.com/core/deep-crawling/#deep-crawling)
  * [1. Quick Example](https://docs.crawl4ai.com/core/deep-crawling/#1-quick-example)
  * [2. Understanding Deep Crawling Strategy Options](https://docs.crawl4ai.com/core/deep-crawling/#2-understanding-deep-crawling-strategy-options)
  * [3. Streaming vs. Non-Streaming Results](https://docs.crawl4ai.com/core/deep-crawling/#3-streaming-vs-non-streaming-results)
  * [4. Filtering Content with Filter Chains](https://docs.crawl4ai.com/core/deep-crawling/#4-filtering-content-with-filter-chains)
  * [5. Using Scorers for Prioritized Crawling](https://docs.crawl4ai.com/core/deep-crawling/#5-using-scorers-for-prioritized-crawling)
  * [6. Advanced Filtering Techniques](https://docs.crawl4ai.com/core/deep-crawling/#6-advanced-filtering-techniques)
  * [7. Building a Complete Advanced Crawler](https://docs.crawl4ai.com/core/deep-crawling/#7-building-a-complete-advanced-crawler)
  * [8. Limiting and Controlling Crawl Size](https://docs.crawl4ai.com/core/deep-crawling/#8-limiting-and-controlling-crawl-size)
  * [9. Common Pitfalls & Tips](https://docs.crawl4ai.com/core/deep-crawling/#9-common-pitfalls-tips)
  * [10. Summary & Next Steps](https://docs.crawl4ai.com/core/deep-crawling/#10-summary-next-steps)


# Deep Crawling
One of Crawl4AI's most powerful features is its ability to perform **configurable deep crawling** that can explore websites beyond a single page. With fine-tuned control over crawl depth, domain boundaries, and content filtering, Crawl4AI gives you the tools to extract precisely the content you need.
In this tutorial, you'll learn:
  1. How to set up a **Basic Deep Crawler** with BFS strategy 
  2. Understanding the difference between **streamed and non-streamed** output 
  3. Implementing **filters and scorers** to target specific content 
  4. Creating **advanced filtering chains** for sophisticated crawls 
  5. Using **BestFirstCrawling** for intelligent exploration prioritization 


> **Prerequisites** - You’ve completed or read [AsyncWebCrawler Basics](https://docs.crawl4ai.com/core/simple-crawling/) to understand how to run a simple crawl. - You know how to configure `CrawlerRunConfig`.
## 1. Quick Example
Here's a minimal code snippet that implements a basic deep crawl using the **BFSDeepCrawlStrategy** :
```
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
async def main():
  # Configure a 2-level deep crawl
  config = CrawlerRunConfig(
    deep_crawl_strategy=BFSDeepCrawlStrategy(
      max_depth=2, 
      include_external=False
    ),
    scraping_strategy=LXMLWebScrapingStrategy(),
    verbose=True
  )
  async with AsyncWebCrawler() as crawler:
    results = await crawler.arun("https://example.com", config=config)
    print(f"Crawled {len(results)} pages in total")
    # Access individual results
    for result in results[:3]: # Show first 3 results
      print(f"URL: {result.url}")
      print(f"Depth: {result.metadata.get('depth', 0)}")
if __name__ == "__main__":
  asyncio.run(main())
Copy
```

**What's happening?** - `BFSDeepCrawlStrategy(max_depth=2, include_external=False)` instructs Crawl4AI to: - Crawl the starting page (depth 0) plus 2 more levels - Stay within the same domain (don't follow external links) - Each result contains metadata like the crawl depth - Results are returned as a list after all crawling is complete
## 2. Understanding Deep Crawling Strategy Options
### 2.1 BFSDeepCrawlStrategy (Breadth-First Search)
The **BFSDeepCrawlStrategy** uses a breadth-first approach, exploring all links at one depth before moving deeper:
```
from crawl4ai.deep_crawling import BFSDeepCrawlStrategy
# Basic configuration
strategy = BFSDeepCrawlStrategy(
  max_depth=2,        # Crawl initial page + 2 levels deep
  include_external=False,  # Stay within the same domain
  max_pages=50,       # Maximum number of pages to crawl (optional)
  score_threshold=0.3,    # Minimum score for URLs to be crawled (optional)
)
Copy
```

**Key parameters:** - **`max_depth`**: Number of levels to crawl beyond the starting page -**`include_external`**: Whether to follow links to other domains -**`max_pages`**: Maximum number of pages to crawl (default: infinite) -**`score_threshold`**: Minimum score for URLs to be crawled (default: -inf) -**`filter_chain`**: FilterChain instance for URL filtering -**`url_scorer`**: Scorer instance for evaluating URLs
### 2.2 DFSDeepCrawlStrategy (Depth-First Search)
The **DFSDeepCrawlStrategy** uses a depth-first approach, explores as far down a branch as possible before backtracking.
```
from crawl4ai.deep_crawling import DFSDeepCrawlStrategy
# Basic configuration
strategy = DFSDeepCrawlStrategy(
  max_depth=2,        # Crawl initial page + 2 levels deep
  include_external=False,  # Stay within the same domain
  max_pages=30,       # Maximum number of pages to crawl (optional)
  score_threshold=0.5,    # Minimum score for URLs to be crawled (optional)
)
Copy
```

**Key parameters:** - **`max_depth`**: Number of levels to crawl beyond the starting page -**`include_external`**: Whether to follow links to other domains -**`max_pages`**: Maximum number of pages to crawl (default: infinite) -**`score_threshold`**: Minimum score for URLs to be crawled (default: -inf) -**`filter_chain`**: FilterChain instance for URL filtering -**`url_scorer`**: Scorer instance for evaluating URLs
### 2.3 BestFirstCrawlingStrategy (⭐️ - Recommended Deep crawl strategy)
For more intelligent crawling, use **BestFirstCrawlingStrategy** with scorers to prioritize the most relevant pages:
```
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
# Create a scorer
scorer = KeywordRelevanceScorer(
  keywords=["crawl", "example", "async", "configuration"],
  weight=0.7
)
# Configure the strategy
strategy = BestFirstCrawlingStrategy(
  max_depth=2,
  include_external=False,
  url_scorer=scorer,
  max_pages=25,       # Maximum number of pages to crawl (optional)
)
Copy
```

This crawling approach: - Evaluates each discovered URL based on scorer criteria - Visits higher-scoring pages first - Helps focus crawl resources on the most relevant content - Can limit total pages crawled with `max_pages` - Does not need `score_threshold` as it naturally prioritizes by score
## 3. Streaming vs. Non-Streaming Results
Crawl4AI can return results in two modes:
### 3.1 Non-Streaming Mode (Default)
```
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1),
  stream=False # Default behavior
)
async with AsyncWebCrawler() as crawler:
  # Wait for ALL results to be collected before returning
  results = await crawler.arun("https://example.com", config=config)
  for result in results:
    process_result(result)
Copy
```

**When to use non-streaming mode:** - You need the complete dataset before processing - You're performing batch operations on all results together - Crawl time isn't a critical factor
### 3.2 Streaming Mode
```
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(max_depth=1),
  stream=True # Enable streaming
)
async with AsyncWebCrawler() as crawler:
  # Returns an async iterator
  async for result in await crawler.arun("https://example.com", config=config):
    # Process each result as it becomes available
    process_result(result)
Copy
```

**Benefits of streaming mode:** - Process results immediately as they're discovered - Start working with early results while crawling continues - Better for real-time applications or progressive display - Reduces memory pressure when handling many pages
## 4. Filtering Content with Filter Chains
Filters help you narrow down which pages to crawl. Combine multiple filters using **FilterChain** for powerful targeting.
### 4.1 Basic URL Pattern Filter
```
from crawl4ai.deep_crawling.filters import FilterChain, URLPatternFilter
# Only follow URLs containing "blog" or "docs"
url_filter = URLPatternFilter(patterns=["*blog*", "*docs*"])
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(
    max_depth=1,
    filter_chain=FilterChain([url_filter])
  )
)
Copy
```

### 4.2 Combining Multiple Filters
```
from crawl4ai.deep_crawling.filters import (
  FilterChain,
  URLPatternFilter,
  DomainFilter,
  ContentTypeFilter
)
# Create a chain of filters
filter_chain = FilterChain([
  # Only follow URLs with specific patterns
  URLPatternFilter(patterns=["*guide*", "*tutorial*"]),
  # Only crawl specific domains
  DomainFilter(
    allowed_domains=["docs.example.com"],
    blocked_domains=["old.docs.example.com"]
  ),
  # Only include specific content types
  ContentTypeFilter(allowed_types=["text/html"])
])
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(
    max_depth=2,
    filter_chain=filter_chain
  )
)
Copy
```

### 4.3 Available Filter Types
Crawl4AI includes several specialized filters:
  * **`URLPatternFilter`**: Matches URL patterns using wildcard syntax
  * **`DomainFilter`**: Controls which domains to include or exclude
  * **`ContentTypeFilter`**: Filters based on HTTP Content-Type
  * **`ContentRelevanceFilter`**: Uses similarity to a text query
  * **`SEOFilter`**: Evaluates SEO elements (meta tags, headers, etc.)


## 5. Using Scorers for Prioritized Crawling
Scorers assign priority values to discovered URLs, helping the crawler focus on the most relevant content first.
### 5.1 KeywordRelevanceScorer
```
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
# Create a keyword relevance scorer
keyword_scorer = KeywordRelevanceScorer(
  keywords=["crawl", "example", "async", "configuration"],
  weight=0.7 # Importance of this scorer (0.0 to 1.0)
)
config = CrawlerRunConfig(
  deep_crawl_strategy=BestFirstCrawlingStrategy(
    max_depth=2,
    url_scorer=keyword_scorer
  ),
  stream=True # Recommended with BestFirstCrawling
)
# Results will come in order of relevance score
async with AsyncWebCrawler() as crawler:
  async for result in await crawler.arun("https://example.com", config=config):
    score = result.metadata.get("score", 0)
    print(f"Score: {score:.2f} | {result.url}")
Copy
```

**How scorers work:** - Evaluate each discovered URL before crawling - Calculate relevance based on various signals - Help the crawler make intelligent choices about traversal order
## 6. Advanced Filtering Techniques
### 6.1 SEO Filter for Quality Assessment
The **SEOFilter** helps you identify pages with strong SEO characteristics:
```
from crawl4ai.deep_crawling.filters import FilterChain, SEOFilter
# Create an SEO filter that looks for specific keywords in page metadata
seo_filter = SEOFilter(
  threshold=0.5, # Minimum score (0.0 to 1.0)
  keywords=["tutorial", "guide", "documentation"]
)
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(
    max_depth=1,
    filter_chain=FilterChain([seo_filter])
  )
)
Copy
```

### 6.2 Content Relevance Filter
The **ContentRelevanceFilter** analyzes the actual content of pages:
```
from crawl4ai.deep_crawling.filters import FilterChain, ContentRelevanceFilter
# Create a content relevance filter
relevance_filter = ContentRelevanceFilter(
  query="Web crawling and data extraction with Python",
  threshold=0.7 # Minimum similarity score (0.0 to 1.0)
)
config = CrawlerRunConfig(
  deep_crawl_strategy=BFSDeepCrawlStrategy(
    max_depth=1,
    filter_chain=FilterChain([relevance_filter])
  )
)
Copy
```

This filter: - Measures semantic similarity between query and page content - It's a BM25-based relevance filter using head section content
## 7. Building a Complete Advanced Crawler
This example combines multiple techniques for a sophisticated crawl:
```
import asyncio
from crawl4ai import AsyncWebCrawler, CrawlerRunConfig
from crawl4ai.content_scraping_strategy import LXMLWebScrapingStrategy
from crawl4ai.deep_crawling import BestFirstCrawlingStrategy
from crawl4ai.deep_crawling.filters import (
  FilterChain,
  DomainFilter,
  URLPatternFilter,
  ContentTypeFilter
)
from crawl4ai.deep_crawling.scorers import KeywordRelevanceScorer
async def run_advanced_crawler():
  # Create a sophisticated filter chain
  filter_chain = FilterChain([
    # Domain boundaries
    DomainFilter(
      allowed_domains=["docs.example.com"],
      blocked_domains=["old.docs.example.com"]
    ),
    # URL patterns to include
    URLPatternFilter(patterns=["*guide*", "*tutorial*", "*blog*"]),
    # Content type filtering
    ContentTypeFilter(allowed_types=["text/html"])
  ])
  # Create a relevance scorer
  keyword_scorer = KeywordRelevanceScorer(
    keywords=["crawl", "example", "async", "configuration"],
    weight=0.7
  )
  # Set up the configuration
  config = CrawlerRunConfig(
    deep_crawl_strategy=BestFirstCrawlingStrategy(
      max_depth=2,
      include_external=False,
      filter_chain=filter_chain,
      url_scorer=keyword_scorer
    ),
    scraping_strategy=LXMLWebScrapingStrategy(),
    stream=True,
    verbose=True
  )
  # Execute the crawl
  results = []
  async with AsyncWebCrawler() as crawler:
    async for result in await crawler.arun("https://docs.example.com", config=config):
      results.append(result)
      score = result.metadata.get("score", 0)
      depth = result.metadata.get("depth", 0)
      print(f"Depth: {depth} | Score: {score:.2f} | {result.url}")
  # Analyze the results
  print(f"Crawled {len(results)} high-value pages")
  print(f"Average score: {sum(r.metadata.get('score', 0) for r in results) / len(results):.2f}")
  # Group by depth
  depth_counts = {}
  for result in results:
    depth = result.metadata.get("depth", 0)
    depth_counts[depth] = depth_counts.get(depth, 0) + 1
  print("Pages crawled by depth:")
  for depth, count in sorted(depth_counts.items()):
    print(f" Depth {depth}: {count} pages")
if __name__ == "__main__":
  asyncio.run(run_advanced_crawler())
Copy
```

## 8. Limiting and Controlling Crawl Size
### 8.1 Using max_pages
You can limit the total number of pages crawled with the `max_pages` parameter:
```
# Limit to exactly 20 pages regardless of depth
strategy = BFSDeepCrawlStrategy(
  max_depth=3,
  max_pages=20
)
Copy
```

This feature is useful for: - Controlling API costs - Setting predictable execution times - Focusing on the most important content - Testing crawl configurations before full execution
### 8.2 Using score_threshold
For BFS and DFS strategies, you can set a minimum score threshold to only crawl high-quality pages:
```
# Only follow links with scores above 0.4
strategy = DFSDeepCrawlStrategy(
  max_depth=2,
  url_scorer=KeywordRelevanceScorer(keywords=["api", "guide", "reference"]),
  score_threshold=0.4 # Skip URLs with scores below this value
)
Copy
```

Note that for BestFirstCrawlingStrategy, score_threshold is not needed since pages are already processed in order of highest score first.
## 9. Common Pitfalls & Tips
1.**Set realistic limits.** Be cautious with `max_depth` values > 3, which can exponentially increase crawl size. Use `max_pages` to set hard limits.
2.**Don't neglect the scoring component.** BestFirstCrawling works best with well-tuned scorers. Experiment with keyword weights for optimal prioritization.
3.**Be a good web citizen.** Respect robots.txt. (disabled by default)
4.**Handle page errors gracefully.** Not all pages will be accessible. Check `result.status` when processing results.
5.**Balance breadth vs. depth.** Choose your strategy wisely - BFS for comprehensive coverage, DFS for deep exploration, BestFirst for focused relevance-based crawling.
## 10. Summary & Next Steps
In this **Deep Crawling with Crawl4AI** tutorial, you learned to:
  * Configure **BFSDeepCrawlStrategy** , **DFSDeepCrawlStrategy** , and **BestFirstCrawlingStrategy**
  * Process results in streaming or non-streaming mode
  * Apply filters to target specific content
  * Use scorers to prioritize the most relevant pages
  * Limit crawls with `max_pages` and `score_threshold` parameters
  * Build a complete advanced crawler with combined techniques


With these tools, you can efficiently extract structured data from websites at scale, focusing precisely on the content you need for your specific use case.
#### On this page
  * [1. Quick Example](https://docs.crawl4ai.com/core/deep-crawling/#1-quick-example)
  * [2. Understanding Deep Crawling Strategy Options](https://docs.crawl4ai.com/core/deep-crawling/#2-understanding-deep-crawling-strategy-options)
  * [2.1 BFSDeepCrawlStrategy (Breadth-First Search)](https://docs.crawl4ai.com/core/deep-crawling/#21-bfsdeepcrawlstrategy-breadth-first-search)
  * [2.2 DFSDeepCrawlStrategy (Depth-First Search)](https://docs.crawl4ai.com/core/deep-crawling/#22-dfsdeepcrawlstrategy-depth-first-search)
  * [2.3 BestFirstCrawlingStrategy (⭐️ - Recommended Deep crawl strategy)](https://docs.crawl4ai.com/core/deep-crawling/#23-bestfirstcrawlingstrategy-recommended-deep-crawl-strategy)
  * [3. Streaming vs. Non-Streaming Results](https://docs.crawl4ai.com/core/deep-crawling/#3-streaming-vs-non-streaming-results)
  * [3.1 Non-Streaming Mode (Default)](https://docs.crawl4ai.com/core/deep-crawling/#31-non-streaming-mode-default)
  * [3.2 Streaming Mode](https://docs.crawl4ai.com/core/deep-crawling/#32-streaming-mode)
  * [4. Filtering Content with Filter Chains](https://docs.crawl4ai.com/core/deep-crawling/#4-filtering-content-with-filter-chains)
  * [4.1 Basic URL Pattern Filter](https://docs.crawl4ai.com/core/deep-crawling/#41-basic-url-pattern-filter)
  * [4.2 Combining Multiple Filters](https://docs.crawl4ai.com/core/deep-crawling/#42-combining-multiple-filters)
  * [4.3 Available Filter Types](https://docs.crawl4ai.com/core/deep-crawling/#43-available-filter-types)
  * [5. Using Scorers for Prioritized Crawling](https://docs.crawl4ai.com/core/deep-crawling/#5-using-scorers-for-prioritized-crawling)
  * [5.1 KeywordRelevanceScorer](https://docs.crawl4ai.com/core/deep-crawling/#51-keywordrelevancescorer)
  * [6. Advanced Filtering Techniques](https://docs.crawl4ai.com/core/deep-crawling/#6-advanced-filtering-techniques)
  * [6.1 SEO Filter for Quality Assessment](https://docs.crawl4ai.com/core/deep-crawling/#61-seo-filter-for-quality-assessment)
  * [6.2 Content Relevance Filter](https://docs.crawl4ai.com/core/deep-crawling/#62-content-relevance-filter)
  * [7. Building a Complete Advanced Crawler](https://docs.crawl4ai.com/core/deep-crawling/#7-building-a-complete-advanced-crawler)
  * [8. Limiting and Controlling Crawl Size](https://docs.crawl4ai.com/core/deep-crawling/#8-limiting-and-controlling-crawl-size)
  * [8.1 Using max_pages](https://docs.crawl4ai.com/core/deep-crawling/#81-using-max_pages)
  * [8.2 Using score_threshold](https://docs.crawl4ai.com/core/deep-crawling/#82-using-score_threshold)
  * [9. Common Pitfalls & Tips](https://docs.crawl4ai.com/core/deep-crawling/#9-common-pitfalls-tips)
  * [10. Summary & Next Steps](https://docs.crawl4ai.com/core/deep-crawling/#10-summary-next-steps)


> Feedback 
##### Search
xClose
Type to start searching
[ Ask AI ](https://docs.crawl4ai.com/core/ask-ai/ "Ask Crawl4AI Assistant")
