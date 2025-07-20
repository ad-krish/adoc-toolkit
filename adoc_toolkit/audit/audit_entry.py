"""Audit log entry model."""

import json
from datetime import datetime
from typing import Any, Optional

from pydantic import BaseModel, Field


class AuditEntry(BaseModel):
    """Audit log entry model."""

    timestamp: datetime = Field(
        default_factory=datetime.now, description="Timestamp of the audit event"
    )
    ip_address: Optional[str] = Field(
        default=None, description="IP address of the user/client"
    )
    user_id: Optional[str] = Field(
        default=None, description="User ID performing the operation"
    )
    command_object: str = Field(description="Command or object being accessed")
    operation_type: str = Field(
        description="Type of operation (GET, POST, PUT, DELETE, etc.)"
    )
    details: Optional[dict[str, Any]] = Field(
        default=None, description="Additional operation details"
    )

    def to_compressed_log_line(self) -> str:
        """Convert audit entry to a compressed log line format.

        Returns:
            Compressed log line suitable for file logging
        """
        # Create a compact representation
        log_data = {
            "ts": self.timestamp.isoformat(),
            "ip": self.ip_address,
            "uid": self.user_id,
            "cmd": self.command_object,
            "op": self.operation_type,
        }

        # Add details if present
        if self.details is not None:
            log_data["details"] = self.details

        # Remove None values to save space
        log_data = {k: v for k, v in log_data.items() if v is not None}

        return json.dumps(log_data, separators=(",", ":"))

    @classmethod
    def from_http_request(
        cls,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        ip_address: Optional[str] = None,
        user_id: Optional[str] = None,
    ) -> "AuditEntry":
        """Create audit entry from HTTP request data.

        Args:
            method: HTTP method (GET, POST, etc.)
            url: Request URL
            headers: Request headers (will be compressed)
            ip_address: Client IP address
            user_id: User ID performing the request

        Returns:
            AuditEntry instance
        """
        # Compress headers by only including important ones and shortening names
        compressed_headers: dict[str, str] = {}
        if headers:
            # Only log important headers with shortened names
            header_mapping = {
                "content-type": "ct",
                "authorization": "auth",
                "user-agent": "ua",
                "accesskey": "ak",
                "secretkey": "sk",
            }

            for header, value in headers.items():
                header_lower = header.lower()
                if header_lower in header_mapping:
                    # Mask sensitive headers
                    if header_lower in ("authorization", "accesskey", "secretkey"):
                        if value:
                            compressed_headers[header_mapping[header_lower]] = (
                                f"{value[:4]}***{value[-4:]}"
                                if len(value) > 8
                                else "***"
                            )
                    else:
                        compressed_headers[header_mapping[header_lower]] = value

        details: dict[str, Any] = {
            "url": url,
        }

        if compressed_headers:
            details["hdrs"] = compressed_headers

        return cls(
            ip_address=ip_address,
            user_id=user_id,
            command_object="http_request",
            operation_type=method.upper(),
            details=details,
        )
