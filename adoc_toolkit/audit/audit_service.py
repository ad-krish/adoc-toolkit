"""Immutable audit service wrapper for ADOC toolkit."""

import logging
import socket
import threading
from typing import Any, Optional

from .immutable_log import (
    FunctionalLogger,
    FunctionalStorage,
    create_logger,
)


class ImmutableAuditLogger:
    """Immutable audit logger using blockchain technology."""

    _instance: Optional["ImmutableAuditLogger"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize immutable audit logger."""
        self._blockchain_logger: Optional[FunctionalLogger] = None
        self._setup_blockchain()

    @classmethod
    def get_instance(cls) -> "ImmutableAuditLogger":
        """Get singleton instance of immutable audit logger."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset the singleton instance (for testing)."""
        with cls._lock:
            cls._instance = None

    def _setup_blockchain(self) -> None:
        """Setup blockchain logger based on configuration."""
        from ..config import get_config_manager
        config_manager = get_config_manager()
        
        # Check if immutable logging is enabled
        log_enabled = config_manager.get("audit.log.enabled")
        if not log_enabled:
            self._blockchain_logger = None
            return

        try:
            # Get blockchain configuration
            database_path = config_manager.get("audit.log.database_path")
            difficulty = config_manager.get("audit.log.difficulty")
            batch_size = config_manager.get("audit.log.batch_size")
            batch_timeout = config_manager.get("audit.log.batch_timeout")

            # Set defaults if not configured
            if not database_path:
                self._blockchain_logger = None
                return
            if not difficulty:
                difficulty = 4
            if not batch_size:
                batch_size = 100
            if not batch_timeout:
                batch_timeout = 120.0

            # Create audit directory if it doesn't exist
            from pathlib import Path
            db_path = Path(database_path)
            db_path.parent.mkdir(parents=True, exist_ok=True)

            # Create functional logger with batching
            # Ensure proper type conversion
            batch_size_int = int(batch_size) if batch_size is not None else 100
            batch_timeout_float = float(batch_timeout) if batch_timeout is not None else 120.0
            
            self._blockchain_logger = create_logger(
                db_path=database_path,
                batch_size=batch_size_int,
                batch_timeout=batch_timeout_float
            )
            
            # Store difficulty for use when creating blocks
            self._difficulty = difficulty
                
        except Exception as e:
            logging.warning(f"Failed to setup blockchain logger: {e}")
            self._blockchain_logger = None

    def is_enabled(self) -> bool:
        """Check if audit logging is enabled."""
        return self._blockchain_logger is not None

    def is_blockchain_enabled(self) -> bool:
        """Check if blockchain logging is enabled."""
        return self._blockchain_logger is not None

    def log_entry(self, entry_data: dict[str, Any]) -> bool:
        """Log an entry to the blockchain.

        Args:
            entry_data: Dictionary containing log entry data

        Returns:
            True if entry was logged successfully
        """
        # Auto-reconfigure if needed
        self._auto_reconfigure_if_needed()
        
        if not self.is_enabled():
            return False

        try:
            # Extract required fields
            operation = entry_data.get("operation", "unknown")
            user_id = entry_data.get("user_id", "unknown")
            resource = entry_data.get("resource", "unknown")
            action = entry_data.get("action", "execute")
            details = entry_data.get("details", {})
            metadata = entry_data.get("metadata", {})

            # Add to blockchain using functional logger
            self._blockchain_logger, block = self._blockchain_logger.log_entry(
                operation=operation,
                user_id=user_id,
                resource=resource,
                action=action,
                details=details,
                metadata=metadata,
                difficulty=self._difficulty
            )

            # Return True if entry was added (block creation is optional with batching)
            return True

        except Exception as e:
            logging.error(f"Failed to log entry: {e}")
            return False

    def log_operation(
        self,
        command_object: str,
        operation_type: str,
        details: dict[str, Any] | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> bool:
        """Log an operation to blockchain.

        Args:
            command_object: Command or object being accessed
            operation_type: Type of operation
            details: Additional operation details
            user_id: User ID
            ip_address: IP address

        Returns:
            True if operation was logged successfully
        """
        # Auto-reconfigure if needed
        self._auto_reconfigure_if_needed()
        
        if not self.is_enabled():
            return False

        # Get local IP if not provided
        if not ip_address:
            ip_address = self._get_local_ip()

        entry_data = {
            "operation": operation_type,
            "user_id": user_id or "unknown",
            "resource": command_object,
            "action": "execute",
            "details": details or {},
            "metadata": {
                "timestamp": self._get_timestamp(),
                "ip_address": ip_address,
                "command_object": command_object,
            }
        }

        return self.log_entry(entry_data)

    def log_http_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> bool:
        """Log an HTTP request to blockchain.

        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            user_id: User ID
            ip_address: IP address
            details: Additional details to include

        Returns:
            True if request was logged successfully
        """
        # Auto-reconfigure if needed
        self._auto_reconfigure_if_needed()
        
        if not self.is_enabled():
            return False

        # Get local IP if not provided
        if not ip_address:
            ip_address = self._get_local_ip()

        # Merge details
        request_details = {
            "method": method,
            "url": url,
            "headers": headers or {},
            "ip_address": ip_address,
        }
        if details:
            request_details.update(details)

        entry_data = {
            "operation": "http_request",
            "user_id": user_id or "unknown",
            "resource": url,
            "action": method,
            "details": request_details,
            "metadata": {
                "timestamp": self._get_timestamp(),
                "ip_address": ip_address,
            }
        }

        return self.log_entry(entry_data)

    def get_blockchain_info(self) -> dict[str, Any]:
        """Get blockchain information."""
        if not self.is_enabled():
            return {
                "enabled": False,
                "error": "Blockchain logger not enabled"
            }
        
        try:
            info = self._blockchain_logger.get_info()
            info["enabled"] = True

            # Add configuration information
            from ..config import get_config_manager
            config_manager = get_config_manager()
            info["database_path"] = config_manager.get("audit.log.database_path")
            info["difficulty"] = config_manager.get("audit.log.difficulty")
            info["batch_size"] = config_manager.get("audit.log.batch_size")
            info["batch_timeout"] = config_manager.get("audit.log.batch_timeout")

            return info
        except Exception as e:
            return {"enabled": True, "error": str(e)}

    def verify_blockchain_integrity(self) -> dict[str, Any]:
        """Verify blockchain integrity."""
        if not self._blockchain_logger:
            return {"enabled": False}

        try:
            is_valid = self._blockchain_logger.verify_integrity()
            return {
                "enabled": True,
                "integrity_verified": is_valid,
                "message": "Blockchain integrity verified" if is_valid else "Blockchain integrity compromised"
            }
        except Exception as e:
            return {
                "enabled": True,
                "integrity_verified": False,
                "error": str(e),
                "message": f"Error verifying integrity: {e}"
            }

    def get_blockchain_logs(
        self, 
        limit: int = 100,
        user_id: str = None,
        operation: str = None,
        resource: str = None,
        action: str = None,
        start_time: float = None,
        end_time: float = None
    ) -> list[dict[str, Any]]:
        """Get recent blockchain logs.

        Args:
            limit: Maximum number of log entries to return
            user_id: Filter by user ID
            operation: Filter by operation type
            resource: Filter by resource
            action: Filter by action
            start_time: Filter by start time
            end_time: Filter by end time

        Returns:
            List of log entries
        """
        if not self.is_enabled():
            return []

        try:
            # Get filtered log entries from functional logger
            all_entries = self._blockchain_logger.get_logs(
                user_id=user_id,
                operation=operation,
                resource=resource,
                action=action,
                start_time=start_time,
                end_time=end_time,
                limit=limit
            )
            
            # Sort by timestamp (newest first)
            all_entries.sort(key=lambda x: x.get("timestamp", 0), reverse=True)
            
            return all_entries
        except Exception as e:
            logging.error(f"Failed to get blockchain logs: {e}")
            return []

    def clear_blockchain(self) -> None:
        """Clear all blocks from the blockchain (for testing)."""
        if self._blockchain_logger:
            self._blockchain_logger.storage.clear_blocks()

    def _get_local_ip(self) -> str | None:
        """Get local IP address."""
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect(("8.8.8.8", 80))
                return s.getsockname()[0]
        except Exception:
            return None

    def _get_timestamp(self) -> float:
        """Get current timestamp."""
        import time
        return time.time()

    def reconfigure(self) -> None:
        """Reconfigure the audit logger."""
        self._setup_blockchain()

    def _auto_reconfigure_if_needed(self) -> None:
        """Auto-reconfigure if configuration has changed."""
        from ..config import get_config_manager
        config_manager = get_config_manager()
        
        # Check if audit logging is enabled
        log_enabled = config_manager.get("audit.log.enabled")
        
        # If audit logging is disabled but we have a logger, reconfigure
        if not log_enabled and self._blockchain_logger is not None:
            self._setup_blockchain()
            return
            
        # If audit logging is enabled but we don't have a logger, reconfigure
        if log_enabled and self._blockchain_logger is None:
            self._setup_blockchain()
            return
            
        # If we have a logger, check if configuration has changed
        if self._blockchain_logger is not None:
            current_batch_size = config_manager.get("audit.log.batch_size")
            current_batch_timeout = config_manager.get("audit.log.batch_timeout")
            current_database_path = config_manager.get("audit.log.database_path")
            
            # If any configuration has changed, reconfigure
            # Convert to appropriate types for comparison
            current_batch_size_int = int(current_batch_size) if current_batch_size is not None else 100
            current_batch_timeout_float = float(current_batch_timeout) if current_batch_timeout is not None else 120.0
            
            if (current_batch_size_int != self._blockchain_logger.batch_size or
                current_batch_timeout_float != self._blockchain_logger.batch_timeout or
                current_database_path != self._blockchain_logger.storage.db_path):
                self._setup_blockchain()


def get_immutable_audit_logger() -> ImmutableAuditLogger:
    """Get the immutable audit logger instance."""
    return ImmutableAuditLogger.get_instance()


def immutable_audit_enabled() -> bool:
    """Check if immutable audit logging is enabled."""
    return get_immutable_audit_logger().is_enabled()


def log_http_request_immutable(
    method: str,
    url: str,
    headers: dict[str, str] | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
) -> bool:
    """Log an HTTP request using immutable audit logging."""
    return get_immutable_audit_logger().log_http_request(
        method=method,
        url=url,
        headers=headers,
        user_id=user_id,
        ip_address=ip_address,
    )


def log_operation_immutable(
    command_object: str,
    operation_type: str,
    details: dict[str, Any] | None = None,
    user_id: str | None = None,
    ip_address: str | None = None,
) -> bool:
    """Log an operation using immutable audit logging."""
    return get_immutable_audit_logger().log_operation(
        command_object=command_object,
        operation_type=operation_type,
        details=details,
        user_id=user_id,
        ip_address=ip_address,
    ) 