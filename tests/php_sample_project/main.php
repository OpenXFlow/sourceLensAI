<?php

// tests/sample_project2/main.php

/**
 * Main execution script for Sample Project 2.
 * Orchestrates the loading, processing, and saving of data items.
 */

// This is crucial for autoloading all our classes
require 'vendor/autoload.php';

use SampleProject2\DataHandler;
use SampleProject2\ItemProcessor;

/**
 * Executes the main data processing pipeline.
 */
function runProcessingPipeline(): void
{
    echo "Starting Sample Project 2 processing pipeline...\n";

    try {
        // 1. Load configuration
        $config = require 'config.php';

        // 2. Initialize components
        $dataHandler = new DataHandler($config['DATA_FILE_PATH']);
        $itemProcessor = new ItemProcessor($config['PROCESSING_THRESHOLD']);

        // 3. Load data
        $itemsToProcess = $dataHandler->loadItems();
        if (empty($itemsToProcess)) {
            echo "No items loaded. Exiting pipeline.\n";
            return;
        }

        // 4. Process data items
        foreach ($itemsToProcess as $item) {
            $itemProcessor->processItem($item);
        }

        // 5. Save processed data
        $dataHandler->saveItems($itemsToProcess);

    } catch (Throwable $e) {
        // Catch any error or exception for graceful exit
        echo "A critical error occurred: " . $e->getMessage() . "\n";
    } finally {
        echo "Sample Project 2 processing pipeline finished.\n";
    }
}

// Run the main function
runProcessingPipeline();