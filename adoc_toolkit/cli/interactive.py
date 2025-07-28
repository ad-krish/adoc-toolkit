"""Interactive command processor using prompt_toolkit."""

import json
import shlex
import sys
from functools import reduce
from pathlib import Path
from typing import Optional, Callable, Any, Iterator

from prompt_toolkit import prompt
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.document import Document
from prompt_toolkit.history import InMemoryHistory
from rich.console import Console
from rich.text import Text

from ..http import ADOCHTTPClient
from ..models import CompletionItem
from .environment_validator import (
    validate_environments_at_startup,
    load_default_environment,
)
from .commands import (
    Command,
    ExitCommand,
    ExportExecutionMetricsCommand,
    ExportMetricsCommand,
    FindAssetCommand,
    GetCommand,
    HelpCommand,
    HistoryCommand,
    SetConfigCommand,
    ShowEnvCommand,
    TextToDQPolicyCommand,
    UseCommand,
)


# Pure functions for command processing
def parse_input_safely(user_input: str) -> list[str]:
    """Parse user input safely, handling unmatched quotes.

    Args:
        user_input: Raw user input string

    Returns:
        List of parsed parts
    """
    try:
        return shlex.split(user_input.strip())
    except ValueError:
        return user_input.strip().split()


def extract_command_and_args(parts: list[str]) -> tuple[str, list[str]]:
    """Extract command name and arguments from parsed parts.

    Args:
        parts: List of parsed input parts

    Returns:
        Tuple of (command_name, arguments_list)
    """
    if not parts:
        return "", []
    return parts[0].lower(), parts[1:]


def parse_input(user_input: str) -> tuple[str, list[str]]:
    """Parse user input into command and arguments using pure functions.

    Args:
        user_input: Raw user input

    Returns:
        Tuple of (command_name, arguments_list)
    """
    parts = parse_input_safely(user_input)
    return extract_command_and_args(parts)


def should_add_to_history(command_text: str, excluded_commands: set[str]) -> bool:
    """Determine if a command should be added to history.

    Args:
        command_text: The command text to check
        excluded_commands: Set of excluded command names

    Returns:
        True if command should be added to history
    """
    parts = command_text.strip().split()
    if not parts:
        return False

    command_name = parts[0].lower()

    # Skip excluded commands
    if command_name in excluded_commands:
        return False

    # Skip if it's just a number (history recall)
    if len(parts) == 1 and command_name.isdigit():
        return False

    return True


def update_history_list(
    history: list[str], command_text: str, max_history: int
) -> list[str]:
    """Update history list with new command, maintaining order and limits.

    Args:
        history: Current history list
        command_text: New command to add
        max_history: Maximum history size

    Returns:
        Updated history list
    """
    # Remove duplicate if it exists
    filtered_history = [cmd for cmd in history if cmd != command_text]

    # Add to front of history (most recent first)
    updated_history = [command_text] + filtered_history

    # Maintain max history limit
    return updated_history[:max_history]


def create_history_data(history: list[str], max_history: int) -> dict[str, Any]:
    """Create history data structure for serialization.

    Args:
        history: Current history list
        max_history: Maximum history size

    Returns:
        Dictionary with history data
    """
    return {
        "version": "2.0",
        "history": history[:max_history],
    }


def validate_history_data(history_data: dict[str, Any]) -> Optional[list[str]]:
    """Validate and extract history list from loaded data.

    Args:
        history_data: Loaded history data

    Returns:
        Validated history list or None if invalid
    """
    if not isinstance(history_data, dict):
        return None

    if "history" not in history_data:
        return None

    history_list = history_data["history"]
    if not isinstance(history_list, list):
        return None

    return history_list


def load_history_from_file(history_file: Path, max_history: int) -> list[str]:
    """Load command history from file using pure functions.

    Args:
        history_file: Path to history file
        max_history: Maximum history size

    Returns:
        List of history commands
    """
    try:
        if not history_file.exists():
            return []

        with open(history_file, encoding="utf-8") as f:
            history_data = json.load(f)

        history_list = validate_history_data(history_data)
        if history_list is None:
            return []

        # Load history with most recent first, limit to max_history
        return history_list[:max_history]

    except (json.JSONDecodeError, OSError, KeyError, TypeError):
        # If file is corrupted or unreadable, start with empty history
        return []


def save_history_to_file(
    history_file: Path, history: list[str], max_history: int
) -> bool:
    """Save command history to file using pure functions.

    Args:
        history_file: Path to history file
        history: Current history list
        max_history: Maximum history size

    Returns:
        True if save was successful, False otherwise
    """
    try:
        history_data = create_history_data(history, max_history)

        # Ensure parent directory exists
        history_file.parent.mkdir(parents=True, exist_ok=True)

        # Write to temporary file first, then rename for atomic operation
        temp_file = history_file.with_suffix(".tmp")
        with open(temp_file, "w", encoding="utf-8") as f:
            json.dump(history_data, f, indent=2, ensure_ascii=False)

        # Atomic rename
        temp_file.replace(history_file)
        return True

    except (OSError, TypeError):
        # Fail silently - history persistence is not critical to functionality
        return False


def create_environment_info(
    environment: Optional[str], config: Optional[dict]
) -> dict[str, str]:
    """Create environment info dictionary using pure function.

    Args:
        environment: Current environment name
        config: Environment configuration

    Returns:
        Dictionary with environment info
    """
    if not config:
        return {}

    return {
        "environment": environment or "",
        "base_url": config.get("base_url", ""),
        "access_key": config.get("access_key", ""),
        "secret_key": config.get("secret_key", ""),
    }


def create_prompt_text(environment: Optional[str]) -> str:
    """Create prompt text using pure function.

    Args:
        environment: Current environment name

    Returns:
        Formatted prompt text
    """
    if environment:
        return f"ADOC ({environment}) > "
    return "ADOC > "


def create_status_message(response) -> tuple[str, str]:
    """Create status message and style for HTTP response using pure function.

    Args:
        response: HTTPResponse object

    Returns:
        Tuple of (status_message, style)
    """
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

    return status_msg, style


def extract_error_message(response) -> Optional[str]:
    """Extract error message from response using pure function.

    Args:
        response: HTTPResponse object

    Returns:
        Error message string or None
    """
    if response.is_success:
        return None

    try:
        error_data = response.json()
        if isinstance(error_data, dict):
            if "message" in error_data:
                return error_data["message"]
            elif "error" in error_data:
                return error_data["error"]
    except ValueError:
        # Not JSON, show raw text if reasonable length
        if len(response.text) < 200:
            return response.text

    return None


def create_command_completions(commands: dict[str, Command]) -> Iterator[Completion]:
    """Create command name completions using pure function.

    Args:
        commands: Dictionary of available commands

    Yields:
        Completion objects for command names
    """
    for cmd_name, cmd in commands.items():
        if cmd_name == cmd.name:  # Only show primary names, not aliases
            yield Completion(cmd_name, start_position=0, display_meta=cmd.description)


def create_filtered_completions(
    commands: dict[str, Command], current_word: str
) -> Iterator[Completion]:
    """Create filtered command completions using pure function.

    Args:
        commands: Dictionary of available commands
        current_word: Current word being typed

    Yields:
        Completion objects for matching commands
    """
    for cmd_name, cmd in commands.items():
        if cmd_name == cmd.name and cmd_name.startswith(current_word):
            yield Completion(
                cmd_name,
                start_position=-len(current_word),
                display_meta=cmd.description,
            )


def create_structured_completion(completion: Any, start_position: int) -> Completion:
    """Create completion object from structured completion data using pure function.

    Args:
        completion: Completion data (CompletionItem or string)
        start_position: Start position for completion

    Returns:
        Completion object
    """
    if isinstance(completion, CompletionItem):
        return Completion(
            completion.text,
            start_position=start_position,
            display_meta=completion.description,
        )
    else:
        return Completion(completion, start_position=start_position)


def create_completion_from_structured(
    completion: Any, current_word: str, is_new_word: bool
) -> Completion:
    """Create completion from structured completion data using pure function.

    Args:
        completion: Structured completion data
        current_word: Current word being typed
        is_new_word: Whether starting a new word

    Returns:
        Completion object
    """
    if is_new_word:
        return create_structured_completion(completion, 0)
    else:
        if isinstance(completion, CompletionItem):
            if completion.text.startswith(current_word):
                return Completion(
                    completion.text,
                    start_position=-len(current_word),
                    display_meta=completion.description,
                )
        else:
            if completion.startswith(current_word):
                return Completion(completion, start_position=-len(current_word))
        return None


def filter_valid_completions(
    completions: list[Any], current_word: str, is_new_word: bool
) -> Iterator[Completion]:
    """Filter and create valid completions using pure function.

    Args:
        completions: List of completion data
        current_word: Current word being typed
        is_new_word: Whether starting a new word

    Yields:
        Valid Completion objects
    """
    for completion in completions:
        result = create_completion_from_structured(
            completion, current_word, is_new_word
        )
        if result is not None:
            yield result


class ADOCCompleter(Completer):
    """Custom completer for ADOC commands with command-specific completions."""

    def __init__(self, commands: dict[str, Command]):
        self.commands = commands

    def get_completions(self, document: Document, complete_event=None):
        """Generate completions based on current document state."""
        text = document.text
        words = text.split()

        if not words:
            # Complete command names using pure function
            yield from create_command_completions(self.commands)
        elif len(words) == 1 and not text.endswith(" "):
            # Complete command names that start with the current word
            current_word = words[0]
            yield from create_filtered_completions(self.commands, current_word)
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
                        is_new_word = text.endswith(" ")
                        current_word = words[-1] if not is_new_word else ""

                        if is_new_word:
                            # Starting a new word
                            for completion in structured_completions:
                                yield create_structured_completion(completion, 0)
                        else:
                            # Completing current word
                            yield from filter_valid_completions(
                                structured_completions, current_word, False
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
                    is_new_word = text.endswith(" ")
                    current_word = words[-1] if not is_new_word else ""

                    yield from filter_valid_completions(
                        completions, current_word, is_new_word
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

        # Validate environment configuration at startup
        self._validate_environment_config()

        # Load default environment if specified
        self._load_default_environment()

        self._setup_default_commands()
        self._load_history_file()

    def _validate_environment_config(self) -> None:
        """Validate environment configuration at startup."""
        is_valid, errors = validate_environments_at_startup()

        if not is_valid:
            self.console.print(
                "\n🔍 Environment Configuration Validation", style="bold red"
            )
            self.console.print("=" * 50, style="red")

            for error in errors:
                self.console.print(f"\n{error}")

            self.console.print("\n" + "=" * 50, style="red")
            self.console.print(
                "❌ Please fix the configuration errors above before continuing.\n"
                "   The toolkit will start, but you may encounter issues with environment commands.\n"
                "   See docs/environment-setup.md for detailed setup instructions.",
                style="red",
            )
            self.console.print()

    def _load_default_environment(self) -> None:
        """Load and set the default environment if specified in config."""
        default_env_data = load_default_environment()

        if default_env_data:
            env_name, env_config = default_env_data
            self._on_environment_change(env_name, env_config)
            self.console.print(
                f"✅ Automatically loaded default environment: {env_name}",
                style="green",
            )
            self.console.print()

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
        export_execution_metrics_cmd = ExportExecutionMetricsCommand(
            environment_info_callback=self.get_current_environment_info
        )
        get_cmd = GetCommand(http_client=self.http_client)
        find_asset_cmd = FindAssetCommand(http_client=self.http_client)
        text_to_dq_policy_cmd = TextToDQPolicyCommand()

        self.register_command(help_cmd)
        self.register_command(exit_cmd)
        self.register_command(use_cmd)
        self.register_command(show_env_cmd)
        self.register_command(history_cmd)
        self.register_command(set_config_cmd)
        self.register_command(export_metrics_cmd)
        self.register_command(export_execution_metrics_cmd)
        self.register_command(get_cmd)
        self.register_command(find_asset_cmd)
        self.register_command(text_to_dq_policy_cmd)

    def register_command(self, command: Command) -> None:
        """Register a command in the processor.

        Args:
            command: Command instance to register
        """
        self.commands[command.name] = command

        # Register aliases using functional approach
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
        """Get current environment information using pure function.

        Returns:
            Dictionary with environment info (base_url, access_key, secret_key)
        """
        return create_environment_info(
            self.current_environment, self.current_environment_config
        )

    def add_to_history(self, command_text: str) -> None:
        """Add a command to history using pure functions.

        Args:
            command_text: Command text to add to history
        """
        if should_add_to_history(command_text, self._excluded_commands):
            # Add to prompt_toolkit history for arrow key navigation
            self.history.append_string(command_text)

            # Also maintain our custom history for the history command
            self.command_history = update_history_list(
                self.command_history, command_text, self._max_history
            )
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
        """Load command history from file and populate prompt_toolkit history."""
        self.command_history = load_history_from_file(
            self._history_file, self._max_history
        )

        # Also populate prompt_toolkit history for arrow key navigation
        # Reverse the order since prompt_toolkit expects most recent commands at the end
        for command in reversed(self.command_history):
            if should_add_to_history(command, self._excluded_commands):
                self.history.append_string(command)

    def _save_history_file(self) -> None:
        """Save command history to file using pure function."""
        save_history_to_file(
            self._history_file, self.command_history, self._max_history
        )

    def _handle_http_response(self, response) -> None:
        """Handle HTTP responses with default logging and error reporting.

        Args:
            response: HTTPResponse object
        """
        # Use pure functions to create status message and extract error
        status_msg, style = create_status_message(response)
        self.console.print(status_msg, style=style)

        error_message = extract_error_message(response)
        if error_message:
            self.console.print(f"Error: {error_message}", style="red")

    def _get_prompt_text(self) -> str:
        """Get the prompt text with current environment using pure function."""
        return create_prompt_text(self.current_environment)

    def get_completer(self) -> ADOCCompleter:
        """Create a custom completer for available commands."""
        return ADOCCompleter(self.commands)

    def parse_input(self, user_input: str) -> tuple[str, list[str]]:
        """Parse user input into command and arguments using pure function.

        Args:
            user_input: Raw user input

        Returns:
            Tuple of (command_name, arguments_list)
        """
        return parse_input(user_input)

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
