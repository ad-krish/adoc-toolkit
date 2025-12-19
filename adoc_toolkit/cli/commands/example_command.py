"""Example command implementation - template for new commands."""

from typing import Union

from rich.console import Console

from ...models import CompletionItem
from .base import Command


class ExampleCommand(Command):
    """Example command that demonstrates the command pattern."""

    @property
    def name(self) -> str:
        """Command name used for invocation."""
        return "example"

    @property
    def description(self) -> str:
        """Brief description for help listings."""
        return "Example command template"

    @property
    def aliases(self) -> list[str]:
        """Command aliases."""
        return ["ex", "demo"]

    def get_help(self) -> str:
        """Get detailed help text for the command.

        Returns:
            Detailed help text with usage examples
        """
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: example [options] [arguments]\n\n"
        help_text += "This is an example command that demonstrates the command pattern.\n\n"
        help_text += "Options:\n"
        help_text += "  --help     Show this help message\n"
        help_text += "  --option1  Description of option1\n\n"
        help_text += "Examples:\n"
        help_text += "  example                    # Basic usage\n"
        help_text += "  example --option1 value    # With option\n"
        help_text += "  example arg1 arg2          # With arguments\n"
        return help_text

    def execute(self, args: list[str]) -> bool:
        """Execute the command.

        Args:
            args: Command arguments

        Returns:
            True to continue interactive mode, False to exit
        """
        console = Console()

        # Handle --help flag
        if args and args[0] == "--help":
            console.print(self.get_help())
            return True

        # Parse arguments
        if not args:
            console.print("Error: Arguments required", style="red")
            console.print("Usage: example [options] [arguments]")
            console.print("Type 'example --help' for more information")
            return True

        # Implement command logic here
        try:
            # Your command implementation
            result = self._process_arguments(args)
            console.print(f"Command executed successfully: {result}", style="green")
            return True
        except Exception as e:
            console.print(f"Error executing command: {e}", style="red")
            return True

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions.

        Args:
            current_input: The current input text
            cursor_position: Current cursor position

        Returns:
            List of completion suggestions
        """
        # Parse current input to determine context
        words = current_input[:cursor_position].split()

        if len(words) == 1 and words[0] == self.name:
            # Suggest options and arguments
            return [
                "--help",
                "--option1",
                "argument1",
                "argument2"
            ]
        elif len(words) > 1 and words[1] == "--option1":
            # Suggest values for option1
            return [
                "value1",
                "value2",
                "value3"
            ]

        return []

    def _process_arguments(self, args: list[str]) -> str:
        """Process command arguments.

        Args:
            args: Command arguments

        Returns:
            Processing result
        """
        # Implement argument processing logic
        return f"Processed {len(args)} arguments: {', '.join(args)}"
