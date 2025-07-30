"""Help command implementation."""

from .base import Command


class HelpCommand(Command):
    """Display help information."""

    def __init__(self, command_registry: dict[str, Command]):
        self.command_registry = command_registry

    @property
    def name(self) -> str:
        return "help"

    @property
    def description(self) -> str:
        return "Show available commands and their descriptions"

    @property
    def aliases(self) -> list[str]:
        return ["h", "?"]

    def execute(self, args: list[str]) -> bool:
        if args and args[0] in self.command_registry:
            cmd = self.command_registry[args[0]]
            print(cmd.get_help())
        else:
            print("Available commands:")
            # Get unique commands (avoid duplicates from aliases)
            unique_commands = {}
            for name, cmd in self.command_registry.items():
                if name == cmd.name:  # Only show primary name, not aliases
                    unique_commands[name] = cmd

            for i, cmd in enumerate(unique_commands.values()):
                # Add spacing between commands (except before the first one)
                if i > 0:
                    print()
                
                # Command name in bold on first line
                print(f"  \033[1m{cmd.name}\033[0m")
                
                # Description on second line
                print(f"    {cmd.description}")
                
                # Aliases on separate line in subtle gray text
                if cmd.aliases:
                    print(f"    \033[90mAliases: {', '.join(cmd.aliases)}\033[0m")
                
                # Contributor information in subtle gray text
                if cmd.contributor:
                    print(f"    \033[96mContributor: {cmd.contributor}\033[0m")
            
            print(
                "\nType 'help <command>' or '<command> --help' for detailed help "
                "on a specific command."
            )
        return True
