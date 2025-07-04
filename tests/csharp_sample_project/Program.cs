// tests/sample_project2/Program.cs

namespace SampleProject2;

/// <summary>
/// Main execution class for Sample Project 2.
/// </summary>
public class Program
{
    /// <summary>
    /// Main entry point for the application.
    /// </summary>
    public static void Main(string[] args)
    {
        RunProcessingPipeline();
    }

    /// <summary>
    /// Executes the main data processing pipeline.
    /// </summary>
    public static void RunProcessingPipeline()
    {
        Console.WriteLine("Starting Sample Project 2 processing pipeline...");

        try
        {
            // 1. Initialize components using configuration
            string dataPath = AppConfig.GetDataPath();
            int threshold = AppConfig.GetThreshold();

            var dataHandler = new DataHandler(dataPath);
            var itemProcessor = new ItemProcessor(threshold);

            // 2. Load data
            List<Item> itemsToProcess = dataHandler.LoadItems();
            if (itemsToProcess.Count == 0)
            {
                Console.WriteLine("No items loaded. Exiting pipeline.");
                return;
            }

            Console.WriteLine($"Successfully loaded {itemsToProcess.Count} items.");

            // 3. Process data items
            foreach (var item in itemsToProcess)
            {
                Console.WriteLine($"Passing item to processor: {item}");
                itemProcessor.ProcessItem(item);
            }
            
            // 4. Save processed data
            bool saveSuccess = dataHandler.SaveItems(itemsToProcess);
            if(saveSuccess)
            {
                Console.WriteLine("Processed items saved successfully.");
            }
            else
            {
                Console.WriteLine("Failed to save processed items.");
            }
        }
        catch (Exception ex)
        {
            Console.WriteLine($"A critical error occurred: {ex.Message}");
            // In a real app, log the full exception: Console.WriteLine(ex.ToString());
        }
        finally
        {
            Console.WriteLine("Sample Project 2 processing pipeline finished.");
        }
    }
}