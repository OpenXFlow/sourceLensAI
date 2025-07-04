"""Contain the logic for processing Item objects in Sample Project 2."""

import logging

# Import Item model using relative imports
from .models import Item

# Assume we might have utils later, e.g., for complex calculations or logging format
# from . import utils

# Use standard logging
logger: logging.Logger = logging.getLogger(__name__)


class ItemProcessor:
    """Process individual Item objects based on configured rules."""

    _threshold: int

    def __init__(self: "ItemProcessor", threshold: int) -> None:
        """Initialize the ItemProcessor with a processing threshold.

        Args:
            threshold (int): The numerical threshold used in the processing
                logic. Items with a value above this threshold might be
                handled differently.

        """
        self._threshold = threshold
        logger.info("ItemProcessor initialized with threshold: %d", self._threshold)

    def process_item(self: "ItemProcessor", item: Item) -> bool:
        """Process a single item.

        Mark the item as processed and apply logic based on the threshold.
        In this example, it simply logs whether the item's value exceeds
        the threshold.

        Args:
            item (Item): The Item object to process.

        Returns:
            bool: True if processing was successful, False otherwise.

        """
        if not isinstance(item, Item):
            logger.error(
                "Invalid object passed to process_item. Expected Item, got %s.",
                type(item).__name__,
            )
            return False

        logger.debug(
            "Processing item ID: %d, Name: '%s', Value: %.2f",
            item.item_id,
            item.name,
            item.value,
        )

        # Apply some simple logic based on the threshold
        if item.value > self._threshold:
            logger.info(
                "Item '%s' (ID: %d) value %.2f exceeds threshold %d.",
                item.name,
                item.item_id,
                item.value,
                self._threshold,
            )
            # Potential place for different actions based on threshold
        else:
            logger.info(
                "Item '%s' (ID: %d) value %.2f is within threshold %d.",
                item.name,
                item.item_id,
                item.value,
                self._threshold,
            )

        # Mark the item as processed using its own method
        item.mark_as_processed()

        # Simulate successful processing
        return True


# End of tests/sample_project2/item_processor.py
