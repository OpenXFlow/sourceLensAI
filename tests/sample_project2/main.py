# tests/sample_project2/main.py

"""Main execution script for Sample Project 2.

Orchestrates the loading, processing, and saving of data items using
configuration settings and dedicated handler/processor classes.
"""

import logging

# Use relative imports for components within this package
from . import config
from .data_handler import DataHandler
from .item_processor import ItemProcessor
from .models import Item # Import the Item model for type hinting


def setup_main_logging() -> None:
    """Sets up basic logging for the main script execution."""
    # Simple console logging for demonstration
    logging.basicConfig(
        level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO),
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # Suppress excessive logging from libraries if needed (optional)
    # logging.getLogger("some_library").setLevel(logging.WARNING)


def run_processing_pipeline() -> None:
    """Executes the main data processing pipeline."""
    logger = logging.getLogger(__name__) # Get logger instance for this function
    logger.info("Starting Sample Project 2 processing pipeline...")

    try:
        # 1. Initialize components using configuration
        data_path = config.get_data_path()
        threshold = config.get_threshold()

        data_handler = DataHandler(data_source_path=data_path)
        item_processor = ItemProcessor(threshold=threshold)

        # 2. Load data
        items_to_process: list[Item] = data_handler.load_items()
        if not items_to_process:
            logger.warning("No items loaded from data source. Exiting pipeline.")
            return

        logger.info("Successfully loaded %d items.", len(items_to_process))

        # 3. Process data items
        processed_items: list[Item] = []
        failed_items: list[Item] = []

        for item in items_to_process:
            logger.debug("Passing item to processor: %s", item)
            success = item_processor.process_item(item)
            if success:
                processed_items.append(item)
            else:
                logger.error("Failed to process item: %s", item)
                failed_items.append(item) # Keep track of failed items if needed

        logger.info("Processed %d items successfully, %d failed.", len(processed_items), len(failed_items))

        # 4. Save processed data (passing the list of successfully processed items)
        # Note: In this example, items are modified in-place (processed flag)
        # so we save the original list reference (which now contains modified items)
        # or specifically the `processed_items` list if we only wanted to save successful ones.
        # Here, we save all items that were attempted, including those marked processed.
        save_success = data_handler.save_items(items_to_process)

        if save_success:
            logger.info("Processed items saved successfully.")
        else:
            logger.error("Failed to save processed items.")

    except FileNotFoundError as e:
         logger.critical("Configuration error: Data file path not found. %s", e, exc_info=True)
    except Exception as e:
        # Catch any other unexpected errors during the pipeline execution
        logger.critical("An unexpected error occurred during pipeline execution: %s", e, exc_info=True)

    finally:
        logger.info("Sample Project 2 processing pipeline finished.")


# Standard Python entry point
if __name__ == "__main__":
    setup_main_logging()
    run_processing_pipeline()

# End of tests/sample_project2/main.py