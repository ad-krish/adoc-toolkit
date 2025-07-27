import pytest
from unittest.mock import Mock, patch
import os
from typing import Dict, Any

from adoc_toolkit.llm import client as llm_client
from adoc_toolkit.models import LLMRequest, LLMResponse


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


def test_get_llm_client_claude(dummy_console, dummy_process_response):
    c = llm_client.get_llm_client("claude", dummy_console, dummy_process_response)
    assert isinstance(c, llm_client.ClaudeLLMClient)


def test_get_llm_client_chatgpt(dummy_console, dummy_process_response):
    c = llm_client.get_llm_client("chatgpt", dummy_console, dummy_process_response)
    assert isinstance(c, llm_client.ChatGPTLLMClient)


def test_get_llm_client_unsupported(dummy_console, dummy_process_response):
    with pytest.raises(ValueError):
        llm_client.get_llm_client("unknown", dummy_console, dummy_process_response)


def test_grok_generate_response_success(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2+2?",
        api_key="key",
        model="grok-beta",
    )

    # Mock the entire _generate_grok_response method
    with patch.object(c, "_generate_grok_response") as mock_generate:
        mock_response = LLMResponse(
            content='{"rule":{}}', model_used="grok-beta", vendor="grok", metadata={}
        )
        mock_generate.return_value = mock_response

        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == '{"rule":{}}'
        assert result.model_used == "grok-beta"
        assert result.vendor == "grok"


def test_grok_generate_response_import_error(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    # Mock the _generate_grok_response method to raise ImportError
    with patch.object(
        c,
        "_generate_grok_response",
        side_effect=ImportError("No module named 'xai_sdk'"),
    ):
        with pytest.raises(ImportError):
            c.generate_response(request)


def test_gemini_generate_response_success(dummy_console):
    c = llm_client.GeminiLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2+2?",
        api_key="key",
        model="gemini-1.5-pro",
    )

    # Mock the entire _generate_gemini_response method
    with patch.object(c, "_generate_gemini_response") as mock_generate:
        mock_response = LLMResponse(
            content='{"rule":{}}',
            model_used="gemini-1.5-pro",
            vendor="gemini",
            metadata={},
        )
        mock_generate.return_value = mock_response

        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == '{"rule":{}}'
        assert result.model_used == "gemini-1.5-pro"
        assert result.vendor == "gemini"


def test_gemini_generate_response_import_error(dummy_console):
    c = llm_client.GeminiLLMClient(dummy_console)
    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    # Mock the _generate_gemini_response method to raise ImportError
    with patch.object(
        c,
        "_generate_gemini_response",
        side_effect=ImportError("No module named 'google.generativeai'"),
    ):
        with pytest.raises(ImportError):
            c.generate_response(request)


def test_claude_generate_response_success(dummy_console):
    c = llm_client.ClaudeLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2+2?",
        api_key="key",
        model="claude-3-5-sonnet-20241022",
    )

    # Mock the entire _generate_claude_response method
    with patch.object(c, "_generate_claude_response") as mock_generate:
        mock_response = LLMResponse(
            content='{"rule":{}}',
            model_used="claude-3-5-sonnet-20241022",
            vendor="claude",
            metadata={},
        )
        mock_generate.return_value = mock_response

        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == '{"rule":{}}'
        assert result.model_used == "claude-3-5-sonnet-20241022"
        assert result.vendor == "claude"


def test_claude_generate_response_import_error(dummy_console):
    c = llm_client.ClaudeLLMClient(dummy_console)
    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    # Mock the _generate_claude_response method to raise ImportError
    with patch.object(
        c,
        "_generate_claude_response",
        side_effect=ImportError("No module named 'anthropic'"),
    ):
        with pytest.raises(ImportError):
            c.generate_response(request)


def test_generate_with_processing_with_processor(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    processor_called = False

    def test_processor(response: LLMResponse, kwargs: Dict[str, Any]):
        nonlocal processor_called
        processor_called = True
        assert isinstance(response, LLMResponse)
        assert response.content == "test response"
        assert "request" in kwargs
        assert isinstance(kwargs["request"], LLMRequest)

    c.response_processor = test_processor

    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    # Mock the generate_response method to return a proper LLMResponse
    with patch.object(c, "generate_response") as mock_generate:
        mock_response = LLMResponse(
            content="test response", model_used="grok-beta", vendor="grok", metadata={}
        )
        mock_generate.return_value = mock_response

        result = c.generate_with_processing(request)
        assert result is True
        assert processor_called


def test_generate_with_processing_without_processor(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)

    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    # Mock the generate_response method to return a proper LLMResponse
    with patch.object(c, "generate_response") as mock_generate:
        mock_response = LLMResponse(
            content="test response", model_used="grok-beta", vendor="grok", metadata={}
        )
        mock_generate.return_value = mock_response

        result = c.generate_with_processing(request)
        assert result is True
        # Check that the response was printed to console
        assert any("test response" in str(msg) for msg in dummy_console.messages)


def test_generate_with_processing_error(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)

    request = LLMRequest(system_prompt="test", user_prompt="test", api_key="key")

    with patch("xai_sdk.Client", side_effect=Exception("Test error")):
        result = c.generate_with_processing(request)
        assert result is False
        assert any(
            "Error generating response" in msg[0] for msg in dummy_console.messages
        )


# Legacy DQPolicyLLMClient tests
def test_dq_policy_llm_client_system_prompt():
    client = llm_client.DQPolicyLLMClient(Mock(), Mock(), Mock())
    prompt = client.get_system_prompt()
    assert (
        "ERROR" in prompt or "You are an expert data quality policy extractor" in prompt
    )


def test_dq_policy_llm_client_user_prompt():
    client = llm_client.DQPolicyLLMClient(Mock(), Mock(), Mock())
    prompt = client.get_user_prompt("test text")
    assert "test text" in prompt


def test_dq_policy_llm_client_generate_with_grok(dummy_console):
    processor_called = False

    def test_processor(response: LLMResponse, uids):
        nonlocal processor_called
        processor_called = True

    # Create a proper mock for the llm_client
    mock_llm_client = Mock()

    # Mock generate_with_processing to actually call the response processor
    def mock_generate_with_processing(request):
        # Simulate what the real method does - call the response processor
        if mock_llm_client.response_processor:
            mock_response = Mock()
            mock_response.content = "test response"
            mock_llm_client.response_processor(mock_response, {})
        return True

    mock_llm_client.generate_with_processing.side_effect = mock_generate_with_processing

    client = llm_client.DQPolicyLLMClient(
        mock_llm_client, dummy_console, test_processor
    )

    # Test the vendor-agnostic generate_policy method
    result = client.generate_policy("test text", "test_key", "grok-beta", ["1"])
    assert result is True
    assert processor_called
