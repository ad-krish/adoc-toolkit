"""Log configuration model."""

from enum import Enum
from pathlib import Path
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class LogLevel(str, Enum):
    """Log level enumeration."""

    TRACE = "TRACE"
    DEBUG = "DEBUG"
    INFO = "INFO"
    ERROR = "ERROR"


class LogRotateConfig(BaseModel):
    """Log rotation configuration."""

    onsize: str = Field(
        default="10MB",
        description="Size threshold for log rotation (e.g., '10MB', '100KB', '1GB')",
    )
    ontime: int = Field(
        default=120, description="Time threshold for log rotation in minutes"
    )

    @field_validator("onsize")
    @classmethod
    def validate_size(cls, v: str) -> str:
        """Validate size format."""
        if not v:
            return "10MB"

        v = v.strip().upper()
        if not v:
            return "10MB"

        # Check if it ends with valid units
        # (order by length desc to match longest first)
        valid_units = ["GB", "MB", "KB", "B"]
        unit_found = False
        size_part = ""
        for unit in valid_units:
            if v.endswith(unit):
                size_part = v[: -len(unit)]
                unit_found = True
                break

        if not unit_found:
            raise ValueError(f"Invalid size unit. Must end with one of: {valid_units}")

        # Validate the numeric part
        try:
            size_value = float(size_part)
        except ValueError as err:
            raise ValueError(
                "Size must be a valid number followed by unit (B, KB, MB, GB)"
            ) from err

        if size_value <= 0:
            raise ValueError("Size must be positive")

        return v

    @field_validator("ontime")
    @classmethod
    def validate_time(cls, v: int) -> int:
        """Validate time threshold."""
        if v <= 0:
            raise ValueError("Time threshold must be positive")
        return v

    def size_in_bytes(self) -> int:
        """Convert size string to bytes."""
        size_str = self.onsize.upper()

        if size_str.endswith("GB"):
            return int(float(size_str[:-2]) * 1024 * 1024 * 1024)
        elif size_str.endswith("MB"):
            return int(float(size_str[:-2]) * 1024 * 1024)
        elif size_str.endswith("KB"):
            return int(float(size_str[:-2]) * 1024)
        elif size_str.endswith("B"):
            return int(float(size_str[:-1]))
        else:
            # Fallback to MB
            return int(float(size_str) * 1024 * 1024)


class LogConfig(BaseModel):
    """Log configuration model."""

    level: LogLevel = Field(
        default=LogLevel.INFO, description="Log level for application logging"
    )
    filepath: Optional[str] = Field(
        default=None,
        description=(
            "Path to log file. If None, defaults to logs/adoc-toolkit-MM-dd-YYYY.log"
        ),
    )
    rotate: LogRotateConfig = Field(
        default_factory=LogRotateConfig, description="Log rotation configuration"
    )

    @field_validator("filepath")
    @classmethod
    def validate_filepath(cls, v: Optional[str]) -> Optional[str]:
        """Validate and normalize filepath."""
        if v is None or not v.strip():
            return None

        # Strip whitespace
        v = v.strip()

        # Expand user path if needed
        path = Path(v).expanduser()

        # Return as string
        return str(path)

    def get_default_filepath(self) -> str:
        """Get default log file path with current date."""
        from datetime import datetime

        # Create logs directory in current working directory
        logs_dir = Path.cwd() / "logs"

        # Generate filename with current date
        date_str = datetime.now().strftime("%m-%d-%Y")
        filename = f"adoc-toolkit-{date_str}.log"

        return str(logs_dir / filename)

    def get_effective_filepath(self) -> str:
        """Get the effective log file path."""
        if self.filepath:
            return self.filepath
        return self.get_default_filepath()
