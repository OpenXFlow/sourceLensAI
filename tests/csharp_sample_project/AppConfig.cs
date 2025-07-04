// tests/sample_project2/AppConfig.cs

namespace SampleProject2;

/// <summary>
/// Stores configuration settings used by other parts of the application.
/// </summary>
public static class AppConfig
{
    // --- Constants for Configuration ---

    /// <summary>
    /// Simulates a path to a data file (used by DataHandler).
    /// </summary>
    public const string DataFilePath = "data/items.json";

    /// <summary>
    /// A processing parameter (used by ItemProcessor).
    /// </summary>
    public const int ProcessingThreshold = 100;

    /// <summary>
    /// Example setting for logging level.
    /// </summary>
    public const string LogLevel = "INFO";

    /// <summary>
    /// Returns the configured path for the data file.
    /// </summary>
    public static string GetDataPath()
    {
        Console.WriteLine($"Config: Providing data file path: {DataFilePath}");
        return DataFilePath;
    }

    /// <summary>
    /// Returns the configured processing threshold.
    /// </summary>
    public static int GetThreshold()
    {
        Console.WriteLine($"Config: Providing processing threshold: {ProcessingThreshold}");
        return ProcessingThreshold;
    }
}