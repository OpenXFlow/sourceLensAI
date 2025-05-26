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

package com.sampleproject;

/**
 * Represents a single data item to be processed.
 * Defines the structure of data objects used within the application.
 */
public class Item {
    private int itemId;
    private String name;
    private double value;
    private boolean processed;

    /**
     * Constructs an Item object.
     *
     * @param itemId A unique integer identifier for the item.
     * @param name The name of the item.
     * @param value A numerical value associated with the item.
     */
    public Item(int itemId, String name, double value) {
        this.itemId = itemId;
        this.name = name;
        this.value = value;
        this.processed = false; // Default value
    }

    /**
     * Gets the item ID.
     * @return The item ID.
     */
    public int getItemId() {
        return itemId;
    }

    /**
     * Sets the item ID.
     * @param itemId The new item ID.
     */
    public void setItemId(int itemId) {
        this.itemId = itemId;
    }

    /**
     * Gets the name of the item.
     * @return The name of the item.
     */
    public String getName() {
        return name;
    }

    /**
     * Sets the name of the item.
     * @param name The new name.
     */
    public void setName(String name) {
        this.name = name;
    }

    /**
     * Gets the value of the item.
     * @return The value of the item.
     */
    public double getValue() {
        return value;
    }

    /**
     * Sets the value of the item.
     * @param value The new value.
     */
    public void setValue(double value) {
        this.value = value;
    }

    /**
     * Checks if the item has been processed.
     * @return True if processed, false otherwise.
     */
    public boolean isProcessed() {
        return processed;
    }

    /**
     * Sets the processed status of the item.
     * @param processed The new processed status.
     */
    public void setProcessed(boolean processed) {
        this.processed = processed;
    }

    /**
     * Sets the processed flag to True.
     * This method updates the item's state to indicate that it has
     * undergone processing.
     */
    public void markAsProcessed() {
        System.out.printf("Model Item %d: Marking '%s' as processed.%n", this.itemId, this.name);
        this.processed = true;
    }

    /**
     * Returns a user-friendly string representation of the item.
     *
     * @return A string detailing the item's ID, name, value, and
     *         processing status.
     */
    @Override
    public String toString() {
        String status = processed ? "Processed" : "Pending";
        return String.format("Item(ID=%d, Name='%s', Value=%.2f, Status=%s)",
                             this.itemId, this.name, this.value, status);
    }
}
// End of com/sampleproject/Item.java