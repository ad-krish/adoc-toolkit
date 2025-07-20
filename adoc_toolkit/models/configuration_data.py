"""Configuration data model."""

from typing import Any

from pydantic import BaseModel, Field

from ..audit.audit_config import AuditConfig
from ..http.http_config import HTTPConfig
from ..logs.log_config import LogConfig


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

    def set(self, key: str, value: Any) -> None:
        """Set configuration value by dot-notation key."""
        parts = key.split(".")

        # Handle known HTTP configuration with validation
        if key.startswith("http.") and len(parts) == 2:
            http_key = parts[1]
            if hasattr(self.http, http_key):
                setattr(self.http, http_key, value)
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
                    setattr(self.log, log_key, value)
                    return
            elif len(parts) == 3 and parts[1] == "rotate":
                # Log rotation config (e.g., log.rotate.onsize, log.rotate.ontime)
                rotate_key = parts[2]
                if hasattr(self.log.rotate, rotate_key):
                    setattr(self.log.rotate, rotate_key, value)
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
