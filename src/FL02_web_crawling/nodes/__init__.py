# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

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
