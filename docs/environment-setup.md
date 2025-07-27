# Environment Setup Guide

## Overview

The ADOC Toolkit uses environment configurations to manage different AccelData Observability Cloud instances. Each environment contains the base URL, access key, and secret key needed to authenticate with the ADOC platform.

## Configuration File Location

Environment configurations are stored in:
```
config/environments.yaml
```

## Environment Configuration Structure

### Basic Structure

```yaml
# ADOC Toolkit Environment Configuration
# Configure your AccelData Observability Cloud environments here

environments:
  environment-name:
    name: "Display Name"
    base_url: "https://environment.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"

# Default environment to use if none specified
default_environment: "environment-name"
```

### Configuration Fields

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `name` | string | Yes | Display name for the environment |
| `base_url` | string | Yes | Base URL for the ADOC platform (e.g., `https://environment.acceldata.app`) |
| `access_key` | string | Yes | Access key for API authentication |
| `secret_key` | string | Yes | Secret key for API authentication |

## Example Configuration

```yaml
# ADOC Toolkit Environment Configuration
# Configure your AccelData Observability Cloud environments here

environments:
  cs-india:
    name: "dev"
    base_url: "https://dev.acceldata.app"
    access_key: "YH*********4B"
    secret_key: "X*********Y"
  
  training:
    name: "uat" 
    base_url: "https://uat.acceldata.app"
    access_key: "VL******GV"
    secret_key: "A**Z"
  
  se-demo:
    name: "prod"
    base_url: "https://prod.acceldata.app"
    access_key: "G********0"
    secret_key: "H***********R"

# Default environment to use if none specified
default_environment: "se-demo"
```

## Setting Up Your Environments

### Step 1: Create Configuration File

1. Navigate to the `config/` directory in your ADOC Toolkit installation
2. Create or edit the `environments.yaml` file
3. Add your environment configurations following the structure above

### Step 2: Add Your Environments

For each ADOC environment you want to access:

1. **Get your credentials** from your AccelData administrator:
   - Access Key
   - Secret Key
   - Base URL

2. **Add the environment** to your `environments.yaml`:

```yaml
environments:
  my-environment:
    name: "My Environment"
    base_url: "https://my-environment.acceldata.app"
    access_key: "YOUR_ACCESS_KEY_HERE"
    secret_key: "YOUR_SECRET_KEY_HERE"
```

### Step 3: Set Default Environment (Optional)

You can specify a default environment that will be used when the toolkit starts:

```yaml
default_environment: "my-environment"
```

## Security Best Practices

### 🔒 Credential Security

1. **Never commit credentials** to version control
2. **Use environment variables** for sensitive data in production
3. **Restrict file permissions** on the configuration file
4. **Rotate credentials regularly** according to your organization's security policy

### Environment Variables (Recommended)

For enhanced security, you can use environment variables for sensitive credentials:

```yaml
environments:
  production:
    name: "Production"
    base_url: "https://production.acceldata.app"
    access_key: "${ADOC_ACCESS_KEY}"
    secret_key: "${ADOC_SECRET_KEY}"
```

Then set the environment variables:
```bash
export ADOC_ACCESS_KEY="your-access-key"
export ADOC_SECRET_KEY="your-secret-key"
```

### File Permissions

Set appropriate file permissions on your configuration file:

```bash
# Unix/Linux/macOS
chmod 600 config/environments.yaml

# Windows (PowerShell)
icacls config/environments.yaml /inheritance:r /grant:r "%USERNAME%:F"
```

## Using Environments

### Switching Environments

Once configured, use the `use` command to switch between environments:

```bash
ADOC > use my-environment
Environment set to my-environment
```

### Viewing Current Environment

Check your current environment configuration:

```bash
ADOC > show-env
Current Environment: my-environment
Base URL: https://my-environment.acceldata.app
Access Key: YH******4B (masked)
Secret Key: X9******UY (masked)
```

### Available Environments

List all available environments:

```bash
ADOC > use
use: Switch to a different environment
Usage: use <environment-name>

Available environments:
  cs-india: cs-india
  training: training
  se-demo: se-demo
```

## Troubleshooting

### Common Issues

#### 1. Environment Not Found

**Error**: `Error: Environment 'environment-name' not found`

**Solution**: 
- Check that the environment name exists in `config/environments.yaml`
- Verify the YAML syntax is correct
- Ensure there are no extra spaces or special characters in the environment name

#### 2. Authentication Errors

**Error**: `401 Unauthorized` or `403 Forbidden`

**Solution**:
- Verify your access key and secret key are correct
- Check that your credentials have the necessary permissions
- Ensure the base URL is correct for your environment

#### 3. Connection Errors

**Error**: `Connection refused` or `Timeout`

**Solution**:
- Verify the base URL is accessible from your network
- Check if you need to configure a proxy
- Ensure your firewall allows connections to the ADOC platform

#### 4. Configuration File Not Found

**Error**: `File not found: config/environments.yaml`

**Solution**:
- Ensure the `config/` directory exists in your ADOC Toolkit installation
- Create the `environments.yaml` file if it doesn't exist
- Check file permissions

### Validation

The toolkit validates your environment configuration:

1. **File Format**: Ensures the YAML file is properly formatted
2. **Required Fields**: Checks that all required fields are present
3. **URL Format**: Validates that base URLs are properly formatted
4. **Credential Format**: Ensures access and secret keys are provided

## Environment Types

### Development Environments

Typically used for development and testing:

```yaml
dev:
  name: "Development"
  base_url: "https://dev.acceldata.app"
  access_key: "DEV_ACCESS_KEY"
  secret_key: "DEV_SECRET_KEY"
```

### Staging Environments

Used for pre-production testing:

```yaml
staging:
  name: "Staging"
  base_url: "https://staging.acceldata.app"
  access_key: "STAGING_ACCESS_KEY"
  secret_key: "STAGING_SECRET_KEY"
```

### Production Environments

For live production systems:

```yaml
production:
  name: "Production"
  base_url: "https://production.acceldata.app"
  access_key: "${PROD_ACCESS_KEY}"
  secret_key: "${PROD_SECRET_KEY}"
```

## Related Commands

- [`use`](use.md): Switch between environments
- [`show-env`](show_env.md): Display current environment information
- [`get`](get.md): Make API requests (requires environment to be set)
- [`help`](help.md): Get help for environment-related commands

## Next Steps

After setting up your environments:

1. **Test your configuration** by switching to an environment and making a test API call
2. **Explore available APIs** using the `get` command
3. **Set up additional configurations** using `set-config` for HTTP timeouts, logging, etc.
4. **Configure export settings** for data export operations

For more information about specific commands, see the individual command documentation in the `docs/` directory. 
