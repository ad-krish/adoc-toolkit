"""Show environment command implementation."""

from typing import Any, Callable, Optional

from .base import Command


class ShowEnvCommand(Command):
    """Show current environment configuration with masked credentials."""

    def __init__(
        self, environment_info_callback: Optional[Callable[[], dict[str, Any]]] = None
    ) -> None:
        """Initialize ShowEnvCommand.

        Args:
            environment_info_callback: Function to get current environment info.
        """
        self.environment_info_callback = environment_info_callback

    @property
    def name(self) -> str:
        return "show-env"

    @property
    def description(self) -> str:
        return "Show current environment configuration"

    @property
    def aliases(self) -> list[str]:
        return ["env"]

    def get_help(self) -> str:
        """Get detailed help for show-env command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: show-env\n\n"
        help_text += "Displays the current environment configuration including:\n"
        help_text += "- Environment name\n"
        help_text += "- Base URL\n"
        help_text += "- Masked access key (shows first 2 and last 2 characters)\n"
        help_text += "- Masked secret key (shows first 2 and last 2 characters)\n\n"
        help_text += "Note: Keys are masked for security purposes."
        return help_text

    def _mask_key(self, key: str) -> str:
        """Mask a key showing only first 2 and last 2 characters.

        Args:
            key: The key to mask.

        Returns:
            Masked key with variable length asterisks.
        """
        if not key or len(key) < 4:
            return "*" * max(len(key), 3)  # Mask short or empty keys fully

        import random

        random.seed(hash(key))  # Ensure consistent masking for the same key
        mask_length = random.randint(8, 16)  # Variable length for obfuscation

        return f"{key[:2]}{'*' * mask_length}{key[-2:]}"

    def execute(self, args: list[str]) -> bool:
        """Execute the show-env command.

        Args:
            args: Command-line arguments.

        Returns:
            True on successful execution.
        """
        if args and args[0] == "--help":
            print(self.get_help())
            return True

        if not self.environment_info_callback:
            print("Error: No environment information available")
            return True

        env_info = self.environment_info_callback()
        if not env_info or "environment" not in env_info:
            print("No environment is currently selected")
            print("Use 'use <environment-name>' to select an environment")
            return True

        print(f"Current Environment: {env_info['environment']}")
        print(f"Base URL: {env_info.get('base_url', 'Not configured')}")

        access_key = env_info.get("access_key", "")
        secret_key = env_info.get("secret_key", "")

        print(
            f"Access Key: {self._mask_key(access_key) if access_key else 'Not configured'}"
        )
        print(
            f"Secret Key: {self._mask_key(secret_key) if secret_key else 'Not configured'}"
        )

        return True
