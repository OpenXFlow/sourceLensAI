// Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

/**
 * @file Main execution script for the Sample Project.
 * Orchestrates loading, processing, and saving of data items.
 * @module main
 */

// Using ES6 module imports
import * as config from './config.js'; // Import all exports from config.js
import { DataHandler } from './dataHandler.js';
import { ItemProcessor } from './itemProcessor.js';
// Item is implicitly used via DataHandler and ItemProcessor, no direct import needed here
// unless we were to create Item instances directly in main.js

/**
 * Sets up basic logging for the main script execution.
 * In a browser environment, console methods are already available.
 * In Node.js, this could be expanded to use a more sophisticated logger if needed.
 */
function setupMainLogging() {
    // For client-side JS, console is the primary logging tool.
    // For Node.js, one might configure a library like Winston or Pino here
    // based on config.LOG_LEVEL.
    // This basic setup just ensures console methods are used according to a level.
    const level = config.LOG_LEVEL.toUpperCase();
    console.log(`Logging level set to: ${level}`);
    // Simple mapping for demonstration; a real app might use a logging library
    if (level === "DEBUG") {
        // console.debug is often an alias for console.log or might need specific browser flags
    } else if (level === "INFO") {
        // console.info is standard
    } else if (level === "WARNING") {
        // console.warn is standard
    } else if (level === "ERROR" || level === "CRITICAL") {
        // console.error is standard
    }
    // Default console.log will catch messages if no specific method is called.
}

/**
 * Executes the main data processing pipeline.
 */
function runProcessingPipeline() {
    console.info("Starting Sample Project processing pipeline...");

    try {
        // 1. Initialize components using configuration
        const dataPath = config.getDataPath();
        const threshold = config.getThreshold();

        const dataHandler = new DataHandler(dataPath);
        const itemProcessor = new ItemProcessor(threshold);

        // 2. Load data
        /** @type {import('./item.js').Item[]} */
        const itemsToProcess = dataHandler.loadItems();

        if (!itemsToProcess || itemsToProcess.length === 0) {
            console.warn("No items loaded from data source. Exiting pipeline.");
            return;
        }
        console.info(`Successfully loaded ${itemsToProcess.length} items.`);

        // 3. Process data items
        /** @type {import('./item.js').Item[]} */
        const processedItems = [];
        /** @type {import('./item.js').Item[]} */
        const failedItems = [];

        for (const item of itemsToProcess) {
            console.debug(`Passing item to processor: ${item.toString()}`);
            const success = itemProcessor.processItem(item);
            if (success) {
                processedItems.push(item);
            } else {
                console.error(`Failed to process item: ${item.toString()}`);
                failedItems.push(item);
            }
        }
        console.info(`Processed ${processedItems.length} items successfully, ${failedItems.length} failed.`);

        // 4. Save processed data
        const saveSuccess = dataHandler.saveItems(itemsToProcess); // Python example passes original list

        if (saveSuccess) {
            console.info("Processed items saved successfully (simulated).");
        } else {
            console.error("Failed to save processed items (simulated).");
        }

    } catch (e) {
        // Basic error handling. In a real app, distinguish error types.
        // JS error types are less specific than Python's for IO/File, etc.
        // common ones: Error, TypeError, RangeError, ReferenceError
        console.error("A runtime error occurred during pipeline execution:", e.message, e.stack);
        // Could check e.name for specific error types if needed
    } finally {
        console.info("Sample Project processing pipeline finished.");
    }
}

// --- Main execution ---
// This will run when the script is loaded as a module or directly.
// To make it behave like Python's if __name__ == "__main__":
// (which is mainly for when a file can be both imported and run directly)
// in Node.js, you might check: if (require.main === module) { ... }
// For browser or simple Node.js scripts, direct execution is common.

setupMainLogging();
runProcessingPipeline();

// End of javascript_sample_project/main.js