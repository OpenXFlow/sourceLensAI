"""Main Logic Module for the Sample Project.

Demonstrates coordinating other modules (`config`, `utils`) via a class (`DataProcessor`).
Includes an example execution flow (`run_sample_processing`) when run directly.
This serves as an example input for the SourceLens tool.
"""

from typing import Any  # Import Any for dict type hint

# Use relative imports within the sample_project package
from . import config, utils


class DataProcessor:
    """Process data using configuration and utilities.

    Encapsulates the logic for initializing with settings from `config.py`,
    validating input data using `utils.validate_input`, formatting messages
    using `utils.format_message`, and simulating data submission.
    """

    # D107: Added docstring for __init__
    def __init__(self) -> None:
        """Initialize the DataProcessor with settings from the config module."""
        self.mode: str = config.PROCESSING_MODE
        self.endpoint: str = config.API_ENDPOINT
        # Example print statement for demonstration
        print(f"MainLogic: DataProcessor initialized in '{self.mode}' mode for endpoint '{self.endpoint}'.")

    # D102: Added docstring for submit_data
    def submit_data(self, user: str, data: dict[str, Any]) -> str:
        """Validate data using utils and format a submission message.

        Args:
            user: The username associated with the data submission.
            data: The data dictionary to process (expects an 'id' key for validation).

        Returns:
            A string indicating the success or error status, including a formatted log message.

        """
        print(f"MainLogic: Attempting to submit data for user '{user}'.")
        # Validate input first
        if utils.validate_input(data):
            # If valid, format success message and simulate submission
            data_id = data.get('id', 'N/A') # Provide a default if 'id' is missing
            message = f"Submitting valid data (ID: {data_id}) to {self.endpoint}"
            formatted_log = utils.format_message(user, message)
            # In a real application, an HTTP request would be made here
            print(f"MainLogic: SIMULATING submission log: {formatted_log}")
            return f"Success: {formatted_log}"
        # No explicit else needed, function returns if condition is met
        error_message = "Invalid data provided."
        formatted_log = utils.format_message(user, error_message)
        print(f"MainLogic: FAILED submission log: {formatted_log}")
        return f"Error: {formatted_log}"

# D103: Added docstring for run_sample_processing
def run_sample_processing() -> None:
    """Run an example workflow demonstrating the DataProcessor usage."""
    print("\n--- Running Sample Processing ---")
    processor = DataProcessor()

    valid_data: dict[str, Any] = {"id": 123, "value": "test"}
    invalid_data: dict[str, Any] = {"value": "bad"}

    result_valid = processor.submit_data(user="Alice", data=valid_data)
    print(f"Result (Alice): {result_valid}")

    result_invalid = processor.submit_data(user="Bob", data=invalid_data)
    print(f"Result (Bob): {result_invalid}")

    print("--- Sample Processing Complete ---\n")

# Standard Python idiom to allow running this script directly
if __name__ == "__main__":
    run_sample_processing()

# End of tests/sample_project/main_logic.py
