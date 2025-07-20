"""Audit configuration model."""

from typing import Optional

from pydantic import BaseModel, Field, field_validator


class AuditConfig(BaseModel):
    """Audit logging configuration settings."""

    logfile: Optional[str] = Field(
        default=None,
        description="Path to audit log file. If None, audit logging is disabled.",
    )

    @field_validator("logfile")
    @classmethod
    def validate_logfile(cls, v: Optional[str]) -> Optional[str]:
        """Validate audit log file path."""
        if v is None or v.strip() == "":
            return None
        return v.strip()
