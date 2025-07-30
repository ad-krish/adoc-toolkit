"""Data sources handler for show command."""

from typing import Any

import pandas as pd
from rich.console import Console
from rich.table import Table

from ....http import ADOCHTTPClient
from ....models import DataSource, DataSourceResponse, DATA_SOURCE_COLUMNS


class DataSourceHandler:
    """Handler for data-sources resource type."""

    def __init__(self, http_client: ADOCHTTPClient):
        """Initialize the data sources handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client
        self.console = Console()

    def fetch_resources(self) -> list[DataSource]:
        """Fetch data sources from the API.

        Returns:
            List of DataSource objects

        Raises:
            Exception: If API request fails
        """
        response = self.http_client.get("/catalog-server/api/data-sources")

        if not response.is_success:
            raise Exception(f"Failed to fetch data-sources: {response.status_code}")

        # Parse response data
        response_data = response.json()
        data_response = DataSourceResponse.from_api_response(response_data)

        return data_response.data_sources

    def create_table(self, df: pd.DataFrame) -> Table:
        """Create a rich table for displaying data sources.

        Args:
            df: Pandas DataFrame with data sources

        Returns:
            Rich Table with data sources
        """
        table = Table(
            title="Data Sources",
            show_header=True,
            header_style="bold magenta",
            show_lines=True
        )

        # Define columns
        columns = [
            {"py_name": "assembly", "display": "Assembly", "style": "cyan", "no_wrap": True},
            {"py_name": "source", "display": "Source Type", "style": "green"},
            {"py_name": "assembly_id", "display": "Assembly ID", "style": "yellow", "justify": "right"},
            {"py_name": "schedule", "display": "Schedule", "style": "blue"},
            {"py_name": "is_virtual", "display": "Virtual", "style": "red", "justify": "center"},
            {"py_name": "is_protected_resource", "display": "Protected", "style": "red", "justify": "center"},
            {"py_name": "integration_id", "display": "Integration ID", "style": "white", "no_wrap": False},
        ]

        # Add columns to table
        for col in columns:
            kwargs = {k: v for k, v in col.items() if k not in ("py_name", "display")}
            table.add_column(col["display"], **kwargs)

        # Define formatters
        formatters = {
            "schedule": lambda v: v if v else "None",
            "is_virtual": lambda v: "Yes" if v else "No",
            "is_protected_resource": lambda v: "Yes" if v else "No",
            "assembly_id": str,
            "assembly": str,
            "source": str,
            "integration_id": str,
        }

        # Add rows to table
        for _, row in df.iterrows():
            values = []
            for col in columns:
                v = row[col["py_name"]]
                formatter = formatters.get(col["py_name"], str)
                values.append(formatter(v))
            table.add_row(*values)

        return table

    def display_resources(self, resources: list[DataSource]) -> None:
        """Display data sources in a table.

        Args:
            resources: List of DataSource objects
        """
        if not resources:
            self.console.print("No data-sources found.", style="yellow")
            return

        # Convert to DataFrame for efficient operations
        df = pd.DataFrame([r.model_dump() for r in resources])
        
        # Create and display table
        table = self.create_table(df)
        self.console.print(table)
        
        # Show summary
        self.console.print(f"\nTotal data-sources: {len(resources)}", style="green") 