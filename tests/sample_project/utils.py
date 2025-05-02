"""Utility Module for the Sample Project.

Provides reusable helper functions for tasks like message formatting
and basic data validation, intended as an example for SourceLens analysis.
"""

import time
from typing import Any  # Import Any for dict type hint


# D103: Added docstring for format_message
def format_message(name: str, message: str) -> str:
    """Format a simple message string including a timestamp and username.

    Args:
        name: The username to include in the message.
        message: The core message content.

    Returns:
        A formatted string, e.g., "[YYYY-MM-DD HH:MM:SS] User 'name' says: message".

    """
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    formatted = f"[{timestamp}] User '{name}' says: {message}"
    # Example print statement (often used for debugging)
    print(f"Utils: Formatted message: {formatted}")
    return formatted

# D103: Added docstring for validate_input
def validate_input(data: dict[str, Any]) -> bool:
    """Perform a basic validation check on input data dictionary.

    Checks specifically if the dictionary contains an 'id' key
    and if the value associated with that key is an integer.

    Args:
        data: The input dictionary to validate.

    Returns:
        True if data contains an integer 'id', False otherwise.

    """
    # Check key existence and type safely using .get() and isinstance
    is_valid = isinstance(data.get("id"), int)
    # Example print statement for demonstration/debugging
    print(f"Utils: Validating input data... Result: {is_valid}")
    return is_valid

# End of tests/sample_project/utils.py
