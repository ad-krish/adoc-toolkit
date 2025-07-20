# Set-Config Command

## Overview
The `set-config` command allows you to configure various settings for the ADOC Toolkit, particularly HTTP client behavior for API interactions.

## Usage
```
set-config <key> <value>
set-config --list
set-config --show <key>
```

## Configuration Keys

### HTTP Configuration
All HTTP-related settings that control how the toolkit interacts with ADOC APIs:

#### `http.timeout`
- **Description**: HTTP request timeout in seconds
- **Default**: 120
- **Range**: 1-3600
- **Example**: `set-config http.timeout 60`

#### `http.retries`
- **Description**: Number of retry attempts for failed requests
- **Default**: 3
- **Range**: 0-10
- **Example**: `set-config http.retries 5`

#### `http.proxy`
- **Description**: HTTP proxy URL for requests
- **Default**: None
- **Format**: HTTP or HTTPS URL
- **Example**: `set-config http.proxy https://proxy.company.com:8080`
- **To remove**: `set-config http.proxy none`

## Examples

### Basic Configuration
```
ADOC > set-config http.timeout 90
✅ Configuration set: http.timeout = 90
💡 HTTP configuration changes will apply to new requests

ADOC > set-config http.retries 5
✅ Configuration set: http.retries = 5

ADOC > set-config http.proxy https://proxy.example.com:3128
✅ Configuration set: http.proxy = https://proxy.example.com:3128
```

### Viewing Configuration
```
ADOC > set-config --list
┏━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┳━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┓
┃ Key          ┃ Value                          ┃ Description                                          ┃
┡━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━╇━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━┩
│ http.proxy   │ https://proxy.example.com:3128 │ HTTP proxy URL for requests                          │
│ http.retries │ 5                              │ Number of retry attempts for failed requests        │
│ http.timeout │ 90                             │ HTTP request timeout in seconds                      │
└──────────────┴────────────────────────────────┴──────────────────────────────────────────────────────┘

ADOC > set-config --show http.timeout
http.timeout: 90
```

### Removing Proxy Configuration
```
ADOC > set-config http.proxy none
✅ Configuration set: http.proxy = None
```

## Auto-completion

The `set-config` command supports intelligent auto-completion:

- **Configuration keys**: Tab completion for all available configuration keys
- **Flag options**: Completion for `--list` and `--show` flags
- **Value suggestions**: Context-aware suggestions for configuration values
  - Timeout values: 30, 60, 120, 300
  - Retry values: 0, 1, 3, 5
  - Proxy templates: Common proxy URL formats

## Error Handling

### Validation Errors
```
ADOC > set-config http.timeout invalid
Error: Timeout must be an integer

ADOC > set-config http.retries -1
Error: Retries must be non-negative

ADOC > set-config http.proxy invalid-url
Error: Proxy must be a valid HTTP or HTTPS URL
```

### Missing Arguments
```
ADOC > set-config http.timeout
Error: Both key and value are required
Usage: set-config <key> <value>
```

## Configuration Persistence

All configuration changes are automatically saved to `~/.adoc-toolkit-config.json` and persist across toolkit sessions.

### Configuration File Format
```json
{
  "version": "1.0",
  "http": {
    "timeout": 90,
    "retries": 5,
    "proxy": "https://proxy.example.com:3128"
  }
}
```

## Integration with HTTP Client

HTTP configuration settings are automatically applied to all API requests:

1. **Timeout**: Controls how long to wait for responses
2. **Retries**: Determines retry behavior for failed requests
3. **Proxy**: Routes all HTTP traffic through specified proxy

Changes take effect immediately for new requests.

## Aliases

The `set-config` command can also be invoked using:
- `config` - Short alias
- `set` - Alternative alias

```
ADOC > config http.timeout 60
ADOC > set http.retries 3
```

## Related Commands

- [`show-env`](show_env.md): Display current environment configuration
- [`use`](use.md): Switch between environments
- [`history`](history.md): View command history

## Best Practices

1. **Timeout Settings**: 
   - Use shorter timeouts (30-60s) for development environments
   - Use longer timeouts (120-300s) for production environments with potentially slower responses

2. **Retry Configuration**:
   - Use 0-1 retries for development to fail fast
   - Use 3-5 retries for production to handle transient failures

3. **Proxy Configuration**:
   - Always use HTTPS proxies when possible
   - Test connectivity after setting proxy configuration
   - Use `set-config http.proxy none` to disable proxy for troubleshooting

4. **Configuration Review**:
   - Regularly review settings with `set-config --list`
   - Document proxy settings for team environments
   - Keep timeout values reasonable to avoid hanging operations