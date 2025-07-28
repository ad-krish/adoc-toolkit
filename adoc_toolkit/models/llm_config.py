"""LLM configuration model."""

from enum import Enum

from pydantic import BaseModel, Field, field_validator


class LLMVendor(str, Enum):
    """LLM vendor options."""

    CLAUDE = "claude"
    GEMINI = "gemini"
    GROK = "grok"
    CHATGPT = "chatgpt"


class LLMConfig(BaseModel):
    """LLM configuration settings."""

    vendor: LLMVendor = Field(
        default=LLMVendor.GEMINI, description="LLM vendor to use for AI operations"
    )
    apikey: str | None = Field(
        default=None, description="API key for the selected LLM vendor"
    )
    model: str | None = Field(
        default=None, description="Model name for the selected LLM vendor"
    )
    temperature: float = Field(
        default=0.2, description="Temperature for LLM response generation (0.0 to 2.0)"
    )
    # Configurable model options - can be overridden from config file
    model_options: dict[str, list[str]] | None = Field(
        default=None, description="Available models for each vendor (configurable)"
    )

    @field_validator("vendor")
    @classmethod
    def validate_vendor(cls, v: LLMVendor) -> LLMVendor:
        """Validate vendor is a supported option."""
        return v

    @field_validator("apikey")
    @classmethod
    def validate_apikey(cls, v: str | None) -> str | None:
        """Validate API key format."""
        if v is not None and not v.strip():
            return None
        return v

    @field_validator("temperature")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        """Validate temperature is within valid range."""
        if not isinstance(v, int | float):
            raise ValueError("Temperature must be a number")
        if v < 0.0 or v > 2.0:
            raise ValueError("Temperature must be between 0.0 and 2.0")
        return float(v)

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None, info) -> str | None:
        """Validate model based on vendor."""
        if v is None:
            # Set default model based on vendor
            vendor = info.data.get("vendor", LLMVendor.GEMINI)
            return cls._get_default_model(vendor)
        return v

    @classmethod
    def _get_default_model(cls, vendor: LLMVendor) -> str:
        """Get default model for the specified vendor."""
        default_models = {
            LLMVendor.CLAUDE: "claude-3-5-sonnet-20241022",
            LLMVendor.GEMINI: "gemini-1.5-pro",
            LLMVendor.GROK: "grok-beta",
            LLMVendor.CHATGPT: "gpt-4o",
        }
        return default_models.get(vendor, "gemini-1.5-pro")

    def get_model(self) -> str:
        """Get the current model, using default if not set."""
        if self.model is None:
            return self._get_default_model(self.vendor)
        return self.model

    def get_vendor_options(self) -> list[str]:
        """Get list of available vendor options."""
        return [vendor.value for vendor in LLMVendor]

    def get_model_options(self) -> list[str]:
        """Get list of available model options for current vendor."""
        # If custom model options are configured, use them
        if self.model_options and self.vendor.value in self.model_options:
            return self.model_options[self.vendor.value]

        # Otherwise, use hardcoded defaults
        default_model_options = {
            LLMVendor.CLAUDE: [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
            ],
            LLMVendor.GEMINI: [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
            ],
            LLMVendor.GROK: [
                "grok-beta",
                "grok-2",
            ],
            LLMVendor.CHATGPT: [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        }
        return default_model_options.get(self.vendor, ["gemini-1.5-pro"])

    def get_all_model_options(self) -> dict[str, list[str]]:
        """Get all model options for all vendors."""
        if self.model_options:
            return self.model_options

        # Return hardcoded defaults
        return {
            LLMVendor.CLAUDE.value: [
                "claude-3-5-sonnet-20241022",
                "claude-3-5-haiku-20241022",
                "claude-3-opus-20240229",
                "claude-3-sonnet-20240229",
            ],
            LLMVendor.GEMINI.value: [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro",
            ],
            LLMVendor.GROK.value: [
                "grok-beta",
                "grok-2",
            ],
            LLMVendor.CHATGPT.value: [
                "gpt-4o",
                "gpt-4o-mini",
                "gpt-4-turbo",
                "gpt-3.5-turbo",
            ],
        }
