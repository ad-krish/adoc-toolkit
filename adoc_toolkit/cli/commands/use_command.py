"""Use command implementation."""

from collections.abc import Callable
from pathlib import Path
from typing import Any

import yaml

from ...models import CompletionItem
from .base import Command


class UseCommand(Command):
    """Switch to a different environment."""

    def __init__(
        self,
        environment_callback: Callable[[str, dict[str, Any]], None] | None = None,
    ):
        """Initialize UseCommand.

        Args:
            environment_callback: Function to call when environment changes
        """
        self.environment_callback = environment_callback
        self._config_cache = None

    @property
    def name(self) -> str:
        return "use"

    @property
    def description(self) -> str:
        return "Switch to a different environment"

    @property
    def contributor(self) -> str | None:
        return None

    def get_help(self) -> str:
        """Get detailed help for use command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: use <environment-name>\n\n"
        help_text += "Switches the active environment for ADOC operations.\n"
        help_text += (
            "Environment configurations are stored in config/environments.yaml\n\n"
        )

        # Show available environments
        try:
            config = self._load_config()
            if config and "environments" in config:
                help_text += "Available environments:\n"
                for env_name, env_config in config["environments"].items():
                    env_display_name = env_config.get("name", env_name)
                    help_text += f"  {env_name}: {env_display_name}\n"
            else:
                help_text += "No environments configured in config/environments.yaml"
        except Exception as e:
            help_text += f"Error loading environment config: {e}"

        return help_text

    def _load_config(self) -> dict[str, Any] | None:
        """Load environment configuration from YAML file."""
        if self._config_cache is not None:
            return self._config_cache

        config_path = Path("config/environments.yaml")

        if not config_path.exists():
            return None

        try:
            with open(config_path) as f:
                config_data = yaml.safe_load(f)
                self._config_cache = config_data
                return self._config_cache
        except Exception:
            return None

    def execute(self, args: list[str]) -> bool:
        """Execute the use command."""
        # Handle --help flag
        if args and args[0] == "--help":
            print(self.get_help())
            return True

        if not args:
            print("Error: Environment name required")
            print("Usage: use <environment-name>")
            print("Type 'use --help' for more information")
            return True

        environment_name = args[0].lower()
        config = self._load_config()

        if not config:
            print("Error: Could not load config/environments.yaml")
            print("Make sure the file exists and is valid YAML format")
            return True

        environments = config.get("environments", {})
        if environment_name not in environments:
            print(f"Error: Environment '{environment_name}' not found")
            print("Available environments:")
            for env_name in environments.keys():
                print(f"  {env_name}")
            return True

        # Environment exists, set it as active
        env_config = environments[environment_name]

        print(f"Environment set to {environment_name}")

        # Call callback to notify the processor about environment change
        if self.environment_callback:
            self.environment_callback(environment_name, env_config)

        return True

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[str | CompletionItem]:
        """Get auto-completion suggestions for environment names with descriptions."""
        config = self._load_config()
        if not config or "environments" not in config:
            return []

        # Parse the input to get the current argument being typed
        parts = current_input.strip().split()

        # If we're typing the first argument after "use"
        if len(parts) <= 2:
            current_arg = parts[1] if len(parts) == 2 else ""
            env_names = list(config["environments"].keys())

            # Filter environment names that start with the current argument
            if current_arg:
                completions = [
                    CompletionItem(
                        text=env,
                        description=f"Environment: {config['environments'][env].get('description', 'No description available')}",  # noqa: E501
                    )
                    for env in env_names
                    if env.startswith(current_arg.lower())
                ]
            else:
                completions = [
                    CompletionItem(
                        text=env,
                        description=f"Environment: {config['environments'][env].get('description', 'No description available')}",  # noqa: E501
                    )
                    for env in env_names
                ]

            return completions

        return []
