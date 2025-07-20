"""Base command class for ADOC toolkit interactive shell."""

from abc import ABC, abstractmethod


class Command(ABC):
    """Base class for all interactive commands."""

    @property
    @abstractmethod
    def name(self) -> str:
        """Command name."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """Command description."""
        pass

    @property
    def aliases(self) -> list[str]:
        """Command aliases."""
        return []

    def get_help(self) -> str:
        """Get detailed help text for the command.

        Returns:
            Detailed help text for the command
        """
        help_text = f"{self.name}: {self.description}"
        if self.aliases:
            help_text += f"\nAliases: {', '.join(self.aliases)}"
        return help_text

    @abstractmethod
    def execute(self, args: list[str]) -> bool:
        """Execute the command.

        Args:
            args: Command arguments

        Returns:
            True to continue, False to exit
        """
        pass

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions for this command.

        Args:
            current_input: The current input text
            cursor_position: Current cursor position in the input

        Returns:
            List of completion suggestions
        """
        return []
