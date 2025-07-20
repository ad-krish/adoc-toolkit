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
    cmd = SetConfigCommand()

    # Test completion at start
    completions = cmd.get_completions("set-config ", 11)
    assert "http.timeout" in completions
    assert "http.retries" in completions
    assert "http.proxy" in completions
    assert "log.level" in completions
    assert "log.filepath" in completions
    assert "log.rotate.onsize" in completions
    assert "log.rotate.ontime" in completions
    assert "audit.logfile" in completions
    assert "--list" in completions
    assert "--show" in completions

    # Test partial completion for HTTP
    completions = cmd.get_completions("set-config http.t", 17)
    assert "http.timeout" in completions
    assert "http.retries" not in completions

    # Test partial completion for log keys
    completions = cmd.get_completions("set-config l", 12)
    assert "log.level" in completions
    assert "log.filepath" in completions
    assert "log.rotate.onsize" in completions
    assert "log.rotate.ontime" in completions
    assert "http.timeout" not in completions

    # Test partial completion for log.
    completions = cmd.get_completions("set-config log.", 15)
    assert "log.level" in completions
    assert "log.filepath" in completions
    assert "log.rotate.onsize" in completions
    assert "log.rotate.ontime" in completions
    assert "audit.logfile" not in completions


def test_completions_for_show_flag() -> None:
    """Test auto-completion for --show flag."""
    cmd = SetConfigCommand()

    completions = cmd.get_completions("set-config --show ", 18)
    assert "http.timeout" in completions
    assert "http.retries" in completions
    assert "http.proxy" in completions
    assert "log.level" in completions
    assert "log.filepath" in completions
    assert "log.rotate.onsize" in completions
    assert "log.rotate.ontime" in completions
    assert "audit.logfile" in completions


def test_completions_for_values() -> None:
    """Test auto-completion for configuration values."""
    cmd = SetConfigCommand()

    # Test timeout value completions
    completions = cmd.get_completions("set-config http.timeout ", 24)
    assert "30" in completions
    assert "60" in completions
    assert "120" in completions
    assert "300" in completions

    # Test retries value completions
    completions = cmd.get_completions("set-config http.retries ", 24)
    assert "0" in completions
    assert "1" in completions
    assert "3" in completions
    assert "5" in completions

    # Test proxy value completions
    completions = cmd.get_completions("set-config http.proxy ", 22)
    assert "https://proxy.example.com:8080" in completions
    assert "none" in completions

    # Test log level value completions
    completions = cmd.get_completions("set-config log.level ", 21)
    assert "TRACE" in completions
    assert "DEBUG" in completions
    assert "INFO" in completions
    assert "ERROR" in completions

    # Test log filepath value completions
    completions = cmd.get_completions("set-config log.filepath ", 24)
    assert "logs/adoc-toolkit.log" in completions
    assert "./adoc-toolkit.log" in completions
    assert "none" in completions

    # Test log rotation size value completions
    completions = cmd.get_completions("set-config log.rotate.onsize ", 30)
    assert "10MB" in completions
    assert "50MB" in completions
    assert "100MB" in completions
    assert "1GB" in completions

    # Test log rotation time value completions
    completions = cmd.get_completions("set-config log.rotate.ontime ", 30)
    assert "60" in completions
    assert "120" in completions
    assert "240" in completions
    assert "480" in completions

    # Test audit logfile value completions
    completions = cmd.get_completions("set-config audit.logfile ", 25)
    assert "audit/adoc-audit.log" in completions
    assert "./audit.log" in completions
    assert "none" in completions


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
