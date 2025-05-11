// cpp_sample_project/include/Config.h

#ifndef CONFIG_H
#define CONFIG_H

#include <string>
#include <iostream> // For std::cout in getter methods (demonstration)

/**
 * @brief Handles configuration settings for the Sample Project 2.
 *
 * This namespace stores configuration values used by other parts of the application,
 * such as file paths or processing parameters. It also provides static methods
 * to access these values, simulating the behavior of the Python config module.
 */
namespace Config {
    // --- Constants for Configuration ---

    /**
     * @brief Path to a (simulated) data file used by DataHandler.
     */
    const std::string DATA_FILE_PATH = "data/items.json";

    /**
     * @brief A processing parameter used by ItemProcessor.
     */
    const int PROCESSING_THRESHOLD = 100;

    /**
     * @brief Example setting for logging level (could be used by main).
     */
    const std::string LOG_LEVEL = "INFO";

    /**
     * @brief Return the configured path for the data file.
     *
     * @return const std::string& A constant reference to the path string for the data file.
     */
    inline const std::string& getDataPath() {
        // In a real app, this might involve more complex logic,
        // like checking environment variables first.
        // For demonstration, printing a message similar to the Python example.
        // Consider using a proper logging mechanism in a real application.
        // std::cout << "Config: Providing data file path: " << DATA_FILE_PATH << std::endl;
        return DATA_FILE_PATH;
    }

    /**
     * @brief Return the configured processing threshold.
     *
     * @return int The integer threshold value.
     */
    inline int getThreshold() {
        // For demonstration, printing a message similar to the Python example.
        // std::cout << "Config: Providing processing threshold: " << PROCESSING_THRESHOLD << std::endl;
        return PROCESSING_THRESHOLD;
    }

    /**
     * @brief Return the configured logging level.
     *
     * @return const std::string& A constant reference to the log level string.
     */
    inline const std::string& getLogLevel() {
        return LOG_LEVEL;
    }

} // namespace Config

#endif // CONFIG_H
// End of cpp_sample_project/include/Config.h