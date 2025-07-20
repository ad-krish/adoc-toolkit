"""HTTP exceptions for ADOC API interactions."""

from typing import Optional

from .response import HTTPResponse


class HTTPError(Exception):
    """Exception raised for HTTP-related errors."""

    def __init__(self, message: str, response: Optional[HTTPResponse] = None):
        """Initialize HTTP error.

        Args:
            message: Error message
            response: Associated HTTP response if available
        """
        super().__init__(message)
        self.response = response
