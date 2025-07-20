"""Tests for configuration management."""

import tempfile
from pathlib import Path

from adoc_toolkit.config import ConfigManager


def test_config_manager_initialization() -> None:
    """Test configuration manager initialization."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        config = ConfigManager(config_file)

        # Should have default values
        assert config.get("http.timeout") == 120
        assert config.get("http.retries") == 3
        assert config.get("http.proxy") is None


def test_config_get_and_set() -> None:
    """Test getting and setting configuration values."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        config = ConfigManager(config_file)

        # Test setting values
        config.set("http.timeout", 60)
        config.set("http.retries", 5)
        config.set("http.proxy", "https://proxy.example.com")

        # Test getting values
        assert config.get("http.timeout") == 60
        assert config.get("http.retries") == 5
        assert config.get("http.proxy") == "https://proxy.example.com"

        # Test non-existent key
        assert config.get("nonexistent.key") is None


def test_config_persistence() -> None:
    """Test configuration persistence to file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        # First instance - set values
        config1 = ConfigManager(config_file)
        config1.set("http.timeout", 90)
        config1.set("http.proxy", "https://test.proxy.com")

        # Second instance - should load persisted values
        config2 = ConfigManager(config_file)
        assert config2.get("http.timeout") == 90
        assert config2.get("http.proxy") == "https://test.proxy.com"
        assert config2.get("http.retries") == 3  # Default value


def test_config_validation() -> None:
    """Test configuration value validation."""
    config = ConfigManager()

    # Test timeout validation
    valid, value, error = config.validate_value("http.timeout", "60")
    assert valid is True
    assert value == 60
    assert error == ""

    valid, value, error = config.validate_value("http.timeout", "invalid")
    assert valid is False
    assert "must be an integer" in error

    valid, value, error = config.validate_value("http.timeout", "-5")
    assert valid is False
    assert "positive integer" in error

    # Test retries validation
    valid, value, error = config.validate_value("http.retries", "3")
    assert valid is True
    assert value == 3

    valid, value, error = config.validate_value("http.retries", "15")
    assert valid is False
    assert "cannot exceed 10" in error

    # Test proxy validation
    valid, value, error = config.validate_value("http.proxy", "https://proxy.com")
    assert valid is True
    assert value == "https://proxy.com"

    valid, value, error = config.validate_value("http.proxy", "none")
    assert valid is True
    assert value is None

    valid, value, error = config.validate_value("http.proxy", "invalid-url")
    assert valid is False
    assert "valid HTTP or HTTPS URL" in error


def test_config_section_operations() -> None:
    """Test configuration section operations."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        config = ConfigManager(config_file)

        # Set some values
        config.set("http.timeout", 45)
        config.set("http.retries", 2)

        # Test get_section
        http_section = config.get_section("http")
        assert http_section["timeout"] == 45
        assert http_section["retries"] == 2
        assert http_section["proxy"] is None

        # Test list_all
        all_config = config.list_all()
        assert "http" in all_config
        assert all_config["http"]["timeout"] == 45


def test_config_corrupted_file_handling() -> None:
    """Test handling of corrupted configuration files."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        # Write invalid JSON
        config_file.write_text("{ invalid json }")

        config = ConfigManager(config_file)

        # Should still work with default values
        assert config.get("http.timeout") == 120
        assert config.get("http.retries") == 3
        assert config.get("http.proxy") is None


def test_config_nested_keys() -> None:
    """Test nested configuration key handling."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        config = ConfigManager(config_file)

        # Set nested values
        config.set("deep.nested.key", "value")
        config.set("another.section.setting", 42)

        # Test retrieval
        assert config.get("deep.nested.key") == "value"
        assert config.get("another.section.setting") == 42
        assert config.get("deep.nested") == {"key": "value"}
        assert config.get("nonexistent.nested.key") is None


def test_config_edge_cases() -> None:
    """Test configuration edge cases."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "adoc-toolkit-config.json"

        config = ConfigManager(config_file)

        # Test empty key components
        config.set("empty..key", "value")
        assert config.get("empty..key") == "value"

        # Test overwriting non-dict with dict
        config.set("simple", "string")
        config.set("simple.nested", "nested_value")
        assert config.get("simple.nested") == "nested_value"

        # Test None values
        config.set("null.value", None)
        assert config.get("null.value") is None


def test_config_file_resolution() -> None:
    """Test configuration file resolution logic."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Change to temporary directory
        original_cwd = Path.cwd()
        try:
            import os

            os.chdir(temp_dir)

            # Test 1: Explicit config file
            explicit_config = Path(temp_dir) / "explicit-config.json"
            config = ConfigManager(explicit_config)
            assert config._config_file == explicit_config

            # Test 2: Config directory file
            config_dir = Path(temp_dir) / "config"
            config_dir.mkdir()
            config_dir_file = config_dir / "adoc-toolkit-config.json"
            config_dir_file.write_text('{"test": "config_dir"}')

            config = ConfigManager()
            assert config._config_file.resolve() == config_dir_file.resolve()

            # Test 3: Home directory fallback (when config/ doesn't exist)
            config_dir_file.unlink()
            config_dir.rmdir()

            config = ConfigManager()
            expected_home_file = Path.home() / "adoc-toolkit-config.json"
            assert config._config_file == expected_home_file

        finally:
            os.chdir(original_cwd)
