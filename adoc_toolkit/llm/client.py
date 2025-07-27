import os
import time
from typing import Callable, Optional, Dict, Any, Union, Tuple
from abc import ABC, abstractmethod
from functools import wraps, partial
from operator import attrgetter
import logging

from ..models import (
    LLMRequest,
    LLMResponse,
    GrokRequest,
    GeminiRequest,
    ClaudeRequest,
    ChatGPTRequest,
    LLMClientConfig,
)

# Type aliases for functional programming
Console = Any
ProcessingResult = Tuple[bool, Optional[str]]
ResponseProcessor = Callable[[LLMResponse, Dict[str, Any]], None]

def with_error_handling(func: Callable) -> Callable:
    """Decorator for functional error handling."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            return None, str(e)
    return wrapper

def compose(*functions: Callable) -> Callable:
    """Function composition utility."""
    def inner(arg):
        result = arg
        for f in reversed(functions):
            result = f(result)
        return result
    return inner

def safe_get(container: Any, key: str, default: Any = None) -> Any:
    """Safely get attribute or key with default value."""
    try:
        return getattr(container, key, default) if hasattr(container, key) else container.get(key, default)
    except (AttributeError, KeyError, TypeError):
        return default

def extract_content(response: Any) -> str:
    """Pure function to extract content from various response types."""
    # Handle OpenAI response format
    if hasattr(response, 'choices') and response.choices:
        choice = response.choices[0]
        if hasattr(choice, 'message') and hasattr(choice.message, 'content'):
            return choice.message.content
        elif hasattr(choice, 'text'):
            return choice.text
        else:
            return str(choice)
    
    # Handle Claude response format
    if hasattr(response, 'content'):
        if isinstance(response.content, list) and response.content:
            return response.content[0].text if hasattr(response.content[0], 'text') else str(response.content[0])
        elif hasattr(response.content, 'text'):
            return response.content.text
        else:
            return str(response.content)
    
    # Handle other response formats
    elif hasattr(response, 'text'):
        return response.text
    else:
        return str(response)

def create_llm_response(content: str, model: str, vendor: str, metadata: Dict[str, Any]) -> LLMResponse:
    """Pure function to create LLMResponse."""
    return LLMResponse(
        content=content,
        model_used=model,
        vendor=vendor,
        metadata=metadata
    )

def calculate_processing_time(start_time: float) -> float:
    """Pure function to calculate processing time."""
    return time.time() - start_time

def print_status_message(console: Console, message: str, style: str = "blue") -> None:
    """Pure function to print status message."""
    console.print(message, style=style)

def print_error_message(console: Console, message: str) -> None:
    """Pure function to print error message."""
    console.print(message, style="red")

def print_success_response(console: Console, content: str) -> None:
    """Pure function to print success response."""
    console.print("\n✅ Generated Response:", style="green")
    console.print(content, style="white")

def process_response_with_processor(
    response: LLMResponse, 
    processor: Optional[ResponseProcessor], 
    request: LLMRequest
) -> None:
    """Pure function to process response with optional processor."""
    if processor:
        processor(response, {"request": request})
    else:
        return None

def validate_request(request: LLMRequest, request_type: type) -> Any:
    """Pure function to validate and convert request."""
    return request_type.model_validate(request.model_dump())

def create_vendor_client_map() -> Dict[str, Callable]:
    """Pure function to create vendor client mapping."""
    return {
        "grok": GrokLLMClient,
        "gemini": GeminiLLMClient,
        "claude": ClaudeLLMClient,
        "chatgpt": ChatGPTLLMClient
    }

def get_client_class(vendor: str, client_map: Dict[str, Callable]) -> Callable:
    """Pure function to get client class from vendor."""
    vendor_lower = vendor.lower()
    if vendor_lower not in client_map:
        raise ValueError(f"Unsupported LLM vendor: {vendor}")
    return client_map[vendor_lower]

class BaseLLMClient(ABC):
    """Base class for LLM clients that can be used with any command."""
    
    def __init__(self, console: Console, response_processor: Optional[ResponseProcessor] = None):
        self.console = console
        self.response_processor = response_processor

    @staticmethod
    def print_status(console: Console, message: str, style: str = "blue") -> None:
        """Print status message to console."""
        print_status_message(console, message, style)

    @staticmethod
    def print_error(console: Console, message: str) -> None:
        """Print error message to console."""
        print_error_message(console, message)

    @abstractmethod
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        """Generate response from LLM with given request."""
        pass

    def generate_with_processing(self, request: LLMRequest) -> bool:
        """Generate response and process it if processor is available."""
        start_time = time.time()
        
        try:
            response = self.generate_response(request)
            
            # Add processing time
            response = self._add_processing_time(response, start_time)
            
            # Process response
            self._process_response(response, request)
            
            return True
        except Exception as e:
            self.print_error(self.console, f"Error generating response: {e}")
            return False

    def _add_processing_time(self, response: LLMResponse, start_time: float) -> LLMResponse:
        """Add processing time to response."""
        response.processing_time = calculate_processing_time(start_time)
        return response

    def _process_response(self, response: LLMResponse, request: LLMRequest) -> None:
        """Process response with processor or print to console."""
        if self.response_processor:
            process_response_with_processor(response, self.response_processor, request)
        else:
            print_success_response(self.console, response.content)

class GrokLLMClient(BaseLLMClient):
    """Grok LLM client implementation."""
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        return self._generate_grok_response(request)
    
    @with_error_handling
    def _generate_grok_response(self, request: LLMRequest) -> LLMResponse:
        """Pure function to generate Grok response."""
        from xai_sdk import Client
        from xai_sdk.chat import user, system

        # Validate request using pure function
        grok_request = validate_request(request, GrokRequest)
        
        # Set environment variable
        os.environ["XAI_API_KEY"] = grok_request.api_key
        
        # Create client and chat
        client = Client(api_key=grok_request.api_key, timeout=grok_request.timeout)
        chat = client.chat.create(model=grok_request.model)

        # Print status
        print_status_message(self.console, "Generating response with Grok...")
        
        # Compose chat operations
        chat_operations = compose(
            lambda c: c.append(system(grok_request.system_prompt)),
            lambda c: c.append(user(grok_request.user_prompt)),
            lambda c: c.sample()
        )
        
        response = chat_operations(chat)
        
        # Create response using pure function
        return create_llm_response(
            content=response.content,
            model=grok_request.model,
            vendor="grok",
            metadata={"timeout": grok_request.timeout, "temperature": grok_request.temperature or 0.2}
        )

class GeminiLLMClient(BaseLLMClient):
    """Gemini LLM client implementation."""
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        return self._generate_gemini_response(request)
    
    @with_error_handling
    def _generate_gemini_response(self, request: LLMRequest) -> LLMResponse:
        """Pure function to generate Gemini response."""
        import google.generativeai as genai
        import google.api_core.exceptions

        # Validate request using pure function
        gemini_request = validate_request(request, GeminiRequest)
        
        # Configure and create model
        genai.configure(api_key=gemini_request.api_key)
        model = genai.GenerativeModel(gemini_request.model)

        print_status_message(self.console, "Generating response with Gemini...")
        
        # Create content messages using pure function
        messages = self._create_gemini_messages(gemini_request)
        
        try:
            response = model.generate_content(
                messages,
                generation_config={
                    "temperature": gemini_request.temperature or 0.2
                }
            )
        except google.api_core.exceptions.GoogleAPIError as e:
            raise Exception(f"Gemini API error: {e}")
        except Exception as e:
            raise Exception(f"Error calling Gemini: {e}")

        # Extract content using pure function
        content = extract_content(response)
        
        # Create response using pure function
        return create_llm_response(
            content=content,
            model=gemini_request.model,
            vendor="gemini",
            metadata={**gemini_request.additional_params, "temperature": gemini_request.temperature or 0.2}
        )
    
    def _create_gemini_messages(self, gemini_request: GeminiRequest) -> list:
        """Pure function to create Gemini messages."""
        # Gemini doesn't support system roles, so combine system prompt with user prompt
        combined_prompt = f"{gemini_request.system_prompt}\n\n{gemini_request.user_prompt}"
        return [
            {"role": "user", "parts": [combined_prompt]}
        ]

class ClaudeLLMClient(BaseLLMClient):
    """Claude LLM client implementation."""
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        return self._generate_claude_response(request)
    
    @with_error_handling
    def _generate_claude_response(self, request: LLMRequest) -> LLMResponse:
        """Pure function to generate Claude response."""
        import anthropic

        # Validate request using pure function
        claude_request = validate_request(request, ClaudeRequest)

        # Create client
        client = anthropic.Anthropic(api_key=claude_request.api_key)

        print_status_message(self.console, "Generating response with Claude...")
        
        # Create messages using pure function
        messages = self._create_claude_messages(claude_request)
        
        try:
            response = client.messages.create(
                model=claude_request.model,
                max_tokens=claude_request.max_tokens,
                system=claude_request.system_prompt,
                messages=messages,
                temperature=claude_request.temperature or 0.2
            )
        except Exception as e:
            raise Exception(f"Claude API error: {e}")

        # Extract content using pure function
        content = extract_content(response)
        
        # Create response using pure function
        return create_llm_response(
            content=content,
            model=claude_request.model,
            vendor="claude",
            metadata={"max_tokens": claude_request.max_tokens, "temperature": claude_request.temperature or 0.2}
        )
    
    def _create_claude_messages(self, claude_request: ClaudeRequest) -> list:
        """Pure function to create Claude messages."""
        return [
            {"role": "user", "content": claude_request.user_prompt}
        ]

class ChatGPTLLMClient(BaseLLMClient):
    """ChatGPT LLM client implementation."""
    
    def generate_response(self, request: LLMRequest) -> LLMResponse:
        return self._generate_chatgpt_response(request)
    
    @with_error_handling
    def _generate_chatgpt_response(self, request: LLMRequest) -> LLMResponse:
        """Pure function to generate ChatGPT response."""
        import openai

        # Validate request using pure function
        chatgpt_request = validate_request(request, ChatGPTRequest)

        # Configure OpenAI client
        openai.api_key = chatgpt_request.api_key

        print_status_message(self.console, "Generating response with ChatGPT...")
        
        # Create messages using pure function
        messages = self._create_chatgpt_messages(chatgpt_request)
        
        try:
            response = openai.ChatCompletion.create(
                model=chatgpt_request.model,
                messages=messages,
                max_tokens=chatgpt_request.max_tokens,
                temperature=chatgpt_request.temperature,
                **chatgpt_request.additional_params
            )
        except Exception as e:
            raise Exception(f"ChatGPT API error: {e}")

        # Extract content using pure function
        content = extract_content(response)
        
        # Create response using pure function
        return create_llm_response(
            content=content,
            model=chatgpt_request.model,
            vendor="chatgpt",
            metadata={
                "max_tokens": chatgpt_request.max_tokens,
                "temperature": chatgpt_request.temperature,
                **chatgpt_request.additional_params
            }
        )
    
    def _create_chatgpt_messages(self, chatgpt_request: ChatGPTRequest) -> list:
        """Pure function to create ChatGPT messages."""
        return [
            {"role": "system", "content": chatgpt_request.system_prompt},
            {"role": "user", "content": chatgpt_request.user_prompt}
        ]

def get_llm_client(vendor: str, console: Console, response_processor: Optional[ResponseProcessor] = None) -> BaseLLMClient:
    """Get LLM client for the specified vendor."""
    client_map = create_vendor_client_map()
    client_class = get_client_class(vendor, client_map)
    return client_class(console, response_processor)

# Import DQPolicyLLMClient for backward compatibility
from ..cli.commands.dq_policy_llm_client import DQPolicyLLMClient 