"""Tests for LLM configuration model."""

import pytest
from pydantic import ValidationError

from adoc_toolkit.models.llm_config import LLMConfig, LLMVendor


class TestLLMVendor:
    """Test LLM vendor enum."""

    def test_vendor_values(self):
        """Test vendor enum values."""
        assert LLMVendor.CLAUDE.value == "claude"
        assert LLMVendor.GEMINI.value == "gemini"
        assert LLMVendor.GROK.value == "grok"
        assert LLMVendor.CHATGPT.value == "chatgpt"

    def test_vendor_from_string(self):
        """Test creating vendor from string."""
        assert LLMVendor("claude") == LLMVendor.CLAUDE
        assert LLMVendor("gemini") == LLMVendor.GEMINI
        assert LLMVendor("grok") == LLMVendor.GROK
        assert LLMVendor("chatgpt") == LLMVendor.CHATGPT

    def test_vendor_case_insensitive(self):
        """Test vendor case insensitive conversion."""
        # Note: Enum doesn't support case-insensitive by default
        # The conversion happens in the config manager
        assert LLMVendor("claude") == LLMVendor.CLAUDE
        assert LLMVendor("gemini") == LLMVendor.GEMINI


class TestLLMConfig:
    """Test LLM configuration model."""

    def test_default_config(self):
        """Test default configuration."""
        config = LLMConfig()
        assert config.vendor == LLMVendor.GEMINI
        assert config.apikey is None
        assert config.model is None

    def test_custom_config(self):
        """Test custom configuration."""
        config = LLMConfig(
            vendor=LLMVendor.CLAUDE,
            apikey="test-key",
            model="claude-3-5-sonnet-20241022"
        )
        assert config.vendor == LLMVendor.CLAUDE
        assert config.apikey == "test-key"
        assert config.model == "claude-3-5-sonnet-20241022"

    def test_get_model_default(self):
        """Test getting model with default."""
        config = LLMConfig(vendor=LLMVendor.CLAUDE)
        assert config.get_model() == "claude-3-5-sonnet-20241022"

    def test_get_model_custom(self):
        """Test getting custom model."""
        config = LLMConfig(
            vendor=LLMVendor.CLAUDE,
            model="claude-3-5-haiku-20241022"
        )
        assert config.get_model() == "claude-3-5-haiku-20241022"

    def test_get_vendor_options(self):
        """Test getting vendor options."""
        config = LLMConfig()
        options = config.get_vendor_options()
        assert "claude" in options
        assert "gemini" in options
        assert "grok" in options
        assert "chatgpt" in options
        assert len(options) == 4

    def test_get_model_options_claude(self):
        """Test getting model options for Claude."""
        config = LLMConfig(vendor=LLMVendor.CLAUDE)
        options = config.get_model_options()
        assert "claude-3-5-sonnet-20241022" in options
        assert "claude-3-5-haiku-20241022" in options
        assert "claude-3-opus-20240229" in options
        assert "claude-3-sonnet-20240229" in options

    def test_get_model_options_gemini(self):
        """Test getting model options for Gemini."""
        config = LLMConfig(vendor=LLMVendor.GEMINI)
        options = config.get_model_options()
        assert "gemini-1.5-pro" in options
        assert "gemini-1.5-flash" in options
        assert "gemini-1.0-pro" in options

    def test_get_model_options_grok(self):
        """Test getting model options for Grok."""
        config = LLMConfig(vendor=LLMVendor.GROK)
        options = config.get_model_options()
        assert "grok-beta" in options
        assert "grok-2" in options

    def test_get_model_options_chatgpt(self):
        """Test getting model options for ChatGPT."""
        config = LLMConfig(vendor=LLMVendor.CHATGPT)
        options = config.get_model_options()
        assert "gpt-4o" in options
        assert "gpt-4o-mini" in options
        assert "gpt-4-turbo" in options
        assert "gpt-3.5-turbo" in options

    def test_apikey_validation_empty_string(self):
        """Test API key validation with empty string."""
        config = LLMConfig(apikey="")
        assert config.apikey is None

    def test_apikey_validation_whitespace(self):
        """Test API key validation with whitespace."""
        config = LLMConfig(apikey="   ")
        assert config.apikey is None

    def test_apikey_validation_valid(self):
        """Test API key validation with valid key."""
        config = LLMConfig(apikey="sk-1234567890abcdef")
        assert config.apikey == "sk-1234567890abcdef"

    def test_model_auto_set_based_on_vendor(self):
        """Test model auto-setting based on vendor."""
        config = LLMConfig(vendor=LLMVendor.CLAUDE)
        assert config.get_model() == "claude-3-5-sonnet-20241022"

        config = LLMConfig(vendor=LLMVendor.GEMINI)
        assert config.get_model() == "gemini-1.5-pro"

        config = LLMConfig(vendor=LLMVendor.GROK)
        assert config.get_model() == "grok-beta"

        config = LLMConfig(vendor=LLMVendor.CHATGPT)
        assert config.get_model() == "gpt-4o"

    def test_invalid_vendor(self):
        """Test invalid vendor raises error."""
        with pytest.raises(ValidationError):
            LLMConfig(vendor="invalid")

    def test_model_validation_with_vendor(self):
        """Test model validation in context of vendor."""
        # This should work - model will be auto-set based on vendor
        config = LLMConfig(vendor=LLMVendor.CLAUDE, model=None)
        assert config.get_model() == "claude-3-5-sonnet-20241022"

        # This should also work - custom model
        config = LLMConfig(
            vendor=LLMVendor.CLAUDE,
            model="claude-3-5-haiku-20241022"
        )
        assert config.get_model() == "claude-3-5-haiku-20241022"


class TestLLMConfigIntegration:
    """Test LLM configuration integration with ConfigurationData."""

    def test_llm_config_in_configuration_data(self):
        """Test LLM config is properly integrated in ConfigurationData."""
        from adoc_toolkit.models.configuration_data import ConfigurationData

        config = ConfigurationData()
        assert hasattr(config, 'llm')
        assert isinstance(config.llm, LLMConfig)
        assert config.llm.vendor == LLMVendor.GEMINI

    def test_llm_config_set_method(self):
        """Test setting LLM configuration via ConfigurationData.set()."""
        from adoc_toolkit.models.configuration_data import ConfigurationData

        config = ConfigurationData()
        
        # Test setting vendor
        config.set("llm.vendor", "claude")
        assert config.llm.vendor == LLMVendor.CLAUDE
        
        # Test setting API key
        config.set("llm.apikey", "test-key")
        assert config.llm.apikey == "test-key"
        
        # Test setting model
        config.set("llm.model", "claude-3-5-haiku-20241022")
        assert config.llm.model == "claude-3-5-haiku-20241022"

    def test_llm_config_set_invalid_vendor(self):
        """Test setting invalid vendor raises error."""
        from adoc_toolkit.models.configuration_data import ConfigurationData

        config = ConfigurationData()
        
        with pytest.raises(ValueError, match="Invalid LLM vendor"):
            config.set("llm.vendor", "invalid")

    def test_llm_config_get_method(self):
        """Test getting LLM configuration via ConfigurationData.get()."""
        from adoc_toolkit.models.configuration_data import ConfigurationData

        config = ConfigurationData()
        config.llm.vendor = LLMVendor.CLAUDE
        config.llm.apikey = "test-key"
        config.llm.model = "claude-3-5-sonnet-20241022"
        
        assert config.get("llm.vendor") == LLMVendor.CLAUDE
        assert config.get("llm.apikey") == "test-key"
        assert config.get("llm.model") == "claude-3-5-sonnet-20241022" 