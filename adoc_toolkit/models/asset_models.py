"""Pydantic models for asset-related data structures."""


from pydantic import BaseModel, ConfigDict, Field


class AssetType(BaseModel):
    """Model for asset type information."""

    name: str = Field(description="Name of the asset type")
    id: str | int | None = Field(
        default=None, description="ID of the asset type"
    )
    description: str | None = Field(
        default=None, description="Description of the asset type"
    )


class Asset(BaseModel):
    """Model for asset information."""

    model_config = ConfigDict(populate_by_name=True)

    id: str | int = Field(description="Unique asset identifier")
    name: str = Field(description="Name of the asset")
    uid: str = Field(description="Unique asset UID")
    asset_type: AssetType = Field(
        alias="assetType", description="Type information for the asset"
    )
    description: str | None = Field(default=None, description="Asset description")
    created_at: str | None = Field(
        default=None, alias="createdAt", description="Creation timestamp"
    )
    updated_at: str | None = Field(
        default=None, alias="updatedAt", description="Last update timestamp"
    )


class AssetSearchResponse(BaseModel):
    """Model for asset search API response."""

    model_config = ConfigDict(populate_by_name=True)

    assets: list[Asset] = Field(description="List of found assets")
    total_count: int | None = Field(
        default=None, alias="totalCount", description="Total number of assets"
    )
    page: int | None = Field(default=None, description="Current page number")
    page_size: int | None = Field(
        default=None, alias="pageSize", description="Number of assets per page"
    )


class AssetSearchRequest(BaseModel):
    """Model for asset search request parameters."""

    model_config = ConfigDict(populate_by_name=True)

    name: str = Field(description="Asset name to search for")
    asset_type: str | None = Field(
        default=None, alias="assetType", description="Filter by asset type"
    )
    limit: int | None = Field(
        default=None, description="Maximum number of results to return"
    )
    offset: int | None = Field(default=None, description="Number of results to skip")
