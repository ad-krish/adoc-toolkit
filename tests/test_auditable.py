"""Tests for auditable mixin and decorators."""

import json
import tempfile
from pathlib import Path

from adoc_toolkit.audit import (
    AuditableMixin,
)
from adoc_toolkit.audit import (
    audit_command as audit_operation,
)
from adoc_toolkit.audit import (
    audit_http_request_decorator as audit_http_request,
)
from adoc_toolkit.config import get_config_manager, reset_config_manager


class AuditableTestClass(AuditableMixin):
    """Test class that uses AuditableMixin."""

    def __init__(self):
        super().__init__()

    def test_method(self, param1: str, param2: int = 10) -> None:
        """Test method for audit testing."""
        return f"{param1}_{param2}"


def test_auditable_mixin_context():
    """Test setting and using audit context."""
    obj = AuditableTestClass()

    # Set audit context
    obj.set_audit_context(user_id="test_user", ip_address="192.168.1.1")

    assert obj._audit_user_id == "test_user"
    assert obj._audit_ip_address == "192.168.1.1"


def test_auditable_mixin_operation_logging():
    """Test audit operation logging through mixin."""
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

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="mixin_user", ip_address="10.0.0.1")

        obj.audit_operation(
            command_object="test_object",
            operation_type="TEST_OP",
            details={"param": "value"},
        )

        # Check that the operation was logged to blockchain
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "TEST_OP"
        assert latest_log["user_id"] == "mixin_user"
        assert latest_log["resource"] == "test_object"
        assert latest_log["details"]["param"] == "value"


def test_auditable_mixin_http_logging():
    """Test HTTP request logging through mixin."""
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

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="http_user", ip_address="172.16.0.1")

        obj.audit_http_request(
            method="PUT",
            url="https://api.example.com/resource",
            headers={"Content-Type": "application/json"},
        )

        # Check that the request was logged to blockchain
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "http_request"
        assert latest_log["user_id"] == "http_user"
        assert latest_log["resource"] == "https://api.example.com/resource"
        assert latest_log["action"] == "PUT"
        assert latest_log["details"]["method"] == "PUT"
        assert latest_log["details"]["url"] == "https://api.example.com/resource"


def test_audit_operation_decorator():
    """Test audit operation decorator."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        @audit_operation("decorated_func", "CALL")
        def test_function(arg1: str, arg2: int) -> None:
            return f"{arg1}_{arg2}"

        # Call the decorated function
        result = test_function("test", 42)

        # Check that the operation was logged
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "CALL"
        assert latest_log["resource"] == "decorated_func"
        assert result == "test_42"


def test_audit_operation_decorator_with_args():
    """Test audit operation decorator with argument extraction."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        @audit_operation("func_with_args", "EXECUTE", extract_args=True)
        def test_function_with_args(
            name: str, count: int, password: str = "secret"
        ) -> None:
            return f"{name}_{count}"

        # Call the decorated function
        result = test_function_with_args("test", 42, "mypassword")

        # Check that the operation was logged with extracted args
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "EXECUTE"
        assert latest_log["resource"] == "func_with_args"
        assert "function_name" in latest_log["details"]
        assert "args" in latest_log["details"]
        assert "kwargs" in latest_log["details"]
        assert result == "test_42"


def test_audit_operation_decorator_with_mixin():
    """Test audit operation decorator with AuditableMixin."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        class DecoratedClass(AuditableMixin):
            def __init__(self):
                super().__init__()
                self.set_audit_context(user_id="decorated_user")

            @audit_operation("method_call", "INVOKE")
            def decorated_method(self, param: str) -> None:
                return f"decorated_{param}"

        obj = DecoratedClass()
        result = obj.decorated_method("test_param")

        # Check that the operation was logged
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "INVOKE"
        assert latest_log["resource"] == "method_call"
        assert latest_log["user_id"] == "decorated_user"
        assert result == "decorated_test_param"


def test_audit_http_request_decorator():
    """Test audit HTTP request decorator."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Enable audit logging
        config_manager.set("audit.log.enabled", True)
        config_manager.set("audit.log.database_path", str(database_path))
        config_manager.set("audit.log.difficulty", 1)

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        @audit_http_request()
        def make_request(method: str, url: str, headers: dict = None) -> None:
            return f"{method}_{url}"

        # Call the decorated function
        result = make_request("GET", "https://api.example.com/test", {"Content-Type": "application/json"})

        # Check that the request was logged
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "http_request"
        assert latest_log["resource"] == "https://api.example.com/test"
        assert latest_log["action"] == "GET"
        assert latest_log["details"]["method"] == "GET"
        assert latest_log["details"]["url"] == "https://api.example.com/test"
        assert result == "GET_https://api.example.com/test"


def test_audit_disabled_no_logs():
    """Test that no logs are created when audit is disabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        database_path = Path(temp_dir) / "audit.db"

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        
        # Disable audit logging
        config_manager.set("audit.log.enabled", False)

        # Reset the singleton instance to force reconfiguration
        from adoc_toolkit.audit import ImmutableAuditLogger
        ImmutableAuditLogger.reset_instance()

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        @audit_operation("test", "OP")
        def test_func():
            return "test_result"

        # Call the function
        result = test_func()

        # Check that no logs were created
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) == 0
        assert result == "test_result"


def test_audit_context_override():
    """Test that audit context can be overridden."""
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

        # Clear any existing blockchain
        from adoc_toolkit.audit import get_immutable_audit_logger
        logger = get_immutable_audit_logger()
        logger.clear_blockchain()

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="default_user", ip_address="192.168.1.1")

        # Override context for specific operation
        obj.audit_operation(
            command_object="test_object",
            operation_type="TEST_OP",
            user_id="override_user",
            ip_address="10.0.0.1",
        )

        # Check that the operation was logged with override values
        logs = logger.get_blockchain_logs(limit=10)
        
        assert len(logs) >= 1
        latest_log = logs[0]
        assert latest_log["operation"] == "TEST_OP"
        assert latest_log["user_id"] == "override_user"
        assert latest_log["resource"] == "test_object"
