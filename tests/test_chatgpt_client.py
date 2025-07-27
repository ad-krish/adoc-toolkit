"""Tests for ChatGPT LLM client."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from adoc_toolkit.llm.client import ChatGPTLLMClient
from adoc_toolkit.models import LLMRequest, LLMResponse, ChatGPTRequest


class TestChatGPTLLMClient:
    """Test ChatGPT LLM client functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Mock()
        self.client = ChatGPTLLMClient(self.console)

    def test_client_initialization(self):
        """Test ChatGPT client initialization."""
        assert isinstance(self.client, ChatGPTLLMClient)
        assert self.client.console == self.console

    def test_generate_response_method_exists(self):
        """Test that generate_response method exists."""
        assert hasattr(self.client, "generate_response")
        assert callable(self.client.generate_response)

    def test_create_chatgpt_messages(self):
        """Test ChatGPT message creation."""
        request = ChatGPTRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello, how are you?",
            api_key="test-key",
            model="gpt-4o",
        )

        messages = self.client._create_chatgpt_messages(request)

        expected_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Hello, how are you?"},
        ]

        assert messages == expected_messages

    @patch("builtins.__import__")
    def test_generate_chatgpt_response_success(self, mock_import):
        """Test successful ChatGPT response generation."""
        # Mock the openai module
        mock_openai = Mock()
        mock_openai.ChatCompletion.create.return_value = Mock()
        mock_openai.ChatCompletion.create.return_value.choices = [Mock()]
        mock_openai.ChatCompletion.create.return_value.choices[0].message = Mock()
        mock_openai.ChatCompletion.create.return_value.choices[
            0
        ].message.content = "I'm doing well, thank you!"
        mock_import.return_value = mock_openai

        request = ChatGPTRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello, how are you?",
            api_key="test-key",
            model="gpt-4o",
        )

        response = self.client.generate_response(request)

        # Verify OpenAI was called correctly
        mock_openai.ChatCompletion.create.assert_called_once()
        call_args = mock_openai.ChatCompletion.create.call_args
        assert call_args[1]["model"] == "gpt-4o"
        assert call_args[1]["max_tokens"] == 4000
        assert call_args[1]["temperature"] == 0.7

        # Verify response
        assert isinstance(response, LLMResponse)
        assert response.content == "I'm doing well, thank you!"
        assert response.model_used == "gpt-4o"
        assert response.vendor == "chatgpt"

    @patch("builtins.__import__")
    def test_generate_chatgpt_response_with_custom_params(self, mock_import):
        """Test ChatGPT response generation with custom parameters."""
        # Mock the openai module
        mock_openai = Mock()
        mock_openai.ChatCompletion.create.return_value = Mock()
        mock_openai.ChatCompletion.create.return_value.choices = [Mock()]
        mock_openai.ChatCompletion.create.return_value.choices[0].message = Mock()
        mock_openai.ChatCompletion.create.return_value.choices[
            0
        ].message.content = "Custom response"
        mock_import.return_value = mock_openai

        request = ChatGPTRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello, how are you?",
            api_key="test-key",
            model="gpt-4o",
            max_tokens=1000,
            temperature=0.5,
            additional_params={"top_p": 0.9},
        )

        response = self.client.generate_response(request)

        # Verify OpenAI was called with custom parameters
        call_args = mock_openai.ChatCompletion.create.call_args
        assert call_args[1]["max_tokens"] == 1000
        assert call_args[1]["temperature"] == 0.5
        assert call_args[1]["top_p"] == 0.9

    @patch("builtins.__import__")
    def test_generate_chatgpt_response_api_error(self, mock_import):
        """Test ChatGPT response generation with API error."""
        # Mock the openai module
        mock_openai = Mock()
        mock_openai.ChatCompletion.create.side_effect = Exception("API Error")
        mock_import.return_value = mock_openai

        request = ChatGPTRequest(
            system_prompt="You are a helpful assistant.",
            user_prompt="Hello, how are you?",
            api_key="test-key",
            model="gpt-4o",
        )

        # The with_error_handling decorator returns (None, error_message) on exception
        result = self.client._generate_chatgpt_response(request)
        assert result[0] is None  # First element of tuple should be None
        assert (
            "ChatGPT API error" in result[1]
        )  # Second element should contain error message

    def test_chatgpt_request_validation(self):
        """Test ChatGPT request validation."""
        # Test valid model
        request = ChatGPTRequest(
            system_prompt="Test", user_prompt="Test", api_key="test-key", model="gpt-4o"
        )

        assert request.model == "gpt-4o"
        assert request.max_tokens == 4000
        assert request.temperature == 0.7

        # Test invalid model
        with pytest.raises(ValueError) as exc_info:
            ChatGPTRequest(
                system_prompt="Test",
                user_prompt="Test",
                api_key="test-key",
                model="invalid-model",
            )
        assert "Invalid ChatGPT model" in str(exc_info.value)

    def test_chatgpt_request_defaults(self):
        """Test ChatGPT request default values."""
        request = ChatGPTRequest(
            system_prompt="Test", user_prompt="Test", api_key="test-key"
        )

        assert request.model == "gpt-4o"  # Default model
        assert request.max_tokens == 4000  # Default max_tokens
        assert request.temperature == 0.7  # Default temperature

    def test_extract_content_function(self):
        """Test content extraction from OpenAI response."""
        from adoc_toolkit.llm.client import extract_content

        # Test OpenAI response format
        mock_response = Mock()
        mock_response.choices = [Mock()]
        mock_response.choices[0].message = Mock()
        mock_response.choices[0].message.content = "Test content"

        content = extract_content(mock_response)
        assert content == "Test content"

        # Test fallback to string conversion
        mock_response.choices = []
        content = extract_content(mock_response)
        assert "Mock" in str(
            content
        )  # Should contain Mock object string representation


class TestChatGPTRequest:
    """Test ChatGPT request model."""

    def test_valid_models(self):
        """Test that all valid ChatGPT models are accepted."""
        valid_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]

        for model in valid_models:
            request = ChatGPTRequest(
                system_prompt="Test",
                user_prompt="Test",
                api_key="test-key",
                model=model,
            )
            assert request.model == model

    def test_invalid_model(self):
        """Test that invalid models are rejected."""
        with pytest.raises(ValueError) as exc_info:
            ChatGPTRequest(
                system_prompt="Test",
                user_prompt="Test",
                api_key="test-key",
                model="invalid-model",
            )
        assert "Invalid ChatGPT model" in str(exc_info.value)

    def test_default_values(self):
        """Test default values for ChatGPT request."""
        request = ChatGPTRequest(
            system_prompt="Test", user_prompt="Test", api_key="test-key"
        )

        assert request.model == "gpt-4o"
        assert request.max_tokens == 4000
        assert request.temperature == 0.7

    def test_custom_values(self):
        """Test custom values for ChatGPT request."""
        request = ChatGPTRequest(
            system_prompt="Test",
            user_prompt="Test",
            api_key="test-key",
            model="gpt-3.5-turbo",
            max_tokens=2000,
            temperature=0.3,
        )

        assert request.model == "gpt-3.5-turbo"
        assert request.max_tokens == 2000
        assert request.temperature == 0.3
