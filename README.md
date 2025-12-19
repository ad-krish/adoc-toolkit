 # ADOC Toolkit

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code Style: Black](https://img.shields.io/badge/code%20style-black-000000.svg)](https://github.com/psf/black)
[![Tests](https://img.shields.io/badge/tests-passing-brightgreen)](https://github.com/niranta-life/adoc-toolkit/actions)
[![Docs](https://img.shields.io/badge/docs-passing-brightgreen)](https://github.com/niranta-life/adoc-toolkit)
[![Contributions Welcome](https://img.shields.io/badge/contributions-welcome-brightgreen)](https://github.com/niranta-life/adoc-toolkit/blob/main/CONTRIBUTING.md)

**Acceldata Observability Cloud ("ADOC") toolkit** for managing and interacting with ADOC SaaS platform. This interactive command-line tool provides easy access to ADOC APIs, data export capabilities, and AI-powered data quality policy generation.

## 🚀 Quick Start

### Prerequisites
- **Python 3.10 or higher**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** (recommended) or pip

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

2. **Configure your environment** (required before making API calls):
   ```bash
   ADOC > use <environment-name>
   ```
   
   > **📋 Environment Setup**: Before using the toolkit, you need to configure your ADOC environments. See the [Environment Setup Guide](docs/environment-setup.md) for detailed instructions on configuring `config/environments.yaml`.

3. **Explore available commands**:
   ```bash
   ADOC > help
   ```

### Interactive CLI Features

The ADOC Toolkit provides a rich interactive command-line interface with several productivity features:

- **Command History Navigation**: Use ↑ and ↓ arrow keys to browse through your command history
- **Auto-completion**: Press Tab to get intelligent suggestions for commands and parameters
- **Command History**: Use the `history` command to view and recall previous commands
- **Environment Switching**: Easily switch between different ADOC environments
- **Rich Output**: Colorized output and formatted tables for better readability

### Core Commands

#### Environment Management
- **[`use`](docs/use.md)** - Switch to a different ADOC environment
- **[`show-env`](docs/show_env.md)** - Display current environment configuration

> **📋 Environment Setup**: Configure your environments in `config/environments.yaml`. See the [Environment Setup Guide](docs/environment-setup.md) for detailed instructions.

##### Timezone Configuration

The toolkit supports configurable timezones for datetime fields in exported data. By default, all timestamps use **UTC**, but you can configure each environment to use a specific timezone.

**Configuration** (`config/environments.yaml`):
```yaml
environments:
  cs-india:
    name: "cs-india"
    base_url: "https://cs-india.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"
    timezone: "Asia/Kolkata"  # Optional, defaults to UTC
```

**Supported Timezones**: Use [IANA timezone names](https://en.wikipedia.org/wiki/List_of_tz_database_time_zones):
- `UTC` (default)
- `America/New_York` (US Eastern Time)
- `America/Los_Angeles` (US Pacific Time)
- `Europe/London` (UK Time)
- `Asia/Kolkata` (Indian Standard Time)
- `Asia/Tokyo` (Japan Standard Time)
- `Australia/Sydney` (Australian Eastern Time)
- And many more...

**⚠️ Important**: Use full IANA timezone names (e.g., `Asia/Kolkata`), **not** abbreviations (e.g., `IST`, `PST`, `EST`). Abbreviations are ambiguous and not supported.

**What Gets Affected**:
- 📊 **Exported Data**: Column headers include timezone (e.g., `execution_date (UTC)` or `execution_date (Asia/Kolkata)`) in both `export-execution-metrics` and `export-metrics` commands
- 📁 **Tracking Files**: Timestamps in `.last_run_tracking.json` use configured timezone
- ⏰ **All DateTime Fields**: Automatically converted to your configured timezone

**Example Output**:
```csv
policy_name,execution_date (Asia/Kolkata),rows_scanned
MyPolicy,2025-11-05 23:54:17,1000
```

#### API Access
- **[`get`](docs/get.md)** - Make GET requests to ADOC API endpoints
  ```bash
  ADOC > get /catalog-server/api/assets/search name=Snowflake
  ADOC > get /catalog-server/api/asset-types
  ```

#### Data Export
- **[`export-metrics`](docs/export_execution_metrics.md)** - Export metrics data in various formats (JSON, CSV, Parquet, Avro)
- **[`export-execution-metrics`](docs/export_execution_metrics.md)** - Export execution metrics with filtering options

#### AI-Powered Features
- **[`text-to-dq-policy`](docs/text_to_dq_policy.md)** - Generate data quality policies from natural language descriptions
- **[`human-response`](docs/human_response.md)** - Get human-readable explanations of data quality results

#### Configuration
- **[`set-config`](docs/set_config.md)** - Configure toolkit settings
- **[`show-config`](docs/set_config.md)** - Display current configuration

#### Utilities
- **[`history`](docs/history.md)** - View command history
- **[`help`](docs/help.md)** - Get help for commands
- **[`find-asset`](docs/find-asset.md)** - Search for assets
- **`exit`** - Exit the interactive shell

### Key Features

- **Interactive Shell**: Rich command-line interface with auto-completion and command history navigation
- **Command History**: Use ↑/↓ arrow keys to navigate through previous commands
- **Environment Management**: Easy switching between different ADOC environments
- **Timezone Support**: Configurable timezone for datetime fields with automatic conversion (UTC default)
- **API Integration**: Direct access to ADOC platform APIs with automatic authentication
- **Data Export**: Export metrics in multiple formats (JSON, CSV, Parquet, Avro) with timezone-aware timestamps
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

#### Timezone-Aware Data Export
```bash
# Configure timezone in config/environments.yaml:
# timezone: "Asia/Kolkata"

ADOC > use cs-india
ADOC > export-execution-metrics
# Output CSV will have: execution_date (Asia/Kolkata) column
# All timestamps automatically converted to Indian Standard Time
```

## 📚 Documentation

### User Guides
- **[Environment Setup](docs/environment-setup.md)** - Configure ADOC environments
- **[HTTP Client Usage](docs/http_client.md)** - Understanding HTTP requests and responses
- **[LLM Configuration](docs/llm_config.md)** - Configure AI/LLM features
- **[LLM Client Usage](docs/llm_client_usage.md)** - Using AI-powered features
- **[Tracing Guide](docs/tracing-guide.md)** - Debugging and monitoring

### Command Reference
- **[get](docs/get.md)** - HTTP GET requests with auto-completion
- **[use](docs/use.md)** - Environment management
- **[show-env](docs/show_env.md)** - Display environment configuration
- **[set-config](docs/set_config.md)** - Configuration management
- **[history](docs/history.md)** - Command history and recall
- **[help](docs/help.md)** - Built-in help system
- **[find-asset](docs/find-asset.md)** - Asset search functionality
- **[export-execution-metrics](docs/export_execution_metrics.md)** - Data export capabilities
- **[text-to-dq-policy](docs/text_to_dq_policy.md)** - AI-powered policy generation
- **[human-response](docs/human_response.md)** - Human-readable explanations

### Development Guides
- **[Command Development](docs/command-development.md)** - How to add new commands

## 🛠️ Development

### Prerequisites
- **Python 3.10+**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)**
- **Git**

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

## 🤝 Contributing

We welcome contributions from the community! This guide will help you get started.

### How to Contribute

#### 1. **Fork and Clone**
```bash
# Fork the repository on GitHub, then clone your fork
git clone https://github.com/YOUR_USERNAME/adoc-toolkit.git
cd adoc-toolkit

# Add the original repository as upstream
git remote add upstream https://github.com/niranta-life/adoc-toolkit.git
```

#### 2. **Setup Development Environment**
```bash
# Install dependencies and development tools
make dev-setup

# Verify everything works
make test
```

#### 3. **Create a Feature Branch**
```bash
# Create and switch to a new branch
git checkout -b feature/your-feature-name

# Or for bug fixes
git checkout -b fix/your-bug-description
```

#### 4. **Make Your Changes**

Follow our development standards:

- **Code Style**: Follow PEP 8 (enforced by ruff)
- **Type Hints**: Add type hints to all public functions
- **Documentation**: Add docstrings to all public functions and classes
- **Testing**: Write tests for new functionality
- **Documentation**: Update relevant documentation

#### 5. **Test Your Changes**
```bash
# Run all quality checks
make ci-test

# Run specific test suites
make test-cli        # CLI functionality tests
make test-http       # HTTP client tests
make test-export     # Export functionality tests

# Test interactively
make run
```

#### 6. **Commit Your Changes**
```bash
# Use conventional commit messages
git commit -m "feat: add new command for asset search"
git commit -m "fix: resolve HTTP timeout issue"
git commit -m "docs: update environment setup guide"
```

#### 7. **Push and Create Pull Request**
```bash
# Push your branch
git push origin feature/your-feature-name

# Create a pull request on GitHub
```

### Contribution Guidelines

#### **Code Standards**
- **Python 3.10+**: Use modern Python features
- **Type Hints**: Required for all public APIs
- **Docstrings**: Use Google-style docstrings
- **Testing**: Maintain >90% test coverage
- **Linting**: Code must pass ruff checks

#### **Commit Message Format**
Use [Conventional Commits](https://www.conventionalcommits.org/):
```
feat: add new command for data export
fix: resolve authentication timeout issue
docs: update environment setup guide
test: add tests for new export functionality
refactor: simplify HTTP client configuration
```

#### **Pull Request Process**
1. **Description**: Clearly describe what you're changing and why
2. **Testing**: Include tests for new functionality
3. **Documentation**: Update relevant documentation
4. **Screenshots**: Include screenshots for UI changes
5. **Checklist**: Use the PR template checklist

#### **What We're Looking For**
- **Bug Fixes**: Clear, reproducible bug reports with fixes
- **New Features**: Well-designed, tested new functionality
- **Documentation**: Improvements to guides and examples
- **Performance**: Optimizations that improve user experience
- **Testing**: Additional test coverage

#### **Getting Help**
- **Issues**: Use GitHub Issues for bug reports and feature requests
- **Discussions**: Use GitHub Discussions for questions and ideas
- **Documentation**: Check the `docs/` directory for detailed guides

### Development Resources

#### **Key Documentation**
- **[Command Development Guide](docs/command-development.md)** - How to add new commands
- **[Environment Setup](docs/environment-setup.md)** - Development environment setup
- **[HTTP Client Usage](docs/http_client.md)** - Understanding HTTP integration
- **[LLM Configuration](docs/llm_config.md)** - AI/LLM feature development

#### **Testing Guidelines**
- **Unit Tests**: Test individual functions and classes
- **Integration Tests**: Test command interactions
- **CLI Tests**: Test command-line interface behavior
- **Mock External Services**: Don't rely on external APIs in tests

#### **Code Review Checklist**
- [ ] Code follows project style guidelines
- [ ] Type hints are present and correct
- [ ] Docstrings are complete and accurate
- [ ] Tests are comprehensive and pass
- [ ] Documentation is updated
- [ ] No breaking changes (or clearly documented)

## 📦 Optional Features

### Export Format Support

Install additional dependencies for extended export format support:

```bash
uv sync --extra export
```

This enables:
- **Parquet** export format (requires pyarrow)
- **Avro** export format (requires fastavro)

## 📄 License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.

## 🆘 Support

- **Documentation**: Check the `docs/` directory for detailed command documentation
- **Environment Setup**: See the [Environment Setup Guide](docs/environment-setup.md) for configuring your ADOC environments
- **Issues**: Report bugs and feature requests on [GitHub Issues](https://github.com/niranta-life/adoc-toolkit/issues)
- **Discussions**: Ask questions and share ideas on [GitHub Discussions](https://github.com/niranta-life/adoc-toolkit/discussions)
- **Help**: Use `help` command in the interactive shell for command assistance

---

**Made with ❤️ by the ADOC Toolkit Team**
