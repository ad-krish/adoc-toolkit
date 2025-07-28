"""Tests for custom LLM model options from config file."""

import json
import tempfile
from pathlib import Path

from adoc_toolkit.config import reset_config_manager
from adoc_toolkit.models.llm_config import LLMVendor


class TestCustomModelOptions:
    """Test custom model options from config file."""

    def test_custom_model_options_from_config(self):
        """Test loading custom model options from config file."""
        # Create a temporary config file with custom model options
        custom_config = {
            "llm": {
                "model_options": {
                    "value": {
                        "claude": [
                            "claude-3-5-sonnet-20241022",
                            "claude-3-5-haiku-20241022",
                        ],
                        "gemini": ["gemini-1.5-pro", "gemini-1.5-flash"],
                        "grok": ["grok-beta"],
                        "chatgpt": ["gpt-4o", "gpt-4o-mini"],
                    },
                    "description": "Available models for each vendor (configurable)",
                    "type": "object",
                    "options": ["custom", "default"],
                    "default": "default",
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom_config, f)
            config_file = Path(f.name)

        try:
            # Reset config manager with custom config file
            config_manager = reset_config_manager(config_file)

            # Get LLM config
            llm_config = config_manager._config.llm

            # Test that custom model options are loaded
            assert llm_config.model_options is not None

            # Test Claude models
            llm_config.vendor = LLMVendor.CLAUDE
            claude_models = llm_config.get_model_options()
            assert "claude-3-5-sonnet-20241022" in claude_models
            assert "claude-3-5-haiku-20241022" in claude_models
            assert len(claude_models) == 2  # Only custom models

            # Test Gemini models
            llm_config.vendor = LLMVendor.GEMINI
            gemini_models = llm_config.get_model_options()
            assert "gemini-1.5-pro" in gemini_models
            assert "gemini-1.5-flash" in gemini_models
            assert len(gemini_models) == 2  # Only custom models

            # Test Grok models
            llm_config.vendor = LLMVendor.GROK
            grok_models = llm_config.get_model_options()
            assert "grok-beta" in grok_models
            assert len(grok_models) == 1  # Only custom models

            # Test ChatGPT models
            llm_config.vendor = LLMVendor.CHATGPT
            chatgpt_models = llm_config.get_model_options()
            assert "gpt-4o" in chatgpt_models
            assert "gpt-4o-mini" in chatgpt_models
            assert len(chatgpt_models) == 2  # Only custom models

        finally:
            # Clean up
            config_file.unlink()

    def test_partial_custom_model_options(self):
        """Test loading partial custom model options (some vendors missing)."""
        # Create a config file with only some vendors defined
        partial_config = {
            "llm": {
                "model_options": {
                    "value": {
                        "claude": ["claude-3-5-sonnet-20241022"],
                        "gemini": ["gemini-1.5-pro"],
                        # Missing grok and chatgpt - should use defaults
                    },
                    "description": "Available models for each vendor (configurable)",
                    "type": "object",
                    "options": ["custom", "default"],
                    "default": "default",
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(partial_config, f)
            config_file = Path(f.name)

        try:
            # Reset config manager with partial config file
            config_manager = reset_config_manager(config_file)

            # Get LLM config
            llm_config = config_manager._config.llm

            # Test Claude (custom)
            llm_config.vendor = LLMVendor.CLAUDE
            claude_models = llm_config.get_model_options()
            assert claude_models == ["claude-3-5-sonnet-20241022"]

            # Test Gemini (custom)
            llm_config.vendor = LLMVendor.GEMINI
            gemini_models = llm_config.get_model_options()
            assert gemini_models == ["gemini-1.5-pro"]

            # Test Grok (should use defaults)
            llm_config.vendor = LLMVendor.GROK
            grok_models = llm_config.get_model_options()
            assert "grok-beta" in grok_models
            assert "grok-2" in grok_models

            # Test ChatGPT (should use defaults)
            llm_config.vendor = LLMVendor.CHATGPT
            chatgpt_models = llm_config.get_model_options()
            assert "gpt-4o" in chatgpt_models
            assert "gpt-4o-mini" in chatgpt_models

        finally:
            # Clean up
            config_file.unlink()

    def test_default_model_options_when_none_configured(self):
        """Test that default model options are used when none configured."""
        # Create a config file without model_options
        basic_config = {
            "llm": {
                "vendor": {
                    "value": "gemini",
                    "description": "LLM vendor to use for AI operations",
                    "type": "string",
                    "options": ["claude", "gemini", "grok", "chatgpt"],
                    "default": "gemini",
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(basic_config, f)
            config_file = Path(f.name)

        try:
            # Reset config manager with basic config file
            config_manager = reset_config_manager(config_file)

            # Get LLM config
            llm_config = config_manager._config.llm

            # Should use default model options
            assert llm_config.model_options is None

            # Test that default options are returned
            llm_config.vendor = LLMVendor.CLAUDE
            claude_models = llm_config.get_model_options()
            assert "claude-3-5-sonnet-20241022" in claude_models
            assert "claude-3-5-haiku-20241022" in claude_models
            assert len(claude_models) >= 3  # Default has multiple models

        finally:
            # Clean up
            config_file.unlink()

    def test_get_all_model_options_with_custom_config(self):
        """Test get_all_model_options with custom configuration."""
        # Create a config file with custom model options
        custom_config = {
            "llm": {
                "model_options": {
                    "value": {
                        "claude": ["claude-3-5-sonnet-20241022"],
                        "gemini": ["gemini-1.5-pro"],
                        "grok": ["grok-beta"],
                        "chatgpt": ["gpt-4o"],
                    },
                    "description": "Available models for each vendor (configurable)",
                    "type": "object",
                    "options": ["custom", "default"],
                    "default": "default",
                }
            }
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(custom_config, f)
            config_file = Path(f.name)

        try:
            # Reset config manager with custom config file
            config_manager = reset_config_manager(config_file)

            # Get LLM config
            llm_config = config_manager._config.llm

            # Test get_all_model_options
            all_options = llm_config.get_all_model_options()

            # Should return custom model options
            assert all_options["claude"] == ["claude-3-5-sonnet-20241022"]
            assert all_options["gemini"] == ["gemini-1.5-pro"]
            assert all_options["grok"] == ["grok-beta"]
            assert all_options["chatgpt"] == ["gpt-4o"]

        finally:
            # Clean up
            config_file.unlink()
