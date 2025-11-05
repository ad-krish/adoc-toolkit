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
| `timezone` | string | No | IANA timezone name for datetime fields (default: `UTC`) |

### Timezone Configuration

The toolkit supports configurable timezones for datetime fields in exported data. This ensures timestamps are displayed in your preferred timezone.

#### Default Behavior

By default, all timestamps use **UTC** (Coordinated Universal Time). This is recommended for consistency across different locations and teams.

#### Configuring Custom Timezone

Add the `timezone` field to your environment configuration:

```yaml
environments:
  cs-india:
    name: "cs-india"
    base_url: "https://cs-india.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"
    timezone: "Asia/Kolkata"  # Optional, defaults to UTC
```

#### Supported Timezones

**Important**: Use full [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones), **NOT** abbreviations.

**Common Timezone Examples:**

| Region | IANA Timezone Name | Abbreviation (NOT supported) |
|--------|-------------------|------------------------------|
| **India** | `Asia/Kolkata` | IST ❌ |
| **US East** | `America/New_York` | EST/EDT ❌ |
| **US West** | `America/Los_Angeles` | PST/PDT ❌ |
| **US Central** | `America/Chicago` | CST/CDT ❌ |
| **UK** | `Europe/London` | GMT/BST ❌ |
| **Europe (Central)** | `Europe/Paris` or `Europe/Berlin` | CET/CEST ❌ |
| **Japan** | `Asia/Tokyo` | JST ❌ |
| **Australia (Sydney)** | `Australia/Sydney` | AEST/AEDT ❌ |
| **New Zealand** | `Pacific/Auckland` | NZST/NZDT ❌ |
| **Singapore** | `Asia/Singapore` | SGT ❌ |
| **China** | `Asia/Shanghai` | CST ❌ |
| **UTC (default)** | `UTC` | UTC ✓ |

**Why Not Abbreviations?**
- ❌ **Ambiguous**: IST could mean Indian, Irish, or Israel Standard Time
- ❌ **DST Issues**: PST/PDT requires manual switching for daylight saving
- ✅ **IANA Names**: Unambiguous and handle DST automatically

#### What Gets Affected

When you configure a timezone:

1. **📊 Exported CSV/Parquet Files**: 
   - Column headers include timezone: `execution_date (Asia/Kolkata)`
   - All datetime values automatically converted to configured timezone
   
2. **📁 Tracking Files**: 
   - `.last_run_tracking.json` timestamps use configured timezone
   
3. **⏰ All DateTime Fields**:
   - Automatically converted from UTC to your configured timezone
   - Displayed consistently throughout exports

#### Example Output

**With `timezone: "UTC"` (default):**
```csv
policy_name,execution_date (UTC),rows_scanned
MyPolicy,2025-11-05 18:24:17,1000
```

**With `timezone: "Asia/Kolkata"`:**
```csv
policy_name,execution_date (Asia/Kolkata),rows_scanned
MyPolicy,2025-11-05 23:54:17,1000
```
*(Same moment in time, displayed in different timezone)*

#### Validation

The toolkit validates your timezone configuration:
- ✅ Valid IANA timezone name (e.g., `Asia/Kolkata`)
- ❌ Invalid abbreviation (e.g., `IST`) → Error message

**Example Error:**
```
Error: Invalid timezone: IST. Use IANA timezone names like UTC, US/Eastern, Europe/London
```

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
    timezone: "Asia/Kolkata"  # Indian Standard Time
  
  training:
    name: "uat" 
    base_url: "https://uat.acceldata.app"
    access_key: "VL******GV"
    secret_key: "A**Z"
    timezone: "UTC"  # Default (can be omitted)
  
  se-demo:
    name: "prod"
    base_url: "https://prod.acceldata.app"
    access_key: "G********0"
    secret_key: "H***********R"
    timezone: "America/New_York"  # US Eastern Time

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
Timezone: Asia/Kolkata
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

## Validation

The ADOC Toolkit automatically validates your `environments.yaml` file when loading configurations. The validation ensures:

### Required Structure
- **Top-level `environments` section**: Must be present and contain at least one environment
- **Environment objects**: Each environment must be a YAML object (dictionary)
- **Required fields**: Each environment must have `name`, `base_url`, `access_key`, and `secret_key`

### Field Validation
- **Environment names**: Must contain only letters, numbers, hyphens, and underscores
- **Base URLs**: Must be valid HTTP/HTTPS URLs with a domain
- **Access keys**: Must be uppercase letters and numbers, minimum 8 characters
- **Secret keys**: Must be uppercase letters and numbers, minimum 8 characters
- **Timezone**: Must be a valid IANA timezone name (e.g., `UTC`, `Asia/Kolkata`, `America/New_York`)
- **Name consistency**: The `name` field must match the environment key

### Default Environment
- **Optional field**: `default_environment` is optional
- **Must exist**: If specified, must reference an existing environment

### Example Validation Errors

```bash
# Missing environments section
Error: Missing required 'environments' section in configuration

# Invalid environment name
Error: Environment name 'dev@env' contains invalid characters. Use only letters, numbers, hyphens, and underscores

# Invalid base URL
Error: Environment 'dev' base_url must start with 'http://' or 'https://'

# Missing required field
Error: Environment 'dev' is missing required field: access_key

# Invalid key format
Error: Environment 'dev' access_key should contain only uppercase letters and numbers

# Short key
Error: Environment 'dev' access_key is too short (minimum 8 characters)

# Invalid timezone
Error: Invalid timezone: IST. Use IANA timezone names like UTC, US/Eastern, Europe/London
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
  timezone: "UTC"  # Recommended for development
```

### Staging Environments

Used for pre-production testing:

```yaml
staging:
  name: "Staging"
  base_url: "https://staging.acceldata.app"
  access_key: "STAGING_ACCESS_KEY"
  secret_key: "STAGING_SECRET_KEY"
  timezone: "America/New_York"  # Match production timezone
```

### Production Environments

For live production systems:

```yaml
production:
  name: "Production"
  base_url: "https://production.acceldata.app"
  access_key: "${PROD_ACCESS_KEY}"
  secret_key: "${PROD_SECRET_KEY}"
  timezone: "America/New_York"  # Your local business timezone
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
