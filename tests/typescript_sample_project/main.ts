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

import * as config from './config'; // Import all exports from config.ts
import { DataHandler } from './dataHandler';
import { ItemProcessor } from './itemProcessor';
import { Item } from './item'; // Explicitly import Item for type annotations

/**
 * Sets up basic logging for the main script execution.
 * This is a simplified setup; a real application might use a dedicated logging library.
 */
function setupMainLogging(): void {
    const level = config.LOG_LEVEL.toUpperCase();
    console.log(`Logging level set to (approximate): ${level}`);
    // In a real app, you'd configure a proper logger instance here.
    // For this example, we rely on console methods and their default behavior.
}

/**
 * Executes the main data processing pipeline.
 */
function runProcessingPipeline(): void {
    console.info("Starting Sample Project processing pipeline (TypeScript)...");

    try {
        // 1. Initialize components using configuration
        const dataPath: string = config.getDataPath();
        const threshold: number = config.getThreshold();

        const dataHandler = new DataHandler(dataPath);
        const itemProcessor = new ItemProcessor(threshold);

        // 2. Load data
        const itemsToProcess: Item[] = dataHandler.loadItems();

        if (!itemsToProcess || itemsToProcess.length === 0) {
            console.warn("No items loaded from data source. Exiting pipeline.");
            return;
        }
        console.info(`Successfully loaded ${itemsToProcess.length} items.`);

        // 3. Process data items
        const processedItems: Item[] = [];
        const failedItems: Item[] = [];

        for (const item of itemsToProcess) {
            if (typeof console.debug === 'function') {
                console.debug(`Passing item to processor: ${item.toString()}`);
            } else {
                console.log(`Passing item to processor (debug level): ${item.toString()}`);
            }
            const success: boolean = itemProcessor.processItem(item);
            if (success) {
                processedItems.push(item);
            } else {
                console.error(`Failed to process item: ${item.toString()}`);
                failedItems.push(item);
            }
        }
        console.info(`Processed ${processedItems.length} items successfully, ${failedItems.length} failed.`);

        // 4. Save processed data
        const saveSuccess: boolean = dataHandler.saveItems(itemsToProcess);

        if (saveSuccess) {
            console.info("Processed items saved successfully (simulated).");
        } else {
            console.error("Failed to save processed items (simulated).");
        }

    } catch (e: any) { // Catching 'any' for broader error types in JS runtime
        // In a more robust application, consider more specific error handling
        // or custom error classes.
        const errorMessage = e instanceof Error ? e.message : String(e);
        const errorStack = e instanceof Error && e.stack ? e.stack : 'No stack available.';
        console.error("A runtime error occurred during pipeline execution:", errorMessage, errorStack);
    } finally {
        console.info("Sample Project processing pipeline finished.");
    }
}

// --- Main execution ---
// This code will run when the script is executed.
setupMainLogging();
runProcessingPipeline();

// End of typescript_sample_project/main.ts