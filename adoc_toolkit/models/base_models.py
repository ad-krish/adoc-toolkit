"""Base models for show command."""

from typing import Dict
from pydantic import BaseModel, Field


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