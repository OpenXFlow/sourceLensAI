# The MIT License (MIT)
# Copyright (c) 2025 Jozef Darida  (LinkedIn/Xing)
# For full license text, see the LICENSE file in the project root.

"""Custom exceptions used within the SourceLens utilities, particularly for LLM interactions."""

from typing import Optional


class LlmApiError(Exception):
    """Custom exception for LLM API call failures."""

    def __init__(self, message: str, status_code: Optional[int] = None, provider: Optional[str] = None) -> None:
        """Initialize the LLM API Error.

        Args:
            message: The error message.
            status_code: Optional HTTP status code associated with the error.
            provider: Optional name of the LLM provider that caused the error.
        """
        self.status_code = status_code
        self.provider = provider
        status_str = f" (Status: {status_code})" if status_code else ""
        provider_str = provider or "Unknown"  # Ensure provider_str is always a string
        super().__init__(f"LLM API Error ({provider_str}): {message}{status_str}")


# End of src/sourcelens/utils/_exceptions.py
