// Sources/SampleProject2/Item.swift

import Foundation

/// Represents a single data item to be processed.
public class Item: CustomStringConvertible {
    public let itemId: Int
    public let name: String
    public let value: Double
    public var processed: Bool

    /// Initializes a new instance of the Item class.
    public init(itemId: Int, name: String, value: Double, processed: Bool = false) {
        self.itemId = itemId
        self.name = name
        self.value = value
        self.processed = processed
    }

    /// Sets the processed flag to true, updating the item's state.
    public func markAsProcessed() {
        print("Model Item \(self.itemId): Marking '\(self.name)' as processed.")
        self.processed = true
    }

    /// Returns a user-friendly string representation of the item.
    public var description: String {
        let status = processed ? "Processed" : "Pending"
        return "Item(ID=\(itemId), Name='\(name)', Value=\(String(format: "%.2f", value)), Status=\(status))"
    }
}