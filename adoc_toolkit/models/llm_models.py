"""LLM-related Pydantic models."""

from typing import Optional, Dict, Any, List
from pydantic import BaseModel, Field, field_validator


class LLMRequest(BaseModel):
    """LLM request model."""

    system_prompt: str = Field(description="System prompt for the LLM")
    user_prompt: str = Field(description="User prompt for the LLM")
    api_key: str = Field(description="API key for the LLM vendor")
    model: Optional[str] = Field(default=None, description="Model name to use")
    max_tokens: Optional[int] = Field(
        default=None, description="Maximum tokens for response"
    )
    temperature: Optional[float] = Field(
        default=None, description="Temperature for response generation"
    )
    additional_params: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional vendor-specific parameters"
    )


class LLMResponse(BaseModel):
    """LLM response model."""

    content: str = Field(description="Response content from LLM")
    model_used: str = Field(description="Model that was used for generation")
    vendor: str = Field(description="LLM vendor that was used")
    tokens_used: Optional[int] = Field(
        default=None, description="Number of tokens used"
    )
    processing_time: Optional[float] = Field(
        default=None, description="Processing time in seconds"
    )
    metadata: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional response metadata"
    )


class GrokRequest(LLMRequest):
    """Grok-specific request model."""

    timeout: int = Field(default=3600, description="Request timeout in seconds")

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate Grok model."""
        if v and v not in ["grok-beta", "grok-2"]:
            raise ValueError(f"Invalid Grok model: {v}")
        return v or "grok-beta"


class GeminiRequest(LLMRequest):
    """Gemini-specific request model."""

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate Gemini model."""
        valid_models = ["gemini-1.5-pro", "gemini-1.5-flash", "gemini-1.0-pro"]
        if v and v not in valid_models:
            raise ValueError(f"Invalid Gemini model: {v}")
        return v or "gemini-1.5-pro"


class ClaudeRequest(LLMRequest):
    """Claude-specific request model."""

    max_tokens: int = Field(
        default=4000, description="Maximum tokens for Claude response"
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: Optional[str]) -> Optional[str]:
        """Validate Claude model."""
        valid_models = [
            "claude-3-5-sonnet-20241022",
            "claude-3-5-haiku-20241022",
            "claude-3-opus-20240229",
            "claude-3-sonnet-20240229",
        ]
        if v and v not in valid_models:
            raise ValueError(f"Invalid Claude model: {v}")
        return v or "claude-3-5-sonnet-20241022"


class ChatGPTRequest(LLMRequest):
    """ChatGPT-specific request model."""

    model: str = Field(default="gpt-4o", description="ChatGPT model to use")
    max_tokens: int = Field(
        default=4000, description="Maximum tokens for ChatGPT response"
    )
    temperature: float = Field(
        default=0.7, description="Temperature for ChatGPT response generation"
    )

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str) -> str:
        """Validate ChatGPT model."""
        valid_models = [
            "gpt-4o",
            "gpt-4o-mini",
            "gpt-4-turbo",
            "gpt-4",
            "gpt-3.5-turbo",
        ]
        if v not in valid_models:
            raise ValueError(f"Invalid ChatGPT model: {v}")
        return v


class LLMClientConfig(BaseModel):
    """Configuration for LLM client."""

    vendor: str = Field(description="LLM vendor name")
    api_key: str = Field(description="API key for the vendor")
    model: Optional[str] = Field(default=None, description="Default model to use")
    timeout: Optional[int] = Field(default=None, description="Request timeout")
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    additional_config: Optional[Dict[str, Any]] = Field(
        default_factory=dict, description="Additional vendor-specific configuration"
    )


class PromptConfig(BaseModel):
    """Configuration for prompt management."""

    system_prompt_file: Optional[str] = Field(
        default=None, description="Path to system prompt file"
    )
    system_prompt_text: Optional[str] = Field(
        default=None, description="System prompt text"
    )
    user_prompt_template: Optional[str] = Field(
        default=None, description="User prompt template"
    )

    @field_validator("system_prompt_file", "system_prompt_text")
    @classmethod
    def validate_prompt_source(cls, v: Optional[str], info) -> Optional[str]:
        """Ensure at least one prompt source is provided."""
        if info.field_name == "system_prompt_text":
            return v
        if info.field_name == "system_prompt_file":
            return v
        return v


class DQPolicyPromptConfig(PromptConfig):
    """DQ Policy specific prompt configuration."""

    system_prompt_file: str = Field(
        default="config/prompts/text_to_dq_policy_system.txt",
        description="Path to DQ policy system prompt file",
    )
    user_prompt_template: str = Field(
        default="Provided text content:\n{text}",
        description="User prompt template for DQ policy generation",
    )
