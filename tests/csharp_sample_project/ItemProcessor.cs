// tests/sample_project2/ItemProcessor.cs

namespace SampleProject2;

/// <summary>
/// Processes individual Item objects based on configured rules.
/// </summary>
public class ItemProcessor
{
    private readonly int _threshold;

    /// <summary>
    /// Initializes the ItemProcessor with a processing threshold.
    /// </summary>
    public ItemProcessor(int threshold)
    {
        _threshold = threshold;
        Console.WriteLine($"ItemProcessor initialized with threshold: {_threshold}");
    }

    /// <summary>
    /// Processes a single item, marking it as processed and applying logic.
    /// </summary>
    /// <param name="item">The Item object to process.</param>
    /// <returns>True if processing was successful.</returns>
    public bool ProcessItem(Item item)
    {
        Console.WriteLine($"Processing item ID: {item.ItemId}, Name: '{item.Name}', Value: {item.Value}");

        if (item.Value > _threshold)
        {
            Console.WriteLine($"Item '{item.Name}' (ID: {item.ItemId}) value {item.Value:F2} exceeds threshold {_threshold}.");
        }
        else
        {
            Console.WriteLine($"Item '{item.Name}' (ID: {item.ItemId}) value {item.Value:F2} is within threshold {_threshold}.");
        }

        item.MarkAsProcessed();
        return true;
    }
}