# Help Command

## Overview

The `help` command displays information about available commands and provides detailed help for specific commands.

## Usage

```bash
help [command-name]
```

## Arguments

- **command-name** (optional): The name of a specific command to get detailed help for

## Features

- **Command Listing**: Shows all available commands with descriptions
- **Detailed Help**: Provides comprehensive help for specific commands
- **Alias Support**: Shows command aliases in the listing
- **No Arguments**: Shows general help when no command is specified

## Examples

### Basic Usage

```bash
# Show all available commands
ADOC > help
Available commands:
  exit: Exit the interactive shell
  export-metrics: Export metrics data
  get (fetch, request): Make GET HTTP requests to ADOC API endpoints
  help (h, ?): Show available commands and their descriptions
  history: Show command history
  set-config: Set configuration values
  show-env (env): Show current environment configuration
  use: Switch to a different environment

Type 'help <command>' or '<command> --help' for detailed help on a specific command.
```

### Detailed Help for Specific Commands

```bash
# Get detailed help for the get command
ADOC > help get
get: Make GET HTTP requests to ADOC API endpoints

Usage: get <url> [query-params]

Options:
  --help [url]            Show this help message, optionally for a specific URL

Description:
  Makes GET HTTP requests to ADOC API endpoints.
  Requires an environment to be set using 'use <environment-name>'.
  URLs are defined in config/adoc-toolkit-api-reference.json.
  Query parameters are specified as key=value pairs.

  Use 'get --help <url>' to see available parameters for a URL.

Examples:
  get /catalog-server/api/assets/search name=Snowflake
  get /catalog-server/api/assets/search name=Snowflake ids=1234567890

Note: Set an environment first with 'use <environment-name>' before making requests.
```

### Help for Environment Commands

```bash
# Get help for use command
ADOC > help use
use: Switch to a different environment
Usage: use <environment-name>

Switches the active environment for ADOC operations.
Environment configurations are stored in config/environments.yaml

Available environments:
  cs-india: cs-india
  training: training
  se-demo: se-demo

# Get help for show-env command
ADOC > help show-env
show-env: Show current environment configuration
Usage: show-env

Displays the current environment configuration including:
- Environment name
- Base URL
- Masked access key (shows first 2 and last 2 characters)
- Masked secret key (shows first 2 and last 2 characters)

Note: Keys are masked for security purposes.
```

## Command Aliases

The `help` command has the following aliases:
- `h`
- `?`

## Available Commands

The help system provides information about all available commands:

| Command | Aliases | Description |
|---------|---------|-------------|
| `exit` | | Exit the interactive shell |
| `export-metrics` | | Export metrics data |
| `get` | `fetch`, `request` | Make GET HTTP requests to ADOC API endpoints |
| `help` | `h`, `?` | Show available commands and their descriptions |
| `history` | | Show command history |
| `set-config` | | Set configuration values |
| `show-env` | `env` | Show current environment configuration |
| `use` | | Switch to a different environment |

## Help System Integration

The help command integrates with the broader help system:

1. **General Help**: `help` shows all available commands
2. **Command-Specific Help**: `help <command>` shows detailed help for a specific command
3. **Built-in Help**: `<command> --help` provides the same detailed help
4. **Consistent Format**: All help follows the same format and structure

## Examples with Real Data

### General Help Output
```bash
ADOC > help
Available commands:
  exit: Exit the interactive shell
  export-metrics: Export metrics data
  get (fetch, request): Make GET HTTP requests to ADOC API endpoints
  help (h, ?): Show available commands and their descriptions
  history: Show command history
  set-config: Set configuration values
  show-env (env): Show current environment configuration
  use: Switch to a different environment

Type 'help <command>' or '<command> --help' for detailed help on a specific command.
```

### Command Not Found
```bash
ADOC > help nonexistent-command
Available commands:
  exit: Exit the interactive shell
  export-metrics: Export metrics data
  get (fetch, request): Make GET HTTP requests to ADOC API endpoints
  help (h, ?): Show available commands and their descriptions
  history: Show command history
  set-config: Set configuration values
  show-env (env): Show current environment configuration
  use: Switch to a different environment

Type 'help <command>' or '<command> --help' for detailed help on a specific command.
```

## Help Formats

The help system supports multiple formats:

### Command List Format
```bash
ADOC > help
Available commands:
  command-name (alias1, alias2): Description
```

### Detailed Help Format
```bash
ADOC > help command-name
command-name: Description
Usage: command-name [options]

Options:
  --option: Description of option

Description:
  Detailed description of what the command does.

Examples:
  command-name example1
  command-name example2

Note: Additional notes or warnings.
```

## Integration with Other Commands

- **All Commands**: Every command supports `--help` flag
- **Interactive Shell**: Help is available at any time during interactive sessions
- **Command Discovery**: Helps users discover available functionality

## Related Commands

- [`get`](get.md): Make API requests (has detailed help)
- [`use`](use.md): Switch environments (has detailed help)
- [`show-env`](show_env.md): Show environment info (has detailed help)
- [`exit`](exit.md): Exit the shell
- [`history`](history.md): Show command history 