# LLM Configuration

## Overview

The ADOC toolkit supports configuration for various Large Language Model (LLM) vendors to enable AI-powered features. The LLM configuration allows you to specify which vendor to use, provide API keys, and select specific models.

## Configuration Options

### LLM Vendor (`llm.vendor`)

Specifies which LLM vendor to use for AI operations.

**Options:**
- `claude` - Anthropic Claude models
- `gemini` - Google Gemini models (default)
- `grok` - xAI Grok models
- `chatgpt` - OpenAI ChatGPT models

**Default:** `gemini`

### API Key (`llm.apikey`)

The API key for the selected LLM vendor. This is required for making API calls to the LLM service.

**Format:** Vendor-specific API key format
**Default:** `None` (not set)

### Model (`llm.model`)

The specific model to use from the selected vendor. If not specified, the toolkit will automatically select the latest recommended model for the vendor.

**Default:** Automatically set based on vendor:
- Claude: `claude-3-5-sonnet-20241022`
- Gemini: `gemini-1.5-pro`
- Grok: `grok-beta`
- ChatGPT: `gpt-4o`

## Usage

### Setting LLM Configuration

```bash
# Set the LLM vendor
ADOC > set-config llm.vendor claude

# Set the API key
ADOC > set-config llm.apikey sk-your-claude-api-key-here

# Set a specific model (optional)
ADOC > set-config llm.model claude-3-5-haiku-20241022
```

### Viewing LLM Configuration

```bash
# List all configuration including LLM settings
ADOC > set-config --list

# Show specific LLM configuration
ADOC > set-config --show llm.vendor
ADOC > set-config --show llm.apikey
ADOC > set-config --show llm.model
```

### Available Models by Vendor

#### Claude Models
- `claude-3-5-sonnet-20241022` (default)
- `claude-3-5-haiku-20241022`
- `claude-3-opus-20240229`
- `claude-3-sonnet-20240229`

#### Gemini Models
- `gemini-1.5-pro` (default)
- `gemini-1.5-flash`
- `gemini-1.0-pro`

#### Grok Models
- `grok-beta` (default)
- `grok-2`

#### ChatGPT Models
- `gpt-4o` (default)
- `gpt-4o-mini`
- `gpt-4-turbo`
- `gpt-3.5-turbo`

## Examples

### Switching to Claude

```bash
ADOC > set-config llm.vendor claude
✅ Configuration set: llm.vendor = claude

ADOC > set-config llm.apikey sk-ant-api03-your-key-here
✅ Configuration set: llm.apikey = sk-ant-api03-your-key-here

ADOC > set-config --show llm.model
# Shows: claude-3-5-sonnet-20241022 (auto-selected)
```

### Switching to ChatGPT

```bash
ADOC > set-config llm.vendor chatgpt
✅ Configuration set: llm.vendor = chatgpt

ADOC > set-config llm.apikey sk-your-openai-key-here
✅ Configuration set: llm.apikey = sk-your-openai-key-here

ADOC > set-config llm.model gpt-4o-mini
✅ Configuration set: llm.model = gpt-4o-mini
```

### Using Gemini (Default)

```bash
ADOC > set-config llm.vendor gemini
✅ Configuration set: llm.vendor = gemini

ADOC > set-config llm.apikey your-gemini-api-key
✅ Configuration set: llm.apikey = your-gemini-api-key

# Model will auto-select to gemini-1.5-pro
```

## Configuration Persistence

LLM configuration settings are automatically saved to your configuration file and will persist between sessions. The configuration is stored in:

- `config/adoc-toolkit-config.json` (if exists)
- `~/adoc-toolkit-config.json` (fallback)

## Validation

The toolkit validates LLM configuration settings:

- **Vendor**: Must be one of the supported vendors (`claude`, `gemini`, `grok`, `chatgpt`)
- **API Key**: Can be any string, but empty strings are converted to `None`
- **Model**: Must be a valid model for the selected vendor

### Error Handling

```bash
# Invalid vendor
ADOC > set-config llm.vendor invalid
Error: Invalid LLM vendor 'invalid'. Must be one of: claude, gemini, grok, chatgpt

# Empty API key (converted to None)
ADOC > set-config llm.apikey ""
✅ Configuration set: llm.apikey = None
```

## Related Commands

- [`set-config`](set_config.md): Set configuration values
- [`show-config`](show_config.md): Display configuration values

## Customizing Model Options

The available models for each vendor can be customized by editing the `adoc-toolkit-config.json` file. The `llm.model_options` setting allows you to define custom model lists for each vendor.

### Example Custom Configuration

```json
{
  "llm": {
    "model_options": {
      "value": {
        "claude": [
          "claude-3-5-sonnet-20241022",
          "claude-3-5-haiku-20241022",
          "claude-3-opus-20240229"
        ],
        "gemini": [
          "gemini-1.5-pro",
          "gemini-1.5-flash"
        ],
        "grok": [
          "grok-beta"
        ],
        "chatgpt": [
          "gpt-4o",
          "gpt-4o-mini"
        ]
      }
    }
  }
}
```

### Setting Custom Model Options

The `llm.model_options` setting is **not available through the set-config command** for security and complexity reasons. Instead, you can customize the available models by editing the configuration file directly.

```bash
# View current configuration
ADOC > set-config --list

# The model options are stored as a JSON object in the configuration file
# You can edit the config file directly to customize available models
```

### Configuration File Location

The configuration file is located at:
- `config/adoc-toolkit-config.json` (if exists)
- `~/adoc-toolkit-config.json` (fallback)

## Notes

- The default vendor is `gemini` for optimal performance and availability
- API keys are stored in plain text in the configuration file - ensure proper file permissions
- Model selection is vendor-specific and validated against available options
- When switching vendors, the model will automatically update to the vendor's default unless explicitly set
- Custom model options override the hardcoded defaults but maintain backward compatibility
- If a vendor is missing from custom model options, the default options will be used 