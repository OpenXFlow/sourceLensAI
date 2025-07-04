// tests/sample_project2/main.go
package main

import (
	"log"
	"sourcelens/sampleproject2/config"
	"sourcelens/sampleproject2/datahandler"
	"sourcelens/sampleproject2/itemprocessor"
)

// runProcessingPipeline executes the main data processing logic.
func runProcessingPipeline() {
	log.Println("Starting Sample Project 2 processing pipeline...")

	// 1. Initialize components using configuration
	dataPath := config.GetDataPath()
	threshold := config.GetThreshold()

	dh := datahandler.NewDataHandler(dataPath)
	ip := itemprocessor.NewItemProcessor(threshold)

	// 2. Load data
	itemsToProcess, err := dh.LoadItems()
	if err != nil {
		log.Fatalf("Failed to load items: %v", err)
	}

	if len(itemsToProcess) == 0 {
		log.Println("No items loaded. Exiting pipeline.")
		return
	}
	log.Printf("Successfully loaded %d items.", len(itemsToProcess))

	// 3. Process data items
	for i := range itemsToProcess {
		item := &itemsToProcess[i] // Get a pointer to the item in the slice
		log.Printf("Passing item to processor: %s", item.String())
		_, err := ip.ProcessItem(item)
		if err != nil {
			log.Printf("Failed to process item %d: %v", item.ItemID, err)
		}
	}

	// 4. Save processed data
	saveSuccess, err := dh.SaveItems(itemsToProcess)
	if err != nil {
		log.Fatalf("Error during save operation: %v", err)
	}
	if saveSuccess {
		log.Println("Processed items saved successfully.")
	} else {
		log.Println("Failed to save processed items.")
	}

	log.Println("Sample Project 2 processing pipeline finished.")
}

func main() {
	// In a real app, you would configure the logger here based on config.GetLogLevel()
	runProcessingPipeline()
}