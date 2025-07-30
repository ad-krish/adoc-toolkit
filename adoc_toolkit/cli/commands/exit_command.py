"""Exit command implementation."""

from .base import Command


class ExitCommand(Command):
    """Exit the interactive session."""

    @property
    def name(self) -> str:
        return "exit"

    @property
    def description(self) -> str:
        return "Exit the interactive session"

    @property
    def aliases(self) -> list[str]:
        return ["quit", "q"]

    @property
    def contributor(self) -> str | None:
        return None

    def get_help(self) -> str:
        """Get detailed help for exit command."""
        return (
            f"{self.name}: {self.description}\nAliases: {', '.join(self.aliases)}\n\n"
            "Exits the interactive ADOC toolkit session."
        )

    def execute(self, args: list[str]) -> bool:
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
            return True
        print("Goodbye!")
        return False
