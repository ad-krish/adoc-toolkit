"""Get command arguments model."""

from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class QueryParameter(BaseModel):
    """Model for API query parameter definition."""

    type: str = Field(description="Parameter data type")
    description: str = Field(description="Parameter description")
    default: Optional[Any] = Field(default=None, description="Default value")
    options: Optional[list[str]] = Field(
        default=None, description="Valid options for enum types"
    )


class APIEndpoint(BaseModel):
    """Model for API endpoint definition."""

    url: str = Field(description="Endpoint URL")
    description: str = Field(description="Endpoint description")
    query_params: dict[str, QueryParameter] = Field(
        default_factory=dict, description="Query parameters"
    )
    response_type: str = Field(description="Expected response type")


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

    @field_validator("endpoint")
    @classmethod
    def validate_endpoint(cls, v: str) -> str:
        """Validate endpoint name."""
        if not v:
            raise ValueError("Endpoint name cannot be empty")
        return v.lower()

    @field_validator("query_params")
    @classmethod
    def validate_query_params(
        cls, v: Optional[dict[str, Any]]
    ) -> Optional[dict[str, Any]]:
        """Validate query parameters."""
        if v is None:
            return v

        # Ensure all values are strings, integers, or booleans
        for key, value in v.items():
            if not isinstance(value, (str, int, bool, float)):
                raise ValueError(
                    f"Query parameter {key} must be string, integer, boolean, or float"
                )

        return v
