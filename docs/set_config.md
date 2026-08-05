# Set-Config Command

## Overview

The `set-config` command allows you to configure various settings for the ADOC Toolkit. You can customize HTTP behavior, logging, and audit trails to match your environment and preferences.

## Usage

```bash
set-config <key> <value>
set-config --list
set-config --show <key>
```

## Listing Configuration

The `--list` option displays all configuration settings in a single table, organized by category:

- **HTTP Configuration**: Network and API settings
- **Logging Configuration**: Log levels, file paths, and rotation
- **Audit Configuration**: Audit trail settings

Category headers span the entire table width, making it easy to find and understand related settings at a glance.

### Example Output

```bash
ADOC > set-config --list
```

The command displays configuration in a single organized table with category headers:

```
                                           Configuration Settings

┏━━━━━━━━━━━━━━━━━━┳━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key              ┃ Value  ┃ Description                           ┃┃ Options                             ┃
┡━━━━━━━━━━━━━━━━━━╇━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ HTTP             │        │                                       ││                                     │
│ Configuration    │        │                                       ││                                     │
│ http.timeout     │ 120    │ HTTP request timeout in seconds       ││ 30, 60, 120, 300                    │
│ http.retries     │ 3      │ Number of retry attempts for failed   ││ 0, 1, 3, 5                          │
│ http.response.t… │ json   │ Response format type                  ││ json, table, csv                    │
│                  │        │                                       ││                                     │
│ Logging          │        │                                       ││                                     │
│ Configuration    │        │                                       ││                                     │
│ log.level        │ INFO   │ Logging level for application logs    ││ TRACE, DEBUG, INFO, ERROR           │
└──────────────────┴────────┴───────────────────────────────────────┴┴─────────────────────────────────────┘
```

## Quick Start

### Basic Configuration

```bash
# Set HTTP timeout to 60 seconds
ADOC > set-config http.timeout 60

# Enable debug logging
ADOC > set-config log.level DEBUG

# Configure proxy for corporate network
ADOC > set-config http.proxy https://proxy.company.com:8080

# View all current settings (grouped by category)
ADOC > set-config --list
```

## Configuration Categories

### 🌐 HTTP Configuration

Control how the toolkit interacts with ADOC APIs:

#### `http.timeout`
- **Purpose**: How long to wait for API responses
- **Default**: 120 seconds
- **Options**: 30, 60, 120, 300 seconds
- **Example**: `set-config http.timeout 60`

#### `http.retries`
- **Purpose**: Number of retry attempts for failed requests
- **Default**: 3 attempts
- **Options**: 0, 1, 3, 5 attempts
- **Example**: `set-config http.retries 5`

#### `http.proxy`
- **Purpose**: HTTP proxy for corporate networks
- **Default**: None (direct connection)
- **Format**: `https://proxy.company.com:8080` or `http://proxy.company.com:3128`
- **Example**: `set-config http.proxy https://proxy.company.com:8080`
- **Remove**: `set-config http.proxy none`

#### `http.response.type`
- **Purpose**: Format for displaying API responses
- **Default**: `json`
- **Options**: `json`, `table`, `csv`
- **Example**: `set-config http.response.type table`

### 📝 Logging Configuration

Control logging behavior and output:

#### `log.level`
- **Purpose**: Level of detail in log messages
- **Default**: `INFO`
- **Options**: `TRACE`, `DEBUG`, `INFO`, `ERROR`
- **Example**: `set-config log.level DEBUG`

#### `log.filepath`
- **Purpose**: Save logs to a file
- **Default**: None (console only)
- **Options**: Any file path
- **Example**: `set-config log.filepath ./adoc-toolkit.log`

#### `log.rotate.onsize`
- **Purpose**: Rotate log file when it reaches this size
- **Default**: `10MB`
- **Options**: `10MB`, `50MB`, `100MB`, `1GB`
- **Example**: `set-config log.rotate.onsize 50MB`

#### `log.rotate.ontime`
- **Purpose**: Rotate log file after this many minutes
- **Default**: 120 minutes
- **Options**: 60, 120, 240, 480 minutes
- **Example**: `set-config log.rotate.ontime 240`

### 🔍 Audit Configuration

Track command execution for compliance:

#### `audit.logfile`
- **Purpose**: Log all commands for audit purposes
- **Default**: None (no audit logging)
- **Options**: Any file path
- **Example**: `set-config audit.logfile ./audit.log`

## Examples

### HTTP Configuration Examples

```bash
# Optimize for development (faster timeouts, fewer retries)
ADOC > set-config http.timeout 30
ADOC > set-config http.retries 1

# Optimize for production (longer timeouts, more retries)
ADOC > set-config http.timeout 300
ADOC > set-config http.retries 5

# Configure corporate proxy
ADOC > set-config http.proxy https://proxy.company.com:8080

# Change response format for better readability
ADOC > set-config http.response.type table
```

### Logging Examples

```bash
# Enable detailed debugging
ADOC > set-config log.level DEBUG

# Save logs to file
ADOC > set-config log.filepath ./adoc-toolkit.log

# Configure log rotation
ADOC > set-config log.rotate.onsize 50MB
ADOC > set-config log.rotate.ontime 240

# Enable audit logging
ADOC > set-config audit.logfile ./audit.log
```

### Viewing Configuration

```bash
# List all current settings
ADOC > set-config --list

# Show specific setting
ADOC > set-config --show http.timeout
ADOC > set-config --show log.level
```

## Auto-completion

The command provides intelligent suggestions:

- **Configuration keys**: Tab completion for all available settings
- **Flag options**: `--list` and `--show` completion
- **Value suggestions**: Context-aware options for each setting
  - Timeout values: 30, 60, 120, 300
  - Log levels: TRACE, DEBUG, INFO, ERROR
  - Response types: json, table, csv

### Auto-completion Examples

```bash
# Start typing a configuration key
ADOC > set-config http.<TAB>
# Shows: http.timeout, http.retries, http.proxy, http.response.type

# Get value suggestions
ADOC > set-config log.level <TAB>
# Shows: TRACE, DEBUG, INFO, ERROR
```

## Error Handling

### Validation Errors

```bash
# Invalid timeout value
ADOC > set-config http.timeout invalid
Error: Timeout must be an integer

# Invalid log level
ADOC > set-config log.level INVALID
Error: Invalid log level. Options: TRACE, DEBUG, INFO, ERROR

# Invalid proxy URL
ADOC > set-config http.proxy invalid-url
Error: Proxy must be a valid HTTP or HTTPS URL
```

### Missing Arguments

```bash
# Missing value
ADOC > set-config http.timeout
Error: Both key and value are required
Usage: set-config <key> <value>
```

## Configuration Persistence

All settings are automatically saved and persist across toolkit sessions. Configuration is stored in:
- **User config**: `~/.adoc-toolkit-config.json`
- **Project config**: `config/adoc-toolkit-config.json` (if present)

## Command Aliases

You can use these shorter aliases:

```bash
ADOC > config http.timeout 60      # Instead of set-config
ADOC > set log.level DEBUG         # Alternative alias
```

## Best Practices

### HTTP Configuration

1. **Development**: Use shorter timeouts (30-60s) and fewer retries (0-1) for faster feedback
2. **Production**: Use longer timeouts (120-300s) and more retries (3-5) for reliability
3. **Proxy**: Always use HTTPS proxies when possible for security
4. **Response Format**: Use `table` for better readability of large datasets

### Logging Configuration

1. **Development**: Use `DEBUG` or `TRACE` level for detailed troubleshooting
2. **Production**: Use `INFO` or `ERROR` level to reduce noise
3. **File Logging**: Enable file logging for persistent records
4. **Rotation**: Set appropriate rotation limits to manage disk space

### Security Considerations

1. **Proxy Configuration**: Use secure proxies and validate connectivity
2. **Audit Logging**: Enable audit logging for compliance requirements
3. **Configuration Review**: Regularly review settings for security implications

## Related Commands

- [`show-env`](show_env.md): Display current environment configuration
- [`use`](use.md): Switch between environments
- [`help`](help.md): Get help for commands
- [`history`](history.md): View command history

## Troubleshooting

### Configuration Not Saving

1. **Check Permissions**: Ensure write access to config directory
2. **Verify Path**: Check if config file path is correct
3. **Restart Toolkit**: Some changes require restart to take effect

### Settings Not Applied

1. **Check Syntax**: Verify configuration key and value format
2. **Validate Options**: Ensure value is in the allowed options list
3. **Restart Commands**: Some settings only apply to new operations

### Auto-completion Issues

1. **Refresh Completions**: Try typing the command again
2. **Check Configuration**: Ensure config file is valid JSON
3. **Restart Toolkit**: Completions are loaded at startup
