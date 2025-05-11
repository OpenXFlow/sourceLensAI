// c_sample_project/include/item.h

#ifndef ITEM_H
#define ITEM_H

#include <stdbool.h> // For bool type (C99 and later)
#include <stdio.h>   // For size_t in item_toString (and potentially FILE* if used elsewhere)

/**
 * @struct Item
 * @brief Represents a single data item to be processed.
 *
 * This structure defines the data objects used within the application.
 * It's an analogue to the Python Item dataclass.
 */
typedef struct {
    int itemId;         /**< A unique integer identifier for the item. */
    char* name;         /**< The name of the item (dynamically allocated string). */
    double value;       /**< A numerical value associated with the item. */
    bool processed;     /**< A boolean flag indicating if the item has been processed. */
} Item;

/**
 * @brief Creates and initializes a new Item.
 *
 * Dynamically allocates memory for the Item structure and its name.
 * The caller is responsible for freeing the returned Item using item_destroy().
 * If name allocation fails, NULL is returned.
 *
 * @param id The unique integer identifier for the item.
 * @param itemName The name of the item. This string will be copied.
 * @param itemValue A numerical value associated with the item.
 * @param isProcessed A boolean flag indicating if the item has been
 *                    processed initially. Defaults to false in typical usage.
 * @return Item* Pointer to the newly created Item, or NULL on allocation failure.
 */
Item* item_create(int id, const char* itemName, double itemValue, bool isProcessed);

/**
 * @brief Destroys an Item object and frees its associated memory.
 *
 * Frees the memory allocated for the item's name and the Item structure itself.
 * Sets the pointer to NULL after freeing to prevent dangling pointer issues.
 *
 * @param item_ptr Pointer to the pointer of the Item to be destroyed.
 *                 The pointer will be set to NULL.
 */
void item_destroy(Item** item_ptr);

/**
 * @brief Sets the processed flag of an Item to true.
 *
 * This function updates the item's state to indicate that it has
 * undergone processing.
 *
 * @param item Pointer to the Item to be marked as processed.
 *             If NULL, the function does nothing.
 */
void item_markAsProcessed(Item* item);

/**
 * @brief Generates a user-friendly string representation of the Item.
 *
 * The caller must provide a buffer of sufficient size.
 * The function will write the string representation into this buffer.
 *
 * @param item Pointer to the Item to represent. If NULL, an error string is written.
 * @param buffer Character buffer to store the string representation.
 * @param buffer_size The size of the character buffer.
 * @return int Number of characters written (excluding null terminator),
 *             or -1 on error (e.g., insufficient buffer).
 */
int item_toString(const Item* item, char* buffer, size_t buffer_size);

#endif // ITEM_H
// End of c_sample_project/include/item.h