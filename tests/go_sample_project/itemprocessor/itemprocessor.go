// tests/sample_project2/itemprocessor/itemprocessor.go
package itemprocessor

import (
	"fmt"
	"log"
	"sourcelens/sampleproject2/models"
)

// ItemProcessor processes individual Item objects.
type ItemProcessor struct {
	threshold int
}

// NewItemProcessor is a constructor for the ItemProcessor.
func NewItemProcessor(threshold int) *ItemProcessor {
	log.Printf("ItemProcessor initialized with threshold: %d", threshold)
	return &ItemProcessor{threshold: threshold}
}

// ProcessItem processes a single item, marking it as processed.
// Takes a pointer to an Item to allow modification.
func (p *ItemProcessor) ProcessItem(item *models.Item) (bool, error) {
	log.Printf("Processing item ID: %d, Name: '%s', Value: %.2f", item.ItemID, item.Name, item.Value)

	if item.Value > float64(p.threshold) {
		fmt.Printf("Item '%s' (ID: %d) value %.2f exceeds threshold %d.\n", item.Name, item.ItemID, item.Value, p.threshold)
	} else {
		fmt.Printf("Item '%s' (ID: %d) value %.2f is within threshold %d.\n", item.Name, item.ItemID, item.Value, p.threshold)
	}

	item.MarkAsProcessed()
	return true, nil
}