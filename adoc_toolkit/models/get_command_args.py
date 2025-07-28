"""Models for get command arguments and API reference."""

from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator


class QueryParameter(BaseModel):
    """Model for API query parameter definition."""

    type: str = Field(description="Parameter type")
    description: str = Field(description="Parameter description")
    default: Optional[Any] = Field(default=None, description="Default value")
    options: Optional[list[str]] = Field(default=None, description="Available options")


class APIEndpoint(BaseModel):
    """Model for API endpoint definition."""

    url: str = Field(description="Endpoint URL")
    description: str = Field(description="Endpoint description")
    query_params: dict[str, QueryParameter] = Field(description="Query parameters")
    response_type: str = Field(description="Response type")


class APIReference(BaseModel):
    """Model for API reference configuration."""

    version: str = Field(description="API reference version")
    description: str = Field(description="API reference description")
    endpoints: dict[str, APIEndpoint] = Field(description="Available endpoints")


class GetCommandArgs(BaseModel):
    """Model for get command arguments."""

    endpoint: str = Field(description="API endpoint name")
    query_params: Optional[dict[str, Any]] = Field(
        default=None, description="Query parameters"
    )
    path_params: Optional[dict[str, str]] = Field(
        default=None, description="Path parameters"
    )

    @field_validator("query_params")
    @classmethod
    def validate_query_params(
        cls, v: Optional[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Validate query parameters."""
        if v is None:
            return v
        for key, value in v.items():
            if not isinstance(key, str):
                raise ValueError("Query parameter keys must be strings")
        return v

    @field_validator("path_params")
    @classmethod
    def validate_path_params(
        cls, v: Optional[dict[str, str]]
    ) -> Optional[dict[str, str]]:
        """Validate path parameters."""
        if v is None:
            return v
        for key, value in v.items():
            if not isinstance(value, str):
                raise ValueError(f"Path parameter {key} must be a string")
        return v
