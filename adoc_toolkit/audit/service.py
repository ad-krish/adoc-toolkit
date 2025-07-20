"""Audit logging service for ADOC toolkit."""

import logging
import socket
from pathlib import Path
from typing import Any, Optional

# get_config_manager imported locally to avoid circular import
from .audit_entry import AuditEntry


class AuditLogger:
    """Centralized audit logging service."""

    _instance: Optional["AuditLogger"] = None

    def __init__(self) -> None:
        """Initialize audit logger."""
        self._logger: Optional[logging.Logger] = None
        self._current_logfile: Optional[str] = None
        self._setup_logger()

    @classmethod
    def get_instance(cls) -> "AuditLogger":
        """Get singleton instance of audit logger."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _setup_logger(self) -> None:
        """Setup or reconfigure the logger based on current configuration."""
        from ..config import get_config_manager

        config_manager = get_config_manager()
        logfile = config_manager.get("audit.logfile")

        # If no logfile configured, disable logging
        if not logfile:
            self._logger = None
            self._current_logfile = None
            return

        # If logfile changed, reconfigure logger
        if logfile != self._current_logfile:
            self._current_logfile = logfile

            # Create logger if it doesn't exist
            if self._logger is None:
                self._logger = logging.getLogger("adoc_toolkit.audit")
                self._logger.setLevel(logging.INFO)
                # Don't propagate to root logger to avoid duplicate logs
                self._logger.propagate = False

            # Clear existing handlers
            for handler in self._logger.handlers[:]:
                self._logger.removeHandler(handler)

            try:
                # Create log directory if it doesn't exist
                log_path = Path(logfile)
                log_path.parent.mkdir(parents=True, exist_ok=True)

                # Add file handler
                file_handler = logging.FileHandler(logfile, mode="a", encoding="utf-8")
                file_handler.setLevel(logging.INFO)

                # Use a simple format for compressed logging
                formatter = logging.Formatter("%(message)s")
                file_handler.setFormatter(formatter)

                self._logger.addHandler(file_handler)
            except (OSError, PermissionError):
                # If we can't create the log file, disable logging
                self._logger = None
                self._current_logfile = None

    def is_enabled(self) -> bool:
        """Check if audit logging is enabled."""
        self._setup_logger()  # Refresh configuration
        return self._logger is not None

    def log_entry(self, entry: AuditEntry) -> None:
        """Log an audit entry.

        Args:
            entry: AuditEntry to log
        """
        if not self.is_enabled():
            return

        try:
            log_line = entry.to_compressed_log_line()
            if self._logger is not None:
                self._logger.info(log_line)
        except Exception:
            # Fail silently to avoid breaking application functionality
            pass

    def log_http_request(
        self,
        method: str,
        url: str,
        headers: Optional[dict[str, str]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log HTTP request audit entry.

        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            user_id: User ID performing the request
            ip_address: Client IP address
        """
        if not self.is_enabled():
            return

        # Try to get IP address if not provided
        if ip_address is None:
            ip_address = self._get_local_ip()

        entry = AuditEntry.from_http_request(
            method=method,
            url=url,
            headers=headers,
            user_id=user_id,
            ip_address=ip_address,
        )

        self.log_entry(entry)

    def log_operation(
        self,
        command_object: str,
        operation_type: str,
        details: Optional[dict[str, Any]] = None,
        user_id: Optional[str] = None,
        ip_address: Optional[str] = None,
    ) -> None:
        """Log a general operation audit entry.

        Args:
            command_object: Command or object being accessed
            operation_type: Type of operation
            details: Additional operation details
            user_id: User ID performing the operation
            ip_address: Client IP address
        """
        if not self.is_enabled():
            return

        # Try to get IP address if not provided
        if ip_address is None:
            ip_address = self._get_local_ip()

        entry = AuditEntry(
            ip_address=ip_address,
            user_id=user_id,
            command_object=command_object,
            operation_type=operation_type,
            details=details,
        )

        self.log_entry(entry)

    def _get_local_ip(self) -> Optional[str]:
        """Get local IP address.

        Returns:
            Local IP address or None if unable to determine
        """
        try:
            # Connect to a remote address to determine local IP
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                return sock.getsockname()[0]
        except Exception:
            # Fallback to localhost
            return "127.0.0.1"


# Global audit logger instance
def get_audit_logger() -> AuditLogger:
    """Get the global audit logger instance."""
    return AuditLogger.get_instance()


def audit_enabled() -> bool:
    """Check if audit logging is enabled."""
    return get_audit_logger().is_enabled()


def log_http_request(
    method: str,
    url: str,
    headers: Optional[dict[str, str]] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Convenience function to log HTTP request."""
    get_audit_logger().log_http_request(method, url, headers, user_id, ip_address)


def log_operation(
    command_object: str,
    operation_type: str,
    details: Optional[dict[str, Any]] = None,
    user_id: Optional[str] = None,
    ip_address: Optional[str] = None,
) -> None:
    """Convenience function to log general operation."""
    get_audit_logger().log_operation(
        command_object, operation_type, details, user_id, ip_address
    )
