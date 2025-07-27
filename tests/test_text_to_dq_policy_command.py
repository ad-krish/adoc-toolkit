"""Tests for text-to-dq-policy command."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os

from adoc_toolkit.cli.commands.text_to_dq_policy_command import TextToDQPolicyCommand
from adoc_toolkit.models.llm_config import LLMVendor
from adoc_toolkit.llm import client as llm_client


class TestTextToDQPolicyCommand:
    """Test text-to-dq-policy command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.cmd = TextToDQPolicyCommand()

    def test_command_name(self):
        """Test command name property."""
        assert self.cmd.name == "text-to-dq-policy"

    def test_command_description(self):
        """Test command description."""
        assert self.cmd.description == "Convert text to data quality policy using LLM"

    def test_command_aliases(self):
        """Test command aliases."""
        expected_aliases = ["dq-policy", "text2dq"]
        assert self.cmd.aliases == expected_aliases

    def test_help_functionality(self):
        """Test help system integration."""
        help_text = self.cmd.get_help()
        assert "text-to-dq-policy" in help_text
        assert "Convert text to data quality policy using LLM" in help_text
        assert (
            "Usage: text-to-dq-policy <text> [--uids <comma-separated-uids>]"
            in help_text
        )
        assert "--uids <comma-separated-uids>" in help_text
        assert "llm.vendor" in help_text
        assert "llm.model" in help_text
        assert "llm.apikey" in help_text

    def test_execute_no_args(self):
        """Test command execution with no arguments."""
        result = self.cmd.execute([])
        assert result is True

    def test_execute_help_flag(self):
        """Test command execution with --help flag."""
        result = self.cmd.execute(["--help"])
        assert result is True

    def test_execute_empty_text(self):
        """Test command execution with empty text."""
        result = self.cmd.execute(["   "])
        assert result is True

    def test_execute_with_text(self):
        """Test command execution with text input."""
        result = self.cmd.execute(["Sales data must have valid SALE_ID"])
        assert result is True

    def test_execute_with_uids(self):
        """Test command execution with UIDs."""
        result = self.cmd.execute(["Sales data validation", "--uids", "12345,67890"])
        assert result is True

    def test_execute_with_uids_missing_value(self):
        """Test command execution with --uids but no value."""
        result = self.cmd.execute(["Sales data validation", "--uids"])
        assert result is True

    def test_execute_with_empty_uids(self):
        """Test command execution with empty UIDs."""
        result = self.cmd.execute(["Sales data validation", "--uids", ""])
        assert result is True

    def test_get_completions(self):
        """Test auto-completion functionality."""
        completions = self.cmd.get_completions("text-to-dq-policy ", 0)
        assert len(completions) == 1
        assert completions[0].text == '"Sample business text here"'
        assert (
            completions[0].description == "Enter business text to convert to DQ policy"
        )

    def test_get_completions_with_uids_option(self):
        """Test auto-completion for --uids option."""
        completions = self.cmd.get_completions("text-to-dq-policy test ", 0)
        assert len(completions) == 1
        assert completions[0].text == "--uids"
        assert (
            completions[0].description
            == "Specify comma-separated UIDs for policy generation"
        )

    def test_get_completions_with_uids_value(self):
        """Test auto-completion for UID values."""
        completions = self.cmd.get_completions("text-to-dq-policy test --uids", 0)
        assert len(completions) == 1
        assert completions[0].text == "12345,67890,11111"
        assert completions[0].description == "Comma-separated list of UIDs"

    @patch("adoc_toolkit.cli.commands.text_to_dq_policy_command.get_config_manager")
    def test_generate_dq_policy_no_apikey(self, mock_get_config_manager):
        """Test DQ policy generation with no API key configured."""
        # Mock config manager
        mock_config_manager = Mock()
        mock_llm_config = Mock()
        mock_llm_config.apikey = None
        mock_config_manager._config.llm = mock_llm_config
        mock_get_config_manager.return_value = mock_config_manager

        result = self.cmd._generate_dq_policy("test text")
        assert result is True

    @patch("adoc_toolkit.cli.commands.text_to_dq_policy_command.get_config_manager")
    @patch("adoc_toolkit.cli.commands.text_to_dq_policy_command.get_llm_client")
    def test_generate_dq_policy_with_uids(
        self, mock_get_llm_client, mock_get_config_manager
    ):
        """Test DQ policy generation with UIDs."""
        # Mock config manager
        mock_config_manager = Mock()
        mock_llm_config = Mock()
        mock_llm_config.apikey = "test-key"
        mock_llm_config.vendor.value = "grok"
        mock_llm_config.get_model.return_value = "grok-beta"
        mock_config_manager._config.llm = mock_llm_config
        mock_get_config_manager.return_value = mock_config_manager

        # Mock LLM client
        mock_llm_client = Mock()
        mock_llm_client.generate_with_processing.return_value = True
        mock_get_llm_client.return_value = mock_llm_client

        result = self.cmd._generate_dq_policy("test text", ["12345", "67890"])
        assert result is True
        mock_get_llm_client.assert_called_once()
        mock_llm_client.generate_with_processing.assert_called_once()

    @patch("adoc_toolkit.cli.commands.text_to_dq_policy_command.get_config_manager")
    def test_generate_dq_policy_no_vendor(self, mock_get_config_manager):
        """Test DQ policy generation with no vendor configured."""
        # Mock config manager
        mock_config_manager = Mock()
        mock_llm_config = Mock()
        mock_llm_config.apikey = "test-key"
        mock_llm_config.vendor = None
        mock_config_manager._config.llm = mock_llm_config
        mock_get_config_manager.return_value = mock_config_manager

        result = self.cmd._generate_dq_policy("test text")
        assert result is True

    @patch("adoc_toolkit.cli.commands.text_to_dq_policy_command.get_config_manager")
    def test_generate_dq_policy_unsupported_vendor(self, mock_get_config_manager):
        """Test DQ policy generation with unsupported vendor."""
        # Mock config manager
        mock_config_manager = Mock()
        mock_llm_config = Mock()
        mock_llm_config.apikey = "test-key"
        mock_llm_config.vendor.value = "unsupported"
        mock_config_manager._config.llm = mock_llm_config
        mock_get_config_manager.return_value = mock_config_manager

        result = self.cmd._generate_dq_policy("test text")
        assert result is True

    def test_generate_dq_policy_exception(self):
        """Test DQ policy generation with general exception."""
        with patch(
            "adoc_toolkit.cli.commands.text_to_dq_policy_command.get_config_manager",
            side_effect=Exception("Test error"),
        ):
            result = self.cmd._generate_dq_policy("test text")
            assert result is True

    def test_process_response_with_uids(self):
        """Test processing response with UIDs."""
        response_content = (
            '{"rule": {"enabled": true, "backingAsset": {"tableAssetId": "<uid>"}}}'
        )
        uids = ["12345", "67890"]

        # This should not raise an exception
        self.cmd._process_response_with_uids(response_content, uids)

    def test_process_response_with_uids_multiple_policies(self):
        """Test processing response with UIDs and multiple policies."""
        response_content = '[{"rule": {"enabled": true, "backingAsset": {"tableAssetId": "<uid>"}}}, {"rule": {"enabled": true, "backingAsset": {"tableAssetId": "<uid>"}}}]'
        uids = ["12345", "67890"]

        # This should not raise an exception
        self.cmd._process_response_with_uids(response_content, uids)

    def test_process_response_with_uids_invalid_json(self):
        """Test processing response with invalid JSON."""
        response_content = "Invalid JSON content"
        uids = ["12345"]

        # This should not raise an exception
        self.cmd._process_response_with_uids(response_content, uids)


class TestTextToDQPolicyCommandIntegration:
    """Test text-to-dq-policy command integration."""

    def test_command_registration(self):
        """Test that the command can be instantiated and has required properties."""
        cmd = TextToDQPolicyCommand()

        # Test basic properties
        assert cmd.name == "text-to-dq-policy"
        assert cmd.description == "Convert text to data quality policy using LLM"
        assert len(cmd.aliases) > 0

        # Test help text
        help_text = cmd.get_help()
        assert "text-to-dq-policy" in help_text
        assert "Usage:" in help_text

        # Test execution with help
        result = cmd.execute(["--help"])
        assert result is True

    def test_command_completion_integration(self):
        """Test command completion integration."""
        cmd = TextToDQPolicyCommand()

        # Test completions for empty input
        completions = cmd.get_completions("", 0)
        assert len(completions) == 1
        assert hasattr(completions[0], "text")
        assert hasattr(completions[0], "description")


class DummyConsole:
    def __init__(self):
        self.messages = []

    def print(self, message, style=None):
        self.messages.append((message, style))


@pytest.fixture
def dummy_console():
    return DummyConsole()


@pytest.fixture
def dummy_process_response():
    return Mock()


def test_get_llm_client_grok(dummy_console, dummy_process_response):
    c = llm_client.get_llm_client("grok", dummy_console, dummy_process_response)
    assert isinstance(c, llm_client.GrokLLMClient)


def test_get_llm_client_gemini(dummy_console, dummy_process_response):
    c = llm_client.get_llm_client("gemini", dummy_console, dummy_process_response)
    assert isinstance(c, llm_client.GeminiLLMClient)


def test_get_llm_client_unsupported(dummy_console, dummy_process_response):
    with pytest.raises(ValueError):
        llm_client.get_llm_client("unknown", dummy_console, dummy_process_response)
