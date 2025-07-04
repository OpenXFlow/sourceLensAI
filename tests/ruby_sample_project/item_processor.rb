# tests/sample_project2/item_processor.rb

require_relative 'item'

#
# Processes individual Item objects based on configured rules.
#
class ItemProcessor
  # Initializes the ItemProcessor with a processing threshold.
  # @param threshold [Integer] The numerical threshold for processing logic.
  def initialize(threshold)
    @threshold = threshold
    puts "ItemProcessor initialized with threshold: #{@threshold}"
  end

  # Processes a single item, marking it as processed and applying logic.
  # @param item [Item] The Item object to process.
  # @return [Boolean] True if processing was successful.
  def process_item(item)
    puts "Processing item ID: #{item.item_id}, Name: '#{item.name}', Value: #{item.value}"

    if item.value > @threshold
      puts "Item '#{item.name}' (ID: #{item.item_id}) value #{item.value} exceeds threshold #{@threshold}."
    else
      puts "Item '#{item.name}' (ID: #{item.item_id}) value #{item.value} is within threshold #{@threshold}."
    end

    item.mark_as_processed
    true
  end
end