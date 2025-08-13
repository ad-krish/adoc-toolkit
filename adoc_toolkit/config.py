"""Configuration management for ADOC Toolkit."""

import json
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from .models import ConfigItem, ConfigurationData
from .models.llm_config import LLMConfig


class ConfigManager:
    """Manages persistent configuration settings for ADOC Toolkit."""

    def __init__(self, config_file: Path | None = None) -> None:
        """Initialize configuration manager.

        Args:
            config_file: Optional path to configuration file.
                        If not provided, searches in config/ then ~/
        """
        self._config_file = self._resolve_config_file(config_file)
        self._config = ConfigurationData()
        self._load_config()

    def _resolve_config_file(self, config_file: Path | None) -> Path:
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
                        # Check if this is the new enhanced structure
                        if self._is_enhanced_structure(data):
                            # Load as enhanced structure
                            self._config = self._load_enhanced_config(data)
                        else:
                            # Load as legacy structure
                            self._config = ConfigurationData.from_dict(data)
                    else:
                        self._config = ConfigurationData()
            else:
                self._config = ConfigurationData()
        except (json.JSONDecodeError, OSError, TypeError, ValidationError):
            # If file is corrupted or unreadable, start with defaults
            self._config = ConfigurationData()

    def _is_enhanced_structure(self, data: dict) -> bool:
        """Check if the config data uses the enhanced structure with descriptions."""

        def check_enhanced(obj: Any) -> bool:
            if isinstance(obj, dict):
                # Check if this looks like a ConfigItem (has value and description)
                if "value" in obj and "description" in obj and "type" in obj:
                    return True
                # Recursively check nested objects
                return any(check_enhanced(v) for v in obj.values())
            return False

        return check_enhanced(data)

    def _load_enhanced_config(self, data: dict) -> ConfigurationData:
        """Load configuration from enhanced structure."""

        # Convert enhanced structure to legacy structure for compatibility
        def convert_enhanced_to_legacy(obj: Any) -> Any:
            if isinstance(obj, dict):
                if "value" in obj and "description" in obj and "type" in obj:
                    # This is a ConfigItem, extract the value
                    return obj["value"]
                else:
                    # Recursively convert nested objects
                    return {k: convert_enhanced_to_legacy(v) for k, v in obj.items()}
            return obj

        # Convert the data to legacy format
        legacy_data = convert_enhanced_to_legacy(data)

        # Load as legacy structure
        config = ConfigurationData.from_dict(legacy_data)

        # Handle custom LLM model options after loading
        if "llm" in legacy_data and "model_options" in legacy_data["llm"]:
            model_options = legacy_data["llm"]["model_options"]
            if isinstance(model_options, dict):
                # Set the custom model options on the LLM config
                config.llm.model_options = model_options

                # Validate that model_options has the expected structure
                for vendor in ["claude", "gemini", "grok", "chatgpt"]:
                    if vendor not in model_options:
                        # Use default for missing vendors
                        default_config = LLMConfig()
                        config.llm.model_options[vendor] = (
                            default_config.get_all_model_options()[vendor]
                        )

        return config

    def _save_config(self) -> None:
        """Save configuration to file."""
        try:
            # Ensure parent directory exists
            self._config_file.parent.mkdir(parents=True, exist_ok=True)

            # Convert to enhanced structure for saving
            enhanced_data = self._convert_to_enhanced_structure()

            # Write to temporary file first, then rename for atomic operation
            temp_file = self._config_file.with_suffix(".tmp")
            with open(temp_file, "w", encoding="utf-8") as f:
                json.dump(enhanced_data, f, indent=2, ensure_ascii=False)

            # Atomic rename
            temp_file.replace(self._config_file)

        except (OSError, TypeError):
            # Fail silently - configuration persistence is not critical
            pass

    def _convert_to_enhanced_structure(self) -> dict:
        """Convert current config to enhanced structure with descriptions."""
        # Define the enhanced structure with descriptions
        enhanced_structure = {
            "http": {
                "timeout": {
                    "value": self._config.http.timeout,
                    "description": "HTTP request timeout in seconds",
                    "type": "integer",
                    "options": [30, 60, 120, 300],
                    "default": 120,
                },
                "retries": {
                    "value": self._config.http.retries,
                    "description": "Number of retry attempts for failed requests",
                    "type": "integer",
                    "options": [0, 1, 3, 5],
                    "default": 3,
                },
                "proxy": {
                    "value": self._config.http.proxy,
                    "description": "HTTP proxy URL for requests",
                    "type": "string",
                    "options": [
                        "https://proxy.example.com:8080",
                        "http://proxy.example.com:3128",
                        "none",
                    ],
                    "default": None,
                },
                "response": {
                    "type": {
                        "value": self._config.http.response.type,
                        "description": "Response format type",
                        "type": "string",
                        "options": ["json", "table", "csv", "human"],
                        "default": "json",
                    }
                },
            },
            "audit": {
                "log": {
                    "enabled": {
                        "value": self._config.audit.get("log", {}).get("enabled", False),
                        "description": "Enable secure audit log (tamper-proof)",
                        "type": "boolean",
                        "options": [True, False],
                        "default": False,
                    },
                    "database_path": {
                        "value": self._config.audit.get("log", {}).get("database_path", "audit/audit_log.db"),
                        "description": "Path to audit log database",
                        "type": "string",
                        "options": ["audit/audit_log.db", "./audit.db", "none"],
                        "default": "audit/audit_log.db",
                    },
                    "difficulty": {
                        "value": self._config.audit.get("log", {}).get("difficulty", 4),
                        "description": "Audit log mining difficulty (number of leading zeros)",
                        "type": "integer",
                        "options": [1, 2, 3, 4, 5, 6, 7, 8],
                        "default": 4,
                    },
                    "batch_size": {
                        "value": self._config.audit.get("log", {}).get("batch_size", 100),
                        "description": "Number of log entries to batch before creating a block",
                        "type": "integer",
                        "options": [10, 50, 100, 200, 500],
                        "default": 100,
                    },
                    "batch_timeout": {
                        "value": self._config.audit.get("log", {}).get("batch_timeout", 120.0),
                        "description": "Maximum time (seconds) to wait before creating a block",
                        "type": "float",
                        "options": [30.0, 60.0, 120.0, 300.0, 600.0],
                        "default": 120.0,
                    },
                },
            },
            "log": {
                "level": {
                    "value": self._config.log.level.value
                    if hasattr(self._config.log.level, "value")
                    else str(self._config.log.level),
                    "description": "Logging level for application logs",
                    "type": "string",
                    "options": ["TRACE", "DEBUG", "INFO", "ERROR"],
                    "default": "TRACE",
                },
                "filepath": {
                    "value": self._config.log.filepath,
                    "description": "Path to log file",
                    "type": "string",
                    "options": ["logs/adoc-toolkit.log", "./adoc-toolkit.log", "none"],
                    "default": None,
                },
                "rotate": {
                    "onsize": {
                        "value": self._config.log.rotate.onsize,
                        "description": "Log rotation size limit",
                        "type": "string",
                        "options": ["10MB", "50MB", "100MB", "1GB"],
                        "default": "10MB",
                    },
                    "ontime": {
                        "value": self._config.log.rotate.ontime,
                        "description": "Log rotation time interval in minutes",
                        "type": "integer",
                        "options": [60, 120, 240, 480],
                        "default": 120,
                    },
                },
            },
            "llm": {
                "vendor": {
                    "value": self._config.llm.vendor.value,
                    "description": "LLM vendor to use for AI operations",
                    "type": "string",
                    "options": ["claude", "gemini", "grok", "chatgpt"],
                    "default": "gemini",
                },
                "apikey": {
                    "value": self._config.llm.apikey,
                    "description": "API key for the selected LLM vendor",
                    "type": "string",
                    "options": ["your-api-key-here", "none"],
                    "default": None,
                },
                "model": {
                    "value": self._config.llm.get_model(),
                    "description": "Model name for the selected LLM vendor",
                    "type": "string",
                    "options": self._config.llm.get_model_options(),
                    "default": self._config.llm._get_default_model(
                        self._config.llm.vendor
                    ),
                },
                "temperature": {
                    "value": self._config.llm.temperature,
                    "description": "Temperature for LLM response generation",
                    "type": "float",
                    "options": [0.0, 0.1, 0.2, 0.5, 0.7, 1.0, 1.5, 2.0],
                    "default": 0.2,
                },
            },
        }

        return enhanced_structure

    def get(self, key: str) -> Any:
        """Get a configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'http.timeout')

        Returns:
            Configuration value or None if not found
        """
        # First try to get with metadata
        config_item = self._config.get_with_metadata(key)
        if config_item:
            return config_item.value

        # Fall back to regular get
        return self._config.get(key)

    def get_with_metadata(self, key: str) -> ConfigItem | None:
        """Get a configuration value with metadata by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'http.timeout')

        Returns:
            ConfigItem with value and metadata or None if not found
        """
        config_items = self.get_all_config_items()
        return config_items.get(key)

    def get_all_config_items(self) -> dict[str, ConfigItem]:
        """Get all configuration items with their metadata.

        Returns:
            Dictionary of configuration keys to ConfigItem objects
        """
        config_items = {}

        try:
            if self._config_file.exists():
                with open(self._config_file, encoding="utf-8") as f:
                    data = json.load(f)
                    if isinstance(data, dict):
                        self._extract_config_items(data, "", config_items)
        except (json.JSONDecodeError, OSError):
            pass

        return config_items

    def _extract_config_items(
        self, obj: Any, prefix: str, config_items: dict[str, ConfigItem]
    ) -> None:
        """Recursively extract ConfigItem objects from the enhanced structure."""
        if isinstance(obj, dict):
            for key, value in obj.items():
                current_key = f"{prefix}.{key}" if prefix else key
                if (
                    isinstance(value, dict)
                    and "value" in value
                    and "description" in value
                    and "type" in value
                ):
                    # This is a ConfigItem
                    try:
                        config_items[current_key] = ConfigItem.model_validate(value)
                    except Exception:
                        # Skip invalid ConfigItems
                        pass
                else:
                    # Continue traversing
                    self._extract_config_items(value, current_key, config_items)

    def set(self, key: str, value: Any) -> None:
        """Set a configuration value by dot-notation key.

        Args:
            key: Configuration key in dot notation (e.g., 'http.timeout')
            value: Value to set
        """
        # Get the config item to validate the value
        config_item = self._config.get_with_metadata(key)
        if config_item:
            # Validate against options if available
            if config_item.options is not None and value not in config_item.options:
                raise ValueError(
                    f"Invalid value '{value}' for '{key}'. "
                    f"Valid options: {', '.join(map(str, config_item.options))}"
                )

            # Update the value in the config item
            config_item.value = value

            # For enhanced structure, we need to update the actual config model
            # instead of trying to modify the enhanced structure
            self._config.set(key, value)
        else:
            # Fall back to regular set
            self._config.set(key, value)

        self._save_config()

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
            elif key == "llm.temperature":
                return float(value)
            elif key == "log.level":
                # Convert string to LogLevel enum
                from adoc_toolkit.logs import LogLevel

                try:
                    return LogLevel(value.upper())
                except ValueError:
                    valid_levels = [level.value for level in LogLevel]
                    raise ValueError(
                        f"Invalid log level '{value}'. Must be one of: "
                        f"{', '.join(valid_levels)}"
                    ) from None
            elif key == "http.response.type":
                # Convert string to ResponseType enum
                from adoc_toolkit.http.http_config import ResponseType

                try:
                    return ResponseType(value.lower())
                except ValueError:
                    valid_types = [rt.value for rt in ResponseType]
                    raise ValueError(
                        f"Invalid response type '{value}'. Must be one of: "
                        f"{', '.join(valid_types)}"
                    ) from None
            elif key == "llm.vendor":
                # Convert string to LLMVendor enum
                from adoc_toolkit.models.llm_config import LLMVendor

                try:
                    return LLMVendor(value.lower())
                except ValueError:
                    valid_vendors = [vendor.value for vendor in LLMVendor]
                    raise ValueError(
                        f"Invalid LLM vendor '{value}'. Must be one of: "
                        f"{', '.join(valid_vendors)}"
                    ) from None
            elif key in (
                "log.filepath",
                "log.rotate.onsize",
        
                "llm.apikey",
                "llm.model",
            ):
                if value.lower() in ("none", "null", ""):
                    return None
                return value
            elif key.startswith("audit.log."):
                # Handle audit log configuration
                if key == "audit.log.enabled":
                    # Convert string boolean to actual boolean
                    if value.lower() in ("true", "1", "yes", "on"):
                        return True
                    elif value.lower() in ("false", "0", "no", "off"):
                        return False
                    else:
                        raise ValueError(f"Invalid boolean value '{value}'. Must be true/false")
                elif key == "audit.log.difficulty":
                    return int(value)
                elif key == "audit.log.database_path":
                    if value.lower() in ("none", "null", ""):
                        return None
                    return value
                else:
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
            elif key == "llm.vendor":
                raise ValueError(
                    "LLM vendor must be one of: claude, gemini, grok, chatgpt"
                ) from e
            else:
                raise


# Global configuration manager instance - will be initialized when needed
config_manager: ConfigManager | None = None


def get_config_manager(config_file: Path | None = None) -> ConfigManager:
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


def reset_config_manager(config_file: Path | None = None) -> ConfigManager:
    """Reset the global configuration manager with a new config file.

    Args:
        config_file: Optional path to configuration file

    Returns:
        New ConfigManager instance
    """
    global config_manager
    config_manager = ConfigManager(config_file)
    return config_manager
