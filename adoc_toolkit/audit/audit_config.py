"""Audit configuration model."""


from pydantic import BaseModel, Field, field_validator


class AuditConfig(BaseModel):
    """Audit logging configuration settings."""

    logfile: str | None = Field(
        default=None,
        description="Path to audit log file. If None, audit logging is disabled.",
    )

    @field_validator("logfile")
    @classmethod
    def validate_logfile(cls, v: str | None) -> str | None:
        """Validate audit log file path."""
        if v is None or v.strip() == "":
            return None
        return v.strip()
