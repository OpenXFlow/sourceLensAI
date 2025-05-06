# tests/sample_project2/models.py

"""Data models for Sample Project 2.

Defines the structure of data objects used within the application,
using dataclasses for simplicity and type safety.
"""

from dataclasses import dataclass, field

@dataclass
class Item:
    """Represents a single data item to be processed.

    Attributes:
        item_id: A unique integer identifier for the item.
        name: The name of the item (string).
        value: A numerical value associated with the item (float).
        processed: A boolean flag indicating if the item has been processed. Defaults to False.
    """
    item_id: int
    name: str
    value: float
    processed: bool = field(default=False)

    def mark_as_processed(self) -> None:
        """Sets the processed flag to True."""
        print(f"Model Item {self.item_id}: Marking '{self.name}' as processed.")
        self.processed = True

    def __str__(self) -> str:
        """Provides a user-friendly string representation of the item."""
        status = "Processed" if self.processed else "Pending"
        return f"Item(ID={self.item_id}, Name='{self.name}', Value={self.value}, Status={status})"

# End of tests/sample_project2/models.py