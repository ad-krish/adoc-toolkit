"""Interactive command processor using prompt_toolkit."""

import json
import shlex
from pathlib import Path
from typing import Optional

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.text import Text

from ..http import ADOCHTTPClient
from ..models import CompletionItem
from .commands import (
    Command,
    ExitCommand,
    ExportMetricsCommand,
    GetCommand,
    HelpCommand,
    HistoryCommand,
    SetConfigCommand,
    ShowEnvCommand,
    UseCommand,
)


class ADOCCompleter(Completer):
    """Custom completer for ADOC commands with command-specific completions."""

    def __init__(self, commands: dict[str, Command]):
        self.commands = commands

    def get_completions(self, document: Document, complete_event=None):
        """Generate completions based on current document state."""
        text = document.text
        words = text.split()

        if not words:
            # Complete command names
            for cmd_name, cmd in self.commands.items():
                if cmd_name == cmd.name:  # Only show primary names, not aliases
                    yield Completion(
                        cmd_name, start_position=0, display_meta=cmd.description
                    )
        elif len(words) == 1 and not text.endswith(" "):
            # Complete command names that start with the current word
            current_word = words[0]
            for cmd_name, cmd in self.commands.items():
                if cmd_name == cmd.name and cmd_name.startswith(current_word):
                    yield Completion(
                        cmd_name,
                        start_position=-len(current_word),
                        display_meta=cmd.description,
                    )
        else:
            # Command-specific completions
            cmd_name = words[0]
            if cmd_name in self.commands:
                command = self.commands[cmd_name]

                # Try to get structured completions first
                try:
                    structured_completions = command.get_structured_completions(
                        text, document.cursor_position
                    )
                    if structured_completions:
                        # Get the current word being typed
                        if text.endswith(" "):
                            # Starting a new word
                            for completion in structured_completions:
                                yield Completion(
                                    completion.text,
                                    start_position=0,
                                    display_meta=completion.description,
                                )
                        else:
                            # Completing current word
                            current_word = words[-1]
                            for completion in structured_completions:
                                if completion.text.startswith(current_word):
                                    yield Completion(
                                        completion.text,
                                        start_position=-len(current_word),
                                        display_meta=completion.description,
                                    )
                        return
                except AttributeError:
                    # Fall back to old-style completions if get_structured_completions
                    # doesn't exist
                    pass

                # Fall back to old-style completions
                completions = command.get_completions(text, document.cursor_position)
                if completions:
                    # Get the current word being typed
                    if text.endswith(" "):
                        # Starting a new word
                        for completion in completions:
                            if isinstance(completion, CompletionItem):
                                yield Completion(
                                    completion.text,
                                    start_position=0,
                                    display_meta=completion.description,
                                )
                            else:
                                yield Completion(completion, start_position=0)
                    else:
                        # Completing current word
                        current_word = words[-1]
                        for completion in completions:
                            if isinstance(completion, CompletionItem):
                                if completion.text.startswith(current_word):
                                    yield Completion(
                                        completion.text,
                                        start_position=-len(current_word),
                                        display_meta=completion.description,
                                    )
                            else:
                                if completion.startswith(current_word):
                                    yield Completion(
                                        completion, start_position=-len(current_word)
                                    )


class InteractiveProcessor:
    """Interactive command processor with prompt_toolkit integration."""

    def __init__(self, config_file: Optional[str] = None):
        # Initialize configuration manager with specified config file
        from ..config import reset_config_manager

        if config_file:
            reset_config_manager(Path(config_file))
        else:
            reset_config_manager()

        self.console = Console()
        self.commands: dict[str, Command] = {}
        self.history = InMemoryHistory()

        # Environment state
        self.current_environment: Optional[str] = None
        self.current_environment_config: Optional[dict] = None

        # Command history tracking (separate from prompt_toolkit history)
        self.command_history: list[str] = []
        self._max_history = 100
        self._excluded_commands = {
            "history",
            "help",
            "exit",
            "quit",
            "h",
            "?",
            "q",
            "hist",
        }
        self._pending_recall_command: Optional[str] = None

        # History file management
        self._history_file = Path.home() / ".adoc-toolkit-history"

        # HTTP client for API interactions
        self.http_client = ADOCHTTPClient(
            environment_info_callback=self.get_current_environment_info,
            response_handler=self._handle_http_response,
        )

        self._setup_default_commands()
        self._load_history_file()

    def _setup_default_commands(self) -> None:
        """Set up default commands (help, exit)."""
        help_cmd = HelpCommand(self.commands)
        exit_cmd = ExitCommand()
        use_cmd = UseCommand(environment_callback=self._on_environment_change)
        show_env_cmd = ShowEnvCommand(
            environment_info_callback=self.get_current_environment_info
        )
        history_cmd = HistoryCommand(
            get_history_callback=self.get_command_history,
            recall_callback=self.recall_command,
        )
        set_config_cmd = SetConfigCommand()
        export_metrics_cmd = ExportMetricsCommand(
            environment_info_callback=self.get_current_environment_info
        )
        get_cmd = GetCommand(http_client=self.http_client)

        self.register_command(help_cmd)
        self.register_command(exit_cmd)
        self.register_command(use_cmd)
        self.register_command(show_env_cmd)
        self.register_command(history_cmd)
        self.register_command(set_config_cmd)
        self.register_command(export_metrics_cmd)
        self.register_command(get_cmd)

    def register_command(self, command: Command) -> None:
        """Register a command in the processor.

        Args:
            command: Command instance to register
        """
        self.commands[command.name] = command

        # Register aliases
        for alias in command.aliases:
            self.commands[alias] = command

    def _on_environment_change(
        self, environment_name: str, environment_config: dict
    ) -> None:
        """Handle environment change notification.

        Args:
            environment_name: Name of the new environment
            environment_config: Configuration for the new environment
        """
        self.current_environment = environment_name
        self.current_environment_config = environment_config

    def get_current_environment_info(self) -> dict:
        """Get current environment information.

        Returns:
            Dictionary with environment info (base_url, access_key, secret_key)
        """
        if not self.current_environment_config:
            return {}

        return {
            "environment": self.current_environment,
            "base_url": self.current_environment_config.get("base_url", ""),
            "access_key": self.current_environment_config.get("access_key", ""),
            "secret_key": self.current_environment_config.get("secret_key", ""),
        }

    def add_to_history(self, command_text: str) -> None:
        """Add a command to the history, handling duplicates and limits.

        Args:
            command_text: The full command text to add to history
        """
        # Don't add excluded commands or numbers (history recalls)
        parts = command_text.strip().split()
        if not parts:
            return

        command_name = parts[0].lower()

        # Skip excluded commands
        if command_name in self._excluded_commands:
            return

        # Skip if it's just a number (history recall)
        if len(parts) == 1 and command_name.isdigit():
            return

        # Remove duplicate if it exists
        if command_text in self.command_history:
            self.command_history.remove(command_text)

        # Add to front of history (most recent first)
        self.command_history.insert(0, command_text)

        # Maintain max history limit
        if len(self.command_history) > self._max_history:
            self.command_history = self.command_history[: self._max_history]

        # Save to file after each addition
        self._save_history_file()

    def get_command_history(self) -> list[str]:
        """Get the current command history.

        Returns:
            List of command history (most recent first)
        """
        return self.command_history.copy()

    def recall_command(self, command_text: str) -> None:
        """Set a command to be recalled/populated in the next prompt.

        Args:
            command_text: The command text to recall
        """
        self._pending_recall_command = command_text

    def _load_history_file(self) -> None:
        """Load command history from file on startup."""
        try:
            if self._history_file.exists():
                with open(self._history_file, encoding="utf-8") as f:
                    history_data = json.load(f)

                # Validate the data structure
                if isinstance(history_data, dict) and "history" in history_data:
                    history_list = history_data["history"]
                    if isinstance(history_list, list):
                        # Load history with most recent first, limit to max_history
                        self.command_history = history_list[: self._max_history]
        except (json.JSONDecodeError, OSError, KeyError, TypeError):
            # If file is corrupted or unreadable, start with empty history
            # Don't show error to user as this is not critical
            self.command_history = []

    def _save_history_file(self) -> None:
        """Save command history to file."""
        try:
            history_data = {
                "version": "1.0",
                "history": self.command_history[: self._max_history],
            }

            # Ensure parent directory exists
            self._history_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first, then rename for atomic operation
            temp_file = self._history_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(history_data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self._history_file)

        except (OSError, TypeError):
            # Fail silently - history persistence is not critical to functionality
            pass

    def _handle_http_response(self, response) -> None:
        """Handle HTTP responses with default logging and error reporting.

        Args:
            response: HTTPResponse object
        """
        # Log request information
        method = response.request_info.method
        endpoint = response.request_info.endpoint
        retries = response.request_info.retries_attempted

        if response.is_success:
            style = "green"
            status_msg = f"✅ {method} {endpoint} - {response.status_code}"
        elif response.is_client_error:
            style = "yellow"
            status_msg = f"⚠️  {method} {endpoint} - {response.status_code}"
        else:
            style = "red"
            status_msg = f"❌ {method} {endpoint} - {response.status_code}"

        if retries > 0:
            status_msg += f" (after {retries} retries)"

        self.console.print(status_msg, style=style)

        # For non-success responses, show error details if available
        if not response.is_success:
            try:
                error_data = response.json()
                if isinstance(error_data, dict) and "message" in error_data:
                    self.console.print(f"Error: {error_data['message']}", style="red")
                elif isinstance(error_data, dict) and "error" in error_data:
                    self.console.print(f"Error: {error_data['error']}", style="red")
            except ValueError:
                # Not JSON, show raw text if reasonable length
                if len(response.text) < 200:
                    self.console.print(f"Error: {response.text}", style="red")

    def _get_prompt_text(self) -> str:
        """Get the prompt text with current environment."""
        if self.current_environment:
            return f"ADOC ({self.current_environment}) > "
        return "ADOC > "

    def get_completer(self) -> ADOCCompleter:
        """Create a custom completer for available commands."""
        return ADOCCompleter(self.commands)

    def parse_input(self, user_input: str) -> tuple[str, list[str]]:
        """Parse user input into command and arguments.

        Args:
            user_input: Raw user input

        Returns:
            Tuple of (command_name, arguments_list)
        """
        try:
            parts = shlex.split(user_input.strip())
        except ValueError:
            # Handle unmatched quotes gracefully
            parts = user_input.strip().split()

        if not parts:
            return "", []

        return parts[0].lower(), parts[1:]

    def execute_command(self, command_name: str, args: list[str]) -> bool:
        """Execute a command by name.

        Args:
            command_name: Name of command to execute
            args: Command arguments

        Returns:
            True to continue, False to exit
        """
        if command_name not in self.commands:
            self.console.print(f"Unknown command: {command_name}", style="red")
            self.console.print("Type 'help' for available commands.", style="yellow")
            return True

        # Check for --help flag in args
        if args and args[0] == "--help":
            self.console.print(self.commands[command_name].get_help())
            return True

        try:
            return self.commands[command_name].execute(args)
        except Exception as e:
            self.console.print(f"Error executing command: {e}", style="red")
            return True

    def show_banner(self) -> None:
        """Display welcome banner."""
        banner = Text("ADOC Toolkit Interactive Shell", style="bold blue")
        self.console.print(banner)
        self.console.print("Type 'help' for available commands, 'exit' to quit.\n")

    def run(self) -> None:
        """Run the interactive session."""
        self.show_banner()
        completer = self.get_completer()

        try:
            while True:
                try:
                    # Check if we have a pending recall command
                    default_text = ""
                    if self._pending_recall_command:
                        default_text = self._pending_recall_command
                        self._pending_recall_command = None

                    user_input = prompt(
                        self._get_prompt_text(),
                        completer=completer,
                        history=self.history,
                        complete_while_typing=True,
                        default=default_text,
                    )

                    if not user_input.strip():
                        continue

                    # Add to history before executing (unless it's an excluded command)
                    self.add_to_history(user_input.strip())

                    command_name, args = self.parse_input(user_input)
                    if not command_name:
                        continue

                    should_continue = self.execute_command(command_name, args)
                    if not should_continue:
                        break

                except KeyboardInterrupt:
                    self.console.print(
                        "\nUse 'exit' or Ctrl+D to quit.", style="yellow"
                    )
                    continue
                except EOFError:
                    self.console.print("\nGoodbye!")
                    break
        except Exception as e:
            self.console.print(f"Unexpected error: {e}", style="red")
            raise
