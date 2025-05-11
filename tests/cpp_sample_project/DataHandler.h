// cpp_sample_project/include/DataHandler.h

#ifndef DATA_HANDLER_H
#define DATA_HANDLER_H

#include <string>
#include <vector>
#include <iostream> // For basic logging, consider a dedicated library for real projects
#include <stdexcept> // For std::runtime_error or other exceptions

#include "Item.h" // Assuming Item.h is in the same include directory or path is configured

/**
 * @brief Manages loading and saving Item data.
 *
 * Simulates interaction with a data source (e.g., a file or database).
 * In this simple example, it simulates these operations. A real implementation
 * would interact with files, databases, or APIs.
 */
class DataHandler {
private:
    std::string dataSourcePath_; /**< The configured path to the data source (e.g., file path). */
    // In a real app, a logger instance would be preferable.
    // For simplicity, we might use std::cout or a static logger utility.

public:
    /**
     * @brief Constructs a new DataHandler object.
     *
     * Initializes the DataHandler with the path to the data source.
     *
     * @param dataSourcePath The configured path to the data source.
     */
    explicit DataHandler(const std::string& dataSourcePath)
        : dataSourcePath_(dataSourcePath) {
        // In a real C++ app, logging would go to a logger instance or static log function.
        // For now, mirroring Python's direct logging call for demonstration.
        std::cout << "INFO: DataHandler initialized for source: " << dataSourcePath_ << std::endl;
    }

    /**
     * @brief Simulate loading items from the data source.
     *
     * In a real application, this would read from the file/database specified
     * by `dataSourcePath_`. Here, it returns a predefined list for
     * demonstration.
     *
     * @return std::vector<Item> A vector of Item objects.
     * @throws std::runtime_error if data parsing fails for an item.
     */
    std::vector<Item> loadItems() {
        std::cout << "INFO: Simulating loading items from " << dataSourcePath_ << "..." << std::endl;

        // Simulate reading data - replace with actual file reading if needed
        // Using a structure similar to the Python example for simulated_data
        std::vector<std::map<std::string, std::variant<int, double, std::string>>> simulatedRawData = {
            {{"item_id", 1}, {"name", "Gadget Alpha"}, {"value", 150.75}},
            {{"item_id", 2}, {"name", "Widget Beta"}, {"value", 85.0}},
            {{"item_id", 3}, {"name", "Thingamajig Gamma"}, {"value", 210.5}},
            {{"item_id", 4}, {"name", "Doohickey Delta"}, {"value", 55.2}},
            {{"name", "Invalid Item"}, {"value", 10.0}} // Missing item_id
        };

        std::vector<Item> items;
        items.reserve(simulatedRawData.size()); // Pre-allocate memory

        for (const auto& dataDict : simulatedRawData) {
            try {
                // Basic validation for required keys
                if (dataDict.count("item_id") && dataDict.count("name") && dataDict.count("value")) {
                    int id = std::get<int>(dataDict.at("item_id"));
                    std::string name = std::get<std::string>(dataDict.at("name"));
                    double value = std::get<double>(dataDict.at("value"));

                    items.emplace_back(id, name, value); // 'processed' defaults to false in Item constructor
                } else {
                    std::cerr << "WARNING: Skipping invalid data dictionary during load." << std::endl;
                    // More detailed logging of dataDict would be good here in a real app.
                }
            } catch (const std::bad_variant_access& bva) {
                std::cerr << "WARNING: Type error creating Item object from data: " << bva.what() << std::endl;
            } catch (const std::out_of_range& oor) {
                std::cerr << "WARNING: Missing key when creating Item object: " << oor.what() << std::endl;
            }
            // Catching general exceptions is usually not ideal, but for demo:
            catch (const std::exception& e) {
                 std::cerr << "WARNING: Generic error creating Item: " << e.what() << std::endl;
            }
        }

        std::cout << "INFO: Loaded " << items.size() << " items." << std::endl;
        return items;
    }

    /**
     * @brief Simulate saving processed items back to the data source.
     *
     * In a real application, this would write the updated item data to the
     * file/database specified by `dataSourcePath_`.
     *
     * @param items A constant reference to a vector of Item objects (potentially modified) to save.
     * @return bool True if saving was simulated successfully, False otherwise (always true here).
     */
    bool saveItems(const std::vector<Item>& items) {
        std::cout << "INFO: Simulating saving " << items.size() << " items to " << dataSourcePath_ << "..." << std::endl;

        // Simulate writing data - replace with actual file writing if needed
        for (const auto& item : items) {
            // Example: Could convert Item back to JSON and write to file
            // For demonstration, just "log" the item being saved
             std::cout << "DEBUG: Saving item: " << item.toString() << std::endl;
        }

        std::cout << "INFO: Finished simulating save operation." << std::endl;
        return true; // Simulate success
    }
};

#endif // DATA_HANDLER_H
// End of cpp_sample_project/include/DataHandler.h