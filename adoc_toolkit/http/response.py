"""HTTP response wrapper for ADOC API interactions."""

from typing import Any

import aiohttp

from .http_response_info import HTTPResponseInfo


class HTTPResponse:
    """Wrapper for HTTP responses with additional metadata."""

    def __init__(self, response: aiohttp.ClientResponse, request_info: dict[str, Any]):
        """Initialize HTTP response wrapper.

        Args:
            response: The aiohttp response object
            request_info: Information about the original request
        """
        self._response = response
        self.request_info = HTTPResponseInfo(
            status_code=response.status,
            headers=dict(response.headers),
            method=request_info.get("method", "UNKNOWN"),
            url=request_info.get("url", ""),
            endpoint=request_info.get("endpoint", ""),
            retries_attempted=request_info.get("retries_attempted", 0),
        )
        self._text = None
        self._content = None
        self._json_data = None

    @property
    def status_code(self) -> int:
        """Get the HTTP status code."""
        return self.request_info.status_code

    @property
    def headers(self) -> dict[str, str]:
        """Get response headers."""
        return self.request_info.headers

    async def text(self) -> str:
        """Get response body as text."""
        if self._text is None:
            self._text = await self._response.text()
        return self._text

    async def json(self) -> Any:
        """Get response body as JSON.

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response is not valid JSON
        """
        if self._json_data is None:
            try:
                self._json_data = await self._response.json()
            except Exception as e:
                raise ValueError(f"Invalid JSON response: {e}") from e
        return self._json_data

    async def content(self) -> bytes:
        """Get response body as bytes."""
        if self._content is None:
            self._content = await self._response.read()
        return self._content

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

    async def close(self) -> None:
        """Close the response."""
        if not self._response.closed:
            await self._response.release()
