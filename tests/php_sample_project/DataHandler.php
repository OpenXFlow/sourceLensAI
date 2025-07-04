<?php

// tests/sample_project2/DataHandler.php

namespace SampleProject2;

use SampleProject2\Item;

/**
 * Manages loading and saving Item data.
 * Simulates interaction with a data source like a file or database.
 */
class DataHandler
{
    private string $dataSourcePath;

    /**
     * Initialize the DataHandler with the path to the data source.
     * @param string $dataSourcePath The configured path to the data source.
     */
    public function __construct(string $dataSourcePath)
    {
        $this->dataSourcePath = $dataSourcePath;
        echo "DataHandler initialized for source: {$this->dataSourcePath}\n";
    }

    /**
     * Simulate loading items from the data source.
     * In a real app, this would read from a file or database.
     * @return Item[] A list of Item objects.
     */
    public function loadItems(): array
    {
        echo "Simulating loading items from {$this->dataSourcePath}...\n";
        $simulatedData = [
            ['item_id' => 1, 'name' => 'Gadget Alpha', 'value' => 150.75],
            ['item_id' => 2, 'name' => 'Widget Beta', 'value' => 85.0],
            ['item_id' => 3, 'name' => 'Thingamajig Gamma', 'value' => 210.5],
            ['item_id' => 4, 'name' => 'Doohickey Delta', 'value' => 55.2],
        ];

        $items = [];
        foreach ($simulatedData as $data) {
            $items[] = new Item(
                $data['item_id'],
                $data['name'],
                $data['value']
            );
        }

        echo "Loaded " . count($items) . " items.\n";
        return $items;
    }

    /**
     * Simulate saving processed items back to the data source.
     * @param Item[] $items A list of Item objects to save.
     * @return bool True if saving was simulated successfully.
     */
    public function saveItems(array $items): bool
    {
        echo "Simulating saving " . count($items) . " items to {$this->dataSourcePath}...\n";
        foreach ($items as $item) {
            echo "Saving item: " . $item . "\n";
        }
        echo "Finished simulating save operation.\n";
        return true;
    }
}