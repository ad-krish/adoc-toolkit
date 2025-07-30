"""Data source models for show command."""

from typing import Any, List, Dict

import pandas as pd
from pydantic import BaseModel, Field

from .base_models import ColumnDefinition, ResourceColumnSet


class ColumnDefinition(BaseModel):
    """Definition of a column for filtering and sorting."""
    
    name: str = Field(description="Internal column name (used for filtering/sorting)")
    display_name: str = Field(description="Human-readable display name")
    description: str = Field(description="Column description")
    filterable: bool = Field(default=True, description="Whether column can be filtered")
    sortable: bool = Field(default=True, description="Whether column can be sorted")
    data_type: str = Field(description="Data type (string, int, bool, etc.)")


class ResourceColumnSet(BaseModel):
    """Set of columns for a specific resource type."""
    
    resource_type: str = Field(description="Resource type (e.g., data-sources)")
    columns: Dict[str, ColumnDefinition] = Field(description="Column definitions")
    
    def get_filterable_columns(self) -> list[str]:
        """Get list of filterable column names."""
        return [col.name for col in self.columns.values() if col.filterable]
    
    def get_sortable_columns(self) -> list[str]:
        """Get list of sortable column names."""
        return [col.name for col in self.columns.values() if col.sortable]
    
    def get_column_names(self) -> list[str]:
        """Get all column names."""
        return list(self.columns.keys())


class DataSource(BaseModel):
    """Model for a data source from the catalog API."""

    assembly: str = Field(description="Assembly name")
    source: str = Field(description="Source type (e.g., SNOWFLAKE, ORACLE)")
    assembly_id: int = Field(alias="assemblyId", description="Assembly ID")
    schedule: str | None = Field(default=None, description="Schedule configuration")
    assets: list[Any] = Field(default_factory=list, description="Associated assets")
    rules: list[Any] = Field(default_factory=list, description="Associated rules")
    is_virtual: bool = Field(
        alias="isVirtual",
        description="Whether this is a virtual data source"
    )
    integration_id: str = Field(alias="integrationId", description="Integration ID")
    is_protected_resource: bool = Field(
        alias="isProtectedResource",
        description="Whether this is a protected resource"
    )
    created_by: str | None = Field(
        alias="createdBy",
        default=None,
        description="Creator information"
    )

    model_config = {
        "populate_by_name": True
    }


class DataSourceResponse(BaseModel):
    """Model for data sources API response."""

    data_sources: list[DataSource] = Field(description="List of data sources")
    df: pd.DataFrame | None = Field(default=None, description="Pandas DataFrame")

    model_config = {
        "populate_by_name": True,
        "arbitrary_types_allowed": True
    }

    @classmethod
    def from_api_response(
        cls, response_data: list[dict[str, Any]]
    ) -> "DataSourceResponse":
        """Create DataSourceResponse from API response data.

        Args:
            response_data: Raw API response data

        Returns:
            DataSourceResponse object
        """
        data_sources = [DataSource.model_validate(item) for item in response_data]
        
        # Create pandas DataFrame for efficient operations
        df = pd.DataFrame([ds.model_dump() for ds in data_sources])
        
        return cls(data_sources=data_sources, df=df)


class FilterCondition(BaseModel):
    """Model for a single filter condition."""

    column: str = Field(description="Column name to filter on")
    operator: str = Field(description="Comparison operator (=, !=, >, <, >=, <=)")
    value: str = Field(description="Value to compare against")

    @classmethod
    def parse(cls, filter_str: str) -> "FilterCondition":
        """Parse a filter condition from string format 'col=value'."""
        import re
        
        # Match patterns like: col=value, col>value, col<=value, etc.
        pattern = r"^([a-zA-Z_][a-zA-Z0-9_]*)\s*([=!<>]+)\s*(.+)$"
        match = re.match(pattern, filter_str.strip())
        
        if not match:
            raise ValueError(f"Invalid filter format: {filter_str}")
        
        column, operator, value = match.groups()
        return cls(column=column, operator=operator, value=value)


class SortSpec(BaseModel):
    """Model for a single sort specification."""

    column: str = Field(description="Column name to sort on")
    reverse: bool = Field(default=False, description="Sort in descending order")

    @classmethod
    def parse(cls, sort_str: str) -> "SortSpec":
        """Parse a sort specification from string format 'col' or '-col'."""
        sort_str = sort_str.strip()
        if sort_str.startswith("-"):
            return cls(column=sort_str[1:], reverse=True)
        return cls(column=sort_str)


class ShowCommandArgs(BaseModel):
    """Model for show command arguments."""

    resource_type: str | None = Field(default=None, description="Resource type to show (e.g., data-sources)")
    help_flag: bool = Field(default=False, description="Show help")
    filter_str: str | None = Field(default=None, description="Filter string")
    sort_str: str | None = Field(default=None, description="Sort string")
    stats: bool = Field(default=False, description="Show column statistics")

    @classmethod
    def from_args(cls, args: list[str]) -> "ShowCommandArgs":
        """Create ShowCommandArgs from command line arguments.

        Args:
            args: Command line arguments

        Returns:
            ShowCommandArgs object
        """
        parsed = cls()

        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--help":
                parsed.help_flag = True
            elif arg == "--filter" and i + 1 < len(args):
                parsed.filter_str = args[i + 1]
                i += 1
            elif arg == "--sort" and i + 1 < len(args):
                parsed.sort_str = args[i + 1]
                i += 1
            elif arg == "--stats":
                parsed.stats = True
            elif not arg.startswith("--") and parsed.resource_type is None:
                # First non-flag argument is the resource type
                parsed.resource_type = arg
            i += 1

        return parsed


# Column definitions for data sources
DATA_SOURCE_COLUMNS = ResourceColumnSet(
    resource_type="data-sources",
    columns={
        "assembly": ColumnDefinition(
            name="assembly",
            display_name="Assembly",
            description="Assembly name",
            data_type="string"
        ),
        "source": ColumnDefinition(
            name="source", 
            display_name="Source Type",
            description="Source type (e.g., SNOWFLAKE, ORACLE)",
            data_type="string"
        ),
        "assembly_id": ColumnDefinition(
            name="assembly_id",
            display_name="Assembly ID", 
            description="Assembly ID",
            data_type="int"
        ),
        "schedule": ColumnDefinition(
            name="schedule",
            display_name="Schedule",
            description="Schedule configuration",
            data_type="string"
        ),
        "is_virtual": ColumnDefinition(
            name="is_virtual",
            display_name="Virtual",
            description="Whether this is a virtual data source",
            data_type="bool"
        ),
        "integration_id": ColumnDefinition(
            name="integration_id",
            display_name="Integration ID",
            description="Integration ID",
            data_type="string"
        ),
        "is_protected_resource": ColumnDefinition(
            name="is_protected_resource",
            display_name="Protected",
            description="Whether this is a protected resource",
            data_type="bool"
        ),
        "created_by": ColumnDefinition(
            name="created_by",
            display_name="Created By",
            description="Creator information",
            data_type="string"
        ),
        # Note: assets and rules are not filterable/sortable due to being lists
        "assets": ColumnDefinition(
            name="assets",
            display_name="Assets",
            description="Associated assets",
            filterable=False,
            sortable=False,
            data_type="list"
        ),
        "rules": ColumnDefinition(
            name="rules",
            display_name="Rules", 
            description="Associated rules",
            filterable=False,
            sortable=False,
            data_type="list"
        )
    }
)


# Note: RESOURCE_REGISTRY is now defined in registry.py to avoid circular imports
