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

# Health check
ADOC > get health

# List environments
ADOC > get environments

# List datasets
ADOC > get datasets
```

### With Query Parameters

```bash
# Filter datasets by environment
ADOC > get datasets environment=prod

# Limit results
ADOC > get datasets limit=10

# Multiple parameters
ADOC > get datasets environment=prod limit=10 status=active

# Metrics with time range
ADOC > get metrics dataset=my-dataset start_time=2024-01-01T00:00:00Z end_time=2024-01-02T00:00:00Z
```

### Help and Documentation

```bash
# General help
ADOC > get --help

# Help for specific endpoint
ADOC > get --help datasets
```

## Available URLs

The following URLs are available in the API reference:

| URL | Description |
|-----|-------------|
| `/health` | Health check endpoint |
| `/api/v1/environments` | List all environments |
| `/api/v1/datasets` | List all datasets |
| `/api/v1/metrics` | Get metrics data |
| `/api/v1/alerts` | List all alerts |
| `/api/v1/users` | List all users |
| `/api/v1/config` | Get system configuration |
| `/catalog-server/api/assets/search` | Search for assets in catalog |
| `/catalog-server/api/assets` | List all assets |

## Query Parameters

### Common Parameters

Most endpoints support these common parameters:

- **limit**: Maximum number of results to return (default: 100)
- **offset**: Number of results to skip (default: 0)

### URL-Specific Parameters

#### `/api/v1/datasets` URL

- **environment**: Filter by environment name
- **status**: Filter by dataset status (`active`, `inactive`, `error`)

#### `/api/v1/metrics` URL

- **dataset**: Dataset name to filter metrics
- **metric**: Specific metric name
- **start_time**: Start time in ISO format (YYYY-MM-DDTHH:MM:SSZ)
- **end_time**: End time in ISO format (YYYY-MM-DDTHH:MM:SSZ)
- **interval**: Time interval for aggregation (`1m`, `5m`, `15m`, `1h`, `6h`, `1d`)

#### `/api/v1/alerts` URL

- **status**: Filter by alert status (`active`, `resolved`, `acknowledged`)
- **severity**: Filter by alert severity (`low`, `medium`, `high`, `critical`)
- **environment**: Filter by environment name

#### `/api/v1/users` URL

- **role**: Filter by user role (`admin`, `user`, `viewer`)
- **status**: Filter by user status (`active`, `inactive`)

#### `/catalog-server/api/assets/search` URL

- **name**: Asset name to search for
- **type**: Asset type filter (`database`, `table`, `view`, `column`)
- **ids**: Comma-separated list of asset IDs

## Auto-completion

The command provides intelligent auto-completion:

1. **URL Paths**: Type `get /` followed by TAB to see available URLs
2. **Parameter Names**: Type `get <url>?` followed by TAB to see available parameters
3. **Parameter Values**: For parameters with predefined options, typing `=` will show valid values

### Auto-completion Examples

```bash
# Start typing a URL
ADOC > get /<TAB>
# Shows: /health, /api/v1/environments, /catalog-server/api/assets/search, etc.

# Start typing a specific URL
ADOC > get /catalog-server/<TAB>
# Shows: /catalog-server/api/assets/search, /catalog-server/api/assets

# Show parameters for a URL
ADOC > get /catalog-server/api/assets/search?<TAB>
# Shows: name, type, ids, limit, offset

# Complete parameter value
ADOC > get /catalog-server/api/assets/search?type=d<TAB>
# Completes to: get /catalog-server/api/assets/search?type=database

# Add another parameter
ADOC > get /catalog-server/api/assets/search?name=Snowflake&<TAB>
# Shows remaining parameters: type, ids, limit, offset
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

### API Reference File

Endpoints are defined in `config/adoc-toolkit-api-reference.json`. This file contains:

- Endpoint URLs and descriptions
- Query parameter definitions
- Parameter types and validation rules
- Default values and valid options

### Environment Integration

The command requires an environment to be set using the `use` command. It automatically uses the current environment's configuration:
- **Base URL**: From the active environment
- **Access Key**: For authentication
- **Secret Key**: For authentication

If no environment is set, the command will fail with a helpful error message directing you to set an environment first.

## Error Handling

The command provides comprehensive error handling:

- **No Environment**: Fails gracefully with instructions to set an environment first
- **Invalid Endpoints**: Shows available endpoints when an unknown endpoint is specified
- **Parameter Validation**: Warns about invalid parameter values
- **HTTP Errors**: Displays detailed error messages for failed requests
- **Authentication Errors**: Handles authentication failures gracefully

## Integration with Other Commands

- **use**: Switch environments before making requests
- **show-env**: Check current environment configuration
- **help**: Get help for the get command

## Examples with Real Data

### No Environment Set
```bash
ADOC > get health
Error: No environment selected
Please set an environment first using:
  use <environment-name>
Available environments:
  cs-india
  training
  se-demo
```

### Health Check
```bash
ADOC > get health
{
  "status": "healthy",
  "timestamp": "2024-01-15T10:30:00Z",
  "version": "1.2.3"
}
```

### List Datasets
```bash
ADOC > get datasets environment=prod limit=5
{
  "datasets": [
    {
      "name": "prod-dataset-1",
      "environment": "prod",
      "status": "active",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "total": 25,
  "limit": 5,
  "offset": 0
}
```

### Get Metrics
```bash
ADOC > get metrics dataset=my-dataset start_time=2024-01-15T00:00:00Z end_time=2024-01-15T23:59:59Z interval=1h
{
  "metrics": [
    {
      "timestamp": "2024-01-15T00:00:00Z",
      "value": 42.5,
      "metric": "cpu_usage"
    }
  ]
}
```

## Related Commands

- [`use`](use.md): Switch between environments
- [`show-env`](show_env.md): Display current environment information
- [`help`](help.md): Get help for all commands 