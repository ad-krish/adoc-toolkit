"""HTTP response wrapper for ADOC API interactions."""

from typing import Any

import httpx

from .http_response_info import HTTPResponseInfo


class HTTPResponse:
    """Wrapper for HTTP responses with additional metadata."""

    def __init__(self, response: httpx.Response, request_info: dict[str, Any]):
        """Initialize HTTP response wrapper.

        Args:
            response: The httpx response object
            request_info: Information about the original request
        """
        self._response = response
        self.request_info = HTTPResponseInfo(
            status_code=response.status_code,
            headers=dict(response.headers),
            method=request_info.get("method", "UNKNOWN"),
            url=request_info.get("url", ""),
            endpoint=request_info.get("endpoint", ""),
            retries_attempted=request_info.get("retries_attempted", 0),
        )

    @property
    def status_code(self) -> int:
        """Get the HTTP status code."""
        return self.request_info.status_code

    @property
    def headers(self) -> dict[str, str]:
        """Get response headers."""
        return self.request_info.headers

    @property
    def text(self) -> str:
        """Get response body as text."""
        return self._response.text

    def json(self) -> Any:
        """Get response body as JSON.

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response is not valid JSON
        """
        try:
            return self._response.json()
        except Exception as e:
            raise ValueError(f"Invalid JSON response: {e}") from e

    @property
    def content(self) -> bytes:
        """Get response body as bytes."""
        return self._response.content

    @property
    def is_success(self) -> bool:
        """Check if request was successful (2xx status)."""
        return self.request_info.is_success

    @property
    def is_client_error(self) -> bool:
        """Check if request had client error (4xx status)."""
        return self.request_info.is_client_error

    @property
    def is_server_error(self) -> bool:
        """Check if request had server error (5xx status)."""
        return self.request_info.is_server_error

    def __str__(self) -> str:
        """String representation of response."""
        return f"HTTPResponse(status={self.status_code}, url={self.request_info.url})"
