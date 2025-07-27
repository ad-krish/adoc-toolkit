# ADOC Toolkit

Acceldata Observability Cloud ("ADOC") toolkit for managing and interacting with ADOC SaaS platform. This interactive command-line tool provides easy access to ADOC APIs, data export capabilities, and AI-powered data quality policy generation.

## 🚀 Quick Start

### Prerequisites
- Python 3.10 or higher
- [uv](https://docs.astral.sh/uv/getting-started/installation/) (recommended) or pip

### Installation

```bash
# Clone the repository
git clone https://github.com/niranta-life/adoc-toolkit.git
cd adoc-toolkit

# Install dependencies
uv sync

# Run the toolkit
uv run adoc-toolkit
```

### Cross-Platform Launcher Scripts

For convenience, use the provided launcher scripts that handle dependency installation automatically:

```bash
# Unix (Linux/macOS)
bin/adoc-toolkit

# Windows
bin\adoc-toolkit.bat
```

## 📖 User Guide

### Getting Started

1. **Start the interactive shell**:
   ```bash
   uv run adoc-toolkit
   ```

2. **Set your environment** (required before making API calls):
   ```bash
   ADOC > use <environment-name>
   ```
   
   > **📋 Environment Setup**: Before using the toolkit, you need to configure your ADOC environments. See the [Environment Setup Guide](docs/environment-setup.md) for detailed instructions on configuring `config/environments.yaml`.

3. **Explore available commands**:
   ```bash
   ADOC > help
   ```

### Core Commands

#### Environment Management
- **`use <environment>`** - Switch to a different ADOC environment
- **`show-env`** - Display current environment configuration

> **📋 Environment Setup**: Configure your environments in `config/environments.yaml`. See the [Environment Setup Guide](docs/environment-setup.md) for detailed instructions.

#### API Access
- **`get <url> [params]`** - Make GET requests to ADOC API endpoints
  ```bash
  ADOC > get /catalog-server/api/assets/search name=Snowflake
  ADOC > get /catalog-server/api/asset-types
  ```

#### Data Export
- **`export-metrics`** - Export metrics data in various formats (JSON, CSV, Parquet, Avro)
- **`export-execution-metrics`** - Export execution metrics with filtering options

#### AI-Powered Features
- **`text-to-dq-policy`** - Generate data quality policies from natural language descriptions
- **`human-response`** - Get human-readable explanations of data quality results

#### Configuration
- **`set-config`** - Configure toolkit settings
- **`show-config`** - Display current configuration

#### Utilities
- **`history`** - View command history
- **`help [command]`** - Get help for commands
- **`exit`** - Exit the interactive shell

### Key Features

- **Interactive Shell**: Rich command-line interface with auto-completion
- **Environment Management**: Easy switching between different ADOC environments
- **API Integration**: Direct access to ADOC platform APIs with automatic authentication
- **Data Export**: Export metrics in multiple formats (JSON, CSV, Parquet, Avro)
- **AI Integration**: Generate data quality policies using LLM models
- **Cross-Platform**: Works on Windows, macOS, and Linux
- **Auto-completion**: Intelligent suggestions for commands and parameters

### Example Workflows

#### Basic API Exploration
```bash
ADOC > use se-demo
ADOC > get /catalog-server/api/asset-types
ADOC > get /catalog-server/api/assets/search name=Snowflake
```

#### Data Export
```bash
ADOC > export-metrics --format csv --output metrics.csv
ADOC > export-execution-metrics --status completed --days 7
```

#### AI-Powered Policy Generation
```bash
ADOC > text-to-dq-policy "Check that customer email addresses are valid and not null"
```

## 🛠️ Development

### Prerequisites
- Python 3.10+
- [uv](https://docs.astral.sh/uv/getting-started/installation/)
- Git

### Development Setup

```bash
# Clone and setup
git clone https://github.com/niranta-life/adoc-toolkit.git
cd adoc-toolkit

# Complete development setup (install + dev dependencies)
make dev-setup
```

### Available Make Commands

#### Setup Commands
```bash
make install          # Install dependencies using uv
make dev-setup        # Complete development setup (install + dev deps)
```

#### Testing Commands
```bash
make test             # Run all tests
make test-verbose     # Run tests with verbose output
make test-watch       # Run tests in watch mode (requires pytest-watch)
make test-coverage    # Run tests with coverage report
make test-export      # Run export-metrics command tests only
make test-http        # Run HTTP client tests only
make test-audit       # Run audit functionality tests only
make test-logs        # Run logging tests only
```

#### Code Quality Commands
```bash
make lint             # Run linting checks (ruff)
make format           # Format code (ruff format)
make type-check       # Run type checking (mypy)
make all-checks       # Run all code quality checks
```

#### Development Commands
```bash
make clean            # Clean up temporary files and caches
make clean-logs       # Clean up logs directory
make clean-output     # Clean up output directory
make clean-all        # Clean everything (temp files, logs, output)
make build            # Build the package
make run              # Run the interactive toolkit
```

#### Quick Test Combinations
```bash
make test-core        # Run core functionality tests
make test-cli         # Run CLI functionality tests
make ci-test          # Run all CI checks (format, lint, type-check, test)
```

### Development Workflow

1. **Setup development environment**:
   ```bash
   make dev-setup
   ```

2. **Run tests before making changes**:
   ```bash
   make test
   ```

3. **Make your changes** and run quality checks:
   ```bash
   make format lint type-check
   ```

4. **Test your changes**:
   ```bash
   make test
   ```

5. **Run the toolkit** to test interactively:
   ```bash
   make run
   ```

### Code Quality Standards

- **Type Hints**: Required for all public APIs and complex functions
- **Documentation**: Docstrings for all public functions and classes
- **Testing**: Comprehensive test coverage with pytest
- **Code Style**: Follow PEP 8, enforced by ruff
- **Line Length**: 88 characters maximum

### Project Structure

```
adoc-toolkit/
├── adoc_toolkit/           # Main package
│   ├── cli/               # Command-line interface
│   │   ├── commands/      # Individual command implementations
│   │   ├── interactive.py # Interactive processor
│   │   └── main.py        # CLI entry point
│   ├── models/            # Pydantic data models
│   ├── http/              # HTTP client and utilities
│   ├── llm/               # LLM integration
│   ├── audit/             # Audit functionality
│   └── tracing/           # Tracing and monitoring
├── bin/                   # Cross-platform launcher scripts
├── config/                # Configuration files and API references
├── docs/                  # Command documentation
├── tests/                 # Test files
├── Makefile               # Development commands
└── pyproject.toml         # Project configuration
```

### Adding New Commands

When adding new interactive commands, create three files:

1. **Command Implementation**: `adoc_toolkit/cli/commands/<command_name>_command.py`
2. **Test File**: `tests/test_<command_name>_command.py`
3. **Documentation**: `docs/<command_name>.md`

See the [Command Development Guide](docs/command-development.md) for detailed instructions.

## 📦 Optional Features

### Export Format Support

Install additional dependencies for extended export format support:

```bash
uv sync --extra export
```

This enables:
- **Parquet** export format (requires pyarrow)
- **Avro** export format (requires fastavro)

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch: `git checkout -b feature-name`
3. Make your changes following the development workflow
4. Run all checks: `make ci-test`
5. Submit a pull request

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `docs/` directory for detailed command documentation
- **Environment Setup**: See the [Environment Setup Guide](docs/environment-setup.md) for configuring your ADOC environments
- **Issues**: Report bugs and feature requests on GitHub
- **Help**: Use `help` command in the interactive shell for command assistance
