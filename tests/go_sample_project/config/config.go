// tests/sample_project2/config/config.go
package config

import "fmt"

// Constants for Configuration (un-exported)
const (
	dataFilePath       = "data/items.json"
	processingThreshold = 100
	logLevel           = "INFO"
)

// GetDataPath returns the configured path for the data file.
func GetDataPath() string {
	fmt.Printf("Config: Providing data file path: %s\n", dataFilePath)
	return dataFilePath
}

// GetThreshold returns the configured processing threshold.
func GetThreshold() int {
	fmt.Printf("Config: Providing processing threshold: %d\n", processingThreshold)
	return processingThreshold
}

// GetLogLevel returns the configured logging level.
func GetLogLevel() string {
    return logLevel
}