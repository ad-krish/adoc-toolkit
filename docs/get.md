# Get Command

## Overview

The `get` command allows you to make HTTP GET requests to ADOC API endpoints. It supports both direct URL specification and path parameters for dynamic endpoints.

## Usage

```bash
get <url> [path-params] [query-params]
```

## Features

- **Direct URL Access**: Make requests to any defined API endpoint
- **Path Parameters**: Support for dynamic URLs with path parameters (e.g., `/assets/:asset-id`)
- **Query Parameters**: Add query parameters with `?` prefix or key=value pairs
- **Interactive Prompting**: When path parameters are missing, the system prompts for values
- **Auto-completion**: Tab completion for URLs and parameters
- **Response Formatting**: Pretty-printed JSON responses

## Path Parameters

### Syntax
- Use `:param-name` in URLs to define path parameters
- Provide values as `param-name=value` pairs
- If not provided, you'll be prompted interactively
- Auto-completion shows available path parameters after typing a complete URL

### Examples

```bash
# Direct specification
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123

# Interactive prompting (will ask for asset-id)
ADOC > get /catalog-server/api/assets/:asset-id/metadata
Value for asset-id: 123

# Multiple path parameters
ADOC > get /catalog-server/api/assets/:asset-id/users/:user-id/permissions asset-id=123 user-id=456
```

### Auto-completion for Path Parameters

The command provides intelligent auto-completion for path parameters:

1. **URL Completion**: Type `get /` and press Tab to see all available endpoints
2. **Partial URL Completion**: Type `get /catalog-server/api/assets/` and press Tab to see matching endpoints
3. **Path Parameter Suggestions**: After typing a complete URL, press Tab to see available path parameters

```bash
# Auto-complete URLs
ADOC > get /<TAB>
/catalog-server/api/assets/search
/catalog-server/api/assets/:asset-id/metadata
/catalog-server/api/assets/:asset-id/users/:user-id/permissions

# Auto-complete path parameters (after typing complete URL)
ADOC > get /catalog-server/api/assets/:asset-id/users/:user-id/permissions <TAB>
asset-id
user-id
```

### Interactive Prompting

When path parameters are missing, the system will:

1. **Show the parameter name**: `Value for asset-id:`
2. **Accept user input**: Enter the value or press Enter to cancel
3. **Replace in URL**: Use the provided value to complete the request
4. **Handle multiple parameters**: Prompt for each missing parameter in order

### Interactive Prompting

When path parameters are missing, the system will:

1. **Show the parameter name**: `Value for asset-id:`
2. **Accept user input**: Enter the value or press Enter to cancel
3. **Replace in URL**: Use the provided value to complete the request

## Query Parameters

### Syntax
- **With `?` prefix**: `?name=value` or `?flag` (boolean)
- **Direct pairs**: `name=value` (if not a path parameter)

### Examples

```bash
# Using ? prefix
ADOC > get /catalog-server/api/assets/search ?name=test ?page=1

# Direct key=value pairs
ADOC > get /catalog-server/api/assets/search name=test page=1

# Boolean parameters
ADOC > get /catalog-server/api/assets/search ?include_history
```

## Response Formatting

The `get` command respects the `http.response.type` configuration setting:

### Available Formats

- **JSON** (default): Pretty-printed JSON with indentation
- **Table**: Rich table format with borders and columns
- **CSV**: Comma-separated values format
- **Human**: AI-generated human-readable format

### Configuration

Set the response format using the `set-config` command:

```bash
# Set to JSON format
ADOC > set-config http.response.type json

# Set to table format
ADOC > set-config http.response.type table

# Set to CSV format
ADOC > set-config http.response.type csv

# Set to human-readable format
ADOC > set-config http.response.type human
```

### Example Outputs

**JSON Format:**
```json
{
  "data": {
    "id": 123,
    "name": "test-asset",
    "metadata": {
      "type": "table",
      "size": "1GB"
    }
  }
}
```

**Table Format:**
```
                                     Response Data                                     
┏━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key                            ┃ Value                                              ┃
┡━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ data.id                        │ 123                                                │
│ data.name                      │ test-asset                                         │
│ data.metadata.type             │ table                                              │
│ data.metadata.size             │ 1GB                                                │
└────────────────────────────────┴────────────────────────────────────────────────────┘
```

**CSV Format:**
```csv
Key,Value
data.id,123
data.name,test-asset
data.metadata.type,table
data.metadata.size,1GB
```

## Auto-completion

The command supports intelligent tab completion for:

- **URLs**: Complete endpoint paths as you type
- **Path Parameters**: Show available parameters after completing a URL
- **Query Parameters**: Complete parameter names with `?` prefix
- **Parameter Values**: Complete enum values when available

### Auto-completion Behavior

1. **Empty input**: Shows all available endpoints
2. **Partial URL**: Shows matching endpoints
3. **Complete URL**: Shows available path parameters
4. **Query parameters**: Shows available query parameter names

## Error Handling

- **Unknown URLs**: Shows available URLs and suggests using `get --help`
- **Missing Path Parameters**: Prompts for values or allows cancellation
- **Invalid Parameters**: Shows warnings for unknown parameters
- **Network Errors**: Displays clear error messages

## Examples

### Basic Usage

```bash
# Simple GET request
ADOC > get /catalog-server/api/assets/search

# With query parameters
ADOC > get /catalog-server/api/assets/search ?name=Snowflake ?page=1
```

### Path Parameters

```bash
# Direct path parameter
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123

# Interactive path parameter
ADOC > get /catalog-server/api/assets/:asset-id/metadata
Value for asset-id: 123

# Multiple path parameters
ADOC > get /catalog-server/api/assets/:asset-id/users/:user-id/permissions asset-id=123 user-id=456
```

### Complex Examples

```bash
# Path parameters with query parameters
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123 include_history=true format=json

# Multiple query parameters
ADOC > get /catalog-server/api/assets/search ?name=test ?page=1 ?size=10 ?include_history
```

### Response Format Examples

```bash
# JSON response (default)
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123

# Table response
ADOC > set-config http.response.type table
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123

# Human-readable response
ADOC > set-config http.response.type human
ADOC > get /catalog-server/api/assets/:asset-id/metadata asset-id=123
```

## Interactive Path Parameter Prompting

When you don't provide path parameter values, the system prompts you:

```bash
ADOC > get /catalog-server/api/assets/:asset-id/metadata

Value for asset-id: 123
✅ Request successful
Status: 200
URL: /catalog-server/api/assets/123/metadata
Response:
{
  "metadata": {
    "id": "123",
    "name": "test-asset",
    "type": "table"
  }
}
```

To cancel the request, simply press Enter when prompted:

```bash
ADOC > get /catalog-server/api/assets/:asset-id/metadata

Value for asset-id: 
Request cancelled by user
```

## Configuration

The command uses the API reference defined in `config/adoc-toolkit-api-reference.json` to:

- Validate URLs and parameters
- Provide auto-completion suggestions
- Show help information for endpoints

## Related Commands

- [`use`](use.md): Set the environment for API requests
- [`show-env`](show_env.md): Display current environment settings
- [`set-config`](set_config.md): Configure response formatting and other settings
- [`help`](help.md): Get help for other commands

## Next Steps

1. **Set Environment**: Use `use <environment-name>` to configure the API endpoint
2. **Explore Endpoints**: Try `get --help` to see available URLs
3. **Test Path Parameters**: Experiment with dynamic URLs and interactive prompting
4. **Configure Response Format**: Use `set-config http.response.type` to change output format 