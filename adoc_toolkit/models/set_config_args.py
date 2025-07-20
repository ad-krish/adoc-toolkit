"""Set config command arguments model."""

from pydantic import BaseModel, Field, field_validator


class SetConfigArgs(BaseModel):
    """Arguments for set-config command."""

    key: str = Field(description="Configuration key to set")
    value: str = Field(description="Configuration value to set")

    @field_validator("key")
    @classmethod
    def validate_key(cls, v: str) -> str:
        """Validate configuration key format."""
        if not v:
            raise ValueError("Configuration key cannot be empty")
        if not v.replace(".", "").replace("_", "").isalnum():
            raise ValueError(
                "Configuration key must contain only letters, numbers, dots, "
                "and underscores"
            )
        return v
