"""Audit module for ADOC toolkit."""

from .audit_service import (
    ImmutableAuditLogger,
    immutable_audit_enabled,
    get_immutable_audit_logger,
    log_http_request_immutable,
    log_operation_immutable,
)
from .mixins import (
    AuditableMixin,
    audit_http_request as audit_http_request_decorator,
    audit_operation as audit_command,
)

__all__ = [
    "ImmutableAuditLogger",
    "get_immutable_audit_logger",
    "immutable_audit_enabled",
    "log_http_request_immutable",
    "log_operation_immutable",
    "AuditableMixin",
    "audit_command",
    "audit_http_request_decorator",
]
