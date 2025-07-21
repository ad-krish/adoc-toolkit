"""Get command implementation."""

import json
import shlex
from pathlib import Path
from typing import Any, Optional, Union

from rich.console import Console
from rich.table import Table

from ...config import get_config_manager
from ...http import ADOCHTTPClient
from ...models import APIReference, CompletionItem, GetCommandArgs
from .base import Command


class GetCommand(Command):
    """Make GET HTTP requests to ADOC API endpoints."""

    def __init__(self, http_client: Optional[ADOCHTTPClient] = None):
        """Initialize GetCommand.

        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client
        self.console = Console()
        self._api_reference_cache = None

    @property
    def name(self) -> str:
        return "get"

    @property
    def description(self) -> str:
        return "Make GET HTTP requests to ADOC API endpoints"

    @property
    def aliases(self) -> list[str]:
        return ["fetch", "request"]

    def get_help(self) -> str:
        return f"""\
{self.name}: {self.description}

Usage: {self.name} <url> [query-params]

Options:
  --help [url]            Show this help message, optionally for a specific URL

Description:
  Makes GET HTTP requests to ADOC API endpoints.
  Requires an environment to be set using 'use <environment-name>'.
  URLs are defined in config/adoc-toolkit-api-reference.json.
  Query parameters are specified as key=value pairs.

  Use '{self.name} --help <url>' to see available parameters for a URL.

Examples:
  {self.name} /catalog-server/api/assets/search name=Snowflake
  {self.name} /catalog-server/api/assets/search name=Snowflake ids=1234567890

Note: Set an environment first with 'use <environment-name>' before making requests.
"""

    def _load_api_reference(self) -> Optional[APIReference]:
        """Load API reference from JSON file."""
        if self._api_reference_cache is not None:
            return self._api_reference_cache

        config_path = Path("config/adoc-toolkit-api-reference.json")

        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                data = json.load(f)
                self._api_reference_cache = APIReference.model_validate(data)
                return self._api_reference_cache
        except Exception as e:
            self.console.print(f"Error loading API reference: {e}", style="red")
            return None

    def _parse_query_params(self, args: list[str]) -> dict[str, Any]:
        """Parse query parameters from command arguments.

        Args:
            args: Command arguments after endpoint name

        Returns:
            Dictionary of query parameters
        """
        params = {}

        for arg in args:
            if "=" in arg:
                key, value = arg.split("=", 1)
                key = key.strip()
                value = value.strip()

                # Try to convert to appropriate type
                if value.lower() in ("true", "false"):
                    params[key] = value.lower() == "true"
                elif value.isdigit():
                    params[key] = int(value)
                elif value.replace(".", "").isdigit() and value.count(".") == 1:
                    params[key] = float(value)
                else:
                    params[key] = value
            else:
                # Single value without =, treat as boolean flag
                params[arg] = True

        return params

    def _show_endpoint_help(self, url_path: str) -> None:
        """Show detailed help for a specific URL.

        Args:
            url_path: URL path
        """
        api_ref = self._load_api_reference()
        if not api_ref:
            self.console.print("Could not load API reference", style="red")
            return

        if url_path not in api_ref.endpoints:
            self.console.print(f"Unknown URL: {url_path}", style="red")
            self.console.print("Available URLs:")
            for url in api_ref.endpoints.keys():
                self.console.print(f"  {url}")
            return

        endpoint = api_ref.endpoints[url_path]

        # Create help table
        table = Table(title=f"URL: {url_path}")
        table.add_column("Property", style="cyan")
        table.add_column("Value", style="white")

        table.add_row("URL", endpoint.url)
        table.add_row("Description", endpoint.description)
        table.add_row("Response Type", endpoint.response_type)

        if endpoint.query_params:
            table.add_row("Query Parameters", "")
            for param_name, param in endpoint.query_params.items():
                param_desc = f"{param.description} (type: {param.type})"
                if param.default is not None:
                    param_desc += f" (default: {param.default})"
                if param.options:
                    param_desc += f" (options: {', '.join(param.options)})"
                table.add_row(f"  {param_name}", param_desc)
        else:
            table.add_row("Query Parameters", "None")

        self.console.print(table)

    def _show_endpoints_list(self) -> None:
        """Show list of available URLs."""
        api_ref = self._load_api_reference()
        if not api_ref:
            self.console.print("Could not load API reference", style="red")
            return

        table = Table(title="Available URLs")
        table.add_column("URL", style="cyan")
        table.add_column("Description", style="green")

        for url, endpoint in api_ref.endpoints.items():
            table.add_row(url, endpoint.description)

        self.console.print(table)

    def execute(self, args: list[str]) -> bool:
        """Execute the get command."""
        # Handle --help flag
        if args and args[0] == "--help":
            if len(args) > 1:
                # Show help for specific endpoint
                self._show_endpoint_help(args[1])
            else:
                # Show general help
                print(self.get_help())
                self._show_endpoints_list()
            return True

        if not args:
            self.console.print("Error: URL required", style="red")
            self.console.print("Usage: get <url> [query-params]", style="yellow")
            self.console.print("Type 'get --help' for more information", style="yellow")
            return True

        url_path = args[0]
        query_params = self._parse_query_params(args[1:]) if len(args) > 1 else {}

        # Validate arguments
        try:
            GetCommandArgs(endpoint=url_path, query_params=query_params)
        except Exception as e:
            self.console.print(f"Error: {e}", style="red")
            return True

        # Load API reference
        api_ref = self._load_api_reference()
        if not api_ref:
            self.console.print("Error: Could not load API reference", style="red")
            return True

        # Check if URL exists in API reference
        if url_path not in api_ref.endpoints:
            self.console.print(f"Error: Unknown URL '{url_path}'", style="red")
            self.console.print("Available URLs:", style="yellow")
            for url in api_ref.endpoints.keys():
                self.console.print(f"  {url}", style="yellow")
            return True

        endpoint = api_ref.endpoints[url_path]

        # Validate query parameters against endpoint definition
        for param_name, param_value in query_params.items():
            if param_name not in endpoint.query_params:
                self.console.print(
                    f"Warning: Unknown parameter '{param_name}' for URL '{url_path}'",
                    style="yellow",
                )
                continue

            param_def = endpoint.query_params[param_name]
            if param_def.options and param_value not in param_def.options:
                self.console.print(
                    f"Warning: Invalid value '{param_value}' for parameter "
                    f"'{param_name}'",
                    style="yellow",
                )
                self.console.print(
                    f"Valid options: {', '.join(param_def.options)}", style="yellow"
                )

        # Make the HTTP request
        try:
            if not self.http_client:
                self.console.print("Error: HTTP client not available", style="red")
                return True

            response = self.http_client.get(endpoint.url, params=query_params)

            # Display response
            if response.is_success:
                try:
                    data = response.json()

                    # Get response type from configuration
                    config_manager = get_config_manager()
                    response_type = config_manager.get("http.response.type")

                    # Use response formatter
                    from adoc_toolkit.http.formatter import ResponseFormatter

                    formatter = ResponseFormatter(self.console)

                    # Format and print response
                    formatter.print_response(
                        data=data,
                        response_type=response_type,
                        title="",
                    )
                except ValueError:
                    # Not JSON, show as text
                    self.console.print(response.text)
            else:
                self.console.print(
                    f"Request failed with status {response.status_code}", style="red"
                )
                if response.text:
                    self.console.print(response.text, style="red")
                return True

        except Exception as e:
            error_msg = str(e)
            if "No environment selected" in error_msg:
                self.console.print("Error: No environment selected", style="red")
                self.console.print(
                    "Please set an environment first using:", style="yellow"
                )
                self.console.print("  use <environment-name>", style="yellow")
                self.console.print("Available environments:", style="yellow")
                self.console.print("  cs-india", style="yellow")
                self.console.print("  training", style="yellow")
                self.console.print("  se-demo", style="yellow")
            else:
                self.console.print(f"Error making request: {e}", style="red")
            return True

        return True

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions for URLs and parameters with descriptions."""
        api_ref = self._load_api_reference()
        if not api_ref:
            return []

        # Parse the input to get the current argument being typed
        try:
            parts = shlex.split(current_input[:cursor_position])
        except ValueError:
            # Handle unmatched quotes
            parts = current_input[:cursor_position].split()

        if not parts or parts[0] != self.name:
            return []

        # If we're typing the first argument after "get"
        if len(parts) == 2:
            current_arg = parts[1]

            # If the current argument contains a ?, it means we're typing
            # query parameters
            if "?" in current_arg:
                # Find the endpoint that matches this URL
                base_url = current_arg.split("?", 1)[0]
                matching_endpoint = None
                for endpoint_key, endpoint in api_ref.endpoints.items():
                    if base_url == endpoint_key:
                        matching_endpoint = endpoint
                        break

                if matching_endpoint:
                    # Extract the part after ? for parameter completion
                    query_part = current_arg.split("?", 1)[1]

                    # Handle multiple parameters separated by &
                    if "&" in query_part:
                        # Get the last parameter being typed
                        last_param = query_part.split("&")[-1]
                        if "=" not in last_param:
                            # We're typing a parameter name after &
                            param_names = list(matching_endpoint.query_params.keys())
                            if last_param:
                                completions = [
                                    CompletionItem(
                                        text=param,
                                        description=matching_endpoint.query_params[
                                            param
                                        ].description,
                                    )
                                    for param in param_names
                                    if param.startswith(last_param)
                                ]
                            else:
                                completions = [
                                    CompletionItem(
                                        text=param,
                                        description=matching_endpoint.query_params[
                                            param
                                        ].description,
                                    )
                                    for param in param_names
                                ]
                            return completions
                        else:
                            # We're typing a parameter value after &
                            param_name, param_value = last_param.split("=", 1)
                            if param_name in matching_endpoint.query_params:
                                param_def = matching_endpoint.query_params[param_name]
                                if param_def.options:
                                    if param_value:
                                        completions = [
                                            CompletionItem(
                                                text=option,
                                                description=f"Value for {param_name} "
                                                f"parameter",
                                            )
                                            for option in param_def.options
                                            if option.startswith(param_value)
                                        ]
                                    else:
                                        completions = [
                                            CompletionItem(
                                                text=option,
                                                description=f"Value for {param_name} "
                                                f"parameter",
                                            )
                                            for option in param_def.options
                                        ]
                                    return completions
                    elif "=" not in query_part:
                        # We're typing a parameter name
                        param_names = list(matching_endpoint.query_params.keys())
                        if query_part:
                            completions = [
                                CompletionItem(
                                    text=param,
                                    description=matching_endpoint.query_params[
                                        param
                                    ].description,
                                )
                                for param in param_names
                                if param.startswith(query_part)
                            ]
                        else:
                            completions = [
                                CompletionItem(
                                    text=param,
                                    description=matching_endpoint.query_params[
                                        param
                                    ].description,
                                )
                                for param in param_names
                            ]
                            return completions
                    else:
                        # We're typing a parameter value
                        param_name, param_value = query_part.split("=", 1)
                        if param_name in matching_endpoint.query_params:
                            param_def = matching_endpoint.query_params[param_name]
                            if param_def.options:
                                if param_value:
                                    completions = [
                                        CompletionItem(
                                            text=option,
                                            description=f"Value for {param_name} "
                                            f"parameter",
                                        )
                                        for option in param_def.options
                                        if option.startswith(param_value)
                                    ]
                                else:
                                    completions = [
                                        CompletionItem(
                                            text=option,
                                            description=f"Value for {param_name} "
                                            f"parameter",
                                        )
                                        for option in param_def.options
                                    ]
                                return completions

            # Check if we're at the end of input with a space (indicating
            # parameter completion)
            if current_input.endswith(" "):
                # Find the endpoint that matches this URL
                for endpoint_key, endpoint in api_ref.endpoints.items():
                    if current_arg == endpoint_key:
                        # Return all param names for this endpoint with descriptions
                        return [
                            CompletionItem(
                                text=param,
                                description=endpoint.query_params[param].description,
                            )
                            for param in endpoint.query_params.keys()
                        ]

            # Regular URL completion with descriptions
            url_keys = list(api_ref.endpoints.keys())

            # Filter URLs that start with the current argument
            if current_arg:
                completions = [
                    CompletionItem(
                        text=url, description=api_ref.endpoints[url].description
                    )
                    for url in url_keys
                    if url.startswith(current_arg)
                ]
            else:
                completions = [
                    CompletionItem(
                        text=url, description=api_ref.endpoints[url].description
                    )
                    for url in url_keys
                ]

            return completions

        # If we're typing query parameters
        if len(parts) >= 2:
            url_path = parts[1]

            # Find the endpoint that matches this URL
            matching_endpoint = None
            # Strip query parameters for endpoint matching
            base_url = url_path.split("?", 1)[0]
            for endpoint_key, endpoint in api_ref.endpoints.items():
                if base_url == endpoint_key:
                    matching_endpoint = endpoint
                    break

            if matching_endpoint:
                # Check if we're at the end of input with a space (indicating
                # parameter completion)
                if current_input.endswith(" "):
                    # Return all param names for this endpoint with descriptions
                    return [
                        CompletionItem(
                            text=param,
                            description=matching_endpoint.query_params[
                                param
                            ].description,
                        )
                        for param in matching_endpoint.query_params.keys()
                    ]

                # Check if we're typing URL query parameters (after ?)
                if "?" in url_path:
                    # Extract the part after ? for parameter completion
                    query_part = url_path.split("?", 1)[1]
                    if "=" not in query_part:
                        # We're typing a parameter name
                        param_names = list(matching_endpoint.query_params.keys())
                        if query_part:
                            completions = [
                                CompletionItem(
                                    text=param,
                                    description=matching_endpoint.query_params[
                                        param
                                    ].description,
                                )
                                for param in param_names
                                if param.startswith(query_part)
                            ]
                        else:
                            completions = [
                                CompletionItem(
                                    text=param,
                                    description=matching_endpoint.query_params[
                                        param
                                    ].description,
                                )
                                for param in param_names
                            ]
                        return completions
                    # We're typing a parameter value
                    param_name, param_value = query_part.split("=", 1)
                    if param_name in matching_endpoint.query_params:
                        param_def = matching_endpoint.query_params[param_name]
                        if param_def.options:
                            if param_value:
                                completions = [
                                    CompletionItem(
                                        text=option,
                                        description=f"Value for {param_name} parameter",
                                    )
                                    for option in param_def.options
                                    if option.startswith(param_value)
                                ]
                            else:
                                completions = [
                                    CompletionItem(
                                        text=option,
                                        description=f"Value for {param_name} parameter",
                                    )
                                    for option in param_def.options
                                ]
                            return completions

                # Get current word being typed
                current_word = ""
                if len(parts) > 2:
                    current_word = parts[-1]

                # If we're typing a parameter name (before =)
                if "=" not in current_word:
                    param_names = list(matching_endpoint.query_params.keys())
                    if current_word:
                        completions = [
                            CompletionItem(
                                text=param,
                                description=matching_endpoint.query_params[
                                    param
                                ].description,
                            )
                            for param in param_names
                            if param.startswith(current_word)
                        ]
                    else:
                        completions = [
                            CompletionItem(
                                text=param,
                                description=matching_endpoint.query_params[
                                    param
                                ].description,
                            )
                            for param in param_names
                        ]
                    return completions

                # If we're typing a parameter value (after =)
                if "=" in current_word:
                    param_name, param_value = current_word.split("=", 1)
                    if param_name in matching_endpoint.query_params:
                        param_def = matching_endpoint.query_params[param_name]
                        if param_def.options:
                            if param_value:
                                completions = [
                                    CompletionItem(
                                        text=option,
                                        description=f"Value for {param_name} parameter",
                                    )
                                    for option in param_def.options
                                    if option.startswith(param_value)
                                ]
                            else:
                                completions = [
                                    CompletionItem(
                                        text=option,
                                        description=f"Value for {param_name} parameter",
                                    )
                                    for option in param_def.options
                                ]
                            return completions

        return []
