"""Tests for LLM temperature configuration."""

import pytest
from unittest.mock import Mock, patch
from adoc_toolkit.config import get_config_manager, reset_config_manager
from adoc_toolkit.models.llm_config import LLMConfig, LLMVendor


class TestTemperatureConfig:
    """Test temperature configuration functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        # Reset config manager for clean state
        reset_config_manager()

    def test_llm_config_temperature_default(self):
        """Test that LLMConfig has correct default temperature."""
        config = LLMConfig()
        assert config.temperature == 0.2

    def test_llm_config_temperature_validation(self):
        """Test temperature validation in LLMConfig."""
        # Valid temperatures
        config = LLMConfig(temperature=0.0)
        assert config.temperature == 0.0
        
        config = LLMConfig(temperature=1.0)
        assert config.temperature == 1.0
        
        config = LLMConfig(temperature=2.0)
        assert config.temperature == 2.0

    def test_llm_config_temperature_validation_errors(self):
        """Test temperature validation errors."""
        # Too low
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 2.0"):
            LLMConfig(temperature=-0.1)
        
        # Too high
        with pytest.raises(ValueError, match="Temperature must be between 0.0 and 2.0"):
            LLMConfig(temperature=2.1)
        
        # Invalid type - Pydantic handles this automatically
        with pytest.raises(Exception):  # Pydantic validation error
            LLMConfig(temperature="invalid")

    def test_config_manager_temperature_option(self):
        """Test that ConfigManager includes temperature option."""
        # Reset config manager to ensure clean state
        reset_config_manager()
        config_manager = get_config_manager()
        enhanced_structure = config_manager._convert_to_enhanced_structure()
        
        # Check that temperature is in the LLM section
        assert "llm" in enhanced_structure
        assert "temperature" in enhanced_structure["llm"]
        
        # Check temperature configuration
        temp_config = enhanced_structure["llm"]["temperature"]
        # The value might be from config file, but default should be 0.2
        assert temp_config["default"] == 0.2
        assert temp_config["type"] == "float"
        assert "Temperature for LLM response generation" in temp_config["description"]
        assert 0.0 in temp_config["options"]
        assert 0.2 in temp_config["options"]
        assert 1.0 in temp_config["options"]
        assert 2.0 in temp_config["options"]

    def test_set_config_temperature(self):
        """Test setting temperature via ConfigManager."""
        config_manager = get_config_manager()
        
        # Test valid temperature values
        config_manager.set("llm.temperature", 0.5)
        assert config_manager.get("llm.temperature") == 0.5
        
        config_manager.set("llm.temperature", 1.0)
        assert config_manager.get("llm.temperature") == 1.0
        
        config_manager.set("llm.temperature", 0.0)
        assert config_manager.get("llm.temperature") == 0.0

    def test_set_config_temperature_validation(self):
        """Test temperature validation in ConfigManager."""
        config_manager = get_config_manager()
        
        # Test invalid values - these should be caught by the validate_value method
        is_valid, converted_value, error_msg = config_manager.validate_value("llm.temperature", "-0.1")
        assert not is_valid
        assert "Temperature must be between 0.0 and 2.0" in error_msg
        
        is_valid, converted_value, error_msg = config_manager.validate_value("llm.temperature", "2.1")
        assert not is_valid
        assert "Temperature must be between 0.0 and 2.0" in error_msg
        
        is_valid, converted_value, error_msg = config_manager.validate_value("llm.temperature", "invalid")
        assert not is_valid
        assert "could not convert string to float" in error_msg

    def test_temperature_string_conversion(self):
        """Test that string temperature values are converted correctly."""
        config_manager = get_config_manager()
        
        # Test string to float conversion
        is_valid, converted_value, error_msg = config_manager.validate_value("llm.temperature", "0.5")
        assert is_valid
        assert converted_value == 0.5
        
        is_valid, converted_value, error_msg = config_manager.validate_value("llm.temperature", "1.0")
        assert is_valid
        assert converted_value == 1.0

    def test_temperature_in_set_config_help(self):
        """Test that temperature appears in set-config help."""
        from adoc_toolkit.cli.commands.set_config_command import SetConfigCommand
        
        command = SetConfigCommand()
        help_text = command.get_help()
        
        assert "llm.temperature" in help_text
        assert "Temperature for response generation" in help_text
        assert "0.0-2.0" in help_text
        assert "default: 0.2" in help_text
        assert "set-config llm.temperature 0.7" in help_text

    def test_temperature_with_different_vendors(self):
        """Test that temperature works with different LLM vendors."""
        config_manager = get_config_manager()
        
        # Set temperature
        config_manager.set("llm.temperature", 0.8)
        
        # Test with different vendors
        vendors = ["gemini", "claude", "chatgpt", "grok"]
        for vendor in vendors:
            config_manager.set("llm.vendor", vendor)
            assert config_manager.get("llm.temperature") == 0.8 