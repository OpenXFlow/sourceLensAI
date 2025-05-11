// cpp_sample_project/include/ItemProcessor.h

#ifndef ITEM_PROCESSOR_H
#define ITEM_PROCESSOR_H

#include <string>
#include <iostream> // For basic logging, consider a dedicated library for real projects
#include <iomanip>  // For std::fixed, std::setprecision in logging

#include "Item.h" // Assuming Item.h is in the same include directory or path is configured

/**
 * @brief Processes individual Item objects based on configured rules.
 *
 * Contains the logic for processing Item objects, similar to the Python
 * ItemProcessor class.
 */
class ItemProcessor {
private:
    int threshold_; /**< The numerical threshold used in the processing logic. */
    // In a real app, a logger instance would be preferable.

public:
    /**
     * @brief Constructs a new ItemProcessor object.
     *
     * Initializes the ItemProcessor with a processing threshold.
     *
     * @param threshold The numerical threshold. Items with a value above this
     *                  threshold might be handled differently.
     */
    explicit ItemProcessor(int threshold)
        : threshold_(threshold) {
        std::cout << "INFO: ItemProcessor initialized with threshold: " << threshold_ << std::endl;
    }

    /**
     * @brief Process a single item.
     *
     * Marks the item as processed and applies logic based on the threshold.
     * In this example, it simply logs whether the item's value exceeds
     * the threshold.
     *
     * @param item A reference to the Item object to process. It will be modified.
     * @return bool True if processing was successful, False otherwise (always true here).
     */
    bool processItem(Item& item) { // Pass Item by reference to modify it
        // In C++, type checking is done at compile time mostly.
        // A dynamic_cast or typeid could be used for runtime checks if 'item' were a base class pointer,
        // but here we expect an Item object directly.

        std::cout << "DEBUG: Processing item ID: " << item.itemId
                  << ", Name: '" << item.name
                  << "', Value: " << std::fixed << std::setprecision(2) << item.value << std::endl;

        // Apply some simple logic based on the threshold
        if (item.value > threshold_) {
            std::cout << "INFO: Item '" << item.name << "' (ID: " << item.itemId
                      << ") value " << std::fixed << std::setprecision(2) << item.value
                      << " exceeds threshold " << threshold_ << "." << std::endl;
            // Potential place for different actions based on threshold
        } else {
            std::cout << "INFO: Item '" << item.name << "' (ID: " << item.itemId
                      << ") value " << std::fixed << std::setprecision(2) << item.value
                      << " is within threshold " << threshold_ << "." << std::endl;
        }

        // Mark the item as processed using its own method
        item.markAsProcessed();

        // Simulate successful processing
        return true;
    }
};

#endif // ITEM_PROCESSOR_H
// End of cpp_sample_project/include/ItemProcessor.h