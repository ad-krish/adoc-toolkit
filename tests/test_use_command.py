"""Tests for use command."""

import tempfile
from pathlib import Path
from typing import Any, Union
from unittest.mock import patch

from adoc_toolkit.cli.commands.use_command import UseCommand


def test_command_name() -> None:
    """Test command name property."""
    cmd = UseCommand()
    assert cmd.name == "use"


def test_command_description() -> None:
    """Test command description."""
    cmd = UseCommand()
    assert cmd.description == "Switch to a different environment"


def test_command_aliases() -> None:
    """Test command has no aliases."""
    cmd = UseCommand()
    assert cmd.aliases == []


def test_help_functionality() -> None:
    """Test help system integration."""
    cmd = UseCommand()
    help_text = cmd.get_help()
    assert "use" in help_text
    assert "Switch to a different environment" in help_text
    assert "Usage: use <environment-name>" in help_text


def test_execute_with_help_flag() -> None:
    """Test execution with --help flag."""
    cmd = UseCommand()
    result = cmd.execute(["--help"])
    assert result is True


def test_execute_without_args() -> None:
    """Test execution without arguments."""
    cmd = UseCommand()
    result = cmd.execute([])
    assert result is True


def test_execute_with_missing_config() -> None:
    """Test execution when config file is missing."""
    cmd = UseCommand()
    result = cmd.execute(["nonexistent-env"])
    assert result is True


def test_execute_with_valid_environment() -> None:
    """Test execution with valid environment from config."""
    # Create a temporary config file
    config_content = """
environments:
  test-env:
    name: "Test Environment"
    base_url: "https://test.example.com"
    access_key: "test-access-key"
    secret_key: "test-secret-key"
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "environments.yaml"
        config_file.write_text(config_content)

        # Mock the config path
        with patch("adoc_toolkit.cli.commands.use_command.Path") as mock_path:
            mock_path.return_value = config_file

            callback_called = False
            callback_args: Union[tuple[str, dict[str, Any]], None] = None

            def mock_callback(env_name: str, env_config: dict[str, Any]) -> None:
                nonlocal callback_called, callback_args
                callback_called = True
                callback_args = (env_name, env_config)

            cmd = UseCommand(environment_callback=mock_callback)
            result = cmd.execute(["test-env"])

            assert result is True
            assert callback_called
            assert callback_args is not None
            assert callback_args[0] == "test-env"
            assert callback_args[1]["name"] == "Test Environment"


def test_execute_with_invalid_environment() -> None:
    """Test execution with invalid environment name."""
    config_content = """
environments:
  valid-env:
    name: "Valid Environment"
    base_url: "https://valid.example.com"
    access_key: "valid-access-key"
    secret_key: "valid-secret-key"
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "environments.yaml"
        config_file.write_text(config_content)

        # Mock the config path
        with patch("adoc_toolkit.cli.commands.use_command.Path") as mock_path:
            mock_path.return_value = config_file

            cmd = UseCommand()
            result = cmd.execute(["invalid-env"])

            assert result is True


def test_completions_without_config() -> None:
    """Test completions when config file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create a path to a non-existent config file
        non_existent_config = Path(temp_dir) / "nonexistent" / "environments.yaml"

        # Mock the config path to point to non-existent file
        with patch("adoc_toolkit.cli.commands.use_command.Path") as mock_path:
            mock_path.return_value = non_existent_config

            cmd = UseCommand()
            completions = cmd.get_completions("use ", 4)
            assert completions == []


def test_completions_with_environments() -> None:
    """Test completions with valid environments in config."""
    config_content = """
environments:
  dev:
    name: "Development"
  staging:
    name: "Staging"
  production:
    name: "Production"
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "environments.yaml"
        config_file.write_text(config_content)

        # Mock the config path
        with patch("adoc_toolkit.cli.commands.use_command.Path") as mock_path:
            mock_path.return_value = config_file

            cmd = UseCommand()

            # Test completion for empty argument
            completions = cmd.get_completions("use ", 4)
            assert "dev" in completions
            assert "staging" in completions
            assert "production" in completions

            # Test partial completion
            completions = cmd.get_completions("use d", 5)
            assert "dev" in completions
            assert "staging" not in completions


def test_config_caching() -> None:
    """Test that config is cached for performance."""
    config_content = """
environments:
  test-env:
    name: "Test Environment"
"""

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "environments.yaml"
        config_file.write_text(config_content)

        # Mock the config path
        with patch("adoc_toolkit.cli.commands.use_command.Path") as mock_path:
            mock_path.return_value = config_file

            cmd = UseCommand()

            # First load should read from file
            config1 = cmd._load_config()

            # Second load should use cache
            config2 = cmd._load_config()

            # Should be the same object (cached)
            assert config1 is config2
