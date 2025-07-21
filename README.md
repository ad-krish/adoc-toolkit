# ADOC Toolkit

Acceldata Observability Cloud ("ADOC") toolkit for managing and interacting with ADOC SaaS.

## Installation

```bash
# Clone the repository
git clone https://github.com/niranta-life/adoc-toolkit.git
cd adoc-toolkit

# Install dependencies
uv sync

# Install with export format support (optional)
uv sync --extra export

# Install development dependencies
uv sync --dev

# Run tests
uv run pytest

# Code formatting and linting
uv run ruff format .
uv run ruff check .

# Type checking
uv run mypy .
```

## Usage

```bash
# Run interactive mode
uv run adoc-toolkit -i

# Or use the launcher scripts
bin/adoc-toolkit        # Unix (Linux/macOS)
bin\adoc-toolkit.bat    # Windows
```

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.
