"""HTTP response information model."""

from pydantic import BaseModel, Field


class HTTPResponseInfo(BaseModel):
    """HTTP response information model."""

    status_code: int = Field(description="HTTP status code")
    headers: dict[str, str] = Field(description="Response headers")
    method: str = Field(description="Original request method")
    url: str = Field(description="Request URL")
    endpoint: str = Field(description="Original endpoint")
    retries_attempted: int = Field(default=0, description="Number of retries attempted")

    @property
    def is_success(self) -> bool:
        """Check if response indicates success (2xx status)."""
        return 200 <= self.status_code < 300

    @property
    def is_client_error(self) -> bool:
        """Check if response indicates client error (4xx status)."""
        return 400 <= self.status_code < 500

    @property
    def is_server_error(self) -> bool:
        """Check if response indicates server error (5xx status)."""
        return 500 <= self.status_code < 600
