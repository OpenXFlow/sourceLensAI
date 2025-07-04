<?php

// tests/sample_project2/Item.php

namespace SampleProject2;

/**
 * Represents a single data item to be processed.
 */
class Item
{
    /**
     * @param int $itemId A unique integer identifier for the item.
     * @param string $name The name of the item.
     * @param float $value A numerical value associated with the item.
     * @param bool $processed A flag indicating if the item has been processed.
     */
    public function __construct(
        public int $itemId,
        public string $name,
        public float $value,
        public bool $processed = false
    ) {
    }

    /**
     * Set the processed flag to True.
     * This method updates the item's state.
     */
    public function markAsProcessed(): void
    {
        echo "Model Item {$this->itemId}: Marking '{$this->name}' as processed.\n";
        $this->processed = true;
    }

    /**
     * Return a user-friendly string representation of the item.
     *
     * @return string A string detailing the item's properties.
     */
    public function __toString(): string
    {
        $status = $this->processed ? "Processed" : "Pending";
        return sprintf(
            "Item(ID=%d, Name='%s', Value=%.2f, Status=%s)",
            $this->itemId,
            $this->name,
            $this->value,
            $status
        );
    }
}