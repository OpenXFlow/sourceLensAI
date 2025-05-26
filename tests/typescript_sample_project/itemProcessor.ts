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
 * @file Contains the logic for processing Item objects.
 * @module itemProcessor
 */

import { Item } from './item'; // Assuming Item is in item.ts

/**
 * Processes individual Item objects based on configured rules.
 */
export class ItemProcessor {
    private readonly _threshold: number;

    /**
     * Initializes the ItemProcessor with a processing threshold.
     * @param {number} threshold - The numerical threshold.
     */
    constructor(threshold: number) {
        this._threshold = threshold;
        console.info(`ItemProcessor initialized with threshold: ${this._threshold}`);
    }

    /**
     * Processes a single item.
     * Marks the item as processed and applies logic based on the threshold.
     * @param {Item} item - The Item object to process.
     * @returns {boolean} True if processing was successful, False otherwise.
     */
    public processItem(item: Item): boolean {
        // TypeScript's type system largely handles this, but an explicit null check is good practice.
        if (!item) { // Checks for null or undefined
            console.error("Invalid object passed to processItem: item is null or undefined.");
            return false;
        }
        // `item instanceof Item` check can be added for extra runtime safety if objects
        // might come from less type-safe sources, but often omitted if type system is trusted.
        if (!(item instanceof Item)) {
             console.error(`Invalid object passed to processItem. Expected Item, got ${item.constructor.name}.`);
             return false;
        }


        if (typeof console.debug === 'function') {
            console.debug(`Processing item ID: ${item.itemId}, Name: '${item.name}', Value: ${item.value.toFixed(2)}`);
        } else {
            console.log(`Processing item (debug level) ID: ${item.itemId}, Name: '${item.name}', Value: ${item.value.toFixed(2)}`);
        }


        if (item.value > this._threshold) {
            console.info(`Item '${item.name}' (ID: ${item.itemId}) value ${item.value.toFixed(2)} exceeds threshold ${this._threshold}.`);
        } else {
            console.info(`Item '${item.name}' (ID: ${item.itemId}) value ${item.value.toFixed(2)} is within threshold ${this._threshold}.`);
        }

        item.markAsProcessed();
        return true;
    }
}

// End of typescript_sample_project/itemProcessor.ts