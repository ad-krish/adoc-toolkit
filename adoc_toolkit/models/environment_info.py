"""Environment information model."""


from pydantic import BaseModel, Field, field_validator


class EnvironmentInfo(BaseModel):
    """Environment configuration information."""

    name: str = Field(description="Environment name")
    base_url: str = Field(description="Base API URL")
    access_key: str | None = Field(
        default=None, description="Access key for authentication"
    )
    secret_key: str | None = Field(
        default=None, description="Secret key for authentication"
    )
    timezone: str = Field(
        default="UTC",
        description="Timezone for datetime fields (e.g., UTC, US/Eastern, Europe/London)",
    )

    @field_validator("base_url")
    @classmethod
    def validate_base_url(cls, v: str) -> str:
        """Validate base URL format."""
        if not v.startswith(("http://", "https://")):
            raise ValueError("Base URL must be a valid HTTP or HTTPS URL")
        return v.rstrip("/")

    @field_validator("timezone")
    @classmethod
    def validate_timezone(cls, v: str) -> str:
        """Validate timezone string."""
        try:
            from zoneinfo import ZoneInfo
            # Test if timezone is valid
            ZoneInfo(v)
            return v
        except Exception:
            # Fallback: try importing pytz if zoneinfo fails
            try:
                import pytz
                pytz.timezone(v)
                return v
            except Exception:
                raise ValueError(
                    f"Invalid timezone: {v}. Use IANA timezone names like UTC, US/Eastern, Europe/London"
                )
