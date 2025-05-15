# Copyright (C) 2025 Jozef Darida (LinkedIn/Xing)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

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
