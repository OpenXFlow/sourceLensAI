// tests/sample_project2/models/item.go
package models

import "fmt"

// Item represents a single data item to be processed.
type Item struct {
	ItemID    int
	Name      string
	Value     float64
	Processed bool
}

// NewItem is a constructor for the Item struct.
func NewItem(id int, name string, value float64) *Item {
	return &Item{
		ItemID:    id,
		Name:      name,
		Value:     value,
		Processed: false, // Default value
	}
}

// MarkAsProcessed sets the processed flag to true.
// It uses a pointer receiver (*Item) to modify the original struct.
func (i *Item) MarkAsProcessed() {
	fmt.Printf("Model Item %d: Marking '%s' as processed.\n", i.ItemID, i.Name)
	i.Processed = true
}

// String provides a user-friendly string representation, satisfying the fmt.Stringer interface.
func (i *Item) String() string {
	status := "Pending"
	if i.Processed {
		status = "Processed"
	}
	return fmt.Sprintf("Item(ID=%d, Name='%s', Value=%.2f, Status=%s)", i.ItemID, i.Name, i.Value, status)
}