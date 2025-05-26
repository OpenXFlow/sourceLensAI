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

import java.util.ArrayList;
import java.util.List;
import java.util.Map; // For simulated_data structure
import java.util.logging.Level;
import java.util.logging.Logger;

/**
 * Handles data loading and saving operations for the Sample Project.
 * Simulates interaction with a data source (e.g., a file or database).
 */
public class DataHandler {
    private static final Logger LOGGER = Logger.getLogger(DataHandler.class.getName());
    private final String dataSourcePath;

    /**
     * Initializes the DataHandler with the path to the data source.
     *
     * @param dataSourcePath The configured path to the data source (e.g., file path).
     */
    public DataHandler(String dataSourcePath) {
        this.dataSourcePath = dataSourcePath;
        LOGGER.log(Level.INFO, "DataHandler initialized for source: {0}", this.dataSourcePath);
    }

    /**
     * Simulates loading items from the data source.
     * In a real application, this would read from the file/database specified
     * by `this.dataSourcePath`. Here, it returns a predefined list for
     * demonstration.
     *
     * @return A list of Item objects.
     */
    public List<Item> loadItems() {
        LOGGER.log(Level.INFO, "Simulating loading items from {0}...", this.dataSourcePath);

        // Simulate reading data - replace with actual file reading if needed
        // Using a List of Maps to simulate raw data records
        List<Map<String, Object>> simulatedRawData = List.of(
            Map.of("item_id", 1, "name", "Gadget Alpha", "value", 150.75),
            Map.of("item_id", 2, "name", "Widget Beta", "value", 85.0),
            Map.of("item_id", 3, "name", "Thingamajig Gamma", "value", 210.5),
            Map.of("item_id", 4, "name", "Doohickey Delta", "value", 55.2),
            Map.of("name", "Incomplete Gadget", "value", 99.0) // Missing item_id
        );

        List<Item> items = new ArrayList<>();
        for (Map<String, Object> dataDict : simulatedRawData) {
            try {
                if (dataDict.containsKey("item_id") && dataDict.containsKey("name") && dataDict.containsKey("value")) {
                    int id = (Integer) dataDict.get("item_id");
                    String name = (String) dataDict.get("name");
                    double value = ((Number) dataDict.get("value")).doubleValue(); // Handle Integer or Double

                    Item item = new Item(id, name, value);
                    items.add(item);
                } else {
                    LOGGER.log(Level.WARNING, "Skipping invalid data dictionary during load: {0}", dataDict);
                }
            } catch (ClassCastException | NullPointerException e) { // Catch potential casting or null issues
                LOGGER.log(Level.WARNING, "Error creating Item object from data {0}: {1}", new Object[]{dataDict, e.getMessage()});
            }
        }

        LOGGER.log(Level.INFO, "Loaded {0} items.", items.size());
        return items;
    }

    /**
     * Simulates saving processed items back to the data source.
     * In a real application, this would write the updated item data to the
     * file/database specified by `this.dataSourcePath`.
     *
     * @param items A list of Item objects (potentially modified) to save.
     * @return True if saving was simulated successfully, False otherwise (always True here).
     */
    public boolean saveItems(List<Item> items) {
        LOGGER.log(Level.INFO, "Simulating saving {0} items to {1}...", new Object[]{items.size(), this.dataSourcePath});
        // Simulate writing data - replace with actual file writing if needed
        for (Item item : items) {
            // Example: Could convert Item back to dict and write to JSON
            LOGGER.log(Level.FINE, "Saving item: {0}", item.toString());
        }
        LOGGER.log(Level.INFO, "Finished simulating save operation.");
        return true; // Simulate success
    }
}
// End of com/sampleproject/DataHandler.java