"""Environment information model."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class EnvironmentInfo(BaseModel):
    """Environment configuration information."""

    name: str = Field(description="Environment name")
    base_url: str = Field(description="Base API URL")
    access_key: Optional[str] = Field(
        default=None, description="Access key for authentication"
    )
    secret_key: Optional[str] = Field(
        default=None, description="Secret key for authentication"
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must be a valid HTTP or HTTPS URL")
        return v.rstrip("/")
