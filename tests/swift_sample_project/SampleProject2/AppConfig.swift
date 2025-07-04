// Sources/SampleProject2/AppConfig.swift

import Foundation

/// Stores configuration settings used by other parts of the application.
public enum AppConfig {
    
    /// Simulates a path to a data file (used by DataHandler).
    public static let dataFilePath = "data/items.json"
    
    /// A processing parameter (used by ItemProcessor).
    public static let processingThreshold = 100
    
    /// Example setting for logging level.
    public static let logLevel = "INFO"
    
    /// Returns the configured path for the data file.
    public static func getDataPath() -> String {
        print("Config: Providing data file path: \(dataFilePath)")
        return dataFilePath
    }
    
    /// Returns the configured processing threshold.
    public static func getThreshold() -> Int {
        print("Config: Providing processing threshold: \(processingThreshold)")
        return processingThreshold
    }
}