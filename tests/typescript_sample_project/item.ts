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
 * Defines the structure of data objects used within the application.
 */
export class Item {
    public itemId: number;
    public name: string;
    public value: number;
    public processed: boolean;

    /**
     * Constructs an Item object.
     * @param {number} itemId - A unique integer identifier for the item.
     * @param {string} name - The name of the item.
     * @param {number} value - A numerical value associated with the item.
     * @param {boolean} [processed=false] - A flag indicating if the item has been processed.
     */
    constructor(itemId: number, name: string, value: number, processed: boolean = false) {
        this.itemId = itemId;
        this.name = name;
        this.value = value;
        this.processed = processed;
    }

    /**
     * Sets the processed flag to True.
     * This method updates the item's state to indicate that it has
     * undergone processing.
     * @returns {void} This method does not return any value.
     */
    public markAsProcessed(): void {
        // In a real application, this might also log or trigger events.
        // Using console.log for simplicity here, similar to the Python example.
        console.log(`Model Item ${this.itemId}: Marking '${this.name}' as processed.`);
        this.processed = true;
    }

    /**
     * Returns a user-friendly string representation of the item.
     * @returns {string} A string detailing the item's ID, name, value, and processing status.
     */
    public toString(): string {
        const status: string = this.processed ? "Processed" : "Pending";
        return `Item(ID=${this.itemId}, Name='${this.name}', Value=${this.value.toFixed(2)}, Status=${status})`;
    }
}

// End of typescript_sample_project/item.ts