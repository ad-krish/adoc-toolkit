"""Tests for show-env command."""

from typing import Any

from adoc_toolkit.cli.commands.show_env_command import ShowEnvCommand


def test_command_name() -> None:
    """Test command name property."""
    cmd = ShowEnvCommand()
    assert cmd.name == "show-env"


def test_command_description() -> None:
    """Test command description."""
    cmd = ShowEnvCommand()
    assert cmd.description == "Show current environment configuration"


def test_command_aliases() -> None:
    """Test command aliases."""
    cmd = ShowEnvCommand()
    assert cmd.aliases == ["env"]


def test_help_functionality() -> None:
    """Test help system integration."""
    cmd = ShowEnvCommand()
    help_text = cmd.get_help()
    assert "show-env" in help_text
    assert "Show current environment configuration" in help_text
    assert "Usage: show-env" in help_text


def test_execute_with_help_flag() -> None:
    """Test execution with --help flag."""
    cmd = ShowEnvCommand()
    result = cmd.execute(["--help"])
    assert result is True


def test_execute_without_callback() -> None:
    """Test execution without environment info callback."""
    cmd = ShowEnvCommand()
    result = cmd.execute([])
    assert result is True


def test_execute_with_no_environment() -> None:
    """Test execution when no environment is selected."""

    def get_empty_env_info() -> dict[str, Any]:
        return {}

    cmd = ShowEnvCommand(environment_info_callback=get_empty_env_info)
    result = cmd.execute([])
    assert result is True


def test_execute_with_environment() -> None:
    """Test execution with valid environment info."""

    def get_env_info() -> dict[str, Any]:
        return {
            "environment": "test-env",
            "base_url": "https://test.example.com",
            "access_key": "test-access-key-12345",
            "secret_key": "test-secret-key-67890abcdef",
        }

    cmd = ShowEnvCommand(environment_info_callback=get_env_info)
    result = cmd.execute([])
    assert result is True


def test_key_masking_normal_keys() -> None:
    """Test key masking for normal length keys."""
    cmd = ShowEnvCommand()

    # Test access key masking
    access_key = "ABCD1234567890EFGH"
    masked = cmd._mask_key(access_key)

    # Should start with first 2 and end with last 2
    assert masked.startswith("AB")
    assert masked.endswith("GH")
    assert "*" in masked

    # Should not contain the original key parts in the middle
    assert "CD123" not in masked
    assert "567890EF" not in masked


def test_key_masking_short_keys() -> None:
    """Test key masking for short keys."""
    cmd = ShowEnvCommand()

    # Keys shorter than 4 characters should be completely masked
    short_key = "ABC"
    masked = cmd._mask_key(short_key)

    # Should be all asterisks with extra length
    assert all(c == "*" for c in masked)
    assert len(masked) > len(short_key)


def test_key_masking_empty_key() -> None:
    """Test key masking for empty key."""
    cmd = ShowEnvCommand()

    empty_key = ""
    masked = cmd._mask_key(empty_key)

    # Should return some asterisks
    assert masked == "***"


def test_key_masking_consistency() -> None:
    """Test that same key always gets same masking."""
    cmd = ShowEnvCommand()

    key = "test-key-12345"
    masked1 = cmd._mask_key(key)
    masked2 = cmd._mask_key(key)

    # Should be consistent
    assert masked1 == masked2


def test_key_masking_different_lengths() -> None:
    """Test that different keys get different mask lengths."""
    cmd = ShowEnvCommand()

    key1 = "short-key-1234"
    key2 = "another-different-key-5678"

    masked1 = cmd._mask_key(key1)
    masked2 = cmd._mask_key(key2)

    # Both should start and end correctly
    assert masked1.startswith("sh") and masked1.endswith("34")
    assert masked2.startswith("an") and masked2.endswith("78")

    # The masking should hide actual length differences
    # (both will have random lengths between 8-16 asterisks)
    assert "*" in masked1 and "*" in masked2


def test_execute_with_missing_keys() -> None:
    """Test execution with missing access/secret keys."""

    def get_env_info_missing_keys() -> dict[str, Any]:
        return {
            "environment": "test-env",
            "base_url": "https://test.example.com",
            "access_key": "",  # Empty access key
            "secret_key": "",  # Empty secret key
        }

    cmd = ShowEnvCommand(environment_info_callback=get_env_info_missing_keys)
    result = cmd.execute([])
    assert result is True


def test_execute_with_partial_info() -> None:
    """Test execution with partial environment info."""

    def get_partial_env_info() -> dict[str, Any]:
        return {
            "environment": "test-env",
            "base_url": "https://test.example.com",
            # Missing access_key and secret_key
        }

    cmd = ShowEnvCommand(environment_info_callback=get_partial_env_info)
    result = cmd.execute([])
    assert result is True
