"""Configuration data model."""

from typing import Any

from pydantic import BaseModel, Field

from ..audit.audit_config import AuditConfig
from ..http.http_config import HTTPConfig
from ..logs.log_config import LogConfig
from .llm_config import LLMConfig


class ConfigItem(BaseModel):
    """Model for configuration items with descriptions and metadata."""

    value: Any = Field(description="Configuration value")
    description: str = Field(
        description="Human-readable description of the configuration"
    )
    type: str = Field(description="Data type of the configuration")
    options: list[Any] | None = Field(
        default=None, description="Valid options for this configuration"
    )
    default: Any = Field(description="Default value for this configuration")


class ConfigurationData(BaseModel):
    """Complete configuration data model."""

    http: HTTPConfig = Field(
        default_factory=HTTPConfig, description="HTTP client configuration"
    )
    audit: AuditConfig = Field(
        default_factory=AuditConfig, description="Audit logging configuration"
    )
    log: LogConfig = Field(
        default_factory=LogConfig, description="Application logging configuration"
    )
    llm: LLMConfig = Field(default_factory=LLMConfig, description="LLM configuration")
    # Allow additional fields for backward compatibility with tests
    model_config = {"extra": "allow"}

    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value by dot-notation key."""
        parts = key.split(".")
        obj = self

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif (
                hasattr(obj, "__getitem__")
                and hasattr(obj, "__contains__")
                and part in obj
            ):
                obj = obj[part]
            else:
                return default

        return obj

    def get_with_metadata(self, key: str) -> ConfigItem | None:
        """Get configuration value with metadata by dot-notation key."""
        parts = key.split(".")
        obj = self

        for part in parts:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif (
                hasattr(obj, "__getitem__")
                and hasattr(obj, "__contains__")
                and part in obj
            ):
                obj = obj[part]
            else:
                return None

        # Check if the object is a ConfigItem
        if isinstance(obj, dict) and "value" in obj and "description" in obj:
            return ConfigItem.model_validate(obj)

        return None

    def get_all_config_items(self) -> dict[str, ConfigItem]:
        """Get all configuration items with their metadata."""
        config_items = {}

        def traverse_config(obj: Any, prefix: str = "") -> None:
            if isinstance(obj, dict):
                for key, value in obj.items():
                    current_key = f"{prefix}.{key}" if prefix else key
                    if (
                        isinstance(value, dict)
                        and "value" in value
                        and "description" in value
                    ):
                        # This is a ConfigItem
                        config_items[current_key] = ConfigItem.model_validate(value)
                    else:
                        # Continue traversing
                        traverse_config(value, current_key)
            elif hasattr(obj, "__dict__"):
                # Handle Pydantic models
                for key, value in obj.__dict__.items():
                    if not key.startswith("_"):
                        current_key = f"{prefix}.{key}" if prefix else key
                        traverse_config(value, current_key)

        traverse_config(self)
        return config_items

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-notation key."""
        parts = key.split(".")

        # Handle known HTTP configuration with validation
        if key.startswith("http.") and len(parts) >= 2:
            if len(parts) == 2:
                # Direct http config (e.g., http.timeout, http.retries)
                http_key = parts[1]
                if hasattr(self.http, http_key):
                    setattr(self.http, http_key, value)
                    return
            elif len(parts) == 3 and parts[1] == "response":
                # HTTP response config (e.g., http.response.type)
                response_key = parts[2]
                if hasattr(self.http.response, response_key):
                    setattr(self.http.response, response_key, value)
                    return

        # Handle known audit configuration with validation
        if key.startswith("audit.") and len(parts) == 2:
            audit_key = parts[1]
            if hasattr(self.audit, audit_key):
                setattr(self.audit, audit_key, value)
                return

        # Handle known log configuration with validation
        if key.startswith("log.") and len(parts) >= 2:
            if len(parts) == 2:
                # Direct log config (e.g., log.level, log.filepath)
                log_key = parts[1]
                if hasattr(self.log, log_key):
                    # Special handling for log.level to convert string to enum
                    if log_key == "level" and isinstance(value, str):
                        from adoc_toolkit.logs import LogLevel

                        try:
                            value = LogLevel(value.upper())
                        except ValueError:
                            valid_levels = [level.value for level in LogLevel]
                            raise ValueError(
                                f"Invalid log level '{value}'. Must be one of: "
                                f"{', '.join(valid_levels)}"
                            ) from None
                    setattr(self.log, log_key, value)
                    return
            elif len(parts) == 3 and parts[1] == "rotate":
                # Log rotation config (e.g., log.rotate.onsize, log.rotate.ontime)
                rotate_key = parts[2]
                if hasattr(self.log.rotate, rotate_key):
                    setattr(self.log.rotate, rotate_key, value)
                    return

        # Handle known LLM configuration with validation
        if key.startswith("llm.") and len(parts) == 2:
            llm_key = parts[1]
            if hasattr(self.llm, llm_key):
                # Special handling for llm.vendor to convert string to enum
                if llm_key == "vendor" and isinstance(value, str):
                    from .llm_config import LLMVendor

                    try:
                        value = LLMVendor(value.lower())
                    except ValueError:
                        valid_vendors = [vendor.value for vendor in LLMVendor]
                        raise ValueError(
                            f"Invalid LLM vendor '{value}'. Must be one of: "
                            f"{', '.join(valid_vendors)}"
                        ) from None
                setattr(self.llm, llm_key, value)
                return

        # For arbitrary nested keys (for tests and future extensibility)
        obj = self
        for _i, part in enumerate(parts[:-1]):
            if hasattr(obj, part):
                current = getattr(obj, part)
                # If the current value is not a dict but we need to nest,
                # convert it to a dict
                if not isinstance(current, dict):
                    setattr(obj, part, {})
                    current = getattr(obj, part)
                obj = current
            elif hasattr(obj, "__setitem__"):
                if hasattr(obj, "__contains__") and part not in obj:
                    obj[part] = {}
                elif hasattr(obj, "__getitem__") and not isinstance(obj[part], dict):
                    # Convert non-dict to dict for nesting
                    obj[part] = {}
                obj = obj[part]
            else:
                # Create new dictionary attribute
                setattr(obj, part, {})
                obj = getattr(obj, part)

        # Set the final value
        final_key = parts[-1]
        if hasattr(obj, "__setitem__"):
            obj[final_key] = value
        else:
            setattr(obj, final_key, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary representation."""
        result = self.model_dump()
        # Include any extra fields that weren't part of the model
        for key, value in self.__dict__.items():
            if key not in result and not key.startswith("_"):
                result[key] = value
        return result

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigurationData":
        """Create from dictionary data."""
        return cls.model_validate(data)
