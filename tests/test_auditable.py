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
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="mixin_user", ip_address="10.0.0.1")

        obj.audit_operation(
            command_object="test_object",
            operation_type="TEST_OP",
            details={"param": "value"},
        )

        # Check log content
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "test_object"
        assert log_data["op"] == "TEST_OP"
        assert log_data["uid"] == "mixin_user"
        assert log_data["ip"] == "10.0.0.1"
        assert log_data["details"]["param"] == "value"


def test_auditable_mixin_http_logging():
    """Test HTTP request logging through mixin."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="http_user", ip_address="172.16.0.1")

        obj.audit_http_request(
            method="PUT",
            url="https://api.example.com/resource",
            headers={"Content-Type": "application/json"},
        )

        # Check log content
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "http_request"
        assert log_data["op"] == "PUT"
        assert log_data["uid"] == "http_user"
        assert log_data["ip"] == "172.16.0.1"
        assert log_data["details"]["url"] == "https://api.example.com/resource"


def test_audit_operation_decorator():
    """Test audit operation decorator."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        @audit_operation("decorated_func", "CALL")
        def test_function(arg1: str, arg2: int) -> None:
            return f"{arg1}_{arg2}"

        result = test_function("hello", 42)
        assert result == "hello_42"

        # Check audit log
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "decorated_func"
        assert log_data["op"] == "CALL"


def test_audit_operation_decorator_with_args():
    """Test audit operation decorator with argument extraction."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        @audit_operation("func_with_args", "EXECUTE", extract_args=True)
        def test_function_with_args(
            name: str, count: int, password: str = "secret"
        ) -> None:
            return f"{name}_{count}"

        result = test_function_with_args("test", 5, password="hidden")
        assert result == "test_5"

        # Check audit log
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "func_with_args"
        assert log_data["op"] == "EXECUTE"
        assert log_data["details"]["name"] == "test"
        assert log_data["details"]["count"] == "5"
        # Password should not be logged
        assert "password" not in log_data["details"]


def test_audit_operation_decorator_with_mixin():
    """Test audit operation decorator with AuditableMixin class."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        class DecoratedClass(AuditableMixin):
            def __init__(self):
                super().__init__()
                self.set_audit_context(
                    user_id="decorator_user", ip_address="192.168.2.1"
                )

            @audit_operation("method_call", "INVOKE")
            def decorated_method(self, param: str) -> None:
                return f"processed_{param}"

        obj = DecoratedClass()
        result = obj.decorated_method("data")
        assert result == "processed_data"

        # Check audit log
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "method_call"
        assert log_data["op"] == "INVOKE"
        assert log_data["uid"] == "decorator_user"
        assert log_data["ip"] == "192.168.2.1"


def test_audit_http_request_decorator():
    """Test audit HTTP request decorator."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        @audit_http_request()
        def make_request(method: str, url: str, headers: dict = None) -> None:
            return f"Request {method} {url}"

        result = make_request(
            "POST", "https://api.test.com/data", {"Content-Type": "application/json"}
        )
        assert result == "Request POST https://api.test.com/data"

        # Check audit log
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        assert log_data["cmd"] == "http_request"
        assert log_data["op"] == "POST"
        assert log_data["details"]["url"] == "https://api.test.com/data"


def test_audit_disabled_no_logs():
    """Test that no logs are created when audit is disabled."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        reset_config_manager(config_file)
        # Don't set audit.logfile, so auditing is disabled

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="test_user")

        # These should not create any logs or throw errors
        obj.audit_operation("test", "OP")
        obj.audit_http_request("GET", "http://test.com")

        @audit_operation("test", "OP")
        def test_func():
            return "result"

        test_func()

        # No audit files should be created
        audit_files = list(Path(temp_dir).glob("*.log"))
        assert len(audit_files) == 0


def test_audit_context_override():
    """Test that explicit parameters override audit context."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        audit_file = Path(temp_dir) / "audit.log"

        reset_config_manager(config_file)
        get_config_manager().set("audit.logfile", str(audit_file))

        obj = AuditableTestClass()
        obj.set_audit_context(user_id="context_user", ip_address="192.168.1.1")

        # Override context with explicit parameters
        obj.audit_operation(
            command_object="test",
            operation_type="OP",
            user_id="override_user",
            ip_address="10.0.0.1",
        )

        # Check log content
        content = audit_file.read_text()
        log_data = json.loads(content.strip())

        # Should use overridden values, not context
        assert log_data["uid"] == "override_user"
        assert log_data["ip"] == "10.0.0.1"
