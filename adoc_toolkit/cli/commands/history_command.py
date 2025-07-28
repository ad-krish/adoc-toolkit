"""History command implementation."""

import sys
from typing import Callable, Optional

from ...models import CommandExecution
from .base import Command


class HistoryCommand(Command):
    """Show and manage command history."""

    def __init__(
        self,
        get_history_callback: Optional[Callable[[], list[str]]] = None,
        recall_callback: Optional[Callable[[str], None]] = None,
        get_executions_callback: Optional[Callable[[], list[CommandExecution]]] = None,
    ):
        """Initialize HistoryCommand.

        Args:
            get_history_callback: Function to get command history
            recall_callback: Function to recall a command by number
            get_executions_callback: Function to get command execution history
        """
        self.get_history_callback = get_history_callback
        self.recall_callback = recall_callback
        self.get_executions_callback = get_executions_callback

    @property
    def name(self) -> str:
        return "history"

    @property
    def description(self) -> str:
        return "Show command history and recall previous commands"

    @property
    def aliases(self) -> list[str]:
        return ["hist"]

    def get_help(self) -> str:
        """Get detailed help for history command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: history [number] | history --executions [count]\n\n"
        help_text += "Display command history (up to 100 commands):\n"
        help_text += "- Shows 25 commands at a time, press any key for next 25\n"
        help_text += "- Latest commands appear first\n"
        help_text += "- Each command has a number for easy recall\n\n"
        help_text += "Display execution history:\n"
        help_text += "- history --executions [count]: Show execution details\n"
        help_text += "- count: Number to show (10,25,50,100), default 25\n"
        help_text += "- Shows command, status, duration, start/end times\n"
        help_text += "- Press any key for next set, <escape> to exit\n\n"
        help_text += "Recall a command:\n"
        help_text += (
            "- history <number>: Loads command into prompt without executing\n\n"
        )
        help_text += "History excludes: history, help, exit commands and duplicates.\n"
        help_text += "Duplicate commands are moved to top of history list."
        return help_text

    def _display_history_page(
        self, history_items: list[str], start_idx: int, page_size: int = 25
    ) -> bool:
        """Display a page of history items.

        Args:
            history_items: List of history commands
            start_idx: Starting index for this page
            page_size: Number of items per page

        Returns:
            True if there are more pages, False if this is the last page
        """
        end_idx = min(start_idx + page_size, len(history_items))

        if start_idx >= len(history_items):
            return False

        print(f"\nHistory (showing {start_idx + 1}-{end_idx} of {len(history_items)}):")
        print("-" * 50)

        for i in range(start_idx, end_idx):
            # History numbers start from 1, latest first
            history_num = i + 1
            command = history_items[i]
            print(f"{history_num:3d}: {command}")

        has_more = end_idx < len(history_items)
        if has_more:
            remaining = min(page_size, len(history_items) - end_idx)
            print(f"\nPress any key to show next {remaining} commands...")

        return has_more

    def _wait_for_keypress(self) -> bool:
        """Wait for user to press any key.

        Returns:
            True to continue, False if escape was pressed
        """
        try:
            # Try to get a single keypress without Enter
            import termios
            import tty

            if sys.stdin.isatty():
                # Unix-like systems
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    key = sys.stdin.read(1)
                    # Check for escape key (ASCII 27)
                    if ord(key) == 27:
                        return False
                    return True
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            else:
                # Fallback for non-TTY environments
                response = input()
                return response.lower() != "q" and response.lower() != "quit"
        except (ImportError, OSError):
            # Windows or other systems - fallback to input()
            response = input()
            return response.lower() != "q" and response.lower() != "quit"

    def _display_executions_page(
        self, executions: list[CommandExecution], start_idx: int, page_size: int
    ) -> bool:
        """Display a page of execution items.

        Args:
            executions: List of command executions
            start_idx: Starting index for this page
            page_size: Number of items per page

        Returns:
            True if there are more pages, False if this is the last page
        """
        end_idx = min(start_idx + page_size, len(executions))

        if start_idx >= len(executions):
            return False

        print(
            f"\nExecution History (showing {start_idx + 1}-{end_idx} of {len(executions)}):"
        )
        print("-" * 120)
        print(
            f"{'#':<3} {'Command':<40} {'Status':<8} {'Duration':<12} {'Start Time':<19} {'End Time':<19}"
        )
        print("-" * 120)

        for i in range(start_idx, end_idx):
            execution_num = i + 1
            execution = executions[i]

            # Truncate long commands for display
            display_command = execution.command
            if len(display_command) > 37:
                display_command = display_command[:34] + "..."

            print(
                f"{execution_num:<3} {display_command:<40} {execution.status:<8} "
                f"{execution.formatted_duration:<12} {execution.formatted_start_time:<19} "
                f"{execution.formatted_end_time:<19}"
            )

        has_more = end_idx < len(executions)
        if has_more:
            remaining = min(page_size, len(executions) - end_idx)
            print(
                f"\nPress any key to show next {remaining} executions, <escape> to exit..."
            )

        return has_more

    def _parse_executions_args(self, args: list[str]) -> int:
        """Parse --executions arguments to get page size.

        Args:
            args: Command arguments

        Returns:
            Page size (10, 25, 50, or 100)
        """
        # Default page size
        page_size = 25

        # Look for --executions option
        for i, arg in enumerate(args):
            if arg == "--executions":
                # Check if next argument is a valid page size
                if i + 1 < len(args):
                    try:
                        requested_size = int(args[i + 1])
                        if requested_size in [10, 25, 50, 100]:
                            page_size = requested_size
                        else:
                            print(
                                f"Warning: Invalid page size {requested_size}. Valid sizes: 10, 25, 50, 100. Using default: 25"
                            )
                    except ValueError:
                        # Next argument isn't a number, use default
                        pass
                break

        return page_size

    def execute(self, args: list[str]) -> bool:
        """Execute the history command."""
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
            return True

        # Check for --executions option
        if args and "--executions" in args:
            if not self.get_executions_callback:
                print("Error: Execution history functionality not available")
                return True

            # Get execution history from the processor
            executions = self.get_executions_callback()

            if not executions:
                print("No execution history available")
                return True

            # Parse page size from arguments
            page_size = self._parse_executions_args(args)
            start_idx = 0

            # Display executions in pages
            while start_idx < len(executions):
                has_more = self._display_executions_page(
                    executions, start_idx, page_size
                )

                if has_more:
                    if not self._wait_for_keypress():
                        break
                    start_idx += page_size
                else:
                    break

            return True

        if not self.get_history_callback:
            print("Error: History functionality not available")
            return True

        # Get history from the processor
        history_items = self.get_history_callback()

        # If a number is provided, recall that command
        if args:
            try:
                history_num = int(args[0])
                if history_num < 1 or history_num > len(history_items):
                    max_num = len(history_items)
                    print(f"Error: History number {history_num} is out of range")
                    print(f"Valid range: 1-{max_num}")
                    return True

                # Recall the command (history_num - 1 because list is 0-indexed)
                command_to_recall = history_items[history_num - 1]

                if self.recall_callback:
                    self.recall_callback(command_to_recall)
                    print(f"Command recalled: {command_to_recall}")
                else:
                    print(f"Command {history_num}: {command_to_recall}")

                return True
            except ValueError:
                print(f"Error: '{args[0]}' is not a valid number")
                return True

        # Display history if no arguments
        if not history_items:
            print("No command history available")
            return True

        # Display history in pages of 25
        page_size = 25
        start_idx = 0

        while start_idx < len(history_items):
            has_more = self._display_history_page(history_items, start_idx, page_size)

            if has_more:
                if not self._wait_for_keypress():
                    break
                start_idx += page_size
            else:
                break

        return True

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions for history command."""
        # Parse the input to get the current argument being typed
        parts = current_input.strip().split()

        # Check if we're after --executions
        if "--executions" in parts:
            exec_index = parts.index("--executions")
            if exec_index == 1:  # "history --executions"
                if len(parts) == 2:
                    # "history --executions " case (trailing space) - return all page sizes
                    if current_input.endswith(" "):
                        return ["10", "25", "50", "100"]
                elif len(parts) == 3:
                    # "history --executions 1" case - return matching sizes
                    current_arg = parts[2]
                    page_sizes = ["10", "25", "50", "100"]
                    return [size for size in page_sizes if size.startswith(current_arg)]

        # If we're typing the first argument after "history"
        if len(parts) <= 2:
            current_arg = parts[1] if len(parts) == 2 else ""
            completions = []

            # Add --executions option
            if current_arg == "" or "--executions".startswith(current_arg):
                completions.append("--executions")

            # Add history number completions if we have history callback
            if self.get_history_callback:
                history_items = self.get_history_callback()
                if history_items:
                    max_num = len(history_items)
                    for i in range(1, min(max_num + 1, 11)):  # Limit to first 10
                        num_str = str(i)
                        if current_arg == "" or num_str.startswith(current_arg):
                            completions.append(num_str)

            return completions

        return []
