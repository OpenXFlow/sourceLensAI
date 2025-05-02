"""Configuration Module for the Sample Project.

Stores simple settings or constants used by other modules within the sample project.
This serves as an example input for the SourceLens tool.
"""

# A simple configuration setting (using type hints)
API_ENDPOINT: str = "https://example.com/api/v1"
DEFAULT_TIMEOUT_SECONDS: int = 10

# Another setting
PROCESSING_MODE: str = "standard"

def get_timeout() -> int:
    """Return the configured timeout value."""
    # Example print statement, often removed in real applications
    print(f"Config: Returning timeout: {DEFAULT_TIMEOUT_SECONDS}")
    return DEFAULT_TIMEOUT_SECONDS

# End of tests/sample_project/config.py
