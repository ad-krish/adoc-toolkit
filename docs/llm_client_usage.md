# LLM Client Usage Guide

## Overview

The ADOC Toolkit provides an abstract LLM client system that allows any command to use Large Language Models (LLMs) without being tied to specific vendors or use cases. This system is designed to be flexible, extensible, and reusable across different commands.

## Architecture

### Core Components

1. **BaseLLMClient**: Abstract base class that defines the interface for all LLM clients
2. **Vendor-Specific Clients**: Concrete implementations for each LLM vendor (Grok, Gemini, Claude)
3. **Factory Function**: `get_llm_client()` that creates the appropriate client based on vendor
4. **Response Processing**: Optional callback system for custom response handling

### Key Features

- **Vendor Agnostic**: Same interface for all LLM vendors
- **Extensible**: Easy to add new LLM vendors
- **Flexible**: Supports custom response processing
- **Error Handling**: Comprehensive error handling for API failures and missing dependencies

## Basic Usage

### Simple Example

```python
from adoc_toolkit.llm.client import get_llm_client

# Create a client for any vendor
llm_client = get_llm_client("grok", console, response_processor=None)

# Generate a response
response = llm_client.generate_response(
    system_prompt="You are a helpful assistant.",
    user_prompt="What is 2+2?",
    api_key="your-api-key",
    model="grok-beta"
)

print(response)
```

### With Response Processing

```python
def my_response_processor(response: str, kwargs: dict):
    """Custom response processor."""
    print(f"Received response: {response}")
    print(f"With parameters: {kwargs}")

# Create client with custom processor
llm_client = get_llm_client("gemini", console, my_response_processor)

# Generate and process response
llm_client.generate_with_processing(
    system_prompt="You are a data analyst.",
    user_prompt="Analyze this dataset: [data]",
    api_key="your-api-key",
    model="gemini-1.5-pro"
)
```

## Creating Custom Commands

### Example: Text Summarization Command

```python
from adoc_toolkit.cli.commands.base import Command
from adoc_toolkit.llm.client import get_llm_client
from adoc_toolkit.config import get_config_manager

class SummarizeCommand(Command):
    """Command to summarize text using LLM."""
    
    @property
    def name(self) -> str:
        return "summarize"
    
    @property
    def description(self) -> str:
        return "Summarize text using LLM"
    
    def execute(self, args: list[str]) -> bool:
        if not args:
            self.console.print("Error: Text to summarize is required", style="red")
            return True
        
        text = " ".join(args)
        return self._summarize_text(text)
    
    def _summarize_text(self, text: str) -> bool:
        try:
            # Get LLM configuration
            config_manager = get_config_manager()
            llm_config = config_manager._config.llm
            
            if not llm_config.apikey:
                self.console.print("Error: LLM API key not configured", style="red")
                return True
            
            # Create response processor
            def response_processor(response: str, kwargs):
                self.console.print("\n📝 Summary:", style="green")
                self.console.print(response, style="white")
            
            # Get LLM client
            llm_client = get_llm_client(llm_config.vendor.value, self.console, response_processor)
            
            # Define prompts
            system_prompt = "You are a text summarization expert. Provide concise, accurate summaries."
            user_prompt = f"Summarize the following text:\n\n{text}"
            
            # Generate summary
            return llm_client.generate_with_processing(
                system_prompt,
                user_prompt,
                api_key=llm_config.apikey,
                model=llm_config.get_model()
            )
            
        except Exception as e:
            self.console.print(f"Error: {e}", style="red")
            return True
```

### Example: Code Review Command

```python
class CodeReviewCommand(Command):
    """Command to review code using LLM."""
    
    @property
    def name(self) -> str:
        return "code-review"
    
    @property
    def description(self) -> str:
        return "Review code using LLM"
    
    def execute(self, args: list[str]) -> bool:
        if len(args) < 1:
            self.console.print("Error: Code file path is required", style="red")
            return True
        
        file_path = args[0]
        return self._review_code(file_path)
    
    def _review_code(self, file_path: str) -> bool:
        try:
            # Read code file
            with open(file_path, 'r') as f:
                code = f.read()
            
            # Get LLM configuration
            config_manager = get_config_manager()
            llm_config = config_manager._config.llm
            
            # Create response processor
            def response_processor(response: str, kwargs):
                self.console.print("\n🔍 Code Review:", style="green")
                self.console.print(response, style="white")
            
            # Get LLM client
            llm_client = get_llm_client(llm_config.vendor.value, self.console, response_processor)
            
            # Define prompts
            system_prompt = """You are a senior software engineer conducting code reviews. 
            Provide constructive feedback on code quality, best practices, security, and performance."""
            
            user_prompt = f"Review the following code:\n\n```\n{code}\n```"
            
            # Generate review
            return llm_client.generate_with_processing(
                system_prompt,
                user_prompt,
                api_key=llm_config.apikey,
                model=llm_config.get_model()
            )
            
        except Exception as e:
            self.console.print(f"Error: {e}", style="red")
            return True
```

## Adding New LLM Vendors

To add support for a new LLM vendor:

1. **Create a new client class**:

```python
class NewVendorLLMClient(BaseLLMClient):
    """New vendor LLM client implementation."""
    
    def generate_response(self, system_prompt: str, user_prompt: str, **kwargs) -> str:
        try:
            # Import vendor-specific library
            import vendor_library
            
            # Extract parameters
            api_key = kwargs.get('api_key')
            model = kwargs.get('model', 'default-model')
            
            # Initialize client
            client = vendor_library.Client(api_key=api_key)
            
            # Generate response
            response = client.generate(
                system=system_prompt,
                user=user_prompt,
                model=model
            )
            
            return response.text
            
        except ImportError:
            raise ImportError("vendor_library not installed. Please install it with 'uv add vendor_library'")
        except Exception as e:
            raise Exception(f"Error generating response with NewVendor: {e}")
```

2. **Update the factory function**:

```python
def get_llm_client(vendor: str, console, response_processor=None) -> BaseLLMClient:
    vendor = vendor.lower()
    if vendor == "grok":
        return GrokLLMClient(console, response_processor)
    elif vendor == "gemini":
        return GeminiLLMClient(console, response_processor)
    elif vendor == "claude":
        return ClaudeLLMClient(console, response_processor)
    elif vendor == "newvendor":  # Add new vendor
        return NewVendorLLMClient(console, response_processor)
    else:
        raise ValueError(f"Unsupported LLM vendor: {vendor}")
```

3. **Add to LLM configuration**:

```python
class LLMVendor(str, Enum):
    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"
    NEWVENDOR = "newvendor"  # Add new vendor
```

## Best Practices

### 1. Error Handling

Always handle potential errors in your response processor:

```python
def safe_response_processor(response: str, kwargs):
    try:
        # Process response
        processed = process_response(response)
        console.print(processed, style="green")
    except Exception as e:
        console.print(f"Error processing response: {e}", style="red")
```

### 2. Configuration Validation

Validate LLM configuration before using:

```python
def validate_llm_config():
    config_manager = get_config_manager()
    llm_config = config_manager._config.llm
    
    if not llm_config.apikey:
        raise ValueError("LLM API key not configured")
    
    if not llm_config.vendor:
        raise ValueError("LLM vendor not configured")
    
    return llm_config
```

### 3. Prompt Engineering

Store prompts in external files for maintainability:

```python
def load_prompt(prompt_file: str) -> str:
    prompt_path = os.path.join(os.path.dirname(__file__), f'../../config/prompts/{prompt_file}')
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        return f"[ERROR: Prompt file not found: {prompt_file}]"
```

### 4. Testing

Test your LLM client usage with proper mocking:

```python
@patch('adoc_toolkit.llm.client.get_llm_client')
def test_my_command(mock_get_llm_client):
    # Mock LLM client
    mock_client = Mock()
    mock_client.generate_with_processing.return_value = True
    mock_get_llm_client.return_value = mock_client
    
    # Test command
    result = my_command.execute(["test input"])
    assert result is True
    mock_client.generate_with_processing.assert_called_once()
```

## Available Vendors

Currently supported LLM vendors:

- **Grok**: `grok-beta`, `grok-2`
- **Gemini**: `gemini-1.5-pro`, `gemini-1.5-flash`, `gemini-1.0-pro`
- **Claude**: `claude-3-5-sonnet-20241022`, `claude-3-5-haiku-20241022`, `claude-3-opus-20240229`

## Configuration

Configure LLM settings using the `set-config` command:

```bash
# Set vendor
set-config llm.vendor grok

# Set API key
set-config llm.apikey your-api-key

# Set model (optional)
set-config llm.model grok-beta
```

The abstract LLM client system provides a powerful foundation for building AI-powered commands in the ADOC Toolkit while maintaining flexibility and extensibility. 