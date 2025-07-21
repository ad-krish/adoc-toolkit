"""Base command class for ADOC toolkit commands."""

from abc import ABC, abstractmethod
from typing import Union

from ...models import CompletionItem


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

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[Union[str, CompletionItem]]:
        """Get auto-completion suggestions for this command.

        Args:
            current_input: The current input text
            cursor_position: Current cursor position in the input

        Returns:
            List of completion suggestions (strings or CompletionItem objects)
        """
        return []

    def get_structured_completions(
        self, current_input: str, cursor_position: int
    ) -> list[CompletionItem]:
        """Get structured auto-completion suggestions with descriptions.

        Args:
            current_input: The current input text
            cursor_position: Current cursor position in the input

        Returns:
            List of CompletionItem objects with descriptions
        """
        completions = self.get_completions(current_input, cursor_position)
        structured_completions = []

        for completion in completions:
            if isinstance(completion, CompletionItem):
                structured_completions.append(completion)
            else:
                # Convert string completion to CompletionItem
                structured_completions.append(CompletionItem(text=completion))

        return structured_completions
