"""HTTP request data model."""

from typing import Any, Optional, Union

from pydantic import BaseModel, Field, field_validator, model_validator


class HTTPRequestData(BaseModel):
    """HTTP request data model."""

    method: str = Field(description="HTTP method")
    endpoint: str = Field(description="API endpoint")
    headers: Optional[dict[str, str]] = Field(
        default=None, description="Request headers"
    )
    params: Optional[dict[str, Any]] = Field(
        default=None, description="Query parameters"
    )
    data: Optional[Union[dict[str, Any], str, bytes]] = Field(
        default=None, description="Request body data"
    )
    file_path: Optional[str] = Field(
        default=None, description="Path to file for request body"
    )

    @field_validator("method")
    @classmethod
    def validate_method(cls, v: str) -> str:
        """Validate HTTP method."""
        allowed_methods = {"GET", "POST", "PUT", "DELETE", "PATCH", "HEAD", "OPTIONS"}
        if v.upper() not in allowed_methods:
            raise ValueError(
                f"HTTP method must be one of: {', '.join(allowed_methods)}"
            )
        return v.upper()

    @model_validator(mode="after")
    def validate_data_and_file(self) -> "HTTPRequestData":
        """Validate that data and file_path are not both specified."""
        if self.data is not None and self.file_path is not None:
            raise ValueError("Cannot specify both data and file_path")
        return self
