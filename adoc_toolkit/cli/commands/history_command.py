"""History command implementation."""

from typing import Callable, Optional

from .base import Command


class HistoryCommand(Command):
    """Show and manage command history."""

    def __init__(
        self,
        get_history_callback: Optional[Callable[[], list[str]]] = None,
        recall_callback: Optional[Callable[[str], None]] = None,
    ):
        """Initialize HistoryCommand.

        Args:
            get_history_callback: Function to get command history
            recall_callback: Function to recall a command by number
        """
        self.get_history_callback = get_history_callback
        self.recall_callback = recall_callback

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
        help_text += "Usage: history [number]\n\n"
        help_text += "Display command history (up to 100 commands):\n"
        help_text += "- Shows 25 commands at a time, press any key for next 25\n"
        help_text += "- Latest commands appear first\n"
        help_text += "- Each command has a number for easy recall\n\n"
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

    def _wait_for_keypress(self) -> None:
        """Wait for user to press any key."""
        try:
            # Try to get a single keypress without Enter
            import sys
            import termios
            import tty

            if sys.stdin.isatty():
                # Unix-like systems
                old_settings = termios.tcgetattr(sys.stdin)
                try:
                    tty.setcbreak(sys.stdin.fileno())
                    sys.stdin.read(1)
                finally:
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)
            else:
                # Fallback for non-TTY environments
                input()
        except (ImportError, OSError):
            # Windows or other systems - fallback to input()
            input()

    def execute(self, args: list[str]) -> bool:
        """Execute the history command."""
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
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
                self._wait_for_keypress()
                start_idx += page_size
            else:
                break

        return True

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions for history command."""
        if not self.get_history_callback:
            return []

        # Parse the input to get the current argument being typed
        parts = current_input.strip().split()

        # If we're typing the first argument after "history"
        if len(parts) <= 2:
            history_items = self.get_history_callback()
            if not history_items:
                return []

            current_arg = parts[1] if len(parts) == 2 else ""

            # Provide number completions for valid history numbers
            max_num = len(history_items)
            completions = []

            for i in range(1, max_num + 1):
                num_str = str(i)
                if current_arg == "" or num_str.startswith(current_arg):
                    completions.append(num_str)

            return completions[:10]  # Limit to first 10 for performance

        return []
