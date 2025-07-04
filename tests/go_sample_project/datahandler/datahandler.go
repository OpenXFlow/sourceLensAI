// tests/sample_project2/datahandler/datahandler.go
package datahandler

import (
	"fmt"
	"log"
	"sourcelens/sampleproject2/models"
)

// DataHandler manages loading and saving Item data.
type DataHandler struct {
	dataSourcePath string
}

// NewDataHandler is a constructor for the DataHandler.
func NewDataHandler(path string) *DataHandler {
	log.Printf("DataHandler initialized for source: %s", path)
	return &DataHandler{dataSourcePath: path}
}

// LoadItems simulates loading items from the data source.
// It returns a slice of Items and an error (idiomatic Go).
func (dh *DataHandler) LoadItems() ([]models.Item, error) {
	log.Printf("Simulating loading items from %s...", dh.dataSourcePath)
	
	items := []models.Item{
		*models.NewItem(1, "Gadget Alpha", 150.75),
		*models.NewItem(2, "Widget Beta", 85.0),
		*models.NewItem(3, "Thingamajig Gamma", 210.5),
		*models.NewItem(4, "Doohickey Delta", 55.2),
	}

	log.Printf("Loaded %d items.", len(items))
	return items, nil // Return nil for the error to indicate success
}

// SaveItems simulates saving processed items.
func (dh *DataHandler) SaveItems(items []models.Item) (bool, error) {
	log.Printf("Simulating saving %d items to %s...", len(items), dh.dataSourcePath)
	for _, item := range items {
		log.Printf("Saving item: %s", item.String())
	}
	log.Println("Finished simulating save operation.")
	return true, nil
}