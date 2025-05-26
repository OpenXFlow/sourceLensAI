// Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
//
// This program is free software: you can redistribute it and/or modify
// it under the terms of the GNU General Public License as published by
// the Free Software Foundation, either version 3 of the License, or
// (at your option) any later version.
//
// This program is distributed in the hope that it will be useful,
// but WITHOUT ANY WARRANTY; without even the implied warranty of
// MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
// GNU General Public License for more details.
//
// You should have received a copy of the GNU General Public License
// along with this program. If not, see <https://www.gnu.org/licenses/>.

package com.sampleproject;

import java.io.FileNotFoundException; // More specific than IOException for this case
import java.io.IOException; // General I/O
import java.util.List;
import java.util.logging.ConsoleHandler;
import java.util.logging.FileHandler;
import java.util.logging.Formatter;
import java.util.logging.Handler;
import java.util.logging.Level;
import java.util.logging.Logger;
import java.util.logging.SimpleFormatter;

/**
 * Main execution script for the Sample Project.
 * Orchestrates the loading, processing, and saving of data items using
 * configuration settings and dedicated handler/processor classes.
 */
public class Main {
    // Setup a global logger for the Main class itself, can be used by static methods too
    private static final Logger MAIN_LOGGER = Logger.getLogger(Main.class.getName());

    /**
     * Sets up basic logging for the main script execution.
     * Configures a console handler and optionally a file handler.
     */
    public static void setupMainLogging() {
        Logger rootLogger = Logger.getLogger(""); // Get the root logger
        Handler[] handlers = rootLogger.getHandlers();
        // Remove default console_handler if it exists, to avoid duplicate messages
        for (Handler handler : handlers) {
            if (handler instanceof ConsoleHandler) {
                rootLogger.removeHandler(handler);
            }
        }

        Level logLevel = Level.INFO; // Default log level
        try {
            logLevel = Level.parse(Config.LOG_LEVEL.toUpperCase());
        } catch (IllegalArgumentException e) {
            MAIN_LOGGER.log(Level.WARNING, "Invalid LOG_LEVEL defined in Config: {0}. Defaulting to INFO.", Config.LOG_LEVEL);
        }

        rootLogger.setLevel(logLevel); // Set level on root logger

        Formatter formatter = new SimpleFormatter(); // Default formatter: "%1$tb %1$td, %1$tY %1$tl:%1$tM:%1$tS %1$Tp %2$s%n%4$s: %5$s%6$s%n"
                                                 // To match Python: "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
                                                 // Requires custom formatter or careful use of LogRecord fields in SimpleFormatter pattern.
                                                 // For simplicity, using SimpleFormatter. Can be enhanced.

        ConsoleHandler consoleHandler = new ConsoleHandler();
        consoleHandler.setLevel(logLevel);
        console_handler.setFormatter(formatter);
        rootLogger.addHandler(consoleHandler);

        try {
            // Optional: Add file logging
            FileHandler fileHandler = new FileHandler("logs/sample_project_java.log", true); // Append mode
            fileHandler.setLevel(logLevel);
            fileHandler.setFormatter(formatter);
            rootLogger.addHandler(fileHandler);
            MAIN_LOGGER.log(Level.INFO, "File logging initialized to logs/sample_project_java.log");
        } catch (IOException e) {
            MAIN_LOGGER.log(Level.SEVERE, "Failed to initialize file logger.", e);
        }
        // Suppress excessive logging from libraries if needed (optional)
        // Logger.getLogger("some.library.package").setLevel(Level.WARNING);
    }

    /**
     * Executes the main data processing pipeline.
     */
    public static void runProcessingPipeline() {
        // Use a logger specific to this method/class if preferred, or the static MAIN_LOGGER
        Logger logger = Logger.getLogger(Main.class.getName() + ".runProcessingPipeline");
        logger.log(Level.INFO, "Starting Sample Project processing pipeline...");

        try {
            // 1. Initialize components using configuration
            String dataPath = Config.getDataPath();
            int threshold = Config.getThreshold();

            DataHandler dataHandler = new DataHandler(dataPath);
            ItemProcessor itemProcessor = new ItemProcessor(threshold);

            // 2. Load data
            List<Item> itemsToProcess = dataHandler.loadItems();
            if (itemsToProcess.isEmpty()) {
                logger.log(Level.WARNING, "No items loaded from data source. Exiting pipeline.");
                return;
            }
            logger.log(Level.INFO, "Successfully loaded {0} items.", itemsToProcess.size());

            // 3. Process data items
            List<Item> processedItems = new ArrayList<>();
            List<Item> failedItems = new ArrayList<>();

            for (Item item : itemsToProcess) {
                logger.log(Level.FINE, "Passing item to processor: {0}", item);
                boolean success = itemProcessor.processItem(item);
                if (success) {
                    processedItems.add(item);
                } else {
                    logger.log(Level.SEVERE, "Failed to process item: {0}", item);
                    failedItems.add(item);
                }
            }
            logger.log(Level.INFO, "Processed {0} items successfully, {1} failed.",
                       new Object[]{processedItems.size(), failedItems.size()});

            // 4. Save processed data (original list is passed in Python example, assuming all items attempted)
            boolean saveSuccess = dataHandler.saveItems(itemsToProcess);

            if (saveSuccess) {
                logger.log(Level.INFO, "Processed items saved successfully (simulated).");
            } else {
                logger.log(Level.SEVERE, "Failed to save processed items (simulated).");
            }

        } catch (FileNotFoundException e) { // More specific for data file
            logger.log(Level.SEVERE, "Configuration error: Data file path not found.", e);
        } catch (IOException e) { // Broader I/O for other file operations
            logger.log(Level.SEVERE, "An OS or I/O error occurred during pipeline execution.", e);
        } catch (IllegalArgumentException | NullPointerException | ClassCastException e) {
            // Catches common data processing or programming errors
            logger.log(Level.SEVERE, "A runtime error occurred during pipeline execution.", e);
        }
        // No generic `catch (Exception e)` to be more specific.
        finally {
            logger.log(Level.INFO, "Sample Project processing pipeline finished.");
        }
    }

    /**
     * Standard Java entry point.
     * @param args Command line arguments (not used).
     */
    public static void main(String[] args) {
        setupMainLogging(); // Configure logging first
        runProcessingPipeline();
    }
}
// End of com/sampleproject/Main.java