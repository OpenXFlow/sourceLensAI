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

"""Initialize the web prompts sub-package.

This package groups all prompt generation logic specifically tailored for
analyzing web content. It makes specialized prompt formatters
available for use by web content processing nodes.
"""

from .chapter_prompts import WebChapterPrompts, WriteWebChapterContext
from .concept_prompts import WebConceptPrompts
from .inventory_prompts import WebInventoryPrompts
from .relationship_prompts import WebRelationshipPrompts
from .review_prompts import WEB_REVIEW_SCHEMA, WebReviewPrompts  # Added WEB_REVIEW_SCHEMA

# Placeholder for future web prompt modules:
# from .diagram_prompts import WebDiagramPrompts

__all__: list[str] = [
    "WebConceptPrompts",
    "WebRelationshipPrompts",
    "WebChapterPrompts",  # Assuming this class will contain both order and write prompts
    "WriteWebChapterContext",  # Exporting the context dataclass
    "WebInventoryPrompts",
    "WebReviewPrompts",
    "WEB_REVIEW_SCHEMA",  # Exporting the schema
    # Add future WebXxxPrompts classes and relevant constants/schemas here
]

# End of src/sourcelens/prompts/web/__init__.py
