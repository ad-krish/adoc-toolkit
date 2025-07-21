# Show Environment Command

## Overview

The `show-env` command displays the current environment configuration including the environment name, base URL, and masked access/secret keys for security.

## Usage

```bash
show-env
```

## Arguments

None - this command takes no arguments.

## Features

- **Environment Display**: Shows the currently active environment
- **Security**: Masks sensitive credentials showing only first 2 and last 2 characters
- **Configuration Info**: Displays base URL and authentication status
- **No Arguments**: Simple command that requires no parameters

## Examples

### Basic Usage

```bash
# Show current environment configuration
ADOC > show-env
Current Environment: se-demo
Base URL: https://se-demo.acceldata.app
Access Key: GV******V0
Secret Key: HW******VRR
```

### Help and Documentation

```bash
# Show command help
ADOC > show-env --help
show-env: Show current environment configuration
Usage: show-env

Displays the current environment configuration including:
- Environment name
- Base URL
- Masked access key (shows first 2 and last 2 characters)
- Masked secret key (shows first 2 and last 2 characters)

Note: Keys are masked for security purposes.
```

### Error Handling

```bash
# When no environment is set
ADOC > show-env
No environment is currently selected
Use 'use <environment-name>' to select an environment
```

## Key Masking

For security purposes, access and secret keys are masked in the output:

- **Format**: Shows first 2 and last 2 characters with asterisks in between
- **Variable Length**: Uses random-length masking for additional obfuscation
- **Consistent**: Same key always produces the same masked output

### Masking Examples

```bash
# Original key: "GV1PJ3XYFJZEBV0"
# Masked output: "GV******V0"

# Original key: "HWNMVIVGIAG6XQ83Y12F6OK2LTBVRR"
# Masked output: "HW******VRR"
```

## Output Information

The command displays the following information:

- **Current Environment**: Name of the active environment
- **Base URL**: The API base URL for the environment
- **Access Key**: Masked access key for authentication
- **Secret Key**: Masked secret key for authentication

## Aliases

The `show-env` command has the following aliases:
- `env`

## Integration with Other Commands

- **use**: Switch environments before checking configuration
- **get**: Requires environment to be set before making API requests
- **help**: Shows available commands including environment management

## Examples with Real Data

### Environment Not Set
```bash
ADOC > show-env
No environment is currently selected
Use 'use <environment-name>' to select an environment
```

### Environment Set
```bash
ADOC > use cs-india
Environment set to cs-india

ADOC > show-env
Current Environment: cs-india
Base URL: https://cs-india.acceldata.app
Access Key: YH******4B
Secret Key: X9******UY
```

### Environment with Missing Configuration
```bash
ADOC > show-env
Current Environment: se-demo
Base URL: Not configured
Access Key: Not configured
Secret Key: Not configured
```

## Security Considerations

- **Key Masking**: Sensitive credentials are never displayed in full
- **Consistent Masking**: Same key always produces the same masked output
- **Variable Length**: Random-length masking prevents pattern recognition
- **No Storage**: Keys are not stored in plain text in the output

## Related Commands

- [`use`](use.md): Switch between environments
- [`get`](get.md): Make API requests (requires environment to be set)
- [`help`](help.md): Get help for all commands 