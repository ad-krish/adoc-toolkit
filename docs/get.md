# Get Command

## Overview

The `get` command makes GET HTTP requests to ADOC API endpoints. It provides an interactive way to access ADOC platform APIs with automatic authentication using the current environment's access key and secret key.

**Important**: You must set an environment using the `use` command before making any requests. The get command will fail if no environment is selected.

## Usage

```bash
get <url> [query-params]
```

**Prerequisite**: Set an environment first with `use <environment-name>`

## Arguments

- **url**: The API URL path (defined in `config/adoc-toolkit-api-reference.json`)
- **query-params**: Optional query parameters in `key=value` format

## Features

- **Environment Required**: Must set environment with `use <environment-name>` before making requests
- **Automatic Authentication**: Uses access key and secret key from the current environment
- **Auto-completion**: Provides suggestions for endpoints and query parameters
- **Parameter Validation**: Validates query parameters against endpoint definitions
- **Rich Output**: Displays JSON responses in formatted tables
- **Error Handling**: Comprehensive error reporting and validation

## Examples

### Basic Usage

```bash
# First, set an environment
ADOC > use se-demo
Environment set to se-demo

# Search for assets
ADOC > get /catalog-server/api/assets/search name=Snowflake

# Get asset by UID
ADOC > get /catalog-server/api/assets uid=1234567890

# List asset types
ADOC > get /catalog-server/api/asset-types

# List data sources
ADOC > get /catalog-server/api/data-sources
```

### With Query Parameters

```bash
# Search with multiple parameters
ADOC > get /catalog-server/api/assets/search name=Snowflake ids=1234567890

# Get assets with pagination
ADOC > get /catalog-server/api/assets/discover page=1 size=10

# Get rules with filters
ADOC > get /catalog-server/api/rules page=1 size=20 ruleStatus=active

# Get rule executions
ADOC > get /catalog-server/api/rules/executions page=1 size=10 executionStatus=completed
```

### Help and Documentation

```bash
# General help
ADOC > get --help

# Help for specific endpoint
ADOC > get --help /catalog-server/api/assets/search
```

## Auto-completion

The command provides intelligent auto-completion:

1. **URL Paths**: Type `get /` followed by TAB to see available URLs
2. **Parameter Names**: Type `get <url>?` followed by TAB to see available parameters
3. **Parameter Values**: For parameters with predefined options, typing `=` will show valid values

### Auto-completion Examples

```bash
# Start typing a URL
ADOC > get /<TAB>
# Shows: /catalog-server/api/assets/search, /catalog-server/api/assets, etc.

# Start typing a specific URL
ADOC > get /catalog-server/<TAB>
# Shows: /catalog-server/api/assets/search, /catalog-server/api/assets, etc.

# Show parameters for a URL
ADOC > get /catalog-server/api/assets/search?<TAB>
# Shows: name, ids

# Complete parameter value
ADOC > get /catalog-server/api/assets/search?name=S<TAB>
# Completes to: get /catalog-server/api/assets/search?name=Snowflake
```

## Aliases

The `get` command has the following aliases:
- `fetch`
- `request`

## Configuration

### Response Formatting

The command supports different response formats that can be configured:

- **JSON** (default): Pretty-printed JSON output
- **Table**: Rich formatted table display
- **CSV**: Comma-separated values output

Configure the response format using:
```bash
set-config http.response.type json    # JSON format (default)
set-config http.response.type table   # Table format
set-config http.response.type csv     # CSV format
```

## Error Handling

The command provides comprehensive error handling:

- **No Environment**: Fails gracefully with instructions to set an environment first
- **Invalid Endpoints**: Shows available endpoints when an unknown endpoint is specified
- **Parameter Validation**: Warns about invalid parameter values
- **HTTP Errors**: Displays detailed error messages for failed requests
- **Authentication Errors**: Handles authentication failures gracefully

## Examples with Real Data

### No Environment Set
```bash
ADOC > get /catalog-server/api/assets/search
Error: No environment selected
Please set an environment first using:
  use <environment-name>
Available environments:
  dev
  uat
  prod
```
## Related Commands

- [`use`](use.md): Switch between environments
- [`show-env`](show_env.md): Display current environment information
- [`help`](help.md): Get help for all commands 