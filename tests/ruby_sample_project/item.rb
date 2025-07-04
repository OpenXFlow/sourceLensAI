# tests/sample_project2/item.rb

#
# Represents a single data item to be processed.
#
class Item
  attr_reader :item_id, :name, :value
  attr_accessor :processed

  # Initializes a new instance of the Item class.
  # @param item_id [Integer] A unique integer identifier for the item.
  # @param name [String] The name of the item.
  # @param value [Float] A numerical value associated with the item.
  def initialize(item_id, name, value)
    @item_id = item_id
    @name = name
    @value = value
    @processed = false # Default value
  end

  # Sets the processed flag to true.
  def mark_as_processed
    puts "Model Item #{@item_id}: Marking '#{@name}' as processed."
    @processed = true
  end

  # Returns a user-friendly string representation of the item.
  # @return [String] A string detailing the item's properties.
  def to_s
    status = @processed ? 'Processed' : 'Pending'
    "Item(ID=#{@item_id}, Name='#{@name}', Value=#{format('%.2f', @value)}, Status=#{status})"
  end
end