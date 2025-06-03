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

# Import all node classes from their respective modules within this sub-package.
# These nodes constitute the building blocks of the web content analysis pipeline.

from .n01_fetch_web_page import FetchWebPage
from .n01b_segment_web_content import SegmentWebContent  # Pridaný nový node
from .n02_identify_web_concepts import IdentifyWebConcepts
from .n03_analyze_web_relationships import AnalyzeWebRelationships
from .n04_order_web_chapters import OrderWebChapters
from .n05_write_web_chapters import WriteWebChapters
from .n06_generate_web_inventory import GenerateWebInventory
from .n07_generate_web_review import GenerateWebReview
from .n08_combine_web_summary import CombineWebSummary

# Placeholder for future web content analysis nodes, e.g.:
# from .nXX_generate_web_diagrams import GenerateWebDiagrams

__all__ = [
    "FetchWebPage",
    "SegmentWebContent",  # Pridaný nový node do __all__
    "IdentifyWebConcepts",
    "AnalyzeWebRelationships",
    "OrderWebChapters",
    "WriteWebChapters",
    "GenerateWebInventory",
    "GenerateWebReview",
    "CombineWebSummary",
    # Add future web node classes here as they are created
]

# End of src/FL02_web_crawling/nodes/__init__.py
