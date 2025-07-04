// Sources/SampleProject2/main.swift

import Foundation

/// Executes the main data processing pipeline.
func runProcessingPipeline() {
    print("Starting Sample Project 2 processing pipeline...")

    do {
        // 1. Initialize components using configuration
        let dataPath = AppConfig.getDataPath()
        let threshold = AppConfig.getThreshold()

        let dataHandler = DataHandler(dataSourcePath: dataPath)
        let itemProcessor = ItemProcessor(threshold: threshold)

        // 2. Load data
        let itemsToProcess = dataHandler.loadItems()
        guard !itemsToProcess.isEmpty else {
            print("No items loaded. Exiting pipeline.")
            return
        }
        
        print("Successfully loaded \(itemsToProcess.count) items.")

        // 3. Process data items
        for item in itemsToProcess {
            print("Passing item to processor: \(item)")
            _ = itemProcessor.processItem(item: item)
        }

        // 4. Save processed data
        let saveSuccess = dataHandler.saveItems(items: itemsToProcess)
        if saveSuccess {
            print("Processed items saved successfully.")
        } else {
            print("Failed to save processed items.")
        }

    } catch {
        // Swift's structured error handling
        print("A critical error occurred: \(error.localizedDescription)")
    }
    
    print("Sample Project 2 processing pipeline finished.")
}

// Run the main function
runProcessingPipeline()