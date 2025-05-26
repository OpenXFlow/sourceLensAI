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

import { Item } from './item.js'; // Assuming Item is in item.js in the same directory

/**
 * Manages loading and saving Item data.
 * In this simple example, it simulates these operations.
 */
export class DataHandler {
    /**
     * The path to the data source.
     * @type {string}
     * @private
     */
    _dataSourcePath;

    /**
     * Initializes the DataHandler with the path to the data source.
     * @param {string} dataSourcePath - The configured path to the data source.
     */
    constructor(dataSourcePath) {
        this._dataSourcePath = dataSourcePath;
        console.info(`DataHandler initialized for source: ${this._dataSourcePath}`);
    }

    /**
     * Simulates loading items from the data source.
     * @returns {Item[]} A list of Item objects.
     */
    loadItems() {
        console.info(`Simulating loading items from ${this._dataSourcePath}...`);

        const simulatedRawData = [
            { item_id: 1, name: "Gadget Alpha", value: 150.75 },
            { item_id: 2, name: "Widget Beta", value: 85.0 },
            { item_id: 3, name: "Thingamajig Gamma", value: 210.5 },
            { item_id: 4, name: "Doohickey Delta", value: 55.2 },
            { name: "Incomplete Gadget", value: 99.0 } // Missing item_id for testing robustness
        ];

        const items = [];
        for (const dataDict of simulatedRawData) {
            try {
                if (typeof dataDict.item_id === 'number' &&
                    typeof dataDict.name === 'string' &&
                    typeof dataDict.value === 'number') {
                    
                    const item = new Item(
                        dataDict.item_id,
                        dataDict.name,
                        dataDict.value
                    );
                    items.push(item);
                } else {
                    console.warn(`Skipping invalid data dictionary during load: ${JSON.stringify(dataDict)}`);
                }
            } catch (e) { // Catch any error during item creation
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
    saveItems(items) {
        console.info(`Simulating saving ${items.length} items to ${this._dataSourcePath}...`);
        for (const item of items) {
            // In a real app, you might serialize the item to JSON here
            console.debug(`Saving item: ${item.toString()}`);
        }
        console.info("Finished simulating save operation.");
        return true; // Simulate success
    }
}

// End of javascript_sample_project/dataHandler.js