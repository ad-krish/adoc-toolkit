"""Command response model."""

from typing import Any, Optional

from pydantic import BaseModel, Field


class CommandResponse(BaseModel):
    """Response model for command execution."""

    success: bool = Field(description="Whether command executed successfully")
    message: Optional[str] = Field(default=None, description="Response message")
    data: Optional[dict[str, Any]] = Field(default=None, description="Response data")
    continue_session: bool = Field(
        default=True, description="Whether to continue interactive session"
    )
