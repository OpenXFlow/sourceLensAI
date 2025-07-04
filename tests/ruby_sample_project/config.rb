# tests/sample_project2/config.rb

#
# Configuration settings for the Sample Project 2.
# This module stores configuration values used by other parts of the application.
#
module AppConfig
  # --- Constants for Configuration ---
  DATA_FILE_PATH = 'data/items.json'.freeze
  PROCESSING_THRESHOLD = 100
  LOG_LEVEL = 'INFO'.freeze

  # Returns the configured path for the data file.
  # @return [String] The path string for the data file.
  def self.get_data_path
    puts "Config: Providing data file path: #{DATA_FILE_PATH}"
    DATA_FILE_PATH
  end

  # Returns the configured processing threshold.
  # @return [Integer] The integer threshold value.
  def self.get_threshold
    puts "Config: Providing processing threshold: #{PROCESSING_THRESHOLD}"
    PROCESSING_THRESHOLD
  end
end