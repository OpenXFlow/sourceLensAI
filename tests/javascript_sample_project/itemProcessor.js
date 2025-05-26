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

import { Item } from './item.js'; // Assuming Item is in item.js

/**
 * Processes individual Item objects based on configured rules.
 */
export class ItemProcessor {
    /**
     * The numerical threshold used in processing.
     * @type {number}
     * @private
     */
    _threshold;

    /**
     * Initializes the ItemProcessor with a processing threshold.
     * @param {number} threshold - The numerical threshold.
     */
    constructor(threshold) {
        this._threshold = threshold;
        console.info(`ItemProcessor initialized with threshold: ${this._threshold}`);
    }

    /**
     * Processes a single item.
     * Marks the item as processed and applies logic based on the threshold.
     * @param {Item} item - The Item object to process.
     * @returns {boolean} True if processing was successful, False otherwise.
     */
    processItem(item) {
        if (!(item instanceof Item)) {
            console.error(`Invalid object passed to processItem. Expected Item, got ${item ? item.constructor.name : typeof item}.`);
            return false;
        }

        console.debug(`Processing item ID: ${item.itemId}, Name: '${item.name}', Value: ${item.value.toFixed(2)}`);

        if (item.value > this._threshold) {
            console.info(`Item '${item.name}' (ID: ${item.itemId}) value ${item.value.toFixed(2)} exceeds threshold ${this._threshold}.`);
        } else {
            console.info(`Item '${item.name}' (ID: ${item.itemId}) value ${item.value.toFixed(2)} is within threshold ${this._threshold}.`);
        }

        item.markAsProcessed();
        return true;
    }
}

// End of javascript_sample_project/itemProcessor.js