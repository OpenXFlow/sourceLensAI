// cpp_sample_project/include/Item.h

#ifndef ITEM_H
#define ITEM_H

#include <string>
#include <iostream> // For std::ostream, if we implement operator<<
#include <iomanip>  // For std::fixed and std::setprecision

/**
 * @brief Represents a single data item to be processed.
 *
 * This class defines the structure of data objects used within the application,
 * similar to a dataclass in Python for simplicity and type safety.
 */
class Item {
public:
    int itemId;         चक : A unique integer identifier for the item.
    std::string name;   /**< The name of the item. */
    double value;       /**< A numerical value associated with the item. */
    bool processed;     /**< A boolean flag indicating if the item has been processed. */

    /**
     * @brief Construct a new Item object.
     *
     * @param id The unique integer identifier for the item.
     * @param itemName The name of the item.
     * @param itemValue A numerical value associated with the item.
     * @param isProcessed A boolean flag indicating if the item has been
     *                    processed. Defaults to false.
     */
    Item(int id, const std::string& itemName, double itemValue, bool isProcessed = false)
        : itemId(id), name(itemName), value(itemValue), processed(isProcessed) {
        // Constructor body can be empty if all initialization is done in the initializer list
    }

    /**
     * @brief Set the processed flag to True.
     *
     * This method updates the item's state to indicate that it has
     * undergone processing.
     */
    void markAsProcessed() {
        // In a real application, this might also log or trigger other actions.
        // For now, it matches the Python example's simplicity.
        // std::cout << "Model Item " << itemId << ": Marking '" << name << "' as processed." << std::endl;
        this->processed = true;
    }

    /**
     * @brief Return a user-friendly string representation of the item.
     *
     * @return std::string A string detailing the item's ID, name, value, and
     *                     processing status.
     */
    std::string toString() const {
        std::string status = this->processed ? "Processed" : "Pending";
        // Using a stringstream for formatting to mimic f-string behavior
        std::ostringstream oss;
        oss << "Item(ID=" << this->itemId
            << ", Name='" << this->name
            << "', Value=" << std::fixed << std::setprecision(2) << this->value
            << ", Status=" << status << ")";
        return oss.str();
    }

    /**
     * @brief Overload the stream insertion operator for easy printing of Item objects.
     *
     * Allows an Item object to be directly sent to an output stream (e.g., std::cout).
     *
     * @param os The output stream.
     * @param item The Item object to output.
     * @return std::ostream& The output stream with the item's string representation.
     */
    friend std::ostream& operator<<(std::ostream& os, const Item& item) {
        os << item.toString();
        return os;
    }
};

#endif // ITEM_H
// End of cpp_sample_project/include/Item.h