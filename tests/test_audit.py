"""Tests for audit logging functionality."""

import json
import tempfile
from pathlib import Path

from adoc_toolkit.audit import (
    AuditEntry,
    AuditLogger,
    audit_enabled,
    get_audit_logger,
)
from adoc_toolkit.audit import (
    audit_command_execution as log_operation,
)
from adoc_toolkit.audit import (
    audit_http_request as log_http_request,
)
from adoc_toolkit.config import get_config_manager, reset_config_manager


def test_audit_entry_creation():
    """Test audit entry creation and serialization."""
    entry = AuditEntry(
        ip_address="192.168.1.1",
        user_id="test_user",
        command_object="test_command",
        operation_type="TEST",
        details={"key": "value"},
    )

    assert entry.ip_address == "192.168.1.1"
    assert entry.user_id == "test_user"
    assert entry.command_object == "test_command"
    assert entry.operation_type == "TEST"
    assert entry.details == {"key": "value"}

    # Test serialization
    log_line = entry.to_compressed_log_line()
    parsed = json.loads(log_line)

    assert parsed["ip"] == "192.168.1.1"
    assert parsed["uid"] == "test_user"
    assert parsed["cmd"] == "test_command"
    assert parsed["op"] == "TEST"
    assert parsed["details"]["key"] == "value"


def test_audit_entry_from_http_request():
    """Test creating audit entry from HTTP request data."""
    headers = {
        "Content-Type": "application/json",
        "Authorization": "Bearer token123456789",
        "User-Agent": "ADOC-Toolkit/1.0.0",
        "accessKey": "access123456789",
        "secretKey": "secret123456789",
    }

    entry = AuditEntry.from_http_request(
        method="POST",
        url="https://api.example.com/test",
        headers=headers,
        ip_address="10.0.0.1",
        user_id="api_user",
    )

    assert entry.command_object == "http_request"
    assert entry.operation_type == "POST"
    assert entry.ip_address == "10.0.0.1"
    assert entry.user_id == "api_user"

    # Check compressed headers
    assert entry.details["url"] == "https://api.example.com/test"
    assert entry.details["hdrs"]["ct"] == "application/json"
    assert entry.details["hdrs"]["ua"] == "ADOC-Toolkit/1.0.0"

    # Check masked sensitive headers
    assert entry.details["hdrs"]["auth"] == "Bear***6789"
    assert entry.details["hdrs"]["ak"] == "acce***6789"
    assert entry.details["hdrs"]["sk"] == "secr***6789"


def test_audit_logger_disabled_by_default():
    """Test that audit logging is disabled by default."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        reset_config_manager(config_file)

        logger = AuditLogger()
        assert not logger.is_enabled()
        assert not audit_enabled()


def test_audit_logger_enabled_with_logfile():
    """Test that audit logging is enabled when logfile is configured."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        logger = AuditLogger()
        assert logger.is_enabled()
        assert audit_enabled()


def test_audit_logger_logs_entries():
    """Test that audit logger writes entries to log file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        logger = AuditLogger()

        entry = AuditEntry(
            ip_address="127.0.0.1",
            user_id="test",
            command_object="test_cmd",
            operation_type="CREATE",
        )

        logger.log_entry(entry)

        # Check that log file was created and contains entry
        assert audit_file.exists()
        content = audit_file.read_text()
        assert "test_cmd" in content
        assert "CREATE" in content
        assert "127.0.0.1" in content


def test_audit_logger_http_request_logging():
    """Test HTTP request audit logging."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        logger = AuditLogger()

        logger.log_http_request(
            method="GET",
            url="https://test.com/api",
            headers={"Content-Type": "application/json"},
            user_id="test_user",
            ip_address="192.168.1.100",
        )

        # Check log content
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "http_request"
        assert log_data["op"] == "GET"
        assert log_data["uid"] == "test_user"
        assert log_data["ip"] == "192.168.1.100"
        assert log_data["details"]["url"] == "https://test.com/api"


def test_audit_logger_operation_logging():
    """Test general operation audit logging."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        logger = AuditLogger()

        logger.log_operation(
            command_object="config",
            operation_type="UPDATE",
            details={"key": "http.timeout", "value": "60"},
            user_id="admin",
            ip_address="10.0.0.1",
        )

        # Check log content
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "config"
        assert log_data["op"] == "UPDATE"
        assert log_data["uid"] == "admin"
        assert log_data["ip"] == "10.0.0.1"
        assert log_data["details"]["key"] == "http.timeout"


def test_audit_logger_convenience_functions():
    """Test convenience functions for audit logging."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        # Test HTTP request logging
        log_http_request("POST", "https://api.test.com", user_id="user1")

        # Test operation logging
        log_operation("command", "EXECUTE", user_id="user2")

        # Check log content
        content = audit_file.read_text().strip().split("\n")
        assert len(content) == 2

        # Parse both log entries
        http_log = json.loads(content[0])
        op_log = json.loads(content[1])

        assert http_log["cmd"] == "http_request"
        assert http_log["op"] == "POST"
        assert http_log["uid"] == "user1"

        assert op_log["cmd"] == "command"
        assert op_log["op"] == "EXECUTE"
        assert op_log["uid"] == "user2"


def test_audit_logger_singleton():
    """Test that audit logger uses singleton pattern."""
    logger1 = get_audit_logger()
    logger2 = get_audit_logger()

    assert logger1 is logger2
    assert AuditLogger.get_instance() is logger1


def test_audit_logger_reconfiguration():
    """Test that audit logger reconfigures when settings change."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file1 = Path(temp_dir) / "audit1.log"
        audit_file2 = Path(temp_dir) / "audit2.log"

        reset_config_manager(config_file)
        logger = AuditLogger()

        # Initially disabled
        assert not logger.is_enabled()

        # Enable with first log file
        get_config_manager().set("audit.logfile", str(audit_file1))
        assert logger.is_enabled()

        logger.log_operation("test", "OP1")
        assert audit_file1.exists()

        # Change to second log file
        get_config_manager().set("audit.logfile", str(audit_file2))
        logger.log_operation("test", "OP2")
        assert audit_file2.exists()

        # Check content
        content2 = audit_file2.read_text()
        assert "OP2" in content2


def test_audit_logger_silent_failure():
    """Test that audit logger fails silently on errors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        reset_config_manager(config_file)
        # Set an invalid log file path
        get_config_manager().set("audit.logfile", "/invalid/path/audit.log")

        logger = AuditLogger()

        # This should not raise an exception
        logger.log_operation("test", "OP")
        logger.log_http_request("GET", "http://test.com")


def test_audit_config_validation():
    """Test audit configuration validation."""
    from adoc_toolkit.audit import AuditConfig

    # Test None/empty values
    config1 = AuditConfig(logfile=None)
    assert config1.logfile is None

    config2 = AuditConfig(logfile="")
    assert config2.logfile is None

    config3 = AuditConfig(logfile="  ")
    assert config3.logfile is None

    # Test valid path
    config4 = AuditConfig(logfile="/path/to/audit.log")
    assert config4.logfile == "/path/to/audit.log"

    # Test path with whitespace
    config5 = AuditConfig(logfile="  /path/to/audit.log  ")
    assert config5.logfile == "/path/to/audit.log"
