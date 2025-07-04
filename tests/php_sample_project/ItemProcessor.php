<?php

// tests/sample_project2/ItemProcessor.php

namespace SampleProject2;

use SampleProject2\Item;

/**
 * Processes individual Item objects based on configured rules.
 */
class ItemProcessor
{
    private int $threshold;

    /**
     * Initialize the ItemProcessor with a processing threshold.
     * @param int $threshold The numerical threshold for processing logic.
     */
    public function __construct(int $threshold)
    {
        $this->threshold = $threshold;
        echo "ItemProcessor initialized with threshold: {$this->threshold}\n";
    }

    /**
     * Process a single item.
     * Marks the item as processed and applies logic based on the threshold.
     * @param Item $item The Item object to process.
     * @return bool True if processing was successful.
     */
    public function processItem(Item $item): bool
    {
        echo "Processing item ID: {$item->itemId}, Name: '{$item->name}', Value: {$item->value}\n";

        if ($item->value > $this->threshold) {
            echo "Item '{$item->name}' (ID: {$item->itemId}) value {$item->value} exceeds threshold {$this->threshold}.\n";
        } else {
            echo "Item '{$item->name}' (ID: {$item->itemId}) value {$item->value} is within threshold {$this->threshold}.\n";
        }

        $item->markAsProcessed();
        return true;
    }
}