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

"""Initialize the web content processing nodes sub-package.

This package groups all processing nodes specifically designed for
fetching and analyzing web content.
"""

from .n01_fetch_web_page import FetchWebPage
from .n02_identify_web_concepts import IdentifyWebConcepts
from .n03_analyze_web_relationships import AnalyzeWebRelationships
from .n04_order_web_chapters import OrderWebChapters
from .n05_write_web_chapters import WriteWebChapters
from .n06_generate_web_inventory import GenerateWebInventory
from .n07_generate_web_review import GenerateWebReview
from .n08_combine_web_summary import CombineWebSummary

# Placeholder for future web content analysis nodes:
# from .nXX_generate_web_diagrams import GenerateWebDiagrams # e.g., concept map


__all__: list[str] = [
    "FetchWebPage",  # n01
    "IdentifyWebConcepts",  # n02
    "AnalyzeWebRelationships",  # n03
    "OrderWebChapters",  # n04
    "WriteWebChapters",  # n05
    "GenerateWebInventory",  # n06
    "GenerateWebReview",  # n07
    "CombineWebSummary",  # n08
    # Add future web node classes here as they are created
]

# End of src/sourcelens/nodes/web/__init__.py
