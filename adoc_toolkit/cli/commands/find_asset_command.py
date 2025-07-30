"""Find asset command implementation."""


from rich.console import Console
from rich.table import Table

from ...http.client import ADOCHTTPClient
from ...models import AssetSearchResponse
from ...tracing.mixins import TraceableMixin
from .base import Command


class FindAssetCommand(Command, TraceableMixin):
    """Find assets by name."""

    def __init__(self, http_client: ADOCHTTPClient):
        """Initialize the find asset command.

        Args:
            http_client: HTTP client for making API calls
        """
        self.http_client = http_client
        self.console = Console()

    @property
    def trace_prefix(self) -> str:
        """Get the trace prefix for this command."""
        return "find_asset"

    @property
    def name(self) -> str:
        return "find-asset"

    @property
    def description(self) -> str:
        return "Find assets by name"

    @property
    def aliases(self) -> list[str]:
        return ["search", "search-asset", "asset-search"]

    @property
    def contributor(self) -> str | None:
        return None

    def get_help(self) -> str:
        """Get detailed help for find-asset command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: find-asset <asset-name>\n\n"
        help_text += "Finds assets by name using the ADOC API.\n"
        help_text += "The search is case-insensitive and supports partial matches.\n\n"
        help_text += "Examples:\n"
        help_text += "  find-asset database\n"
        help_text += "  find-asset 'my table'\n"
        help_text += "  find-asset --help\n\n"
        help_text += "The command will display a table with:\n"
        help_text += "  - Assembly (derived from asset name)\n"
        help_text += "  - Source Type (derived from asset type)\n"
        help_text += "  - Assembly ID (asset ID)\n"
        help_text += "  - Schedule (N/A for assets)\n"
        help_text += "  - Virtual (No for assets)\n"
        help_text += "  - Protected (No for assets)\n"
        help_text += "  - Integration ID (asset UID)\n"
        return help_text

    def execute(self, args: list[str]) -> bool:
        """Execute the find-asset command."""
        self.trace_start("command_execution", args_count=len(args))

        # Handle --help flag
        if args and args[0] == "--help":
            self.trace("help_requested")
            print(self.get_help())
            self.trace_complete("command_execution", help_displayed=True)
            return True

        # Check if asset name is provided
        if not args:
            self.trace_error("command_execution", Exception("Missing asset name"))
            print("Error: Asset name is required")
            print("Usage: find-asset <asset-name>")
            print("Example: find-asset database")
            return True

        asset_name = args[0]
        self.trace("asset_search_started", asset_name=asset_name)

        try:
            # Make API call to search for assets
            self.trace(
                "api_request_started",
                endpoint="/catalog-server/api/assets/search",
                params={"name": asset_name},
            )
            response = self.http_client.get(
                "/catalog-server/api/assets/search", params={"name": asset_name}
            )

            self.trace(
                "api_response_received",
                status_code=response.status_code,
                success=response.is_success,
            )

            if response.is_success:
                # Parse response using Pydantic model
                self.trace("response_parsing_started")
                response_data = response.json()
                asset_search_response = AssetSearchResponse.model_validate(
                    response_data
                )
                self.trace(
                    "response_parsing_completed",
                    assets_count=len(asset_search_response.assets),
                )

                self._display_results(asset_search_response, asset_name)
                self.trace_complete(
                    "command_execution", assets_found=len(asset_search_response.assets)
                )
            else:
                self.trace_error(
                    "api_request", Exception(f"HTTP {response.status_code}")
                )
                print(f"Error searching for assets: HTTP {response.status_code}")

        except Exception as e:
            self.trace_error("command_execution", e)
            print(f"Error executing search: {e}")

        return True

    def _display_results(
        self, asset_search_response: AssetSearchResponse, search_term: str
    ) -> None:
        """Display search results in a formatted table matching data-sources format.

        Args:
            asset_search_response: Validated response data from the API
            search_term: The search term used
        """
        self.trace_start(
            "display_results",
            search_term=search_term,
            total_assets=len(asset_search_response.assets),
        )

        assets = asset_search_response.assets

        if not assets:
            self.trace("no_results_found", search_term=search_term)
            print(f"\nNo assets found matching '{search_term}'")
            print("Try using a different search term or check the spelling.")
            self.trace_complete("display_results", results_count=0)
            return

        print(f"\nFound {len(assets)} asset(s) matching '{search_term}':")

        # Create Rich table matching data-sources format
        table = Table(
            title="Assets",
            show_header=True,
            header_style="bold magenta",
            show_lines=True
        )

        # Add columns matching data-sources format
        table.add_column("Assembly", style="cyan", no_wrap=True)
        table.add_column("Source Type", style="green")
        table.add_column("Assembly ID", style="yellow", justify="right")
        table.add_column("Schedule", style="blue")
        table.add_column("Virtual", style="red", justify="center")
        table.add_column("Protected", style="red", justify="center")
        table.add_column("Integration ID", style="white", no_wrap=False)

        # Add each asset as a row
        for i, asset in enumerate(assets):
            # Map asset data to data-sources format
            assembly = asset.name.split('.')[0] if '.' in asset.name else asset.name
            source_type = asset.asset_type.name.upper()
            assembly_id = str(asset.id)
            schedule = "None"  # Assets don't have schedules
            is_virtual = "No"  # Assets are not virtual
            is_protected = "No"  # Assets are not protected
            integration_id = asset.uid

            table.add_row(
                assembly,
                source_type,
                assembly_id,
                schedule,
                is_virtual,
                is_protected,
                integration_id
            )

            # Trace each asset display
            self.trace(
                "asset_displayed",
                asset_index=i,
                asset_id=assembly_id,
                asset_name=asset.name,
                asset_type=source_type,
                asset_uid=integration_id,
            )

        # Display the table
        self.console.print(table)
        
        # Show summary matching data-sources format
        print(f"\nTotal assets: {len(assets)} (filtered from {len(assets)} total)")

        self.trace_complete("display_results", results_count=len(assets))

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions."""
        # For now, return empty list as we don't have asset name suggestions
        # This could be enhanced to suggest common asset names in the future
        return []
