// c_sample_project/src/config.c

#include "config.h" // Corresponding header file
#include <stdio.h>  // For printf (if uncommented for demonstration)

/**
 * @brief Return the configured path for the data file.
 *
 * This function demonstrates accessing a configuration value.
 * In a real application, this might involve more complex logic,
 * such as reading from a configuration file or environment variables.
 * The current implementation returns a preprocessor-defined constant.
 *
 * @return const char* A pointer to a constant string representing the data file path.
 *                     The string is a literal and should not be modified or freed.
 */
const char* config_get_data_path(void) {
    // For demonstration, printing a message similar to the Python example.
    // Consider using a proper logging mechanism in a real application.
    // printf("Config: Providing data file path: %s\n", DATA_FILE_PATH);
    return DATA_FILE_PATH;
}

/**
 * @brief Return the configured processing threshold.
 *
 * The current implementation returns a preprocessor-defined constant.
 *
 * @return int The integer threshold value.
 */
int config_get_threshold(void) {
    // For demonstration, printing a message similar to the Python example.
    // printf("Config: Providing processing threshold: %d\n", PROCESSING_THRESHOLD);
    return PROCESSING_THRESHOLD;
}

/**
 * @brief Return the configured logging level.
 *
 * The current implementation returns a preprocessor-defined constant.
 *
 * @return const char* A pointer to a constant string representing the log level.
 *                     The string is a literal and should not be modified or freed.
 */
const char* config_get_log_level(void) {
    // printf("Config: Providing log level: %s\n", LOG_LEVEL);
    return LOG_LEVEL;
}

// End of c_sample_project/src/config.c