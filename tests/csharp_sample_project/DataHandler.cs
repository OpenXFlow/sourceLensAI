// tests/sample_project2/DataHandler.cs

namespace SampleProject2;

/// <summary>
/// Manages loading and saving Item data.
/// Simulates interaction with a data source like a file or database.
/// </summary>
public class DataHandler
{
    private readonly string _dataSourcePath;

    /// <summary>
    /// Initializes the DataHandler with the path to the data source.
    /// </summary>
    public DataHandler(string dataSourcePath)
    {
        _dataSourcePath = dataSourcePath;
        Console.WriteLine($"DataHandler initialized for source: {_dataSourcePath}");
    }

    /// <summary>
    /// Simulates loading items from the data source.
    /// </summary>
    /// <returns>A list of Item objects.</returns>
    public List<Item> LoadItems()
    {
        Console.WriteLine($"Simulating loading items from {_dataSourcePath}...");
        var items = new List<Item>
        {
            new Item(1, "Gadget Alpha", 150.75),
            new Item(2, "Widget Beta", 85.0),
            new Item(3, "Thingamajig Gamma", 210.5),
            new Item(4, "Doohickey Delta", 55.2)
        };

        Console.WriteLine($"Loaded {items.Count} items.");
        return items;
    }

    /// <summary>
    /// Simulates saving processed items back to the data source.
    /// </summary>
    /// <param name="items">A list of Item objects to save.</param>
    /// <returns>True if saving was simulated successfully.</returns>
    public bool SaveItems(List<Item> items)
    {
        Console.WriteLine($"Simulating saving {items.Count} items to {_dataSourcePath}...");
        foreach (var item in items)
        {
            Console.WriteLine($"Saving item: {item}");
        }
        Console.WriteLine("Finished simulating save operation.");
        return true;
    }
}