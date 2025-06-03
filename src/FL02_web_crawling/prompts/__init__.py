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

"""Prompts sub-package for the Web Crawling and Analysis Flow (FL02_web_crawling).

This package groups all prompt generation logic and related data structures
specifically tailored for analyzing crawled web content.
"""

# Import prompt generating classes and relevant data structures/constants
# from their respective modules within this sub-package.

from .chapter_prompts import WebChapterPrompts, WriteWebChapterContext
from .concept_prompts import (
    MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS,
    MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS,
    # WEB_CONCEPT_ITEM_SCHEMA, # Schema is defined and used in n02_identify_web_concepts.py
    WebConceptPrompts,
)
from .inventory_prompts import (
    MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT,
    WebInventoryPrompts,
)
from .relationship_prompts import (
    MAX_RELATIONSHIP_LABEL_LEN,
    # WEB_RELATIONSHIPS_DICT_SCHEMA, # Defined in n03_analyze_web_relationships.py
    # WEB_RELATIONSHIP_ITEM_SCHEMA,  # Defined in n03_analyze_web_relationships.py
    WebRelationshipPrompts,
)
from .review_prompts import WEB_REVIEW_SCHEMA, WebReviewPrompts

__all__ = [
    # From concept_prompts.py
    "WebConceptPrompts",
    "MAX_CONTEXT_FILES_FOR_PROMPT_CONCEPTS",
    "MAX_FILE_CONTENT_SNIPPET_LEN_CONCEPTS",
    # From relationship_prompts.py
    "WebRelationshipPrompts",
    "MAX_RELATIONSHIP_LABEL_LEN",
    # From chapter_prompts.py
    "WebChapterPrompts",
    "WriteWebChapterContext",  # Dataclass for chapter writing context
    # From inventory_prompts.py
    "WebInventoryPrompts",
    "MAX_DOCUMENT_SNIPPET_FOR_SUMMARY_PROMPT",
    # From review_prompts.py
    "WebReviewPrompts",
    "WEB_REVIEW_SCHEMA",  # This schema is defined in review_prompts.py
]

# End of src/FL02_web_crawling/prompts/__init__.py
