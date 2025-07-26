"""Set configuration command implementation."""

from typing import Any, Union

from rich.console import Console

from ...config import get_config_manager
from ...models import CompletionItem
from .base import Command


class SetConfigCommand(Command):
    """Command to set configuration values."""

    def __init__(self) -> None:
        """Initialize set-config command."""
        super().__init__()
        self.console = Console()

    @property
    def name(self) -> str:
        """Get command name."""
        return "set-config"

    @property
    def description(self) -> str:
        """Get command description."""
        return "Set configuration values for ADOC toolkit"

    @property
    def aliases(self) -> list[str]:
        """Get command aliases."""
        return ["config", "set"]

    def get_help(self) -> str:
        """Get detailed help for set-config command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: set-config <key> <value>\n"
        help_text += "       set-config --list\n"
        help_text += "       set-config --show <key>\n\n"

        help_text += "Available configuration keys:\n"
        help_text += "  HTTP Configuration:\n"
        help_text += (
            "    http.timeout    - HTTP request timeout in seconds (default: 120)\n"
        )
        help_text += "    http.retries    - Number of retry attempts (default: 3)\n"
        help_text += "    http.proxy      - HTTP proxy URL (optional)\n"
        help_text += "    http.response.type - Response format: json, table, "
        help_text += "csv, human (default: json)\n\n"

        help_text += "  Logging Configuration:\n"
        help_text += "    log.level       - Log level: TRACE, DEBUG, INFO, "
        help_text += "ERROR (default: INFO)\n"
        help_text += "    log.filepath    - Path to log file (optional)\n"
        help_text += (
            "    log.rotate.onsize - Log rotation size threshold (default: 10MB)\n"
        )
        help_text += "    log.rotate.ontime - Log rotation time threshold in "
        help_text += "minutes (default: 120)\n\n"

        help_text += "  Audit Configuration:\n"
        help_text += "    audit.logfile   - Path to audit log file (optional)\n\n"

        help_text += "  LLM Configuration:\n"
        help_text += "    llm.vendor      - LLM vendor: claude, gemini, grok, chatgpt (default: gemini)\n"
        help_text += "    llm.apikey      - API key for the selected LLM vendor (optional)\n"
        help_text += "    llm.model       - Model name for the selected LLM vendor (auto-set based on vendor)\n"
        help_text += "    llm.temperature - Temperature for response generation: 0.0-2.0 (default: 0.2)\n"
        help_text += "                     Note: Available models can be customized by editing the config file\n\n"

        help_text += "Examples:\n"
        help_text += "  set-config http.timeout 60\n"
        help_text += "  set-config http.retries 5\n"
        help_text += "  set-config http.proxy https://proxy.example.com:8080\n"
        help_text += "  set-config http.proxy none    # Remove proxy\n"
        help_text += "  set-config http.response.type table\n"
        help_text += "  set-config http.response.type csv\n"
        help_text += "  set-config http.response.type human\n"
        help_text += "  set-config log.level DEBUG\n"
        help_text += "  set-config log.filepath ./my-app.log\n"
        help_text += "  set-config log.rotate.onsize 50MB\n"
        help_text += "  set-config audit.logfile ./audit.log\n"
        help_text += "  set-config llm.vendor claude\n"
        help_text += "  set-config llm.apikey your-api-key-here\n"
        help_text += "  set-config llm.model claude-3-5-sonnet-20241022\n"
        help_text += "  set-config llm.temperature 0.7\n"
        help_text += "  set-config --list             # Show all configuration\n"
        help_text += "  set-config --show log.level   # Show specific value\n"

        return help_text

    def execute(self, args: list[str]) -> bool:
        """Execute the set-config command.

        Args:
            args: Command arguments

        Returns:
            True to continue interactive mode
        """
        if not args:
            self.console.print("Usage: set-config <key> <value>", style="yellow")
            self.console.print(
                "Use 'set-config --help' for more information.", style="yellow"
            )
            return True

        # Handle special flags
        if args[0] == "--list":
            return self._list_config()
        elif args[0] == "--show" and len(args) >= 2:
            return self._show_config(args[1])
        elif len(args) < 2:
            self.console.print("Error: Both key and value are required", style="red")
            self.console.print("Usage: set-config <key> <value>", style="yellow")
            return True

        key = args[0]
        value = args[1]

        return self._set_config(key, value)

    def _set_config(self, key: str, value: str) -> bool:
        """Set a configuration value.

        Args:
            key: Configuration key
            value: Value to set

        Returns:
            True to continue interactive mode
        """
        # Validate the key and value
        is_valid, converted_value, error_msg = get_config_manager().validate_value(
            key, value
        )

        if not is_valid:
            self.console.print(f"Error: {error_msg}", style="red")
            return True

        # Set the configuration
        try:
            get_config_manager().set(key, converted_value)
            self.console.print(
                f"✅ Configuration set: {key} = {self._format_value(converted_value)}",
                style="green",
            )

            # Show a helpful message for HTTP config changes
            if key.startswith("http."):
                self.console.print(
                    "💡 HTTP configuration changes will apply to new requests",
                    style="blue",
                )

        except Exception as e:
            self.console.print(f"Error setting configuration: {e}", style="red")

        return True

    def _list_config(self) -> bool:
        """List all configuration values with descriptions."""
        config_manager = get_config_manager()
        config_items = config_manager.get_all_config_items()

        if not config_items:
            self.console.print("No configuration items found.", style="yellow")
            return True

        # Create a table to display configuration
        from rich.table import Table

        table = Table(title="Configuration Settings")
        table.add_column("Key", style="cyan", width=30)
        table.add_column("Value", style="white", width=20)
        table.add_column("Description", style="green", width=50)
        table.add_column("Type", style="yellow", width=10)
        table.add_column("Options", style="blue", width=30)

        for key, item in config_items.items():
            # Format the value
            value_str = self._format_value(item.value)

            # Format options
            options_str = ""
            if item.options:
                options_str = ", ".join(map(str, item.options))

            table.add_row(key, value_str, item.description, item.type, options_str)

        self.console.print(table)
        return True

    def _show_config(self, key: str) -> bool:
        """Show detailed information for a specific configuration key."""
        config_manager = get_config_manager()
        config_item = config_manager.get_with_metadata(key)

        if not config_item:
            self.console.print(f"Configuration key '{key}' not found.", style="red")
            return True

        # Create a table to display configuration details
        from rich.table import Table

        table = Table(title=f"Configuration: {key}")
        table.add_column("Property", style="cyan", width=20)
        table.add_column("Value", style="white", width=40)

        table.add_row("Current Value", self._format_value(config_item.value))
        table.add_row("Description", config_item.description)
        table.add_row("Type", config_item.type)
        table.add_row("Default", self._format_value(config_item.default))

        if config_item.options:
            options_str = ", ".join(map(str, config_item.options))
            table.add_row("Valid Options", options_str)
        else:
            table.add_row("Valid Options", "Any value of type " + config_item.type)

        self.console.print(table)
        return True

    def _flatten_config(self, config: dict, prefix: str = "") -> dict:
        """Flatten nested configuration dictionary.

        Args:
            config: Configuration dictionary to flatten
            prefix: Key prefix for nested keys

        Returns:
            Flattened configuration dictionary
        """
        flattened = {}

        for key, value in config.items():
            full_key = f"{prefix}.{key}" if prefix else key

            if isinstance(value, dict):
                flattened.update(self._flatten_config(value, full_key))
            else:
                flattened[full_key] = value

        return flattened

    def _format_value(self, value: Any) -> str:
        """Format configuration value for display.

        Args:
            value: Value to format

        Returns:
            Formatted string representation
        """
        if value is None:
            return "[dim]None[/dim]"
        elif isinstance(value, bool):
            return "[green]true[/green]" if value else "[red]false[/red]"
        elif isinstance(value, str) and not value:
            return "[dim](empty)[/dim]"
        else:
            return str(value)

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions for set-config command with descriptions.

        Args:
            current_input: Current input text
            cursor_position: Current cursor position

        Returns:
            List of completion suggestions with descriptions
        """
        words = current_input.split()

        # Get all configuration items with their metadata
        config_manager = get_config_manager()
        config_items = config_manager.get_all_config_items()

        # If we're typing the second argument after --show
        if len(words) >= 2 and words[1] == "--show":
            if len(words) <= 3 and not (
                len(words) == 3 and current_input.endswith(" ")
            ):
                if len(words) == 2 or current_input.endswith(" "):
                    return [
                        CompletionItem(text=key, description=item.description)
                        for key, item in config_items.items()
                    ]
                else:
                    partial_key = words[2]
                    return [
                        CompletionItem(text=key, description=item.description)
                        for key, item in config_items.items()
                        if key.startswith(partial_key)
                    ]

        # For value completions, provide contextual suggestions with descriptions
        if len(words) == 2 and current_input.endswith(" "):
            key = words[1]
            if key in config_items:
                item = config_items[key]
                if item.options:
                    return [
                        CompletionItem(
                            text=str(option), description=f"Value for {key} parameter"
                        )
                        for option in item.options
                    ]
                else:
                    # Provide some common suggestions based on type
                    if item.type == "string":
                        return [
                            CompletionItem(
                                text="none", description="Disable this setting"
                            ),
                            CompletionItem(
                                text="default", description="Use default value"
                            ),
                        ]
                    elif item.type == "integer":
                        return [
                            CompletionItem(text="0", description="Zero value"),
                            CompletionItem(text="1", description="Single value"),
                            CompletionItem(text="10", description="Small value"),
                            CompletionItem(text="100", description="Medium value"),
                        ]

        # If we're typing the first argument (the key)
        if len(words) <= 2:
            keys = list(config_items.keys()) + ["--list", "--show"]
            key_descriptions = {
                **{key: item.description for key, item in config_items.items()},
                "--list": "List all configuration values",
                "--show": "Show specific configuration value",
            }

            if len(words) <= 1 or current_input.endswith(" "):
                # Complete from beginning (after command or space)
                return [
                    CompletionItem(
                        text=key,
                        description=key_descriptions.get(key, "Configuration option"),
                    )
                    for key in keys
                ]
            else:
                # Filter based on current partial input
                partial_key = words[-1]
                return [
                    CompletionItem(
                        text=key,
                        description=key_descriptions.get(key, "Configuration option"),
                    )
                    for key in keys
                    if key.startswith(partial_key)
                ]

        return []
