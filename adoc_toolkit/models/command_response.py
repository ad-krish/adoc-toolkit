"""Command response models."""

from typing import Any

from pydantic import BaseModel, Field


class CommandResponse(BaseModel):
    """Model for command execution response."""

    success: bool = Field(description="Whether the command executed successfully")
    message: str = Field(description="Response message")
    data: dict[str, Any] | None = Field(default=None, description="Response data")


class CompletionItem(BaseModel):
    """Model for auto-completion items with descriptions."""

    text: str = Field(description="Completion text to insert")
    description: str | None = Field(
        default=None, description="Description to display in completion menu"
    )
    display_text: str | None = Field(
        default=None,
        description="Text to display in completion menu (if different from text)",
    )

    def __post_init__(self) -> None:
        """Set display_text to text if not provided."""
        if self.display_text is None:
            self.display_text = self.text
