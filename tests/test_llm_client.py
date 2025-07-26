import pytest
from unittest.mock import Mock, patch
import os

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
        model="grok-beta"
    )
    
    with patch("xai_sdk.Client") as MockClient, patch("xai_sdk.chat.user"), patch("xai_sdk.chat.system"):
        mock_client_instance = Mock()
        mock_chat = Mock()
        mock_chat.sample.return_value.content = "{\"rule\":{}}"
        MockClient.return_value.chat.create.return_value = mock_chat
        
        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == "{\"rule\":{}}"
        assert result.model_used == "grok-beta"
        assert result.vendor == "grok"

def test_grok_generate_response_import_error(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch.dict("sys.modules", {"xai_sdk": None}):
        with pytest.raises(ImportError):
            c.generate_response(request)

def test_gemini_generate_response_success(dummy_console):
    c = llm_client.GeminiLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2+2?",
        api_key="key",
        model="gemini-1.5-pro"
    )
    
    with patch("google.generativeai.GenerativeModel") as MockModel, patch("google.generativeai.configure"):
        mock_model = Mock()
        mock_response = Mock()
        mock_response.text = "{\"rule\":{}}"
        mock_model.generate_content.return_value = mock_response
        MockModel.return_value = mock_model
        
        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == "{\"rule\":{}}"
        assert result.model_used == "gemini-1.5-pro"
        assert result.vendor == "gemini"

def test_gemini_generate_response_import_error(dummy_console):
    c = llm_client.GeminiLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch.dict("sys.modules", {"google.generativeai": None, "google.api_core.exceptions": None}):
        with pytest.raises(ImportError):
            c.generate_response(request)

def test_claude_generate_response_success(dummy_console):
    c = llm_client.ClaudeLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="You are a helpful assistant.",
        user_prompt="What is 2+2?",
        api_key="key",
        model="claude-3-5-sonnet-20241022"
    )
    
    with patch("anthropic.Anthropic") as MockAnthropic:
        mock_client = Mock()
        mock_response = Mock()
        mock_content = Mock()
        mock_content.text = "{\"rule\":{}}"
        mock_response.content = [mock_content]
        mock_client.messages.create.return_value = mock_response
        MockAnthropic.return_value = mock_client
        
        result = c.generate_response(request)
        assert isinstance(result, LLMResponse)
        assert result.content == "{\"rule\":{}}"
        assert result.model_used == "claude-3-5-sonnet-20241022"
        assert result.vendor == "claude"

def test_claude_generate_response_import_error(dummy_console):
    c = llm_client.ClaudeLLMClient(dummy_console)
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch.dict("sys.modules", {"anthropic": None}):
        with pytest.raises(ImportError):
            c.generate_response(request)

def test_generate_with_processing_with_processor(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    processor_called = False
    
    def test_processor(response: LLMResponse, kwargs):
        nonlocal processor_called
        processor_called = True
        assert isinstance(response, LLMResponse)
        assert response.content == "test response"
        assert kwargs.get('request') is not None
    
    c.response_processor = test_processor
    
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch("xai_sdk.Client") as MockClient, patch("xai_sdk.chat.user"), patch("xai_sdk.chat.system"):
        mock_client_instance = Mock()
        mock_chat = Mock()
        mock_chat.sample.return_value.content = "test response"
        MockClient.return_value.chat.create.return_value = mock_chat
        
        result = c.generate_with_processing(request)
        assert result is True
        assert processor_called

def test_generate_with_processing_without_processor(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch("xai_sdk.Client") as MockClient, patch("xai_sdk.chat.user"), patch("xai_sdk.chat.system"):
        mock_client_instance = Mock()
        mock_chat = Mock()
        mock_chat.sample.return_value.content = "test response"
        MockClient.return_value.chat.create.return_value = mock_chat
        
        result = c.generate_with_processing(request)
        assert result is True
        assert any("Generated Response" in msg[0] for msg in dummy_console.messages)

def test_generate_with_processing_error(dummy_console):
    c = llm_client.GrokLLMClient(dummy_console)
    
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch("xai_sdk.Client", side_effect=Exception("Test error")):
        result = c.generate_with_processing(request)
        assert result is False
        assert any("Error generating response" in msg[0] for msg in dummy_console.messages)

# Legacy DQPolicyLLMClient tests
def test_dq_policy_llm_client_system_prompt():
    client = llm_client.DQPolicyLLMClient(Mock(), Mock())
    prompt = client.get_system_prompt()
    assert "ERROR" in prompt or "You are an expert data quality policy extractor" in prompt

def test_dq_policy_llm_client_user_prompt():
    client = llm_client.DQPolicyLLMClient(Mock(), Mock())
    prompt = client.get_user_prompt("test text")
    assert "test text" in prompt

def test_dq_policy_llm_client_generate_with_grok(dummy_console):
    processor_called = False
    def test_processor(response: LLMResponse, uids):
        nonlocal processor_called
        processor_called = True
    
    client = llm_client.DQPolicyLLMClient(dummy_console, test_processor)
    mock_llm_config = Mock()
    mock_llm_config.apikey = "key"
    mock_llm_config.get_model.return_value = "grok-beta"
    
    request = LLMRequest(
        system_prompt="test",
        user_prompt="test",
        api_key="key"
    )
    
    with patch("xai_sdk.Client") as MockClient, patch("xai_sdk.chat.user"), patch("xai_sdk.chat.system"):
        mock_client_instance = Mock()
        mock_chat = Mock()
        mock_chat.sample.return_value.content = "{\"rule\":{}}"
        MockClient.return_value.chat.create.return_value = mock_chat
        
        result = client.generate_with_grok(request, mock_llm_config, ["1"])
        assert result is True
        assert processor_called 