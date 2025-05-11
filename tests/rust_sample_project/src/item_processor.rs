// rust_sample_project/src/item_processor.rs

use std::io::{self, Write}; // For println, if not using a logging crate

// Import Item struct from the item module
use crate::item::Item;

/**
 * @struct ItemProcessor
 * @brief Processes individual Item objects based on configured rules.
 */
pub struct ItemProcessor {
    threshold: i32,
    // A proper logger instance would be used in a real application.
}

impl ItemProcessor {
    /**
     * @brief Constructs a new ItemProcessor object.
     *
     * Initializes the ItemProcessor with a processing threshold.
     *
     * @param threshold The numerical threshold. Items with a value above this
     *                  threshold might be handled differently.
     * @return ItemProcessor A new ItemProcessor instance.
     */
    pub fn new(threshold: i32) -> Self {
        // For demonstration, mirroring Python's direct logging.
        // Use the `log` crate for actual logging.
        println!("INFO: ItemProcessor initialized with threshold: {}", threshold);
        ItemProcessor { threshold }
    }

    /**
     * @brief Process a single item.
     *
     * Marks the item as processed and applies logic based on the threshold.
     * In this example, it simply logs whether the item's value exceeds
     * the threshold.
     *
     * @param item A mutable reference to the Item object to process.
     * @return bool True if processing was successful (always true in this simulation).
     *              Rust functions typically return Result<T, E> for operations that can fail.
     *              Returning bool here to match Python example's simplicity.
     */
    pub fn process_item(&self, item: &mut Item) -> bool {
        // Type checking `isinstance(item, Item)` from Python is handled by Rust's
        // static type system at compile time, as `item` is explicitly typed as `&mut Item`.

        // Using format! macro for constructing the debug string, then println!
        // This is similar to f-strings but separates formatting from printing.
        let debug_msg = format!(
            "DEBUG: Processing item ID: {}, Name: '{}', Value: {:.2}",
            item.item_id, item.name, item.value
        );
        println!("{}", debug_msg);

        // Apply some simple logic based on the threshold
        if item.value > self.threshold as f64 { // Cast threshold to f64 for comparison
            println!(
                "INFO: Item '{}' (ID: {}) value {:.2} exceeds threshold {}.",
                item.name, item.item_id, item.value, self.threshold
            );
            // Potential place for different actions based on threshold
        } else {
            println!(
                "INFO: Item '{}' (ID: {}) value {:.2} is within threshold {}.",
                item.name, item.item_id, item.value, self.threshold
            );
        }

        // Mark the item as processed using its own method
        item.mark_as_processed();

        // Simulate successful processing
        true
    }
}

// End of rust_sample_project/src/item_processor.rs