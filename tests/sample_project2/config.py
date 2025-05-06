# tests/sample_project2/config.py

"""Configuration settings for the Sample Project 2.

This module stores configuration values used by other parts of the application,
such as file paths or processing parameters.
"""

from typing import Final

# --- Constants for Configuration ---

# Simulate a path to a data file (used by DataHandler)
DATA_FILE_PATH: Final[str] = "data/items.json"

# A processing parameter (used by ItemProcessor)
PROCESSING_THRESHOLD: Final[int] = 100

# Example setting for logging level (could be used by main)
LOG_LEVEL: Final[str] = "INFO"


def get_data_path() -> str:
    """Returns the configured path for the data file.

    Returns:
        The path string for the data file.
    """
    # In a real app, this might involve more complex logic,
    # like checking environment variables first.
    print(f"Config: Providing data file path: {DATA_FILE_PATH}")
    return DATA_FILE_PATH


def get_threshold() -> int:
    """Returns the configured processing threshold.

    Returns:
        The integer threshold value.
    """
    print(f"Config: Providing processing threshold: {PROCESSING_THRESHOLD}")
    return PROCESSING_THRESHOLD

# End of tests/sample_project2/config.py