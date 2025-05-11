// c_sample_project/src/item.c

#include "item.h"    // Corresponding header file
#include <stdlib.h>  // For malloc, free
#include <string.h>  // For strcpy, strlen
#include <stdio.h>   // For snprintf

/**
 * @brief Creates and initializes a new Item.
 *
 * Dynamically allocates memory for the Item structure and its name.
 * The caller is responsible for freeing the returned Item using item_destroy().
 * If name allocation fails, the Item structure is also freed and NULL is returned.
 *
 * @param id The unique integer identifier for the item.
 * @param itemName The name of the item. This string will be copied.
 * @param itemValue A numerical value associated with the item.
 * @param isProcessed A boolean flag indicating if the item has been
 *                    processed initially.
 * @return Item* Pointer to the newly created Item, or NULL on allocation failure.
 */
Item* item_create(int id, const char* itemName, double itemValue, bool isProcessed) {
    if (itemName == NULL) {
        // fprintf(stderr, "Error: itemName cannot be NULL in item_create.\n"); // Optional error logging
        return NULL;
    }

    Item* newItem = (Item*)malloc(sizeof(Item));
    if (newItem == NULL) {
        // perror("Error allocating memory for Item structure"); // Optional error logging
        return NULL;
    }

    // Allocate memory for the name and copy it
    // +1 for the null terminator
    newItem->name = (char*)malloc(strlen(itemName) + 1);
    if (newItem->name == NULL) {
        // perror("Error allocating memory for Item name"); // Optional error logging
        free(newItem); // Clean up the partially allocated Item
        return NULL;
    }
    strcpy(newItem->name, itemName);

    newItem->itemId = id;
    newItem->value = itemValue;
    newItem->processed = isProcessed;

    return newItem;
}

/**
 * @brief Destroys an Item object and frees its associated memory.
 *
 * Frees the memory allocated for the item's name and the Item structure itself.
 * Sets the pointer to the Item to NULL after freeing to prevent dangling pointer issues.
 *
 * @param item_ptr Pointer to the pointer of the Item to be destroyed.
 *                 The pointer will be set to NULL. If *item_ptr is NULL,
 *                 the function does nothing.
 */
void item_destroy(Item** item_ptr) {
    if (item_ptr != NULL && *item_ptr != NULL) {
        if ((*item_ptr)->name != NULL) {
            free((*item_ptr)->name);
            (*item_ptr)->name = NULL; // Good practice
        }
        free(*item_ptr);
        *item_ptr = NULL; // Prevent dangling pointer
    }
}

/**
 * @brief Sets the processed flag of an Item to true.
 *
 * This function updates the item's state to indicate that it has
 * undergone processing.
 *
 * @param item Pointer to the Item to be marked as processed.
 *             If NULL, the function does nothing.
 */
void item_markAsProcessed(Item* item) {
    if (item != NULL) {
        // In a real application, this might also log or trigger other actions.
        // printf("Model Item %d: Marking '%s' as processed.\n", item->itemId, item->name);
        item->processed = true;
    }
}

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
 *             or -1 on error (e.g., insufficient buffer or NULL item).
 */
int item_toString(const Item* item, char* buffer, size_t buffer_size) {
    if (item == NULL || buffer == NULL || buffer_size == 0) {
        if (buffer != NULL && buffer_size > 0) buffer[0] = '\0';
        return -1; // Indicate error
    }

    const char* status = item->processed ? "Processed" : "Pending";
    int written = snprintf(buffer, buffer_size, "Item(ID=%d, Name='%s', Value=%.2f, Status=%s)",
                           item->itemId,
                           item->name ? item->name : "N/A", // Handle NULL name defensively
                           item->value,
                           status);

    if (written < 0 || (size_t)written >= buffer_size) {
        // Error occurred or buffer was too small (snprintf truncates and returns what *would have* been written)
        // To be safe, ensure null termination if truncated and some space was available
        if (buffer_size > 0) {
            buffer[buffer_size - 1] = '\0';
        }
        // Consider returning the number of chars that *would have* been written if not for truncation,
        // or a distinct error code. For simplicity here, we return what snprintf returns.
        // However, if snprintf indicates truncation (written >= buffer_size), it's an error condition for us.
        if((size_t)written >= buffer_size) return -1; // Indicate error due to truncation
        return written; // snprintf might return negative on encoding errors.
    }
    return written; // Success
}

// End of c_sample_project/src/item.c