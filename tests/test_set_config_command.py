"""Tests for set-config command."""

import tempfile
from pathlib import Path

from adoc_toolkit.cli.commands.set_config_command import SetConfigCommand


def test_command_name() -> None:
    """Test command name property."""
    cmd = SetConfigCommand()
    assert cmd.name == "set-config"


def test_command_description() -> None:
    """Test command description."""
    cmd = SetConfigCommand()
    assert cmd.description == "Set configuration values for ADOC toolkit"


def test_command_aliases() -> None:
    """Test command aliases."""
    cmd = SetConfigCommand()
    assert cmd.aliases == ["config", "set"]


def test_help_functionality() -> None:
    """Test help system integration."""
    cmd = SetConfigCommand()
    help_text = cmd.get_help()
    assert "set-config" in help_text
    assert "Set configuration values for ADOC toolkit" in help_text
    assert "Usage: set-config <key> <value>" in help_text
    assert "http.timeout" in help_text
    assert "http.retries" in help_text
    assert "http.proxy" in help_text


def test_execute_with_help_flag() -> None:
    """Test execution with --help flag."""
    cmd = SetConfigCommand()
    result = cmd.execute(["--help"])
    assert result is True


def test_execute_without_args() -> None:
    """Test execution without arguments."""
    cmd = SetConfigCommand()
    result = cmd.execute([])
    assert result is True


def test_execute_with_insufficient_args() -> None:
    """Test execution with insufficient arguments."""
    cmd = SetConfigCommand()
    result = cmd.execute(["http.timeout"])
    assert result is True


def test_execute_set_valid_timeout() -> None:
    """Test setting valid timeout value."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        # Reset the config manager instance
        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["http.timeout", "60"])
        assert result is True

        # Verify the value was set
        from adoc_toolkit.config import get_config_manager

        assert get_config_manager().get("http.timeout") == 60


def test_execute_set_valid_retries() -> None:
    """Test setting valid retries value."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["http.retries", "5"])
        assert result is True

        assert get_config_manager().get("http.retries") == 5


def test_execute_set_valid_proxy() -> None:
    """Test setting valid proxy value."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["http.proxy", "https://proxy.example.com"])
        assert result is True

        assert get_config_manager().get("http.proxy") == "https://proxy.example.com"


def test_execute_set_proxy_none() -> None:
    """Test setting proxy to none."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["http.proxy", "none"])
        assert result is True

        assert get_config_manager().get("http.proxy") is None


def test_execute_set_invalid_timeout() -> None:
    """Test setting invalid timeout value."""
    cmd = SetConfigCommand()
    result = cmd.execute(["http.timeout", "invalid"])
    assert result is True


def test_execute_set_negative_retries() -> None:
    """Test setting negative retries value."""
    cmd = SetConfigCommand()
    result = cmd.execute(["http.retries", "-1"])
    assert result is True


def test_execute_set_invalid_proxy() -> None:
    """Test setting invalid proxy value."""
    cmd = SetConfigCommand()
    result = cmd.execute(["http.proxy", "invalid-url"])
    assert result is True


def test_execute_list_config() -> None:
    """Test listing configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["--list"])
        assert result is True


def test_execute_show_specific_config() -> None:
    """Test showing specific configuration value."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()
        result = cmd.execute(["--show", "http.timeout"])
        assert result is True


def test_execute_show_nonexistent_config() -> None:
    """Test showing nonexistent configuration value."""
    cmd = SetConfigCommand()
    result = cmd.execute(["--show", "nonexistent.key"])
    assert result is True


def test_completions_for_keys() -> None:
    """Test auto-completion for configuration keys."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        # Create enhanced config file for testing
        enhanced_config = {
            "http": {
                "timeout": {
                    "value": 120,
                    "description": "HTTP request timeout in seconds",
                    "type": "integer",
                    "options": [30, 60, 120, 300],
                    "default": 120,
                },
                "retries": {
                    "value": 3,
                    "description": "Number of retry attempts for failed requests",
                    "type": "integer",
                    "options": [0, 1, 3, 5],
                    "default": 3,
                },
                "proxy": {
                    "value": None,
                    "description": "HTTP proxy URL for requests",
                    "type": "string",
                    "options": [
                        "https://proxy.example.com:8080",
                        "http://proxy.example.com:3128",
                        "none",
                    ],
                    "default": None,
                },
                "response": {
                    "type": {
                        "value": "json",
                        "description": "Response format type",
                        "type": "string",
                        "options": ["json", "table", "csv"],
                        "default": "json",
                    }
                },
            },
            "audit": {
                "log": {
                    "enabled": {
                        "value": False,
                        "description": "Enable blockchain audit logging",
                        "type": "boolean",
                        "options": [True, False],
                        "default": False,
                    },
                    "database_path": {
                        "value": None,
                        "description": "Path to audit database",
                        "type": "string",
                        "options": ["audit/auditlog.db", "./auditlog.db", "none"],
                        "default": None,
                    }
                }
            },
            "log": {
                "level": {
                    "value": "TRACE",
                    "description": "Logging level for application logs",
                    "type": "string",
                    "options": ["TRACE", "DEBUG", "INFO", "ERROR"],
                    "default": "TRACE",
                },
                "filepath": {
                    "value": None,
                    "description": "Path to log file",
                    "type": "string",
                    "options": ["logs/adoc-toolkit.log", "./adoc-toolkit.log", "none"],
                    "default": None,
                },
                "rotate": {
                    "onsize": {
                        "value": "10MB",
                        "description": "Log rotation size limit",
                        "type": "string",
                        "options": ["10MB", "50MB", "100MB", "1GB"],
                        "default": "10MB",
                    },
                    "ontime": {
                        "value": 120,
                        "description": "Log rotation time interval in minutes",
                        "type": "integer",
                        "options": [60, 120, 240, 480],
                        "default": 120,
                    },
                },
            },
        }

        # Write enhanced config file
        import json

        with open(config_file, "w") as f:
            json.dump(enhanced_config, f, indent=2)

        # Reset config manager with the enhanced config file
        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()

        # Test completion at start
        completions = cmd.get_completions("set-config ", 11)
        assert any(c.text == "http.timeout" for c in completions)
        assert any(c.text == "http.retries" for c in completions)
        assert any(c.text == "http.proxy" for c in completions)
        assert any(c.text == "log.level" for c in completions)
        assert any(c.text == "log.filepath" for c in completions)
        assert any(c.text == "log.rotate.onsize" for c in completions)
        assert any(c.text == "log.rotate.ontime" for c in completions)
        assert any(c.text == "audit.log.enabled" for c in completions)
        assert any(c.text == "--list" for c in completions)
        assert any(c.text == "--show" for c in completions)

        # Test partial completion for HTTP
        completions = cmd.get_completions("set-config http.t", 17)
        assert any(c.text == "http.timeout" for c in completions)
        assert not any(c.text == "http.retries" for c in completions)

        # Test partial completion for log keys
        completions = cmd.get_completions("set-config l", 12)
        assert any(c.text == "log.level" for c in completions)
        assert any(c.text == "log.filepath" for c in completions)
        assert any(c.text == "log.rotate.onsize" for c in completions)
        assert any(c.text == "log.rotate.ontime" for c in completions)
        assert not any(c.text == "http.timeout" for c in completions)

        # Test partial completion for log.
        completions = cmd.get_completions("set-config log.", 15)
        assert any(c.text == "log.level" for c in completions)
        assert any(c.text == "log.filepath" for c in completions)
        assert any(c.text == "log.rotate.onsize" for c in completions)
        assert any(c.text == "log.rotate.ontime" for c in completions)
        assert not any(c.text == "audit.log.enabled" for c in completions)


def test_completions_for_show_flag() -> None:
    """Test auto-completion for --show flag."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        # Create enhanced config file for testing
        enhanced_config = {
            "http": {
                "timeout": {
                    "value": 120,
                    "description": "HTTP request timeout in seconds",
                    "type": "integer",
                    "options": [30, 60, 120, 300],
                    "default": 120,
                },
                "retries": {
                    "value": 3,
                    "description": "Number of retry attempts for failed requests",
                    "type": "integer",
                    "options": [0, 1, 3, 5],
                    "default": 3,
                },
                "proxy": {
                    "value": None,
                    "description": "HTTP proxy URL for requests",
                    "type": "string",
                    "options": [
                        "https://proxy.example.com:8080",
                        "http://proxy.example.com:3128",
                        "none",
                    ],
                    "default": None,
                },
            },
            "log": {
                "level": {
                    "value": "TRACE",
                    "description": "Logging level for application logs",
                    "type": "string",
                    "options": ["TRACE", "DEBUG", "INFO", "ERROR"],
                    "default": "TRACE",
                },
                "filepath": {
                    "value": None,
                    "description": "Path to log file",
                    "type": "string",
                    "options": ["logs/adoc-toolkit.log", "./adoc-toolkit.log", "none"],
                    "default": None,
                },
                "rotate": {
                    "onsize": {
                        "value": "10MB",
                        "description": "Log rotation size limit",
                        "type": "string",
                        "options": ["10MB", "50MB", "100MB", "1GB"],
                        "default": "10MB",
                    },
                    "ontime": {
                        "value": 120,
                        "description": "Log rotation time interval in minutes",
                        "type": "integer",
                        "options": [60, 120, 240, 480],
                        "default": 120,
                    },
                },
            },
            "audit": {
                "log": {
                    "enabled": {
                        "value": False,
                        "description": "Enable blockchain audit logging",
                        "type": "boolean",
                        "options": [True, False],
                        "default": False,
                    },
                    "database_path": {
                        "value": None,
                        "description": "Path to audit database",
                        "type": "string",
                        "options": ["audit/auditlog.db", "./auditlog.db", "none"],
                        "default": None,
                    }
                }
            },
        }

        # Write enhanced config file
        import json

        with open(config_file, "w") as f:
            json.dump(enhanced_config, f, indent=2)

        # Reset config manager with the enhanced config file
        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()

        completions = cmd.get_completions("set-config --show ", 18)
        assert any(c.text == "http.timeout" for c in completions)
        assert any(c.text == "http.retries" for c in completions)
        assert any(c.text == "http.proxy" for c in completions)
        assert any(c.text == "log.level" for c in completions)
        assert any(c.text == "log.filepath" for c in completions)
        assert any(c.text == "log.rotate.onsize" for c in completions)
        assert any(c.text == "log.rotate.ontime" for c in completions)
        assert any(c.text == "audit.log.enabled" for c in completions)


def test_completions_for_values() -> None:
    """Test auto-completion for configuration values."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        # Create enhanced config file for testing
        enhanced_config = {
            "http": {
                "timeout": {
                    "value": 120,
                    "description": "HTTP request timeout in seconds",
                    "type": "integer",
                    "options": [30, 60, 120, 300],
                    "default": 120,
                },
                "retries": {
                    "value": 3,
                    "description": "Number of retry attempts for failed requests",
                    "type": "integer",
                    "options": [0, 1, 3, 5],
                    "default": 3,
                },
                "proxy": {
                    "value": None,
                    "description": "HTTP proxy URL for requests",
                    "type": "string",
                    "options": [
                        "https://proxy.example.com:8080",
                        "http://proxy.example.com:3128",
                        "none",
                    ],
                    "default": None,
                },
            },
            "log": {
                "level": {
                    "value": "TRACE",
                    "description": "Logging level for application logs",
                    "type": "string",
                    "options": ["TRACE", "DEBUG", "INFO", "ERROR"],
                    "default": "TRACE",
                },
                "filepath": {
                    "value": None,
                    "description": "Path to log file",
                    "type": "string",
                    "options": ["logs/adoc-toolkit.log", "./adoc-toolkit.log", "none"],
                    "default": None,
                },
                "rotate": {
                    "onsize": {
                        "value": "10MB",
                        "description": "Log rotation size limit",
                        "type": "string",
                        "options": ["10MB", "50MB", "100MB", "1GB"],
                        "default": "10MB",
                    }
                },
            },
        }

        # Write enhanced config file
        import json

        with open(config_file, "w") as f:
            json.dump(enhanced_config, f, indent=2)

        # Reset config manager with the enhanced config file
        from adoc_toolkit.config import reset_config_manager

        reset_config_manager(config_file)

        cmd = SetConfigCommand()

        # Test timeout value completions
        completions = cmd.get_completions("set-config http.timeout ", 24)
        assert any(c.text == "30" for c in completions)
        assert any(c.text == "60" for c in completions)
        assert any(c.text == "120" for c in completions)
        assert any(c.text == "300" for c in completions)

        # Test retries value completions
        completions = cmd.get_completions("set-config http.retries ", 24)
        assert any(c.text == "0" for c in completions)
        assert any(c.text == "1" for c in completions)
        assert any(c.text == "3" for c in completions)
        assert any(c.text == "5" for c in completions)

        # Test proxy value completions
        completions = cmd.get_completions("set-config http.proxy ", 22)
        assert any(c.text == "https://proxy.example.com:8080" for c in completions)
        assert any(c.text == "none" for c in completions)

        # Test log level value completions
        completions = cmd.get_completions("set-config log.level ", 21)
        assert any(c.text == "TRACE" for c in completions)
        assert any(c.text == "DEBUG" for c in completions)
        assert any(c.text == "INFO" for c in completions)
        assert any(c.text == "ERROR" for c in completions)

        # Test log filepath value completions
        completions = cmd.get_completions("set-config log.filepath ", 24)
        assert any(c.text == "logs/adoc-toolkit.log" for c in completions)
        assert any(c.text == "./adoc-toolkit.log" for c in completions)
        assert any(c.text == "none" for c in completions)

        # Test log rotation size value completions
        completions = cmd.get_completions("set-config log.rotate.onsize ", 30)
        assert any(c.text == "10MB" for c in completions)
        assert any(c.text == "50MB" for c in completions)
        assert any(c.text == "100MB" for c in completions)
        assert any(c.text == "1GB" for c in completions)


def test_flatten_config() -> None:
    """Test configuration flattening functionality."""
    cmd = SetConfigCommand()

    nested_config = {
        "http": {"timeout": 120, "retries": 3, "proxy": None},
        "other": {"nested": {"value": "test"}},
    }

    flattened = cmd._flatten_config(nested_config)
    assert flattened["http.timeout"] == 120
    assert flattened["http.retries"] == 3
    assert flattened["http.proxy"] is None
    assert flattened["other.nested.value"] == "test"


def test_format_value() -> None:
    """Test value formatting functionality."""
    cmd = SetConfigCommand()

    assert "[dim]None[/dim]" in cmd._format_value(None)
    assert "[green]true[/green]" in cmd._format_value(True)
    assert "[red]false[/red]" in cmd._format_value(False)
    assert "[dim](empty)[/dim]" in cmd._format_value("")
    assert cmd._format_value("test") == "test"
    assert cmd._format_value(42) == "42"
