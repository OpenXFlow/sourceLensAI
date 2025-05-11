// rust_sample_project/src/main.rs

// Declare modules that are part of this crate (files in the same directory or subdirectories)
mod config;
mod data_handler;
mod item;
mod item_processor;

// Bring specific items into scope for easier use
use crate::config::{get_data_path, get_threshold, get_log_level}; // Corrected: use config::get_log_level
use crate::data_handler::DataHandler;
use crate::item::Item;
use crate::item_processor::ItemProcessor;

use std::process::exit; // For program termination with a code

// For simplistic logging similar to Python's basicConfig,
// we'll just use println! and eprintln!
// A more robust solution would use the `log` crate and an implementation like `env_logger`.

/**
 * @brief Set up basic logging for the main application execution.
 *
 * In this simple version, it primarily prints an informational message.
 * It retrieves the log level from config but doesn't fully implement
 * log level filtering as `basicConfig` would.
 */
fn setup_main_logging() {
    // Retrieve log level from config
    let log_level_str = get_log_level(); // Use the imported function

    // In a real app, initialize a logger here, e.g., env_logger::init();
    // or another logger based on log_level_str.
    // For now, just print the intended level.
    println!(
        "INFO: [main:setup_main_logging] Main logging setup. Effective level from config: {}",
        log_level_str
    );
    // This is a placeholder. Actual log level filtering would require a logging crate.
}

/**
 * @brief Execute the main data processing pipeline.
 *
 * Orchestrates the loading, processing, and saving of data items using
 * configuration settings and dedicated handler/processor classes.
 *
 * @return Result<(), String> Ok(()) on success, or an Err(String) on failure.
 */
fn run_processing_pipeline() -> Result<(), String> {
    println!("INFO: [main:run_processing_pipeline] Starting Sample Project Rust processing pipeline...");

    // 1. Initialize components using configuration
    let data_path: String = get_data_path().to_string(); // Get path and convert to owned String
    let threshold: i32 = get_threshold();

    println!(
        "INFO: [main:run_processing_pipeline] Config - Data Path: {}, Threshold: {}",
        data_path, threshold
    );

    let data_handler = DataHandler::new(data_path); // data_path is moved here
    let item_processor = ItemProcessor::new(threshold);

    // 2. Load data
    let mut items_to_process: Vec<Item> = match data_handler.load_items() {
        Ok(items) => items,
        Err(e) => {
            // Using eprintln! for errors, similar to Python's logger.error or logger.critical
            eprintln!("CRITICAL: [main:run_processing_pipeline] Failed to load items: {}", e);
            return Err(format!("Data loading failed: {}", e));
        }
    };

    if items_to_process.is_empty() {
        println!("WARNING: [main:run_processing_pipeline] No items loaded from data source. Exiting pipeline.");
        println!("INFO: [main:run_processing_pipeline] Sample Project Rust processing pipeline finished.");
        return Ok(());
    }

    println!(
        "INFO: [main:run_processing_pipeline] Successfully loaded {} items.",
        items_to_process.len()
    );

    // 3. Process data items
    let mut successful_processing_count = 0;
    let mut failed_processing_count = 0;

    for item_ref_mut in items_to_process.iter_mut() { // Iterate with mutable references
        // Log the item before processing
        // println!("DEBUG: [main:run_processing_pipeline] Passing item to processor: {}", item_ref_mut);
        
        if item_processor.process_item(item_ref_mut) {
            successful_processing_count += 1;
        } else {
            // This path is not taken in the current ItemProcessor::process_item logic,
            // but kept for structural similarity.
            eprintln!(
                "ERROR: [main:run_processing_pipeline] Failed to process item: {}",
                item_ref_mut
            );
            failed_processing_count += 1;
        }
    }

    println!(
        "INFO: [main:run_processing_pipeline] Processed {} items successfully, {} failed.",
        successful_processing_count,
        failed_processing_count
    );

    // 4. Save processed data
    // The `items_to_process` vector now contains the (potentially) modified items.
    match data_handler.save_items(&items_to_process) {
        Ok(_) => {
            println!("INFO: [main:run_processing_pipeline] Processed items saved successfully.");
        }
        Err(e) => {
            eprintln!("ERROR: [main:run_processing_pipeline] Failed to save processed items: {}", e);
            // Decide if this should be a critical error for the pipeline
        }
    }

    println!("INFO: [main:run_processing_pipeline] Sample Project Rust processing pipeline finished.");
    Ok(())
}

/**
 * @brief Main entry point for the application.
 */
fn main() {
    setup_main_logging();

    if let Err(e) = run_processing_pipeline() {
        eprintln!("CRITICAL: [main:main] Pipeline execution failed: {}", e);
        exit(1); // Exit with a non-zero code to indicate failure
    }
    // Implicitly returns 0 (success) if run_processing_pipeline is Ok
}

// End of rust_sample_project/src/main.rs