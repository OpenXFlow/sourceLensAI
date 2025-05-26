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
 * @file Defines the Item class representing a data item.
 * @module item
 */

/**
 * Represents a single data item to be processed.
 */
export class Item {
    /**
     * A unique integer identifier for the item.
     * @type {number}
     */
    itemId;

    /**
     * The name of the item.
     * @type {string}
     */
    name;

    /**
     * A numerical value associated with the item.
     * @type {number}
     */
    value;

    /**
     * A boolean flag indicating if the item has been processed.
     * @type {boolean}
     */
    processed;

    /**
     * Constructs an Item object.
     * @param {number} itemId - A unique integer identifier for the item.
     * @param {string} name - The name of the item.
     * @param {number} value - A numerical value associated with the item.
     */
    constructor(itemId, name, value) {
        this.itemId = itemId;
        this.name = name;
        this.value = value;
        this.processed = false; // Default value
    }

    /**
     * Sets the processed flag to True.
     * This method updates the item's state to indicate that it has
     * undergone processing.
     */
    markAsProcessed() {
        console.log(`Model Item ${this.itemId}: Marking '${this.name}' as processed.`);
        this.processed = true;
    }

    /**
     * Returns a user-friendly string representation of the item.
     * @returns {string} A string detailing the item's ID, name, value, and processing status.
     */
    toString() {
        const status = this.processed ? "Processed" : "Pending";
        return `Item(ID=${this.itemId}, Name='${this.name}', Value=${this.value.toFixed(2)}, Status=${status})`;
    }
}

// End of javascript_sample_project/item.js