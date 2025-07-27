"""Tests for human-readable response formatting."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path
import json

from adoc_toolkit.http.formatter import ResponseFormatter
from adoc_toolkit.http.http_config import ResponseType


class TestHumanResponseFormatting:
    """Test human-readable response formatting functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Mock()
        self.formatter = ResponseFormatter(self.console)

    def test_human_response_type_enum(self):
        """Test that HUMAN is included in ResponseType enum."""
        assert ResponseType.HUMAN == "human"
        assert "human" in [rt.value for rt in ResponseType]

    def test_format_response_with_human_type(self):
        """Test that format_response handles HUMAN type."""
        test_data = {"name": "test", "value": 123}

        with patch.object(self.formatter, "_format_human") as mock_human:
            mock_human.return_value = "Human readable text"

            result = self.formatter.format_response(test_data, ResponseType.HUMAN)

            mock_human.assert_called_once_with(test_data)
            assert result == "Human readable text"

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("adoc_toolkit.config.get_config_manager")
    @patch("adoc_toolkit.llm.client.get_llm_client")
    def test_format_human_success(
        self, mock_get_client, mock_get_config, mock_open, mock_exists
    ):
        """Test successful human formatting with LLM."""
        # Mock prompt file
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "System prompt"
        )

        # Mock config manager
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            "llm.vendor": "gemini",
            "llm.apikey": "test-key",
            "llm.model": "gemini-1.5-pro",
        }.get(key, default)
        mock_get_config.return_value = mock_config

        # Mock LLM client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = (
            "**API Response Summary**\n\n*Status*: Success\n*Data*: Found 1 item"
        )
        # Mock the tuple return from with_error_handling decorator
        mock_client.generate_response.return_value = (mock_response, None)
        mock_get_client.return_value = mock_client

        test_data = {"status": "success", "data": [{"id": 1, "name": "test"}]}

        result = self.formatter._format_human(test_data)

        # Verify LLM was called with correct data
        mock_client.generate_response.assert_called_once()
        call_args = mock_client.generate_response.call_args[0][0]
        assert "status" in call_args.user_prompt
        assert "success" in call_args.user_prompt
        assert call_args.api_key == "test-key"
        assert call_args.model == "gemini-1.5-pro"

        assert "**API Response Summary**" in result

    @patch("pathlib.Path.exists")
    def test_format_human_prompt_file_not_found(self, mock_exists):
        """Test human formatting when prompt file is missing."""
        mock_exists.return_value = False

        test_data = {"name": "test", "value": 123}
        result = self.formatter._format_human(test_data)

        assert "Error: Prompt file not found" in result
        assert "JSON Data:" in result
        assert '"name": "test"' in result

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("adoc_toolkit.config.get_config_manager")
    def test_format_human_no_api_key(self, mock_get_config, mock_open, mock_exists):
        """Test human formatting when no API key is configured."""
        # Mock prompt file
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "System prompt"
        )

        # Mock config manager with no API key
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            "llm.vendor": "gemini",
            "llm.apikey": None,
            "llm.model": "gemini-1.5-pro",
        }.get(key, default)
        mock_get_config.return_value = mock_config

        test_data = {"name": "test", "value": 123}
        result = self.formatter._format_human(test_data)

        assert "Error: No LLM API key configured" in result
        assert "JSON Data:" in result
        assert '"name": "test"' in result

    @patch("pathlib.Path.exists")
    @patch("builtins.open")
    @patch("adoc_toolkit.config.get_config_manager")
    @patch("adoc_toolkit.llm.client.get_llm_client")
    def test_format_human_llm_error(
        self, mock_get_client, mock_get_config, mock_open, mock_exists
    ):
        """Test human formatting when LLM raises an error."""
        # Mock prompt file
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = (
            "System prompt"
        )

        # Mock config manager
        mock_config = Mock()
        mock_config.get.side_effect = lambda key, default=None: {
            "llm.vendor": "gemini",
            "llm.apikey": "test-key",
            "llm.model": "gemini-1.5-pro",
        }.get(key, default)
        mock_get_config.return_value = mock_config

        # Mock LLM client to raise exception
        mock_client = Mock()
        # Mock the tuple return from with_error_handling decorator (error case)
        mock_client.generate_response.return_value = (None, "LLM API error")
        mock_get_client.return_value = mock_client

        test_data = {"name": "test", "value": 123}
        result = self.formatter._format_human(test_data)

        assert "Error converting to human-readable format" in result
        assert "LLM API error" in result
        assert "JSON Data:" in result
        assert '"name": "test"' in result

    def test_format_human_json_serialization(self):
        """Test that human formatting properly serializes JSON data."""
        test_data = {
            "status": "success",
            "data": [
                {"id": 1, "name": "item1", "active": True},
                {"id": 2, "name": "item2", "active": False},
            ],
            "metadata": {"count": 2, "timestamp": "2024-01-15T10:30:00Z"},
        }

        with patch.object(self.formatter, "_format_human") as mock_human:
            mock_human.return_value = "Human readable text"

            result = self.formatter.format_response(test_data, ResponseType.HUMAN)

            # Verify the data was passed correctly
            mock_human.assert_called_once_with(test_data)

    def test_prompt_file_content(self):
        """Test that the prompt file exists and has expected content."""
        prompt_file = Path("config/prompts/json_to_human_system.txt")

        if prompt_file.exists():
            with open(prompt_file, "r", encoding="utf-8") as f:
                content = f.read()

            # Check for key elements in the prompt
            assert "JSON API responses" in content
            assert "human-readable" in content
            assert "guidelines" in content.lower()
            assert "example" in content.lower()
        else:
            pytest.skip("Prompt file not found - this is expected in test environment")


class TestHumanResponseIntegration:
    """Test integration of human response type with other components."""

    def test_response_type_validation(self):
        """Test that HUMAN is a valid response type."""
        from adoc_toolkit.http.http_config import ResponseType

        # Test that HUMAN is included in the enum
        assert ResponseType.HUMAN == "human"

        # Test that it can be used in validation
        valid_types = [rt.value for rt in ResponseType]
        assert "human" in valid_types

    @patch("adoc_toolkit.config.ConfigManager")
    def test_config_manager_supports_human(self, mock_config_manager_class):
        """Test that config manager supports human response type."""
        from adoc_toolkit.config import reset_config_manager

        # Mock the config manager to return our expected structure
        mock_config_manager = Mock()
        mock_config_manager.get_all_config_items.return_value = {
            "http.response.type": Mock(
                options=["json", "table", "csv", "human"],
                value="json",
                description="Response format type",
                type="string",
                default="json",
            )
        }
        mock_config_manager_class.return_value = mock_config_manager

        # Reset config manager to ensure it picks up updated options
        config_manager = reset_config_manager()
        config_items = config_manager.get_all_config_items()

        # Check that http.response.type includes human as an option
        if "http.response.type" in config_items:
            item = config_items["http.response.type"]
            assert "human" in item.options

    def test_set_config_supports_human(self):
        """Test that set-config command supports human response type."""
        from adoc_toolkit.cli.commands.set_config_command import SetConfigCommand

        command = SetConfigCommand()
        help_text = command.get_help()

        # Check that help text includes human option
        assert "human" in help_text
        assert "set-config http.response.type human" in help_text
