"""HTTP response formatter module."""

import csv
import io
import json
from typing import Any

from rich.console import Console
from rich.table import Table

from .http_config import ResponseType


class ResponseFormatter:
    """Formats HTTP responses for console output."""

    def __init__(self, console: Console | None = None):
        """Initialize response formatter.

        Args:
            console: Rich console instance for output
        """
        self.console = console or Console()

    def format_response(
        self,
        data: Any,
        response_type: ResponseType = ResponseType.JSON,
        title: str | None = None,
    ) -> str:
        """Format response data according to the specified type.

        Args:
            data: Response data to format
            response_type: Type of formatting to apply
            title: Optional title for table/csv output

        Returns:
            Formatted string representation
        """
        if response_type == ResponseType.JSON:
            return self._format_json(data)
        elif response_type == ResponseType.TABLE:
            return self._format_table(data, title)
        elif response_type == ResponseType.CSV:
            return self._format_csv(data, title)
        else:
            raise ValueError(f"Unsupported response type: {response_type}")

    def _format_json(self, data: Any) -> str:
        """Format data as JSON.

        Args:
            data: Data to format

        Returns:
            JSON string
        """
        try:
            return json.dumps(data, indent=2, ensure_ascii=False)
        except (TypeError, ValueError):
            # Fallback for non-serializable data
            return str(data)

    def _format_table(self, data: Any, title: str | None = None) -> str:
        """Format data as a Rich table with intelligent flattening.

        Args:
            data: Data to format
            title: Optional table title

        Returns:
            Table string representation
        """
        if not data:
            return "No data to display"

        # Handle different data types
        if isinstance(data, dict):
            return self._format_dict_as_table(data, title)
        elif isinstance(data, list):
            return self._format_list_as_table(data, title)
        else:
            # Fallback to JSON for other types
            return self._format_json(data)

    def _flatten_dict(
        self, data: dict[str, Any], prefix: str = ""
    ) -> list[tuple[str, Any]]:
        """Recursively flatten a dictionary, expanding all nested structures vertically.

        Args:
            data: Dictionary to flatten
            prefix: Current path prefix for nested keys

        Returns:
            List of (key_path, value) tuples
        """
        flattened = []

        for key, value in data.items():
            current_path = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                # Recursively flatten all nested dictionaries
                nested_flattened = self._flatten_dict(value, current_path)
                flattened.extend(nested_flattened)
            elif isinstance(value, list):
                # Check if list contains dictionaries
                if value and all(isinstance(v, dict) for v in value):
                    # Flatten each dictionary in the list with indexed keys
                    for i, item in enumerate(value):
                        item_prefix = f"{current_path}[{i}]"
                        item_flattened = self._flatten_dict(item, item_prefix)
                        flattened.extend(item_flattened)
                elif all(isinstance(v, str | int | float | bool) for v in value):
                    # Simple list of primitives
                    flattened.append((current_path, value))
                else:
                    # Complex list (mixed types or non-primitives)
                    flattened.append((current_path, value))
            else:
                # Primitive values
                flattened.append((current_path, value))

        return flattened

    def _format_dict_as_table(
        self, data: dict[str, Any], title: str | None = None
    ) -> str:
        """Format dictionary as table with intelligent flattening.

        Args:
            data: Dictionary data
            title: Optional table title

        Returns:
            Table string
        """
        table = Table(title=title or "Response Data")
        table.add_column("Key", style="cyan", width=30)
        table.add_column("Value", style="white", width=50)

        flattened_data = self._flatten_dict(data)

        for key_path, value in flattened_data:
            if isinstance(value, dict | list):
                # Format complex nested structures as JSON
                value_str = json.dumps(value, ensure_ascii=False, indent=None)
                # Truncate if too long
                if len(value_str) > 45:
                    value_str = value_str[:42] + "..."
            else:
                value_str = str(value)

            table.add_row(key_path, value_str)

        # Capture table output as string with plain text console
        plain_console = Console(force_terminal=False, color_system=None)
        with plain_console.capture() as capture:
            plain_console.print(table)
        return capture.get()

    def _format_list_as_table(
        self, data: list[Any], title: str | None = None
    ) -> str:
        """Format list as table with intelligent flattening.

        Args:
            data: List data
            title: Optional table title

        Returns:
            Table string
        """
        if not data:
            return "No data to display"

        # Check if all items are dictionaries with similar structure
        if all(isinstance(item, dict) for item in data):
            return self._format_dict_list_as_table(data, title)
        else:
            # For mixed or simple lists, use simple format
            return self._format_simple_list_as_table(data, title)

    def _format_dict_list_as_table(
        self, data: list[dict[str, Any]], title: str | None = None
    ) -> str:
        """Format list of dictionaries as table with intelligent flattening.

        Args:
            data: List of dictionary data
            title: Optional table title

        Returns:
            Table string
        """
        if not data:
            return "No data to display"

        # Analyze structure to determine best approach
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        # If we have many different keys, flatten vertically
        if len(all_keys) > 8:
            return self._format_dict_list_vertically(data, title)
        else:
            # Use traditional horizontal table for consistent structure
            return self._format_dict_list_horizontally(data, title)

    def _format_dict_list_vertically(
        self, data: list[dict[str, Any]], title: str | None = None
    ) -> str:
        """Format list of dictionaries vertically (one row per item per key).

        Args:
            data: List of dictionary data
            title: Optional table title

        Returns:
            Table string
        """
        table = Table(title=title or "Response Data")
        table.add_column("Item", style="cyan", width=10)
        table.add_column("Key", style="cyan", width=30)
        table.add_column("Value", style="white", width=40)

        for i, item in enumerate(data):
            flattened_item = self._flatten_dict(item)

            for key_path, value in flattened_item:
                if isinstance(value, dict | list):
                    value_str = json.dumps(value, ensure_ascii=False, indent=None)
                    if len(value_str) > 37:
                        value_str = value_str[:34] + "..."
                else:
                    value_str = str(value)

                table.add_row(f"Item {i + 1}", key_path, value_str)

        # Capture table output as string with plain text console
        plain_console = Console(force_terminal=False, color_system=None)
        with plain_console.capture() as capture:
            plain_console.print(table)
        return capture.get()

    def _format_dict_list_horizontally(
        self, data: list[dict[str, Any]], title: str | None = None
    ) -> str:
        """Format list of dictionaries horizontally (one row per item).

        Args:
            data: List of dictionary data
            title: Optional table title

        Returns:
            Table string
        """
        # Get all unique keys
        all_keys = set()
        for item in data:
            all_keys.update(item.keys())

        columns = sorted(all_keys)
        table = Table(title=title or "Response Data")

        # Add columns
        for col in columns:
            table.add_column(col, style="cyan", width=20)

        # Add rows
        for item in data:
            row_values = []
            for col in columns:
                value = item.get(col, "")
                if isinstance(value, dict | list):
                    value_str = json.dumps(value, ensure_ascii=False, indent=None)
                    if len(value_str) > 17:
                        value_str = value_str[:14] + "..."
                else:
                    value_str = str(value)
                row_values.append(value_str)
            table.add_row(*row_values)

        # Capture table output as string with plain text console
        plain_console = Console(force_terminal=False, color_system=None)
        with plain_console.capture() as capture:
            plain_console.print(table)
        return capture.get()

    def _format_simple_list_as_table(
        self, data: list[Any], title: str | None = None
    ) -> str:
        """Format simple list as table.

        Args:
            data: List data
            title: Optional table title

        Returns:
            Table string
        """
        table = Table(title=title or "Response Data")
        table.add_column("Index", style="cyan", width=10)
        table.add_column("Value", style="white", width=60)

        for i, item in enumerate(data):
            if isinstance(item, dict | list):
                value_str = json.dumps(item, ensure_ascii=False, indent=None)
                if len(value_str) > 57:
                    value_str = value_str[:54] + "..."
            else:
                value_str = str(item)

            table.add_row(str(i), value_str)

        # Capture table output as string with plain text console
        plain_console = Console(force_terminal=False, color_system=None)
        with plain_console.capture() as capture:
            plain_console.print(table)
        return capture.get()

    def _format_csv(self, data: Any, title: str | None = None) -> str:
        """Format data as CSV with intelligent flattening.

        Args:
            data: Data to format
            title: Optional title (ignored for CSV)

        Returns:
            CSV string
        """
        if not data:
            return "No data to display"

        output = io.StringIO()
        writer = csv.writer(output)

        # Handle different data types
        if isinstance(data, dict):
            writer.writerow(["Key", "Value"])
            flattened_data = self._flatten_dict(data)
            for key_path, value in flattened_data:
                if isinstance(value, dict | list):
                    value_str = json.dumps(value, ensure_ascii=False)
                else:
                    value_str = str(value)
                writer.writerow([key_path, value_str])
        elif isinstance(data, list):
            if not data:
                return "No data to display"

            if all(isinstance(item, dict) for item in data):
                # Use vertical format for complex dictionary lists
                writer.writerow(["Item", "Key", "Value"])
                for i, item in enumerate(data):
                    flattened_item = self._flatten_dict(item)
                    for key_path, value in flattened_item:
                        if isinstance(value, dict | list):
                            value_str = json.dumps(value, ensure_ascii=False)
                        else:
                            value_str = str(value)
                        writer.writerow([f"Item {i + 1}", key_path, value_str])
            else:
                # Simple list
                writer.writerow(["Index", "Value"])
                for i, item in enumerate(data):
                    if isinstance(item, dict | list):
                        value_str = json.dumps(item, ensure_ascii=False)
                    else:
                        value_str = str(item)
                    writer.writerow([i, value_str])
        else:
            # Fallback for other types
            writer.writerow(["Data"])
            writer.writerow([str(data)])

        return output.getvalue()

    def print_response(
        self,
        data: Any,
        response_type: ResponseType = ResponseType.JSON,
        title: str | None = None,
    ) -> None:
        """Print formatted response to console.

        Args:
            data: Response data to format and print
            response_type: Type of formatting to apply
            title: Optional title for table/csv output
        """
        formatted = self.format_response(data, response_type, title)
        self.console.print(formatted)

    def print_response_with_config(
        self,
        data: Any,
        title: str | None = None,
    ) -> None:
        """Print formatted response using configuration-based response type.

        Args:
            data: Response data to format and print
            title: Optional title for table/csv output
        """
        from ..config import get_config_manager

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

        self.print_response(data, response_type, title)
