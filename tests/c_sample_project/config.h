// c_sample_project/include/config.h

#ifndef CONFIG_H
#define CONFIG_H

// --- Constants for Configuration ---

/**
 * @brief Path to a (simulated) data file used by DataHandler.
 */
#define DATA_FILE_PATH "data/items.json"

/**
 * @brief A processing parameter used by ItemProcessor.
 */
#define PROCESSING_THRESHOLD 100

/**
 * @brief Example setting for logging level (could be used by main).
 */
#define LOG_LEVEL "INFO"


// --- Function Declarations for Accessing Configuration ---

/**
 * @brief Return the configured path for the data file.
 *
 * This function demonstrates accessing a configuration value.
 * In a real application, this might involve more complex logic,
 * such as reading from a configuration file or environment variables.
 *
 * @return const char* A pointer to a constant string representing the data file path.
 *                     The string is a literal and should not be modified or freed.
 */
const char* config_get_data_path(void);

/**
 * @brief Return the configured processing threshold.
 *
 * @return int The integer threshold value.
 */
int config_get_threshold(void);

/**
 * @brief Return the configured logging level.
 *
 * @return const char* A pointer to a constant string representing the log level.
 *                     The string is a literal and should not be modified or freed.
 */
const char* config_get_log_level(void);

#endif // CONFIG_H
// End of c_sample_project/include/config.h