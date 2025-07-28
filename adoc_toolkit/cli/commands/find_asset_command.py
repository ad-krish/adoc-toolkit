"""Find asset command implementation."""

from typing import Any, Callable, Optional, Union

from ...models import CompletionItem, AssetSearchResponse, Asset
from ...tracing.mixins import TraceableMixin
from .base import Command


class FindAssetCommand(Command, TraceableMixin):
    """Find assets by name."""

    def __init__(self, http_client):
        """Initialize the find asset command.

        Args:
            http_client: HTTP client for making API calls
        """
        self.http_client = http_client

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
        help_text += "  - Asset ID\n"
        help_text += "  - Asset Name\n"
        help_text += "  - Asset Type\n"
        help_text += "  - Asset UID\n"
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
        """Display search results in a formatted table.

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
        print("=" * 135)

        # Print header
        print(f"{'ID':<15} {'Name':<50} {'Asset Type':<20} {'Asset UID':<50}")
        print("-" * 135)

        # Print each asset
        for i, asset in enumerate(assets):
            asset_id = str(asset.id)  # Convert to string for display
            asset_name = asset.name
            asset_type = asset.asset_type.name
            asset_uid = asset.uid

            # Only truncate asset type for better display, show full name and UID
            asset_type = asset_type[:17] + "..." if len(asset_type) > 20 else asset_type

            print(f"{asset_id:<15} {asset_name:<50} {asset_type:<20} {asset_uid:<50}")

            # Trace each asset display
            self.trace(
                "asset_displayed",
                asset_index=i,
                asset_id=asset_id,
                asset_name=asset_name,
                asset_type=asset_type,
                asset_uid=asset_uid,
            )

        print("=" * 135)
        self.trace_complete("display_results", results_count=len(assets))

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions."""
        # For now, return empty list as we don't have asset name suggestions
        # This could be enhanced to suggest common asset names in the future
        return []
