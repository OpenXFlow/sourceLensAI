# tests/sample_project2/main.rb

#
# Main execution script for Sample Project 2.
# Orchestrates the loading, processing, and saving of data items.
#

require_relative 'config'
require_relative 'data_handler'
require_relative 'item_processor'

# Executes the main data processing pipeline.
def run_processing_pipeline
  puts 'Starting Sample Project 2 processing pipeline...'

  begin
    # 1. Initialize components using configuration
    data_path = AppConfig.get_data_path
    threshold = AppConfig.get_threshold

    data_handler = DataHandler.new(data_path)
    item_processor = ItemProcessor.new(threshold)

    # 2. Load data
    items_to_process = data_handler.load_items
    if items_to_process.empty?
      puts 'No items loaded. Exiting pipeline.'
      return
    end

    puts "Successfully loaded #{items_to_process.length} items."

    # 3. Process data items
    items_to_process.each do |item|
      puts "Passing item to processor: #{item}"
      item_processor.process_item(item)
    end

    # 4. Save processed data
    save_success = data_handler.save_items(items_to_process)
    if save_success
      puts 'Processed items saved successfully.'
    else
      puts 'Failed to save processed items.'
    end

  rescue StandardError => e
    # Catch any standard error for a graceful exit
    puts "A critical error occurred: #{e.message}"
    puts e.backtrace.join("\n")
  ensure
    puts 'Sample Project 2 processing pipeline finished.'
  end
end

# Run the main function
run_processing_pipeline