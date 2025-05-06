# tests/sample_project2/data_handler.py

"""Handles data loading and saving operations for Sample Project 2.

Simulates interaction with a data source (e.g., a file or database).
"""

import logging
from typing import Any

# Import Item model using relative import
from .models import Item

# Use standard logging
logger = logging.getLogger(__name__)

class DataHandler:
    """Manages loading and saving Item data.

    In this simple example, it simulates these operations.
    A real implementation would interact with files, databases, or APIs.
    """

    def __init__(self, data_source_path: str) -> None:
        """Initializes the DataHandler with the path to the data source.

        Args:
            data_source_path: The configured path to the data source (e.g., file path).
        """
        self._data_source = data_source_path
        logger.info("DataHandler initialized for source: %s", self._data_source)

    def load_items(self) -> list[Item]:
        """Simulates loading items from the data source.

        In a real application, this would read from the file/database specified
        by `self._data_source`. Here, it returns a predefined list for demonstration.

        Returns:
            A list of Item objects.
        """
        logger.info("Simulating loading items from %s...", self._data_source)
        # Simulate reading data - replace with actual file reading if needed
        simulated_data = [
            {"item_id": 1, "name": "Gadget Alpha", "value": 150.75},
            {"item_id": 2, "name": "Widget Beta", "value": 85.0},
            {"item_id": 3, "name": "Thingamajig Gamma", "value": 210.5},
            {"item_id": 4, "name": "Doohickey Delta", "value": 55.2},
        ]

        items = []
        for data_dict in simulated_data:
            try:
                # Validate required keys before creating Item
                if all(k in data_dict for k in ("item_id", "name", "value")):
                    item = Item(
                        item_id=int(data_dict["item_id"]),
                        name=str(data_dict["name"]),
                        value=float(data_dict["value"])
                        # 'processed' defaults to False
                    )
                    items.append(item)
                else:
                    logger.warning("Skipping invalid data dictionary during load: %s", data_dict)
            except (ValueError, TypeError) as e:
                logger.warning("Error creating Item object from data %s: %s", data_dict, e)

        logger.info("Loaded %d items.", len(items))
        return items

    def save_items(self, items: list[Item]) -> bool:
        """Simulates saving processed items back to the data source.

        In a real application, this would write the updated item data to the
        file/database specified by `self._data_source`.

        Args:
            items: A list of Item objects (potentially modified) to save.

        Returns:
            True if saving was simulated successfully, False otherwise (always True here).
        """
        logger.info("Simulating saving %d items to %s...", len(items), self._data_source)
        # Simulate writing data - replace with actual file writing if needed
        for item in items:
            # Example: Could convert Item back to dict and write to JSON
            logger.debug("Saving item: %s", item)

        logger.info("Finished simulating save operation.")
        return True # Simulate success

# End of tests/sample_project2/data_handler.py