# Human-Readable Response Format

## Overview

The ADOC toolkit now supports a "human" response type that automatically converts JSON API responses into clear, human-readable text using AI language models. This feature makes API responses accessible to non-technical users and provides concise summaries of complex data.

## Features

- **Automatic Conversion**: Converts JSON responses to natural language
- **Structured Output**: Provides clear, organized summaries
- **Context-Aware**: Highlights important information and provides context
- **Error Handling**: Graceful fallback to JSON if LLM conversion fails
- **Configurable**: Uses the configured LLM vendor and model

## Setup

### 1. Configure LLM

First, set up an LLM vendor and API key:

```bash
# Set LLM vendor (choose one)
ADOC > set-config llm.vendor gemini
ADOC > set-config llm.vendor claude
ADOC > set-config llm.vendor grok
ADOC > set-config llm.vendor chatgpt

# Set your API key
ADOC > set-config llm.apikey your-api-key-here
```

### 2. Enable Human-Readable Responses

```bash
# Set response type to human
ADOC > set-config http.response.type human
```

## Usage

Once configured, all API responses will automatically be converted to human-readable format:

```bash
# Get human-readable response
ADOC > get /catalog-server/api/assets/search name=database
```

### Example Output

**Before (JSON):**
```json
{
  "status": "success",
  "data": [
    {
      "id": "db-001",
      "name": "Production Database",
      "type": "postgresql",
      "status": "active",
      "location": "us-east-1"
    }
  ],
  "metadata": {
    "count": 1,
    "response_time": 245
  }
}
```

**After (Human-Readable):**
```
**API Response Summary**

*Status*: Success
*Response Time*: 245ms

**Data Overview**
- Total records found: 1
- Search criteria: name contains "database"

**Results:**
1. **Production Database**
   - ID: db-001
   - Type: PostgreSQL
   - Status: Active
   - Location: US East

**Additional Information**
- Response time: 245ms
- Cache status: Hit
```

## Configuration

### Response Types

The toolkit supports four response formats:

- **json** (default): Pretty-printed JSON output
- **table**: Rich formatted table display
- **csv**: Comma-separated values output
- **human**: AI-generated human-readable text

### Switching Between Formats

```bash
# Switch to JSON format
ADOC > set-config http.response.type json

# Switch to table format
ADOC > set-config http.response.type table

# Switch to CSV format
ADOC > set-config http.response.type csv

# Switch to human-readable format
ADOC > set-config http.response.type human
```

## Requirements

### LLM Configuration

The human response type requires:

1. **LLM Vendor**: Must be configured (`llm.vendor`)
2. **API Key**: Must be set (`llm.apikey`)
3. **Model**: Automatically selected based on vendor

### Supported LLM Vendors

- **Gemini** (Google): `gemini-1.5-pro`, `gemini-1.5-flash`
- **Claude** (Anthropic): `claude-3-5-sonnet-20241022`, `claude-3-haiku-20240307`
- **Grok** (xAI): `grok-beta`
- **ChatGPT** (OpenAI): `gpt-4o`, `gpt-4o-mini`, `gpt-3.5-turbo`

## Error Handling

The human response type includes comprehensive error handling:

### Missing LLM Configuration
```
Error: No LLM API key configured. Please set 'llm.apikey' first.

JSON Data:
{"status": "success", "data": [...]}
```

### Missing Prompt File
```
Error: Prompt file not found at config/prompts/json_to_human_system.txt

JSON Data:
{"status": "success", "data": [...]}
```

### LLM API Errors
```
Error converting to human-readable format: LLM API error

JSON Data:
{"status": "success", "data": [...]}
```

## Customization

### Prompt File

The system prompt used for conversion is stored in:
```
config/prompts/json_to_human_system.txt
```

You can customize this file to modify how the LLM converts JSON to human-readable text.

### Prompt Guidelines

The prompt instructs the LLM to:

1. **Structure information logically**
2. **Use clear, descriptive language**
3. **Highlight important information**
4. **Provide context**
5. **Format for readability**
6. **Handle different data types appropriately**
7. **Be concise but comprehensive**

## Use Cases

### Non-Technical Users
- Makes API responses accessible to business users
- Converts technical data into natural language
- Provides clear summaries of complex information

### Quick Summaries
- Rapid overview of API responses
- Highlights key data points
- Reduces time to understand results

### Documentation
- Human-readable output for reports
- Clear explanations of data structures
- Better communication of results

## Examples

### Asset Search
```bash
ADOC > get /catalog-server/api/assets/search name=snowflake
```

**Human Output:**
```
**API Response Summary**

*Status*: Success (200 OK)
*Timestamp*: January 15, 2024 at 2:30:45 PM

**Data Overview**
- Total records found: 3
- Search criteria: name contains "snowflake"

**Results:**
1. **Snowflake Data Warehouse**
   - ID: sf-001
   - Name: Production Snowflake
   - Status: Active
   - Type: Data Warehouse
   - Location: US East

2. **Snowflake Analytics**
   - ID: sf-002
   - Name: Analytics Snowflake
   - Status: Active
   - Type: Analytics Platform
   - Location: US West

3. **Snowflake Backup**
   - ID: sf-003
   - Name: Backup Snowflake
   - Status: Inactive
   - Type: Backup System
   - Location: US Central
```

### Health Check
```bash
ADOC > get /health
```

**Human Output:**
```
**API Response Summary**

*Status*: Success (200 OK)

**System Health**
- Overall Status: Healthy
- Database: Connected
- Cache: Operational
- External Services: All Online

**Performance Metrics**
- Response Time: 45ms
- Memory Usage: 67%
- CPU Usage: 23%
- Active Connections: 156

**Additional Information**
- Uptime: 15 days, 7 hours, 32 minutes
- Last Restart: January 1, 2024 at 00:00:00 UTC
```

## Troubleshooting

### Common Issues

1. **"No LLM API key configured"**
   - Solution: Set your API key with `set-config llm.apikey <your-key>`

2. **"Prompt file not found"**
   - Solution: Ensure `config/prompts/json_to_human_system.txt` exists

3. **"LLM API error"**
   - Solution: Check your API key and network connection
   - Verify the LLM service is available

4. **Poor quality output**
   - Solution: Try a different LLM vendor or model
   - Customize the prompt file for better results

### Performance Considerations

- **Response Time**: Human conversion adds 1-3 seconds to response time
- **API Costs**: Uses LLM API calls (may incur costs)
- **Rate Limits**: Subject to LLM provider rate limits

## Related Commands

- [`set-config`](set_config.md): Configure response type and LLM settings
- [`get`](get.md): Make API requests with human-readable output
- [`show-config`](show_config.md): View current configuration
- [`help`](help.md): Get help for all commands 