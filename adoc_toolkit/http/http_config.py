"""HTTP configuration model."""

from enum import Enum
from typing import Optional
from urllib.parse import urlparse

from pydantic import BaseModel, Field, field_validator


class ResponseType(str, Enum):
    """HTTP response formatting types."""

    JSON = "json"
    TABLE = "table"
    CSV = "csv"


class HTTPResponseConfig(BaseModel):
    """HTTP response configuration settings."""

    type: ResponseType = Field(
        default=ResponseType.JSON,
        description="Response formatting type (json|table|csv)",
    )


class HTTPConfig(BaseModel):
    """HTTP client configuration settings."""

    timeout: int = Field(default=120, description="Request timeout in seconds")
    retries: int = Field(default=3, description="Number of retry attempts")
    proxy: Optional[str] = Field(default=None, description="HTTP proxy URL")
    response: HTTPResponseConfig = Field(
        default_factory=HTTPResponseConfig, description="Response configuration"
    )

    @field_validator("timeout")
    @classmethod
    def validate_timeout(cls, v: int) -> int:
        """Validate timeout with custom error messages."""
        if not isinstance(v, int):
            raise ValueError("Timeout must be an integer")
        if v <= 0:
            raise ValueError("Timeout must be a positive integer")
        if v > 3600:
            raise ValueError("Timeout cannot exceed 3600 seconds")
        return v

    @field_validator("retries")
    @classmethod
    def validate_retries(cls, v: int) -> int:
        """Validate retries with custom error messages."""
        if not isinstance(v, int):
            raise ValueError("Retries must be an integer")
        if v < 0:
            raise ValueError("Retries must be non-negative")
        if v > 10:
            raise ValueError("Retries cannot exceed 10")
        return v

    @field_validator("response")
    @classmethod
    def validate_response_config(cls, v: HTTPResponseConfig) -> HTTPResponseConfig:
        """Validate response configuration."""
        return v

    @field_validator("proxy")
    @classmethod
    def validate_proxy(cls, v: Optional[str]) -> Optional[str]:
        """Validate proxy URL format."""
        if v is None or v.lower() == "none":
            return None

        if not v.startswith(("http://", "https://")):
            raise ValueError("Proxy must be a valid HTTP or HTTPS URL")

        try:
            parsed = urlparse(v)
            if not parsed.netloc:
                raise ValueError("Proxy URL must include host")
        except Exception as e:
            raise ValueError(f"Invalid proxy URL: {e}") from e

        return v
