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
 * @file Handles data loading and saving operations for the Sample Project.
 * Simulates interaction with a data source.
 * @module dataHandler
 */

import { Item } from './item'; // ES6 module import

// Define a type for the raw data structure for clarity
type RawItemData = {
    item_id?: number; // Optional to simulate missing data
    name?: string;    // Optional
    value?: number;   // Optional
    [key: string]: any; // Allow other properties
};

/**
 * Manages loading and saving Item data.
 * In this simple example, it simulates these operations.
 */
export class DataHandler {
    private readonly _dataSourcePath: string; // Made readonly as it's set in constructor

    /**
     * Initializes the DataHandler with the path to the data source.
     * @param {string} dataSourcePath - The configured path to the data source.
     */
    constructor(dataSourcePath: string) {
        this._dataSourcePath = dataSourcePath;
        console.info(`DataHandler initialized for source: ${this._dataSourcePath}`);
    }

    /**
     * Simulates loading items from the data source.
     * @returns {Item[]} A list of Item objects.
     */
    public loadItems(): Item[] {
        console.info(`Simulating loading items from ${this._dataSourcePath}...`);

        const simulatedRawData: RawItemData[] = [
            { item_id: 1, name: "Gadget Alpha", value: 150.75 },
            { item_id: 2, name: "Widget Beta", value: 85.0 },
            { item_id: 3, name: "Thingamajig Gamma", value: 210.5 },
            { item_id: 4, name: "Doohickey Delta", value: 55.2 },
            { name: "Incomplete Gadget", value: 99.0 }, // Missing item_id
            { item_id: 5, name: "Faulty Widget", value: "not-a-number" } // Invalid value type
        ];

        const items: Item[] = [];
        for (const dataDict of simulatedRawData) {
            try {
                // More robust type checking for TypeScript
                if (typeof dataDict.item_id === 'number' &&
                    typeof dataDict.name === 'string' &&
                    typeof dataDict.value === 'number') {
                    
                    // Create new Item instance
                    const item = new Item(
                        dataDict.item_id,
                        dataDict.name,
                        dataDict.value
                        // 'processed' defaults to false in Item constructor
                    );
                    items.push(item);
                } else {
                    console.warn(`Skipping invalid data dictionary during load (missing or wrong type of required fields): ${JSON.stringify(dataDict)}`);
                }
            } catch (e: any) { // Catching 'any' for broader compatibility with potential errors
                console.warn(`Error creating Item object from data ${JSON.stringify(dataDict)}: ${e.message}`);
            }
        }

        console.info(`Loaded ${items.length} items.`);
        return items;
    }

    /**
     * Simulates saving processed items back to the data source.
     * @param {Item[]} items - A list of Item objects to save.
     * @returns {boolean} True if saving was simulated successfully.
     */
    public saveItems(items: Item[]): boolean {
        console.info(`Simulating saving ${items.length} items to ${this._dataSourcePath}...`);
        for (const item of items) {
            // In a real app, you might serialize the item to JSON here
            // Using console.debug which might be filtered out by default logger settings
            if (typeof console.debug === 'function') {
                 console.debug(`Saving item: ${item.toString()}`);
            } else {
                 console.log(`Saving item (debug level): ${item.toString()}`);
            }
        }
        console.info("Finished simulating save operation.");
        return true; // Simulate success
    }
}

// End of typescript_sample_project/dataHandler.ts