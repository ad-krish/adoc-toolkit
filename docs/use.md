# Use Command

## Overview

The `use` command switches between different ADOC environments. Each environment has its own configuration including base URL, access key, and secret key for authentication.

## Usage

```bash
use <environment-name>
```

## Arguments

- **environment-name**: The name of the environment to switch to (case-insensitive)

## Features

- **Environment Switching**: Changes the active environment for all subsequent operations
- **Configuration Loading**: Loads environment settings from `config/environments.yaml`
- **Auto-completion**: Provides suggestions for available environment names
- **Validation**: Ensures the specified environment exists before switching

## Examples

### Basic Usage

```bash
# Switch to cs-india environment
ADOC > use dev
Environment set to dev

# Switch to training environment
ADOC > use training
Environment set to training
```

### Help and Documentation

```bash
# Show available environments
ADOC > use --help
use: Switch to a different environment
Usage: use <environment-name>

Switches the active environment for ADOC operations.
Environment configurations are stored in config/environments.yaml

Available environments:
  dev: dev
  uat: uat
  prod: prod
```

### Error Handling

```bash
# Try to use non-existent environment
ADOC > use invalid-env
Error: Environment 'invalid-env' not found
Available environments:
  dev
  uat
  prod

# Try to use without specifying environment
ADOC > use
Error: Environment name required
Usage: use <environment-name>
Type 'use --help' for more information
```

## Available Environments

The following environments are configured in `config/environments.yaml`:

| Environment | Display Name | Base URL |
|-------------|--------------|----------|
| `dev` | dev | https://dev.acceldata.app |
| `uat` | uat | https://uat.acceldata.app |
| `prod` | prod | https://prod.acceldata.app |

## Environment Configuration

Environments are defined in `config/environments.yaml` with the following structure:

```yaml
environments:
  environment-name:
    name: "Display Name"
    base_url: "https://environment.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"
```

## Auto-completion

The command provides intelligent auto-completion:

1. **Environment Names**: Type `use ` followed by TAB to see available environments
2. **Partial Matching**: Type part of an environment name and TAB to complete it

### Auto-completion Examples

```bash
# Start typing an environment name
ADOC > use c<TAB>
# Completes to: use cs-india

# See all available environments
ADOC > use <TAB>
# Shows: cs-india, training, se-demo
```

## Environment Switching

When you switch environments:

1. **Configuration Loaded**: The new environment's settings are loaded
2. **HTTP Client Updated**: The HTTP client is configured with the new environment's base URL and credentials
3. **Authentication Ready**: All subsequent API calls will use the new environment's access key and secret key

## Integration with Other Commands

- **get**: Requires an environment to be set before making API requests
- **show-env**: Displays the current environment configuration
- **help**: Shows available commands including environment management

## Examples with Real Data

### Successful Environment Switch
```bash
ADOC > use dev
Environment set to dev

ADOC > show-env
Current Environment: dev
Base URL: https://dev.acceldata.app
Access Key: AB******CD
Secret Key: EF******GH
```

### Making API Calls After Environment Switch
```bash
ADOC > use dev
Environment set to dev

ADOC > get /catalog-server/api/assets/search name=Snowflake
{
  "assets": [
    {
      "id": "1234567890",
      "name": "Snowflake_Database",
      "type": "database"
    }
  ]
}
```
## Related Commands

- [`show-env`](show_env.md): Display current environment information
- [`get`](get.md): Make API requests (requires environment to be set)
- [`help`](help.md): Get help for all commands 