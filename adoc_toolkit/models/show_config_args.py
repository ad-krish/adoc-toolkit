"""Show config command arguments model."""


from pydantic import BaseModel, Field, model_validator


class ShowConfigArgs(BaseModel):
    """Arguments for show config command."""

    key: str | None = Field(default=None, description="Configuration key to show")
    list_all: bool = Field(default=False, description="List all configuration")

    @model_validator(mode="after")
    def validate_args(self) -> "ShowConfigArgs":
        """Validate that either key or list_all is specified."""
        if not self.key and not self.list_all:
            raise ValueError("Either key or --list flag must be specified")
        if self.key and self.list_all:
            raise ValueError("Cannot specify both key and --list flag")
        return self
