"""Get command implementation."""

import json
import os
import re
from typing import Any, Optional, Union

from rich.console import Console
from rich.table import Table

from ...http import ADOCHTTPClient
from ...http.formatter import ResponseFormatter
from ...http.http_config import ResponseType
from ...models import APIReference, CompletionItem
from ...config import get_config_manager
from .base import Command


class GetCommand(Command):
    """Get command for making HTTP GET requests."""

    def __init__(self, http_client: Optional[ADOCHTTPClient] = None):
        """Initialize the get command.
        
        Args:
            http_client: HTTP client for making requests
        """
        self.http_client = http_client or ADOCHTTPClient()
        self.console = Console()

    @property
    def name(self) -> str:
        return "get"

    @property
    def description(self) -> str:
        return "Make HTTP GET requests to ADOC API endpoints"

    @property
    def aliases(self) -> list[str]:
        return ["g"]

    def get_help(self) -> str:
        """Get detailed help for get command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: get <url> [path-params] [query-params]\n\n"
        help_text += "Examples:\n"
        help_text += "  get /catalog-server/api/assets/search\n"
        help_text += "  get /catalog-server/api/assets/:asset-id/metadata asset-id=123\n"
        help_text += "  get /catalog-server/api/assets/search ?name=test ?page=1\n"
        help_text += "  get /catalog-server/api/assets/:asset-id/metadata asset-id=123 include_history=true\n\n"
        help_text += "Path Parameters:\n"
        help_text += "  - Use :param-name in URLs (e.g., :asset-id)\n"
        help_text += "  - Provide values as param-name=value\n"
        help_text += "  - If not provided, you'll be prompted interactively\n\n"
        help_text += "Query Parameters:\n"
        help_text += "  - Prefix with ? (e.g., ?name=value)\n"
        help_text += "  - Or provide as key=value pairs\n"
        return help_text

    def _load_api_reference(self) -> Optional[APIReference]:
        """Load API reference from configuration file."""
        try:
            config_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "..", "config", 
                "adoc-toolkit-api-reference.json"
            )
            with open(config_path, "r") as f:
                data = json.load(f)
            return APIReference.model_validate(data)
        except Exception as e:
            self.console.print(f"Error loading API reference: {e}", style="red")
            return None

    def _parse_query_params(self, args: list[str]) -> dict[str, Any]:
        """Parse query parameters from command arguments."""
        query_params = {}
        
        for arg in args:
            if arg.startswith("?"):
                # Remove the ? prefix
                param_str = arg[1:]
                if "=" in param_str:
                    key, value = param_str.split("=", 1)
                    # Convert value to appropriate type
                    if value.lower() == "true":
                        query_params[key] = True
                    elif value.lower() == "false":
                        query_params[key] = False
                    elif value.isdigit():
                        query_params[key] = int(value)
                    else:
                        query_params[key] = value
                else:
                    # Boolean parameter (e.g., ?verbose)
                    query_params[param_str] = True
            elif "=" in arg and not arg.startswith("?"):
                # Check if this is a path parameter (no ? prefix)
                key, value = arg.split("=", 1)
                # We'll handle path parameters separately
                pass
        
        return query_params

    def _parse_path_params(self, args: list[str]) -> dict[str, str]:
        """Parse path parameters from command arguments."""
        path_params = {}
        
        for arg in args:
            if "=" in arg and not arg.startswith("?"):
                key, value = arg.split("=", 1)
                path_params[key] = value
        
        return path_params

    def _extract_path_parameters(self, url: str) -> list[str]:
        """Extract path parameter names from a URL.
        
        Args:
            url: URL with potential path parameters
            
        Returns:
            List of path parameter names found in the URL
        """
        # Find all :param-name patterns
        pattern = r':([^/]+)'
        return re.findall(pattern, url)

    def _replace_path_parameters(self, url: str, path_params: dict[str, str]) -> str:
        """Replace path parameters in a URL with actual values.
        
        Args:
            url: URL with path parameters
            path_params: Dictionary of parameter names to values
            
        Returns:
            URL with path parameters replaced
        """
        result = url
        for param_name, param_value in path_params.items():
            placeholder = f":{param_name}"
            result = result.replace(placeholder, str(param_value))
        return result

    def _prompt_for_missing_path_params(
        self, 
        url: str, 
        provided_params: dict[str, str]
    ) -> dict[str, str]:
        """Prompt user for missing path parameters.
        
        Args:
            url: URL with path parameters
            provided_params: Already provided path parameters
            
        Returns:
            Dictionary of all path parameters (provided + prompted)
        """
        path_params = self._extract_path_parameters(url)
        missing_params = {}
        
        for param_name in path_params:
            if param_name not in provided_params:
                # Prompt user for the parameter value
                self.console.print(f"\nValue for {param_name}:", style="yellow")
                
                # Get user input
                user_input = input("Enter value (or press Enter to cancel): ").strip()
                
                if not user_input:
                    # User cancelled
                    return {}
                
                missing_params[param_name] = user_input
        
        # Combine provided and missing parameters
        return {**provided_params, **missing_params}

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

        # Check for path parameters
        path_params = self._extract_path_parameters(url_path)
        if path_params:
            table.add_row("Path Parameters", "")
            for param in path_params:
                table.add_row(f"  {param}", f"Path parameter: {param}")

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

        self.console.print("Available URLs:", style="bold")
        for url in api_ref.endpoints.keys():
            endpoint = api_ref.endpoints[url]
            self.console.print(f"  {url}")
            self.console.print(f"    {endpoint.description}")

    def execute(self, args: list[str]) -> bool:
        """Execute the get command.
        
        Args:
            args: Command arguments
            
        Returns:
            True if command executed successfully, False otherwise
        """
        if not args:
            self.console.print("Usage: get <url> [path-params] [query-params]", style="red")
            self.console.print("Use 'get --help' for more information")
            return True

        # Handle help flag
        if args[0] == "--help":
            print(self.get_help())
            return True

        # Parse URL path
        url_path = args[0]
        
        # Check if URL has path parameters
        path_params_in_url = self._extract_path_parameters(url_path)
        
        # Parse remaining arguments
        remaining_args = args[1:]
        query_params = {}
        path_params = {}
        
        for arg in remaining_args:
            if arg.startswith("?"):
                # Query parameter
                param_str = arg[1:]
                if "=" in param_str:
                    key, value = param_str.split("=", 1)
                    # Convert value to appropriate type
                    if value.lower() == "true":
                        query_params[key] = True
                    elif value.lower() == "false":
                        query_params[key] = False
                    elif value.isdigit():
                        query_params[key] = int(value)
                    else:
                        query_params[key] = value
                else:
                    # Boolean parameter (e.g., ?verbose)
                    query_params[param_str] = True
            elif "=" in arg and not arg.startswith("?"):
                # Check if this is a path parameter
                key, value = arg.split("=", 1)
                if key in path_params_in_url:
                    path_params[key] = value
                else:
                    # Treat as query parameter
                    if value.lower() == "true":
                        query_params[key] = True
                    elif value.lower() == "false":
                        query_params[key] = False
                    elif value.isdigit():
                        query_params[key] = int(value)
                    else:
                        query_params[key] = value

        # Load API reference
        api_ref = self._load_api_reference()
        if not api_ref:
            return False

        # Check if URL exists in API reference
        if url_path not in api_ref.endpoints:
            self.console.print(f"Unknown URL: {url_path}", style="red")
            self.console.print("Use 'get --help' to see available URLs")
            return True

        endpoint = api_ref.endpoints[url_path]
        
        # Handle path parameters
        if path_params_in_url:
            # Prompt for missing path parameters
            all_path_params = self._prompt_for_missing_path_params(url_path, path_params)
            
            if not all_path_params:
                # User cancelled
                self.console.print("Request cancelled by user", style="yellow")
                return True
            
            # Replace path parameters in URL
            final_url = self._replace_path_parameters(endpoint.url, all_path_params)
        else:
            final_url = endpoint.url

        # Make the HTTP request
        try:
            response = self.http_client.get(final_url, params=query_params)
            
            if response.is_success:                                
                # Get response type from configuration
                config_manager = get_config_manager()
                response_type_str = config_manager.get("http.response.type")
                if response_type_str is None:
                    response_type_str = "json"  # Default fallback
                
                # Convert string to ResponseType enum
                try:
                    response_type = ResponseType(response_type_str.lower())
                except ValueError:
                    # Fallback to JSON if invalid response type
                    response_type = ResponseType.JSON
                
                # Create response formatter
                formatter = ResponseFormatter(self.console)
                
                # Check if response is JSON by looking at content-type header or trying to parse as JSON
                content_type = response.headers.get('content-type', '').lower()
                is_json_response = 'json' in content_type or 'application/json' in content_type
                
                if is_json_response:
                    try:
                        data = response.json()
                        self.console.print("Response:", style="bold")
                        formatter.print_response(data, response_type)
                    except Exception as e:
                        self.console.print(f"Error parsing JSON response: {e}", style="red")
                        self.console.print("Raw response:")
                        self.console.print(response.text)
                else:
                    # Try to parse as JSON anyway in case content-type is not set correctly
                    try:
                        data = response.json()
                        self.console.print("Response:", style="bold")
                        formatter.print_response(data, response_type)
                    except Exception:
                        # If JSON parsing fails, show as text
                        self.console.print("Response:")
                        self.console.print(response.text)
            else:
                self.console.print("❌ Request failed", style="red")
                self.console.print(f"Status: {response.status_code}")
                self.console.print(f"URL: {response.request_info.url}")
                if response.text:
                    self.console.print("Error response:")
                    self.console.print(response.text)
                    
        except Exception as e:
            self.console.print(f"❌ Error making request: {e}", style="red")
            return False

        return True

    def _get_already_provided_params(self, args: list[str]) -> set[str]:
        """Extract already provided path parameters from command arguments.
        
        Args:
            args: Command arguments
            
        Returns:
            Set of parameter names that have already been provided
        """
        provided_params = set()
        for arg in args:
            if '=' in arg and not arg.startswith('?'):
                param_name = arg.split('=')[0]
                provided_params.add(param_name)
        return provided_params

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions.
        
        Args:
            current_input: Current input string (full document text)
            cursor_position: Current cursor position
            
        Returns:
            List of completion suggestions
        """
        # Load API reference
        api_ref = self._load_api_reference()
        if not api_ref:
            return []

        # Parse current input
        parts = current_input.split()
        
        # If we don't have at least "get" command, return empty
        if len(parts) < 1:
            return []
        
        # If we only have "get", return all available endpoints
        if len(parts) == 1:
            return list(api_ref.endpoints.keys())
        
        # Get the URL part (second argument)
        url_part = parts[1]
        
        # If URL doesn't start with "/", return empty
        if not url_part.startswith("/"):
            return []
        
        # Get already provided parameters from remaining args
        already_provided = self._get_already_provided_params(parts[2:])
        
        # Check if we have a complete URL and are at the end of the input
        # This indicates we should show path parameters
        if len(parts) >= 2 and url_part in api_ref.endpoints:
            # Check if cursor is at or near the end of the input (after the URL)
            # Allow for small differences due to trailing spaces
            if cursor_position >= len(current_input) - 2:
                params = self._extract_path_parameters(url_part)
                return [param for param in params if param not in already_provided]
        
        # Otherwise, complete the URL path
        matching_urls = [
            url for url in api_ref.endpoints.keys() 
            if url.startswith(url_part)
        ]
        
        return matching_urls
