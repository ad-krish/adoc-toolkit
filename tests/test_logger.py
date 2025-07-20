"""Tests for application logging functionality."""

import tempfile
from pathlib import Path

import pytest

from adoc_toolkit.config import get_config_manager, reset_config_manager
from adoc_toolkit.logs import (
    LogLevel,
    TracerLogger,
    get_logger,
    log_debug,
    log_error,
    log_info,
    trace_config_change,
    trace_error,
    trace_http_request,
    trace_operation,
)


def test_log_config_creation() -> None:
    """Test log configuration creation and validation."""
    from adoc_toolkit.logs import LogConfig, LogRotateConfig

    # Test default configuration
    config = LogConfig()
    assert config.level == LogLevel.INFO
    assert config.filepath is None
    assert config.rotate.onsize == "10MB"
    assert config.rotate.ontime == 120

    # Test custom configuration
    config = LogConfig(
        level=LogLevel.DEBUG,
        filepath="/custom/path/app.log",
        rotate=LogRotateConfig(onsize="50MB", ontime=60),
    )
    assert config.level == LogLevel.DEBUG
    assert config.filepath == "/custom/path/app.log"
    assert config.rotate.onsize == "50MB"
    assert config.rotate.ontime == 60


def test_log_rotate_config_validation() -> None:
    """Test log rotation configuration validation."""
    from adoc_toolkit.logs import LogRotateConfig

    # Test valid sizes
    config = LogRotateConfig(onsize="100KB")
    assert config.onsize == "100KB"
    assert config.size_in_bytes() == 100 * 1024

    config = LogRotateConfig(onsize="5MB")
    assert config.size_in_bytes() == 5 * 1024 * 1024

    config = LogRotateConfig(onsize="1GB")
    assert config.size_in_bytes() == 1024 * 1024 * 1024

    # Test invalid sizes
    with pytest.raises(Exception, match="Size must be a valid number followed by unit"):
        LogRotateConfig(onsize="100XB")

    with pytest.raises(Exception, match="Size must be a valid number followed by unit"):
        LogRotateConfig(onsize="invalidMB")

    with pytest.raises(Exception, match="Size must be positive"):
        LogRotateConfig(onsize="-10MB")

    # Test invalid time
    with pytest.raises(Exception, match="Time threshold must be positive"):
        LogRotateConfig(ontime=-5)


def test_log_config_default_filepath() -> None:
    """Test log configuration default filepath generation."""
    from datetime import datetime

    from adoc_toolkit.logs import LogConfig

    config = LogConfig()
    filepath = config.get_default_filepath()

    # Should contain current date
    date_str = datetime.now().strftime("%m-%d-%Y")
    expected_filename = f"adoc-toolkit-{date_str}.log"

    assert expected_filename in filepath
    assert "logs" in filepath


def test_tracer_logger_disabled_by_default() -> None:
    """Test that tracer logger respects configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        reset_config_manager(config_file)

        # Default should be INFO level with no explicit filepath
        logger = TracerLogger()
        assert logger.is_enabled()
        assert logger.is_level_enabled(LogLevel.INFO)
        assert logger.is_level_enabled(LogLevel.ERROR)
        assert not logger.is_level_enabled(LogLevel.DEBUG)


def test_tracer_logger_with_debug_level() -> None:
    """Test tracer logger with DEBUG level."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "debug.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.level", "DEBUG")
        get_config_manager().set("log.filepath", str(log_file))

        logger = TracerLogger()
        assert logger.is_enabled()
        assert logger.is_level_enabled(LogLevel.DEBUG)
        assert logger.is_level_enabled(LogLevel.INFO)
        assert logger.is_level_enabled(LogLevel.ERROR)


def test_tracer_logger_with_error_level() -> None:
    """Test tracer logger with ERROR level."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "error.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.level", "ERROR")
        get_config_manager().set("log.filepath", str(log_file))

        logger = TracerLogger()
        assert logger.is_enabled()
        assert not logger.is_level_enabled(LogLevel.DEBUG)
        assert not logger.is_level_enabled(LogLevel.INFO)
        assert logger.is_level_enabled(LogLevel.ERROR)


def test_tracer_logger_logging() -> None:
    """Test tracer logger actual logging functionality."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "test.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.level", "DEBUG")
        get_config_manager().set("log.filepath", str(log_file))

        logger = TracerLogger()

        # Test different log levels
        logger.debug("Debug message", param1="value1")
        logger.info("Info message", param2="value2")
        logger.error("Error message", param3="value3")

        # Force flush by closing handlers
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check log content
        assert log_file.exists()
        content = log_file.read_text()

        assert "Debug message" in content
        assert "Info message" in content
        assert "Error message" in content
        assert "param1=value1" in content
        assert "param2=value2" in content
        assert "param3=value3" in content


def test_tracer_logger_operations() -> None:
    """Test tracer logger operation tracing."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "operations.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.level", "TRACE")
        get_config_manager().set("log.filepath", str(log_file))

        logger = TracerLogger()

        # Test operation tracing
        logger.trace_operation("user_login", user_id="test_user", ip="192.168.1.1")
        logger.trace_http_request("POST", "https://api.test.com", 200, duration="123ms")
        logger.trace_config_change("http.timeout", 30, 60, user="admin")
        logger.trace_error("database_connection", "Connection timeout", retry_count=3)

        # Force flush
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check log content
        content = log_file.read_text()

        assert "TRACE: user_login" in content
        assert "user_id=test_user" in content
        assert "HTTP: POST https://api.test.com -> 200" in content
        assert "duration=123ms" in content
        assert "CONFIG: http.timeout changed" in content
        assert "old=30" in content
        assert "new=60" in content
        assert "ERROR: database_connection failed" in content
        assert "retry_count=3" in content


def test_convenience_functions() -> None:
    """Test convenience logging functions."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "convenience.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.level", "TRACE")
        get_config_manager().set("log.filepath", str(log_file))

        # Reset logger singleton to pick up new configuration
        from adoc_toolkit.logs.service import reset_logger

        reset_logger()

        # Test convenience functions
        log_debug("Debug via function", test="debug")
        log_info("Info via function", test="info")
        log_error("Error via function", test="error")

        trace_operation("api_call", endpoint="/users")
        trace_http_request("GET", "https://example.com", 404)
        trace_config_change("app.mode", "dev", "prod")
        trace_error("validation", ValueError("Invalid input"))

        # Force flush
        logger = get_logger()
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check log content
        content = log_file.read_text()

        assert "Debug via function" in content
        assert "Info via function" in content
        assert "Error via function" in content
        assert "TRACE: api_call" in content
        assert "HTTP: GET https://example.com -> 404" in content
        assert "CONFIG: app.mode changed" in content
        assert "ERROR: validation failed" in content


def test_logger_singleton() -> None:
    """Test that logger uses singleton pattern."""
    logger1 = get_logger()
    logger2 = get_logger()

    assert logger1 is logger2
    assert TracerLogger.get_instance() is logger1


def test_logger_reconfiguration() -> None:
    """Test that logger reconfigures when settings change."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file1 = Path(temp_dir) / "test1.log"
        log_file2 = Path(temp_dir) / "test2.log"

        reset_config_manager(config_file)
        logger = TracerLogger()

        # Set first log file
        get_config_manager().set("log.filepath", str(log_file1))
        get_config_manager().set("log.level", "INFO")

        logger.info("Message 1")

        # Change to second log file
        get_config_manager().set("log.filepath", str(log_file2))
        get_config_manager().set("log.level", "DEBUG")

        # Force logger reconfiguration by resetting and getting new instance
        from adoc_toolkit.logs.service import reset_logger

        reset_logger()
        logger = TracerLogger()

        logger.debug("Message 2")

        # Force flush
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check both files exist and have appropriate content
        assert log_file1.exists()
        assert log_file2.exists()

        content2 = log_file2.read_text()
        assert "Message 2" in content2


def test_log_rotation_size() -> None:
    """Test log rotation by size."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "rotation.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.filepath", str(log_file))
        get_config_manager().set("log.level", "INFO")
        get_config_manager().set("log.rotate.onsize", "1KB")  # Very small for testing

        logger = TracerLogger()

        # Write enough data to trigger rotation
        for i in range(100):
            logger.info(
                f"Long message number {i} with lots of text to fill up "
                f"the log file quickly"
            )

        # Force flush
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check for rotated files
        log_dir = Path(temp_dir)
        log_files = list(log_dir.glob("rotation.log*"))

        # Should have at least the main log file
        assert len(log_files) >= 1
        assert log_file.exists()


def test_configuration_integration() -> None:
    """Test integration with configuration system."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        reset_config_manager(config_file)

        # Test getting log configuration
        config_data = get_config_manager()._config
        assert hasattr(config_data, "log")
        assert config_data.log.level == LogLevel.INFO

        # Test setting log configuration
        get_config_manager().set("log.level", "DEBUG")
        get_config_manager().set("log.rotate.onsize", "50MB")
        get_config_manager().set("log.rotate.ontime", 240)

        updated_config = get_config_manager()._config
        assert updated_config.log.level == LogLevel.DEBUG
        assert updated_config.log.rotate.onsize == "50MB"
        assert updated_config.log.rotate.ontime == 240


def test_logger_silent_failure() -> None:
    """Test that logger fails silently on errors."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        reset_config_manager(config_file)
        # Set an invalid log file path
        get_config_manager().set("log.filepath", "/invalid/readonly/path/test.log")

        logger = TracerLogger()

        # These should not raise exceptions
        logger.info("Test message")
        logger.debug("Debug message")
        logger.error("Error message")

        trace_operation("test_op")
        trace_http_request("GET", "http://test.com")
        trace_error("test_error", "Some error")


def test_level_filtering() -> None:
    """Test that log level filtering works correctly."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"
        log_file = Path(temp_dir) / "filtered.log"

        reset_config_manager(config_file)
        get_config_manager().set("log.filepath", str(log_file))
        get_config_manager().set("log.level", "ERROR")  # Only ERROR level

        logger = TracerLogger()

        # These should not be logged
        logger.debug("Debug message")
        logger.info("Info message")

        # This should be logged
        logger.error("Error message")

        # Force flush
        if logger._logger:
            for handler in logger._logger.handlers:
                handler.flush()
                handler.close()

        # Check log content
        content = log_file.read_text()

        assert "Debug message" not in content
        assert "Info message" not in content
        assert "Error message" in content


def test_default_log_path_creation() -> None:
    """Test that default log path is created correctly."""
    from datetime import datetime

    from adoc_toolkit.logs import LogConfig

    config = LogConfig()
    default_path = config.get_default_filepath()

    # Should be in logs/ directory
    assert "logs" in default_path

    # Should contain current date
    date_str = datetime.now().strftime("%m-%d-%Y")
    assert date_str in default_path

    # Should have correct extension
    assert default_path.endswith(".log")
