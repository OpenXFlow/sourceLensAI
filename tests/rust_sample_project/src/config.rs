// rust_sample_project/src/config.rs

// For simplicity, we are using constants directly.
// In a more complex application, these might be loaded from a file or environment variables
// using crates like `config`, `dotenv`, or `serde`.

// No specific `use` statements needed for this simple config module.
// If logging were integrated, `use log::{info, debug};` might be here.

/**
 * @brief Path to a (simulated) data file used by DataHandler.
 */
pub const DATA_FILE_PATH: &str = "data/items.json";

/**
 * @brief A processing parameter used by ItemProcessor.
 */
pub const PROCESSING_THRESHOLD: i32 = 100;

/**
 * @brief Example setting for logging level (could be used by main for a logging crate).
 */
pub const LOG_LEVEL: &str = "INFO";

/**
 * @brief Return the configured path for the data file.
 *
 * This function demonstrates accessing a configuration value.
 *
 * @return &'static str A static string slice representing the data file path.
 */
pub fn get_data_path() -> &'static str {
    // In a real app, this might involve more complex logic.
    // For demonstration, mirroring Python's print statement (commented out).
    // Consider using the `log` crate for actual logging.
    // println!("Config: Providing data file path: {}", DATA_FILE_PATH);
    DATA_FILE_PATH
}

/**
 * @brief Return the configured processing threshold.
 *
 * @return i32 The integer threshold value.
 */
pub fn get_threshold() -> i32 {
    // println!("Config: Providing processing threshold: {}", PROCESSING_THRESHOLD);
    PROCESSING_THRESHOLD
}

/**
 * @brief Return the configured logging level.
 *
 * @return &'static str A static string slice representing the log level.
 */
pub fn get_log_level() -> &'static str {
    // println!("Config: Providing log level: {}", LOG_LEVEL);
    LOG_LEVEL
}

// End of rust_sample_project/src/config.rs