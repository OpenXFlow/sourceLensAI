// tests/sample_project2/Item.cs

namespace SampleProject2;

/// <summary>
/// Represents a single data item to be processed.
/// </summary>
public class Item
{
    public int ItemId { get; set; }
    public string Name { get; set; }
    public double Value { get; set; }
    public bool Processed { get; private set; }

    /// <summary>
    /// Initializes a new instance of the Item class.
    /// </summary>
    public Item(int itemId, string name, double value)
    {
        ItemId = itemId;
        Name = name;
        Value = value;
        Processed = false; // Default value
    }

    /// <summary>
    /// Sets the processed flag to true, updating the item's state.
    /// </summary>
    public void MarkAsProcessed()
    {
        Console.WriteLine($"Model Item {ItemId}: Marking '{Name}' as processed.");
        this.Processed = true;
    }

    /// <summary>
    /// Returns a user-friendly string representation of the item.
    /// </summary>
    public override string ToString()
    {
        string status = Processed ? "Processed" : "Pending";
        return $"Item(ID={ItemId}, Name='{Name}', Value={Value:F2}, Status={status})";
    }
}