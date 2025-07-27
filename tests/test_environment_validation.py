"""Tests for environment configuration validation."""

import pytest
from pathlib import Path
from unittest.mock import patch, mock_open
from adoc_toolkit.cli.environment_validator import EnvironmentValidator


class TestEnvironmentValidation:
    """Test cases for environment configuration validation."""

    def setup_method(self):
        """Set up test fixtures."""
        self.validator = EnvironmentValidator(Path("config/environments.yaml"))

    def test_valid_configuration(self):
        """Test that valid configuration passes validation."""
        # Create a temporary valid config file
        valid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
default_environment: "test-env"
"""
        
        with patch("builtins.open", mock_open(read_data=valid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is True
            assert len(errors) == 0

    def test_missing_environments_section(self):
        """Test validation fails when environments section is missing."""
        invalid_config_content = """
default_environment: "test-env"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("Missing required section" in error for error in errors)

    def test_empty_environments_section(self):
        """Test validation fails when environments section is empty."""
        invalid_config_content = """
environments: {}
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("No environments defined" in error for error in errors)

    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    # Missing access_key and secret_key
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("Missing required field" in error for error in errors)

    def test_invalid_environment_name(self):
        """Test validation fails with invalid environment name."""
        invalid_config_content = """
environments:
  dev@env:  # Invalid character
    name: "dev@env"
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("Invalid environment name" in error for error in errors)

    def test_invalid_base_url(self):
        """Test validation fails with invalid base URL."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "invalid-url"  # Invalid URL
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("must start with 'http://' or 'https://'" in error for error in errors)

    def test_invalid_access_key_format(self):
        """Test validation fails with invalid access key format."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "test123"  # Lowercase not allowed
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("should contain only uppercase letters and numbers" in error for error in errors)

    def test_short_access_key(self):
        """Test validation fails with short access key."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "ABC"  # Too short
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("too short" in error for error in errors)

    def test_invalid_secret_key_format(self):
        """Test validation fails with invalid secret key format."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "secret123"  # Lowercase not allowed
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("should contain only uppercase letters and numbers" in error for error in errors)

    def test_short_secret_key(self):
        """Test validation fails with short secret key."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "ABC"  # Too short
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("too short" in error for error in errors)

    def test_name_mismatch(self):
        """Test validation fails when name field doesn't match environment key."""
        invalid_config_content = """
environments:
  test-env:
    name: "different-name"  # Doesn't match key
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("Name mismatch" in error for error in errors)

    def test_invalid_default_environment(self):
        """Test validation fails with invalid default environment."""
        invalid_config_content = """
environments:
  test-env:
    name: "test-env"
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
default_environment: "non-existent-env"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("does not exist in the environments list" in error for error in errors)

    def test_invalid_config_type(self):
        """Test validation fails when config is not a dictionary."""
        invalid_config_content = "not a dictionary"
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("must be a YAML object" in error for error in errors)

    def test_invalid_environments_type(self):
        """Test validation fails when environments is not a dictionary."""
        invalid_config_content = """
environments: "not a dictionary"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("must be a YAML object" in error for error in errors)

    def test_invalid_environment_config_type(self):
        """Test validation fails when environment config is not a dictionary."""
        invalid_config_content = """
environments:
  test-env: "not a dictionary"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("must be a YAML object" in error for error in errors)

    def test_invalid_field_types(self):
        """Test validation fails when field types are incorrect."""
        invalid_config_content = """
environments:
  test-env:
    name: 123  # Should be string
    base_url: "https://test.acceldata.app"
    access_key: "TEST123456789"
    secret_key: "SECRET123456789"
"""
        
        with patch("builtins.open", mock_open(read_data=invalid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert any("must be a string" in error for error in errors)

    @patch("builtins.open", mock_open(read_data="invalid yaml content"))
    @patch("pathlib.Path.exists", return_value=True)
    def test_yaml_parsing_error(self, mock_exists):
        """Test handling of YAML parsing errors."""
        with patch("yaml.safe_load", side_effect=Exception("YAML parsing error")):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is False
            assert len(errors) > 0

    @patch("pathlib.Path.exists", return_value=False)
    def test_missing_config_file(self, mock_exists):
        """Test handling of missing config file."""
        is_valid, errors = self.validator.validate_config()
        assert is_valid is False
        assert len(errors) > 0

    def test_multiple_environments_validation(self):
        """Test validation with multiple environments."""
        valid_config_content = """
environments:
  dev:
    name: "dev"
    base_url: "https://dev.acceldata.app"
    access_key: "DEV123456789"
    secret_key: "DEVSECRET123456789"
  prod:
    name: "prod"
    base_url: "https://prod.acceldata.app"
    access_key: "PROD123456789"
    secret_key: "PRODSECRET123456789"
default_environment: "dev"
"""
        
        with patch("builtins.open", mock_open(read_data=valid_config_content)):
            is_valid, errors = self.validator.validate_config()
            assert is_valid is True
            assert len(errors) == 0 