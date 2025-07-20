# ADOC Toolkit

Acceldata Observability Cloud ("ADOC") toolkit for managing and interacting with ADOC SaaS.

## Installation

```bash
# Clone the repository
git clone <repository-url>
cd adoc-toolkit

# Install dependencies
uv sync

# Install with export format support (optional)
uv sync --extra export
```

## Optional Dependencies

The toolkit supports additional export formats that require optional dependencies:

- **Parquet format**: Requires `pyarrow` package
- **Avro format**: Requires `fastavro` package

To install these dependencies:

```bash
# Install all export format dependencies
uv sync --extra export

# Or install individually
uv add pyarrow    # For Parquet support
uv add fastavro   # For Avro support
```

## Usage

### Interactive Mode

```bash
# Run interactive mode
uv run adoc-toolkit -i

# Or use the launcher scripts
bin/adoc-toolkit        # Unix (Linux/macOS)
bin\adoc-toolkit.bat    # Windows
```

### Export Metrics

The `export-metrics` command supports multiple output formats:

```bash
# Basic CSV export (default)
export-metrics

# Export to Parquet format (requires pyarrow)
export-metrics --output-type parquet

# Export to Avro format (requires fastavro)
export-metrics --output-type avro

# Custom output directory and filename
export-metrics --output-dir ./reports --output-filename "metrics-%Y%m%d"
```

**Features:**
- Automatic environment name suffix in filenames
- Auto-completion support for all options
- Configurable output directory (defaults to `./output/export-metrics/`)
- Comprehensive error handling and dependency checking
- Smart data type conversion for Parquet/Avro formats (handles "N/A" values, mixed types, datetime formatting)
- Deep statistics and insights display (rule distributions, quality scores, execution status, alerts analysis)
- Comprehensive tracing support with nested call visualization (requires TRACE log level)

## Logging and Tracing

The toolkit supports multiple log levels with a hierarchical structure:

- **TRACE**: Includes all messages (TRACE + DEBUG + INFO + ERROR) + detailed operation tracing
- **DEBUG**: Includes DEBUG + INFO + ERROR messages
- **INFO**: Includes INFO + ERROR messages (default)
- **ERROR**: Includes only ERROR messages

To enable detailed tracing for export-metrics operations, set the log level to TRACE in your configuration.

## Development

```bash
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

## License

Apache License 2.0 - see [LICENSE](LICENSE) file for details.
