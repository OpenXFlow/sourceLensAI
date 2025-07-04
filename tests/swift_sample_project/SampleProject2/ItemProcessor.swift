// Sources/SampleProject2/ItemProcessor.swift

import Foundation

/// Processes individual Item objects based on configured rules.
public class ItemProcessor {
    private let threshold: Int

    /// Initializes the ItemProcessor with a processing threshold.
    public init(threshold: Int) {
        self.threshold = threshold
        print("ItemProcessor initialized with threshold: \(self.threshold)")
    }

    /// Processes a single item, marking it as processed and applying logic.
    /// - Parameter item: The Item object to process.
    /// - Returns: True if processing was successful.
    public func processItem(item: Item) -> Bool {
        print("Processing item ID: \(item.itemId), Name: '\(item.name)', Value: \(item.value)")

        if item.value > Double(self.threshold) {
            print("Item '\(item.name)' (ID: \(item.itemId)) value \(item.value) exceeds threshold \(self.threshold).")
        } else {
            print("Item '\(item.name)' (ID: \(item.itemId)) value \(item.value) is within threshold \(self.threshold).")
        }

        item.markAsProcessed()
        return true
    }
}