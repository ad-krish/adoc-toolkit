"""Configuration management for ADOC Toolkit."""

import json
from pathlib import Path
from typing import Any, Optional

from pydantic import ValidationError

from .models import ConfigurationData


class ConfigManager:
    """Manages persistent configuration settings for ADOC Toolkit."""

    def __init__(self, config_file: Optional[Path] = None) -> None:
        """Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file.
                        If not provided, searches in config/ then ~/
        """
        self._config_file = self._resolve_config_file(config_file)
        self._config = ConfigurationData()
        self._load_config()

    def _resolve_config_file(self, config_file: Optional[Path]) -> Path:
        """Resolve the configuration file path.

        Args:
            config_file: Optional path to configuration file

        Returns:
            Path to configuration file

        Search order:
        1. If config_file is provided, use it
        2. Look for config/adoc-toolkit-config.json
        3. Fall back to ~/adoc-toolkit-config.json
        """
        if config_file:
            return Path(config_file)

        # Try config directory first
        config_dir_file = Path("config") / "adoc-toolkit-config.json"
        if config_dir_file.exists():
            return config_dir_file

        # Fall back to home directory
        return Path.home() / "adoc-toolkit-config.json"

    def _load_config(self) -> None:
        """Load configuration from file."""
        try:
            if self._config_file.exists():
                with open(self._config_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._config = ConfigurationData.from_dict(data)
                    else:
                        self._config = ConfigurationData()
            else:
                self._config = ConfigurationData()
        except (json.JSONDecodeError, OSError, TypeError, ValidationError):
            # If file is corrupted or unreadable, start with defaults
            self._config = ConfigurationData()

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Ensure parent directory exists
            self._config_file.parent.mkdir(parents=True, exist_ok=True)

            # Write to temporary file first, then rename for atomic operation
            temp_file = self._config_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(self._config.to_dict(), f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self._config_file)

        except (OSError, TypeError):
            # Fail silently - configuration persistence is not critical
            pass

    def get(self, key: str) -> Any:
        """Get a configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'http.timeout')

        Returns:
            Configuration value or None if not found
        """
        return self._config.get(key)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'http.timeout')
            value: Value to set
        """
        # Get old value for logging
        old_value = self._config.get(key)

        self._config.set(key, value)
        self._save_config()

        # Log configuration change (avoid circular import by importing here)
        try:
            from .logs import trace_config_change

            trace_config_change(key, old_value, value)
        except ImportError:
            # Logger might not be available during initialization
            pass

    def get_section(self, section: str) -> dict[str, Any]:
        """Get an entire configuration section.

        Args:
            section: Section name (e.g., 'http')

        Returns:
            Dictionary containing section configuration
        """
        section_data = self._config.get(section)
        if hasattr(section_data, "model_dump"):
            return section_data.model_dump()  # type: ignore[no-any-return]
        elif isinstance(section_data, dict):
            return section_data.copy()
        else:
            return {}

    def list_all(self) -> dict[str, Any]:
        """Get all configuration settings.

        Returns:
            Dictionary containing all configuration
        """
        return self._config.to_dict()

    def validate_value(self, key: str, value: str) -> tuple[bool, Any, str]:
        """Validate and convert a configuration value using Pydantic models.

        Args:
            key: Configuration key
            value: String value to validate and convert

        Returns:
            Tuple of (is_valid, converted_value, error_message)
        """
        try:
            # Create a test configuration with the new value
            test_data = self._config.to_dict()

            # Convert string value to appropriate type for validation
            converted_value = self._convert_string_value(key, value)

            # Set the value in test data
            keys = key.split(".")
            target = test_data
            for k in keys[:-1]:
                if k not in target:
                    target[k] = {}
                target = target[k]
            target[keys[-1]] = converted_value

            # Validate using Pydantic
            ConfigurationData.from_dict(test_data)
            return True, converted_value, ""

        except ValidationError as e:
            # Extract the error message for the specific field
            for error in e.errors():
                if ".".join(str(loc) for loc in error["loc"]) == key:
                    return False, None, error["msg"]
            return False, None, str(e)
        except Exception as e:
            return False, None, str(e)

    def _convert_string_value(self, key: str, value: str) -> Any:
        """Convert string value to appropriate type based on key.

        Args:
            key: Configuration key
            value: String value to convert

        Returns:
            Converted value

        Raises:
            ValueError: If conversion fails with appropriate message
        """
        try:
            if key in ("http.timeout", "http.retries"):
                return int(value)
            elif key == "http.proxy":
                if value.lower() in ("none", "null", ""):
                    return None
                return value
            elif key == "log.rotate.ontime":
                return int(value)
            elif key in (
                "log.level",
                "log.filepath",
                "log.rotate.onsize",
                "audit.logfile",
            ):
                if value.lower() in ("none", "null", ""):
                    return None
                return value
            else:
                return value
        except ValueError as e:
            if key == "http.timeout":
                raise ValueError("Timeout must be an integer") from e
            elif key == "http.retries":
                raise ValueError("Retries must be an integer") from e
            elif key == "log.rotate.ontime":
                raise ValueError("Log rotation time must be an integer") from e
            else:
                raise


# Global configuration manager instance - will be initialized when needed
config_manager: Optional[ConfigManager] = None


def get_config_manager(config_file: Optional[Path] = None) -> ConfigManager:
    """Get or create the global configuration manager instance.

    Args:
        config_file: Optional path to configuration file

    Returns:
        Global ConfigManager instance
    """
    global config_manager
    if config_manager is None:
        config_manager = ConfigManager(config_file)
    return config_manager


def reset_config_manager(config_file: Optional[Path] = None) -> ConfigManager:
    """Reset the global configuration manager with a new config file.

    Args:
        config_file: Optional path to configuration file

    Returns:
        New ConfigManager instance
    """
    global config_manager
    config_manager = ConfigManager(config_file)
    return config_manager
