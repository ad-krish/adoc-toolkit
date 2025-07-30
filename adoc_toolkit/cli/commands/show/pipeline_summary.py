"""Pipeline summary handler for show command."""

from datetime import datetime

import pandas as pd
from rich.console import Console
from rich.table import Table

from ....http import ADOCHTTPClient
from ....models.pipeline_models import PipelineSummary, PipelineSummaryResponse


class PipelineSummaryHandler:
    """Handler for pipeline-summary resource type."""

    def __init__(self, http_client: ADOCHTTPClient):
        """Initialize the pipeline summary handler.

        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client
        self.console = Console()

    def fetch_resources(self) -> list[PipelineSummary]:
        """Fetch pipeline summaries from the API.

        Returns:
            List of PipelineSummary objects

        Raises:
            Exception: If API request fails
        """
        # Build the URL with query parameters
        url = "/torch-pipeline/api/pipelines/summary"
        params = {
            "page": 0,
            "size": 100
        }

        response = self.http_client.get(url, params=params)

        if not response.is_success:
            raise Exception(f"Failed to fetch pipeline-summary: {response.status_code}")

        # Parse response data with better error handling
        try:
            response_data = response.json()
        except Exception as e:
            # Log the raw response for debugging
            raw_response = response.text if hasattr(response, 'text') else str(response)
            raise Exception(
                f"Invalid JSON response: {e}. Raw response: {raw_response[:200]}..."
            ) from e

        pipeline_response = PipelineSummaryResponse.from_api_response(response_data)

        return pipeline_response.pipelines

    def create_table(self, df: pd.DataFrame) -> Table:
        """Create a rich table for displaying pipeline summaries.

        Args:
            df: Pandas DataFrame with pipeline summaries

        Returns:
            Rich Table with pipeline summaries
        """
        table = Table(
            title="Pipeline Summaries",
            show_header=True,
            header_style="bold magenta",
            show_lines=True
        )

        # Define columns
        columns = [
            {"py_name": "id", "display": "Id", "style": "cyan", "no_wrap": True},
            {"py_name": "name", "display": "Name", "style": "green", "no_wrap": True},
            {"py_name": "owner", "display": "Owner", "style": "blue"},
            {"py_name": "source_type", "display": "Source", "style": "yellow"},
            {
                "py_name": "total_runs_count",
                "display": "# Runs",
                "style": "white",
                "justify": "right"
            },
            {
                "py_name": "latest_run_result",
                "display": "Last Run Status",
                "style": "red",
                "justify": "center"
            },
            {
                "py_name": "latest_run_finished_at",
                "display": "Finished Time in UTC",
                "style": "white"
            },
        ]

        # Add columns to table
        for col in columns:
            kwargs = {k: v for k, v in col.items() if k not in ("py_name", "display")}
            table.add_column(col["display"], **kwargs)

        # Define formatters
        def format_datetime(value):
            """Format datetime value for display."""
            if pd.isna(value) or value is None:
                return "N/A"
            if isinstance(value, str):
                return value
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%d %H:%M:%S UTC")
            return str(value)

        def format_run_status(value):
            """Format run status for display."""
            if pd.isna(value) or value is None:
                return "N/A"
            return str(value)

        formatters = {
            "id": str,
            "name": str,
            "owner": str,
            "source_type": str,
            "total_runs_count": str,
            "latest_run_result": format_run_status,
            "latest_run_finished_at": format_datetime,
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

    def display_resources(self, resources: list[PipelineSummary]) -> None:
        """Display pipeline summaries in a table.

        Args:
            resources: List of PipelineSummary objects
        """
        if not resources:
            self.console.print("No pipeline-summary found.", style="yellow")
            return

        # Convert to DataFrame for efficient operations
        df = pd.DataFrame([r.model_dump() for r in resources])

        # Create and display table
        table = self.create_table(df)
        self.console.print(table)

        # Show summary
        self.console.print(
            f"\nTotal pipeline-summary: {len(resources)}", style="green"
        )
