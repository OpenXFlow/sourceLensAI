// c_sample_project/src/data_handler.c

#include "data_handler.h"
#include <stdio.h>    // For printf, snprintf (used for logging/debug)
#include <stdlib.h>   // For malloc, free
#include <string.h>   // For strcpy, strlen
#include <stdarg.h>   // For va_list, etc. if we were to implement a printf-like logger

// Helper for logging (simplistic)
// In a real application, use a proper logging library or more robust functions.
static void log_message(const char* level, const char* file, int line, const char* fmt, ...) {
    fprintf(stdout, "%s: [%s:%d] ", level, file, line); // stdout for INFO/DEBUG
    va_list args;
    va_start(args, fmt);
    vfprintf(stdout, fmt, args);
    va_end(args);
    fprintf(stdout, "\n");
    fflush(stdout);
}

// Simplified logging macros
#define LOG_INFO(fmt, ...) log_message("INFO", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_WARN(fmt, ...) log_message("WARN", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_ERROR(fmt, ...) log_message("ERROR", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_DEBUG(fmt, ...) log_message("DEBUG", __FILE__, __LINE__, fmt, ##__VA_ARGS__)


/**
 * @brief Creates and initializes a new DataHandler.
 */
DataHandler* data_handler_create(const char* dataSourcePath) {
    if (dataSourcePath == NULL) {
        LOG_ERROR("dataSourcePath cannot be NULL.");
        return NULL;
    }

    DataHandler* handler = (DataHandler*)malloc(sizeof(DataHandler));
    if (handler == NULL) {
        LOG_ERROR("Failed to allocate memory for DataHandler structure.");
        return NULL;
    }

    handler->dataSourcePath = (char*)malloc(strlen(dataSourcePath) + 1);
    if (handler->dataSourcePath == NULL) {
        LOG_ERROR("Failed to allocate memory for dataSourcePath string.");
        free(handler);
        return NULL;
    }
    strcpy(handler->dataSourcePath, dataSourcePath);

    LOG_INFO("DataHandler initialized for source: %s", handler->dataSourcePath);
    return handler;
}

/**
 * @brief Destroys a DataHandler object and frees its associated memory.
 */
void data_handler_destroy(DataHandler** handler_ptr) {
    if (handler_ptr != NULL && *handler_ptr != NULL) {
        DataHandler* handler = *handler_ptr;
        if (handler->dataSourcePath != NULL) {
            free(handler->dataSourcePath);
            handler->dataSourcePath = NULL;
        }
        free(handler);
        *handler_ptr = NULL;
        LOG_INFO("DataHandler destroyed.");
    }
}

// Helper structure for simulated raw data to match Python example
typedef struct {
    int item_id;
    const char* name;
    double value;
    bool has_id; // To simulate missing keys
    bool has_name;
    bool has_value;
} SimulatedRawItem;


/**
 * @brief Simulate loading items from the data source.
 */
Item** data_handler_loadItems(DataHandler* handler, int* num_items_loaded) {
    if (handler == NULL || num_items_loaded == NULL) {
        LOG_ERROR("NULL parameter passed to data_handler_loadItems.");
        if (num_items_loaded) *num_items_loaded = 0;
        return NULL;
    }

    LOG_INFO("Simulating loading items from %s...", handler->dataSourcePath);
    *num_items_loaded = 0;

    SimulatedRawItem simulated_data[] = {
        {1, "Gadget Alpha", 150.75, true, true, true},
        {2, "Widget Beta", 85.0, true, true, true},
        {3, "Thingamajig Gamma", 210.5, true, true, true},
        {4, "Doohickey Delta", 55.2, true, true, true},
        {0, "Invalid Item (Missing ID)", 10.0, false, true, true} // Example of an invalid item
    };
    int num_simulated_items = sizeof(simulated_data) / sizeof(simulated_data[0]);

    // Allocate array of Item pointers
    Item** items_array = (Item**)malloc(num_simulated_items * sizeof(Item*));
    if (items_array == NULL) {
        LOG_ERROR("Failed to allocate memory for items array.");
        return NULL;
    }

    int current_item_index = 0;
    for (int i = 0; i < num_simulated_items; ++i) {
        // Basic validation similar to Python example
        if (simulated_data[i].has_id && simulated_data[i].has_name && simulated_data[i].has_value) {
            Item* newItem = item_create(
                simulated_data[i].item_id,
                simulated_data[i].name,
                simulated_data[i].value,
                false // 'processed' defaults to false
            );

            if (newItem != NULL) {
                items_array[current_item_index++] = newItem;
            } else {
                LOG_WARN("Failed to create Item object for simulated data index %d.", i);
                // Note: If item_create fails, memory for previous items in items_array is not freed here.
                // A more robust implementation would clean up already allocated items before returning NULL.
            }
        } else {
            LOG_WARN("Skipping invalid simulated data dictionary at index %d.", i);
        }
    }

    *num_items_loaded = current_item_index;
    LOG_INFO("Loaded %d items.", *num_items_loaded);

    if (*num_items_loaded == 0) {
        free(items_array);
        return NULL;
    }
    
    // Optionally, reallocate to the exact size if significantly different (not critical for small N)
    // Item** resized_array = (Item**)realloc(items_array, (*num_items_loaded) * sizeof(Item*));
    // if (resized_array == NULL && *num_items_loaded > 0) { /* handle realloc error */ }
    // else { items_array = resized_array; }

    return items_array;
}

/**
 * @brief Simulate saving processed items back to the data source.
 */
bool data_handler_saveItems(DataHandler* handler, const Item* const* items_array, int num_items) {
    if (handler == NULL) {
        LOG_ERROR("NULL DataHandler passed to saveItems.");
        return false;
    }
    if (items_array == NULL && num_items > 0) {
        LOG_ERROR("NULL items_array passed to saveItems with num_items > 0.");
        return false;
    }


    LOG_INFO("Simulating saving %d items to %s...", num_items, handler->dataSourcePath);

    char item_buffer[256]; // Buffer for item_toString

    for (int i = 0; i < num_items; ++i) {
        if (items_array[i] != NULL) {
            item_toString(items_array[i], item_buffer, sizeof(item_buffer));
            LOG_DEBUG("Saving item: %s", item_buffer);
        } else {
            LOG_WARN("Encountered NULL item at index %d during save operation.", i);
        }
    }

    LOG_INFO("Finished simulating save operation.");
    return true; // Simulate success
}

// End of c_sample_project/src/data_handler.c