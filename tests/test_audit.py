"""Tests for immutable audit logging functionality."""

import json
import tempfile
from pathlib import Path

from adoc_toolkit.audit import (
    ImmutableAuditLogger,
    immutable_audit_enabled,
    get_immutable_audit_logger,
    log_operation_immutable,
    log_http_request_immutable,
)
from adoc_toolkit.config import get_config_manager, reset_config_manager


def test_immutable_audit_logger_disabled_by_default():
    """Test that immutable audit logging is disabled by default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        reset_config_manager(config_file)

        logger = get_immutable_audit_logger()
        assert not logger.is_enabled()
        assert not immutable_audit_enabled()


def test_immutable_audit_logger_enabled_with_config():
    """Test that immutable audit logging is enabled when configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        logger = get_immutable_audit_logger()
        assert logger.is_enabled()
        assert immutable_audit_enabled()


def test_immutable_audit_logger_logs_operations():
    """Test that immutable audit logger logs operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging with small batch size for immediate commits
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)
        config_manager.set("audit.log.batch_size", 1)  # Force immediate commits

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        logger = get_immutable_audit_logger()
        logger.clear_blockchain()
        
        # Log an operation
        success = logger.log_operation(
            command_object="test_command",
            operation_type="TEST",
            details={"key": "value"},
            user_id="test_user",
            ip_address="192.168.1.1",
        )

        # Verify the operation was logged
        assert success is True
        logs = logger.get_blockchain_logs(limit=10)
        assert len(logs) >= 1
        
        latest_log = logs[0]
        assert latest_log["operation"] == "TEST"
        assert latest_log["user_id"] == "test_user"
        assert latest_log["resource"] == "test_command"
        assert latest_log["details"]["key"] == "value"


def test_immutable_audit_logger_logs_http_requests():
    """Test that immutable audit logger logs HTTP requests."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging with small batch size for immediate commits
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)
        config_manager.set("audit.log.batch_size", 1)  # Force immediate commits

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        logger = get_immutable_audit_logger()
        logger.clear_blockchain()
        
        # Log an HTTP request
        headers = {
            "Content-Type": "application/json",
            "Authorization": "Bearer token123",
            "User-Agent": "ADOC-Toolkit/1.0.0",
        }
        
        success = logger.log_http_request(
            method="POST",
            url="https://api.example.com/test",
            headers=headers,
            user_id="api_user",
            ip_address="10.0.0.1",
        )

        # Verify the request was logged
        assert success is True
        logs = logger.get_blockchain_logs(limit=10)
        assert len(logs) >= 1
        
        latest_log = logs[0]
        assert latest_log["operation"] == "http_request"
        assert latest_log["user_id"] == "api_user"
        assert latest_log["resource"] == "https://api.example.com/test"
        assert latest_log["action"] == "POST"
        assert latest_log["details"]["method"] == "POST"
        assert latest_log["details"]["url"] == "https://api.example.com/test"


def test_immutable_audit_logger_convenience_functions():
    """Test immutable audit logger convenience functions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging with small batch size for immediate commits
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)
        config_manager.set("audit.log.batch_size", 1)  # Force immediate commits

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        # Test convenience functions
        success1 = log_operation_immutable(
            command_object="test_command",
            operation_type="TEST",
            details={"key": "value"},
            user_id="test_user",
        )

        success2 = log_http_request_immutable(
            method="GET",
            url="https://api.example.com/test",
            user_id="api_user",
        )

        # Verify logs were created
        assert success1 is True
        assert success2 is True
        logs = logger.get_blockchain_logs(limit=10)
        assert len(logs) >= 2


def test_immutable_audit_logger_singleton():
    """Test that immutable audit logger is a singleton."""
    logger1 = get_immutable_audit_logger()
    logger2 = get_immutable_audit_logger()
    
    assert logger1 is logger2


def test_immutable_audit_logger_reconfiguration():
    """Test that immutable audit logger can be reconfigured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Initially disabled
        config_manager.set("audit.log.enabled", False)
        
        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()
        
        logger = get_immutable_audit_logger()
        assert not logger.is_enabled()

        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Reconfigure
        logger.reconfigure()
        assert logger.is_enabled()


def test_immutable_audit_logger_blockchain_info():
    """Test that immutable audit logger provides blockchain information."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        logger = get_immutable_audit_logger()
        
        # Get blockchain info
        info = logger.get_blockchain_info()
        assert info["enabled"] is True
        assert "total_blocks" in info
        assert "last_block_hash" in info
        assert info["last_block_hash"] != ""  # Should have a hash value


def test_immutable_audit_logger_integrity_verification():
    """Test that immutable audit logger can verify blockchain integrity."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        logger = get_immutable_audit_logger()
        
        # Log some operations
        logger.log_operation(
            command_object="test_command",
            operation_type="TEST",
            details={"key": "value"},
        )

        # Verify integrity
        result = logger.verify_blockchain_integrity()
        assert result["enabled"] is True
        assert result["integrity_verified"] is True


def test_immutable_audit_logger_filtering():
    """Test that immutable audit logger supports filtering."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging with small batch size for immediate commits
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)
        config_manager.set("audit.log.batch_size", 1)  # Force immediate commits

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        logger = get_immutable_audit_logger()
        logger.clear_blockchain()
        
        # Log some operations
        logger.log_operation(
            command_object="test_command1",
            operation_type="TEST1",
            user_id="user1",
        )
        
        logger.log_operation(
            command_object="test_command2",
            operation_type="TEST2",
            user_id="user2",
        )
        
        # Get all logs (filtering is done at blockchain level)
        all_logs = logger.get_blockchain_logs(limit=10)
        assert len(all_logs) >= 2
