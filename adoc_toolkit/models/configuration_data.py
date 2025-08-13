"""Configuration data model."""

from typing import Any

from pydantic import BaseModel, Field

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
    audit: dict[str, Any] = Field(
        default_factory=dict, description="Audit logging configuration"
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
        obj = self

        # Navigate to the parent of the target
        for part in parts[:-1]:
            if hasattr(obj, part):
                obj = getattr(obj, part)
            elif (
                hasattr(obj, "__getitem__")
                and hasattr(obj, "__contains__")
                and part in obj
            ):
                obj = obj[part]
            else:
                # Create nested structure if it doesn't exist
                if hasattr(obj, "__setitem__"):
                    if part not in obj:
                        obj[part] = {}
                    obj = obj[part]
                else:
                    # For Pydantic models, we need to handle this differently
                    # For now, we'll create a dict attribute
                    if not hasattr(obj, part):
                        setattr(obj, part, {})
                    obj = getattr(obj, part)

        # Set the value
        final_key = parts[-1]
        if hasattr(obj, "__setitem__"):
            obj[final_key] = value
        elif hasattr(obj, final_key):
            setattr(obj, final_key, value)
        else:
            # For Pydantic models, we might need to handle this differently
            # For now, we'll try to set it as an attribute
            setattr(obj, final_key, value)

    def to_dict(self) -> dict[str, Any]:
        """Convert configuration to dictionary."""
        return {
            "http": self.http.model_dump() if hasattr(self.http, "model_dump") else self.http,
            "audit": self.audit,
            "log": self.log.model_dump() if hasattr(self.log, "model_dump") else self.log,
            "llm": self.llm.model_dump() if hasattr(self.llm, "model_dump") else self.llm,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ConfigurationData":
        """Create configuration from dictionary."""
        return cls(
            http=data.get("http", {}),
            audit=data.get("audit", {}),
            log=data.get("log", {}),
            llm=data.get("llm", {}),
        )
