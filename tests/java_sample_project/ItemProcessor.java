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

import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Contains the logic for processing Item objects in the Sample Project.
 */
public class ItemProcessor {
    private static final Logger LOGGER = Logger.getLogger(ItemProcessor.class.getName());
    private final int threshold;

    /**
     * Initializes the ItemProcessor with a processing threshold.
     *
     * @param threshold The numerical threshold used in the processing
     *                  logic. Items with a value above this threshold might be
     *                  handled differently.
     */
    public ItemProcessor(int threshold) {
        this.threshold = threshold;
        LOGGER.log(Level.INFO, "ItemProcessor initialized with threshold: {0}", this.threshold);
    }

    /**
     * Processes a single item.
     * Marks the item as processed and applies logic based on the threshold.
     * In this example, it simply logs whether the item's value exceeds
     * the threshold.
     *
     * @param item The Item object to process.
     * @return True if processing was successful (i.e., item is not null
     *         and is an instance of Item), False otherwise.
     */
    public boolean processItem(Item item) {
        if (item == null) {
            LOGGER.log(Level.SEVERE, "Invalid object passed to processItem: item is null.");
            return false;
        }
        // In Java, isinstance is checked by the type system at compile time for parameters.
        // A runtime check might be desired if 'item' could truly be of another type due to
        // polymorphism, but the method signature already specifies 'Item'.
        // For robustness similar to Python's isinstance, an explicit check can be kept if desired,
        // though often omitted in strongly-typed Java methods.

        LOGGER.log(Level.FINE, "Processing item ID: {0}, Name: ''{1}'', Value: {2,number,#.##}",
                new Object[]{item.getItemId(), item.getName(), item.getValue()});

        // Apply some simple logic based on the threshold
        if (item.getValue() > this.threshold) {
            LOGGER.log(Level.INFO, "Item ''{0}'' (ID: {1}) value {2,number,#.##} exceeds threshold {3}.",
                       new Object[]{item.getName(), item.getItemId(), item.getValue(), this.threshold});
            // Potential place for different actions based on threshold
        } else {
            LOGGER.log(Level.INFO, "Item ''{0}'' (ID: {1}) value {2,number,#.##} is within threshold {3}.",
                       new Object[]{item.getName(), item.getItemId(), item.getValue(), this.threshold});
        }

        // Mark the item as processed using its own method
        item.markAsProcessed();

        // Simulate successful processing
        return true;
    }
}
// End of com/sampleproject/ItemProcessor.java