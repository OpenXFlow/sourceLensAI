# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""FL02_web_crawling: SourceLens Flow for Web Content Crawling and Analysis.

This package encapsulates all logic, nodes, and prompts necessary for
fetching content from web sources (URLs, sitemaps, files), processing it,
and generating summaries or analyses based on the crawled textual data.

It can be run independently or orchestrated by the main SourceLens application.
"""

# Import the main flow creation function from the .flow module within this package.
from .flow import create_web_crawling_flow

__all__ = [
    "create_web_crawling_flow",
]

# End of src/FL02_web_crawling/__init__.py
