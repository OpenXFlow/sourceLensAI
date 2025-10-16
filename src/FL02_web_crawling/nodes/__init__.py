# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Nodes sub-package for the Web Crawling and Analysis Flow (FL02_web_crawling).

This package groups all processing nodes (pipeline steps) specifically designed
for fetching, processing, and analyzing web content.
"""

from .n01_fetch_web_page import FetchWebPage
from .n01b_segment_web_content import SegmentWebContent
from .n01c_youtube_content import FetchYouTubeContent
from .n02_identify_web_concepts import IdentifyWebConcepts
from .n03_analyze_web_relationships import AnalyzeWebRelationships
from .n04_order_web_chapters import OrderWebChapters
from .n05_write_web_chapters import WriteWebChapters
from .n06_generate_web_inventory import GenerateWebInventory
from .n07_generate_web_review import GenerateWebReview

# Inserting the new translation node before CombineWebSummary
from .n07b_translate_youtube_transcript import TranslateYouTubeTranscript
from .n08_combine_web_summary import CombineWebSummary

__all__ = [
    "FetchWebPage",
    "SegmentWebContent",
    "FetchYouTubeContent",
    "IdentifyWebConcepts",
    "AnalyzeWebRelationships",
    "OrderWebChapters",
    "WriteWebChapters",
    "GenerateWebInventory",
    "GenerateWebReview",
    "TranslateYouTubeTranscript",  # Added new node
    "CombineWebSummary",
]

# End of src/FL02_web_crawling/nodes/__init__.py
