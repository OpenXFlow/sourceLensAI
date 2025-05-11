// c_sample_project/src/item_processor.c

#include "item_processor.h"
#include <stdio.h>  // For printf (used for logging/debug)
#include <stdlib.h> // For malloc, free

// Helper for logging (simplistic) - copied from data_handler.c for standalone use
// In a real application, this would be in a shared utility module.
#include <stdarg.h> // For va_list etc.

static void log_message_ip(const char* level, const char* file, int line, const char* fmt, ...) {
    fprintf(stdout, "%s: [%s:%d] ", level, file, line);
    va_list args;
    va_start(args, fmt);
    vfprintf(stdout, fmt, args);
    va_end(args);
    fprintf(stdout, "\n");
    fflush(stdout);
}

#define LOG_INFO_IP(fmt, ...) log_message_ip("INFO", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_WARN_IP(fmt, ...) log_message_ip("WARN", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_ERROR_IP(fmt, ...) log_message_ip("ERROR", __FILE__, __LINE__, fmt, ##__VA_ARGS__)
#define LOG_DEBUG_IP(fmt, ...) log_message_ip("DEBUG", __FILE__, __LINE__, fmt, ##__VA_ARGS__)


/**
 * @brief Creates and initializes a new ItemProcessor.
 */
ItemProcessor* item_processor_create(int threshold) {
    ItemProcessor* processor = (ItemProcessor*)malloc(sizeof(ItemProcessor));
    if (processor == NULL) {
        LOG_ERROR_IP("Failed to allocate memory for ItemProcessor structure.");
        return NULL;
    }
    processor->threshold = threshold;
    LOG_INFO_IP("ItemProcessor initialized with threshold: %d", processor->threshold);
    return processor;
}

/**
 * @brief Destroys an ItemProcessor object and frees its associated memory.
 */
void item_processor_destroy(ItemProcessor** processor_ptr) {
    if (processor_ptr != NULL && *processor_ptr != NULL) {
        free(*processor_ptr);
        *processor_ptr = NULL;
        LOG_INFO_IP("ItemProcessor destroyed.");
    }
}

/**
 * @brief Process a single item.
 */
bool item_processor_processItem(ItemProcessor* processor, Item* item) {
    if (processor == NULL) {
        LOG_ERROR_IP("NULL processor passed to item_processor_processItem.");
        return false;
    }
    if (item == NULL) {
        LOG_ERROR_IP("NULL item passed to item_processor_processItem.");
        return false;
    }

    // Using a temporary buffer for item->name to avoid issues if item->name is very long
    // and snprintf truncates it in the middle of a multi-byte char sequence.
    // However, for simple logging, direct use is often fine.
    char name_buffer[128]; // Adjust size as needed
    if (item->name != NULL && strlen(item->name) < sizeof(name_buffer) -1) {
        strcpy(name_buffer, item->name);
    } else if (item->name != NULL) {
        strncpy(name_buffer, item->name, sizeof(name_buffer) - 4); // Leave space for "..."
        strcat(name_buffer, "...");
    } else {
        strcpy(name_buffer, "N/A");
    }


    LOG_DEBUG_IP("Processing item ID: %d, Name: '%s', Value: %.2f",
                 item->itemId,
                 name_buffer,
                 item->value);

    // Apply some simple logic based on the threshold
    if (item->value > processor->threshold) {
        LOG_INFO_IP("Item '%s' (ID: %d) value %.2f exceeds threshold %d.",
                    name_buffer,
                    item->itemId,
                    item->value,
                    processor->threshold);
    } else {
        LOG_INFO_IP("Item '%s' (ID: %d) value %.2f is within threshold %d.",
                    name_buffer,
                    item->itemId,
                    item->value,
                    processor->threshold);
    }

    // Mark the item as processed using its own function
    item_markAsProcessed(item);

    // Simulate successful processing
    return true;
}

// End of c_sample_project/src/item_processor.c