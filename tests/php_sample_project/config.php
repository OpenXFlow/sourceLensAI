<?php

// tests/sample_project2/config.php

/**
 * Configuration settings for the Sample Project 2.
 *
 * This file returns an array of configuration values used by other parts
 * of the application, such as file paths or processing parameters.
 */

return [
    // --- Constants for Configuration ---

    // Path to a data file (used by DataHandler)
    'DATA_FILE_PATH' => 'data/items.json',

    // A processing parameter (used by ItemProcessor)
    'PROCESSING_THRESHOLD' => 100,

    // Example setting for logging level (could be used by main)
    'LOG_LEVEL' => 'INFO',
];