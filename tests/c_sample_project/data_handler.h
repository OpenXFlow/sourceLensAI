// c_sample_project/include/data_handler.h

#ifndef DATA_HANDLER_H
#define DATA_HANDLER_H

#include <stdbool.h> // For bool
#include <stddef.h>  // For size_t

#include "item.h"    // Definition of the Item struct

/**
 * @struct DataHandler
 * @brief Manages loading and saving Item data.
 *
 * This structure holds the path to the data source. Functions operating
 * on this handler simulate interaction with a data source.
 */
typedef struct {
    char* dataSourcePath; /**< The configured path to the data source (dynamically allocated). */
    // In a real application, you might add more state here,
    // e.g., a file pointer if the file is kept open, or a logger instance.
} DataHandler;

/**
 * @brief Creates and initializes a new DataHandler.
 *
 * Dynamically allocates memory for the DataHandler structure and its dataSourcePath.
 * The caller is responsible for freeing the returned DataHandler using data_handler_destroy().
 *
 * @param dataSourcePath The configured path to the data source. This string will be copied.
 * @return DataHandler* Pointer to the newly created DataHandler, or NULL on allocation failure.
 */
DataHandler* data_handler_create(const char* dataSourcePath);

/**
 * @brief Destroys a DataHandler object and frees its associated memory.
 *
 * Frees the memory allocated for the handler's dataSourcePath and the handler itself.
 * Sets the pointer to NULL after freeing.
 *
 * @param handler_ptr Pointer to the pointer of the DataHandler to be destroyed.
 *                    The pointer will be set to NULL.
 */
void data_handler_destroy(DataHandler** handler_ptr);

/**
 * @brief Simulate loading items from the data source.
 *
 * In a real application, this would read from the file/database specified
 * by `handler->dataSourcePath`. Here, it returns a predefined list of items.
 * The caller is responsible for freeing the memory allocated for the items array
 * and each Item within it (e.g., by iterating and calling item_destroy).
 *
 * @param handler Pointer to the DataHandler instance.
 * @param num_items_loaded Pointer to an integer where the number of loaded items will be stored.
 * @return Item** A dynamically allocated array of pointers to Item objects,
 *                or NULL if an error occurs or no items are loaded.
 *                The array itself and each Item* in it must be freed by the caller.
 */
Item** data_handler_loadItems(DataHandler* handler, int* num_items_loaded);

/**
 * @brief Simulate saving processed items back to the data source.
 *
 * In a real application, this would write the updated item data to the
 * file/database specified by `handler->dataSourcePath`.
 *
 * @param handler Pointer to the DataHandler instance.
 * @param items_array An array of pointers to Item objects to save.
 * @param num_items The number of items in the items_array.
 * @return bool True if saving was simulated successfully, false otherwise (always true here).
 */
bool data_handler_saveItems(DataHandler* handler, const Item* const* items_array, int num_items);

#endif // DATA_HANDLER_H
// End of c_sample_project/include/data_handler.h