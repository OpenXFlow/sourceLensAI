"""Custom exceptions used within the SourceLens utilities, particularly for LLM interactions.
"""

from typing import Optional


class LlmApiError(Exception):
    """Custom exception for LLM API call failures."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        provider: Optional[str] = None
    ) -> None:
        """Initialize the LLM API Error."""
        self.status_code = status_code
        self.provider = provider
        status_str = f" (Status: {status_code})" if status_code else ""
        super().__init__(f"LLM API Error ({provider or 'Unknown'}): {message}{status_str}")

# End of src/sourcelens/utils/_exceptions.py
