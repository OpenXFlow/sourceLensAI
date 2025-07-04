# tests/sample_project2/data_handler.rb

require_relative 'item'

#
# Manages loading and saving Item data.
# Simulates interaction with a data source like a file or database.
#
class DataHandler
  # Initializes the DataHandler with the path to the data source.
  # @param data_source_path [String] The configured path to the data source.
  def initialize(data_source_path)
    @data_source_path = data_source_path
    puts "DataHandler initialized for source: #{@data_source_path}"
  end

  # Simulates loading items from the data source.
  # @return [Array<Item>] An array of Item objects.
  def load_items
    puts "Simulating loading items from #{@data_source_path}..."
    simulated_data = [
      { item_id: 1, name: 'Gadget Alpha', value: 150.75 },
      { item_id: 2, name: 'Widget Beta', value: 85.0 },
      { item_id: 3, name: 'Thingamajig Gamma', value: 210.5 },
      { item_id: 4, name: 'Doohickey Delta', value: 55.2 }
    ]

    items = simulated_data.map do |data|
      Item.new(data[:item_id], data[:name], data[:value])
    end

    puts "Loaded #{items.length} items."
    items
  end

  # Simulates saving processed items back to the data source.
  # @param items [Array<Item>] An array of Item objects to save.
  # @return [Boolean] True if saving was simulated successfully.
  def save_items(items)
    puts "Simulating saving #{items.length} items to #{@data_source_path}..."
    items.each do |item|
      puts "Saving item: #{item}"
    end
    puts 'Finished simulating save operation.'
    true
  end
end