"""Data models for Sample Project 2.

Defines the structure of data objects used within the application,
using dataclasses for simplicity and type safety.
"""

from dataclasses import dataclass, field


@dataclass
class Item:
    """Represent a single data item to be processed.

    Attributes:
        item_id (int): A unique integer identifier for the item.
        name (str): The name of the item.
        value (float): A numerical value associated with the item.
        processed (bool): A boolean flag indicating if the item has been
            processed. Defaults to False.

    """

    item_id: int
    name: str
    value: float
    processed: bool = field(default=False)

    def mark_as_processed(self: "Item") -> None:
        """Set the processed flag to True.

        This method updates the item's state to indicate that it has
        undergone processing.

        Returns:
            None: This method does not return any value.

        """
        print(f"Model Item {self.item_id}: Marking '{self.name}' as processed.")
        self.processed = True

    def __str__(self: "Item") -> str:
        """Return a user-friendly string representation of the item.

        Returns:
            str: A string detailing the item's ID, name, value, and
                 processing status.

        """
        status: str = "Processed" if self.processed else "Pending"
        return f"Item(ID={self.item_id}, Name='{self.name}', Value={self.value:.2f}, Status={status})"


# End of tests/sample_project2/models.py
