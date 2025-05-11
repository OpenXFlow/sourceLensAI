// c_sample_project/src/main.c

#include <stdio.h>   // For printf, fprintf, stderr
#include <stdlib.h>  // For EXIT_SUCCESS, EXIT_FAILURE
#include <string.h>  // For strcmp (potentially for log level comparison)

// Include project headers
#include "config.h"
#include "item.h"
#include "data_handler.h"
#include "item_processor.h"

// Basic logging setup (simplistic)
// In a real application, this would be more sophisticated.
static const char* G_LOG_LEVEL = "INFO"; // Global log level, can be set by setupMainLogging

// Simplified logging function for main.c context
// Avoids macro redefinition if headers were included differently.
// In a real project, a single logging utility would be used.
#include <stdarg.h>
static void app_log(const char* level, const char* func_name, const char* fmt, ...) {
    // Basic level filtering
    if (strcmp(G_LOG_LEVEL, "DEBUG") == 0 ||
        (strcmp(G_LOG_LEVEL, "INFO") == 0 && (strcmp(level, "INFO") == 0 || strcmp(level, "WARN") == 0 || strcmp(level, "ERROR") == 0 || strcmp(level, "CRITICAL") == 0)) ||
        (strcmp(G_LOG_LEVEL, "WARN") == 0 && (strcmp(level, "WARN") == 0 || strcmp(level, "ERROR") == 0 || strcmp(level, "CRITICAL") == 0)) ||
        (strcmp(G_LOG_LEVEL, "ERROR") == 0 && (strcmp(level, "ERROR") == 0 || strcmp(level, "CRITICAL") == 0)) ||
        (strcmp(G_LOG_LEVEL, "CRITICAL") == 0 && strcmp(level, "CRITICAL") == 0) ) {

        // Get current time - for more advanced logging
        // time_t now = time(NULL);
        // char time_buf[30];
        // strftime(time_buf, sizeof(time_buf), "%Y-%m-%d %H:%M:%S", localtime(&now));

        // Using stdout for INFO/DEBUG, stderr for WARN/ERROR/CRITICAL
        FILE* output_stream = (strcmp(level, "INFO") == 0 || strcmp(level, "DEBUG") == 0) ? stdout : stderr;

        fprintf(output_stream, "%s: [main:%s] ", level, func_name);
        va_list args;
        va_start(args, fmt);
        vfprintf(output_stream, fmt, args);
        va_end(args);
        fprintf(output_stream, "\n");
        fflush(output_stream);
    }
}

#define LOG_MAIN_INFO(fmt, ...) app_log("INFO", __func__, fmt, ##__VA_ARGS__)
#define LOG_MAIN_WARN(fmt, ...) app_log("WARN", __func__, fmt, ##__VA_ARGS__)
#define LOG_MAIN_ERROR(fmt, ...) app_log("ERROR", __func__, fmt, ##__VA_ARGS__)
#define LOG_MAIN_DEBUG(fmt, ...) app_log("DEBUG", __func__, fmt, ##__VA_ARGS__)
#define LOG_MAIN_CRITICAL(fmt, ...) app_log("CRITICAL", __func__, fmt, ##__VA_ARGS__)


/**
 * @brief Set up basic logging for the main application execution.
 */
void setupMainLogging() {
    // In a real C app, you might parse config_get_log_level()
    // and set G_LOG_LEVEL accordingly.
    // For this example, we assume G_LOG_LEVEL is set or defaults.
    G_LOG_LEVEL = config_get_log_level(); // Set global log level from config
    LOG_MAIN_INFO("Main logging initialized. Effective level: %s", G_LOG_LEVEL);
    // No complex handler/formatter setup as in Python's logging.basicConfig
}

/**
 * @brief Execute the main data processing pipeline.
 */
void runProcessingPipeline() {
    LOG_MAIN_INFO("Starting Sample Project C processing pipeline...");

    DataHandler* dataHandler = NULL;
    ItemProcessor* itemProcessor = NULL;
    Item** itemsToProcess = NULL;
    int num_items = 0;

    // Simulating a try-finally block for resource cleanup
    // C uses explicit cleanup, often with goto for error handling in complex functions
    // or by carefully managing scope and cleanup paths.

    // 1. Initialize components using configuration
    const char* dataPath = config_get_data_path();
    int threshold = config_get_threshold();

    LOG_MAIN_INFO("Config - Data Path: %s, Threshold: %d", dataPath, threshold);

    dataHandler = data_handler_create(dataPath);
    if (dataHandler == NULL) {
        LOG_MAIN_CRITICAL("Failed to create DataHandler.");
        goto cleanup; // Simplified error handling
    }

    itemProcessor = item_processor_create(threshold);
    if (itemProcessor == NULL) {
        LOG_MAIN_CRITICAL("Failed to create ItemProcessor.");
        goto cleanup;
    }

    // 2. Load data
    itemsToProcess = data_handler_loadItems(dataHandler, &num_items);
    if (itemsToProcess == NULL || num_items == 0) {
        LOG_MAIN_WARN("No items loaded from data source. Exiting pipeline.");
        goto cleanup; // Nothing more to do
    }
    LOG_MAIN_INFO("Successfully loaded %d items.", num_items);

    // 3. Process data items
    // We don't explicitly create processedItems/failedItems vectors like in Python
    // as items are processed in-place. We'll just count.
    int success_count = 0;
    int failure_count = 0;

    char item_buffer[256]; // For logging item details

    for (int i = 0; i < num_items; ++i) {
        if (itemsToProcess[i] == NULL) {
            LOG_MAIN_WARN("Encountered NULL item at index %d during processing.", i);
            failure_count++;
            continue;
        }
        item_toString(itemsToProcess[i], item_buffer, sizeof(item_buffer));
        LOG_MAIN_DEBUG("Passing item to processor: %s", item_buffer);

        bool success = item_processor_processItem(itemProcessor, itemsToProcess[i]);
        if (success) {
            success_count++;
        } else {
            item_toString(itemsToProcess[i], item_buffer, sizeof(item_buffer));
            LOG_MAIN_ERROR("Failed to process item: %s", item_buffer);
            failure_count++;
        }
    }
    LOG_MAIN_INFO("Processed %d items successfully, %d failed.", success_count, failure_count);

    // 4. Save processed data
    bool saveSuccess = data_handler_saveItems(dataHandler, (const Item* const*)itemsToProcess, num_items);
    if (saveSuccess) {
        LOG_MAIN_INFO("Processed items saved successfully.");
    } else {
        LOG_MAIN_ERROR("Failed to save processed items.");
    }

cleanup:
    LOG_MAIN_INFO("Sample Project C processing pipeline finished.");

    // Clean up dynamically allocated resources
    if (itemsToProcess != NULL) {
        for (int i = 0; i < num_items; ++i) {
            item_destroy(&itemsToProcess[i]); // Frees each item
        }
        free(itemsToProcess); // Frees the array of pointers
        itemsToProcess = NULL;
    }
    data_handler_destroy(&dataHandler);
    item_processor_destroy(&itemProcessor);
}

/**
 * @brief Main entry point for the C application.
 *
 * @param argc Number of command-line arguments.
 * @param argv Array of command-line argument strings.
 * @return int Exit code (EXIT_SUCCESS or EXIT_FAILURE).
 */
int main(int argc, char* argv[]) {
    (void)argc; // Suppress unused parameter warning
    (void)argv; // Suppress unused parameter warning

    setupMainLogging();
    runProcessingPipeline();

    return EXIT_SUCCESS;
}

// End of c_sample_project/src/main.c