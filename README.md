# ADOC Toolkit

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)
[![Code Style: Ruff](https://img.shields.io/badge/code%20style-ruff-orange.svg)](https://docs.astral.sh/ruff/)

**Acceldata Observability Cloud (ADOC) Toolkit** — an interactive command-line tool for accessing ADOC APIs and exporting policy execution and metrics data.

> **Customer documentation:** See [`docs/ADOC_Toolkit_Customer_Guide.pdf`](docs/ADOC_Toolkit_Customer_Guide.pdf) for the full customer-facing guide, including export column applicability and N/A rules.

## Prerequisites

- **Python 3.10 or higher**
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** (recommended) or `pip`
- Network access to your ADOC instance (or offline install via S3 — see below)
- ADOC API credentials (`access_key` / `secret_key`)

## Installation

```bash
git clone <repository-url>
cd adoc-toolkit

# Install dependencies
uv sync

# Optional: Parquet / Avro export support
uv sync --extra export

# Run
uv run adoc-toolkit
```

### Cross-platform launchers

```bash
# Unix (Linux / macOS)
bin/adoc-toolkit

# Windows
bin\adoc-toolkit.bat
```

### Offline / air-gapped install (S3)

On a machine with internet access, publish dependency wheels:

```bash
make s3-push S3_PATH=s3://your-bucket/adoc-toolkit/packages
# or: bin/s3-push-packages.sh s3://your-bucket/adoc-toolkit/packages
```

On the target machine (AWS CLI required):

```bash
make s3-pull S3_PATH=s3://your-bucket/adoc-toolkit/packages
# or: bin/s3-pull-install.sh s3://your-bucket/adoc-toolkit/packages
```

## Environment setup

Create `config/environments.yaml` before using API or export commands:

```yaml
environments:
  cs-india:
    name: "cs-india"
    base_url: "https://cs-india.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"
    timezone: "Asia/Kolkata"   # Optional; default UTC. Use IANA names only.

default_environment: "cs-india"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Must match the environment key |
| `base_url` | Yes | ADOC instance URL |
| `access_key` | Yes | API access key |
| `secret_key` | Yes | API secret key |
| `timezone` | No | IANA timezone (e.g. `Asia/Kolkata`). Do **not** use abbreviations (`IST`, `EST`) |

Credentials can also use env vars: `${ADOC_ACCESS_KEY}`, `${ADOC_SECRET_KEY}`.

See [Environment Setup Guide](docs/environment-setup.md) for validation rules and security guidance.

## Quick start

```bash
uv run adoc-toolkit

ADOC > use cs-india
ADOC (cs-india) > help
ADOC (cs-india) > export-execution-metrics --backload -7d
ADOC (cs-india) > export-metrics --output-type csv
```

## Interactive commands

| Command | Aliases | Purpose |
|---------|---------|---------|
| `help` | `h`, `?` | List commands or show help for one command |
| `exit` | `quit`, `q` | Exit the shell |
| `use` | — | Switch active ADOC environment |
| `show-env` | `env` | Show current environment (keys masked) |
| `history` | `hist` | View command / execution history |
| `set-config` | `config`, `set` | Configure HTTP, logging, and audit settings |
| `get` | `g` | HTTP GET to ADOC API endpoints |
| `find-asset` | `search`, `search-asset`, `asset-search` | Search assets by name |
| `export-metrics` | `export`, `metrics` | Export rule / asset / alert summary metrics |
| `export-execution-metrics` | `exec-metrics`, `execution-metrics` | Export rule-level execution metrics |
| `example` | `ex`, `demo` | Developer template command |

> There is **no** separate `show-config` command. Use `set-config --list` or `set-config --show <key>`.

API and export commands require an active environment (`use <name>` first).

### Configuration (`set-config`)

```bash
ADOC > set-config --list
ADOC > set-config --show http.timeout
ADOC > set-config http.timeout 120
ADOC > set-config http.response.type table
ADOC > set-config log.level INFO
```

| Key | Default | Options |
|-----|---------|---------|
| `http.timeout` | `120` | 30, 60, 120, 300 |
| `http.retries` | `3` | 0, 1, 3, 5 |
| `http.proxy` | `null` | URL, or `none` to clear |
| `http.response.type` | `json` | `json`, `table`, `csv` |
| `log.level` | `TRACE` | `TRACE`, `DEBUG`, `INFO`, `ERROR` |
| `log.filepath` | `null` | File path |
| `log.rotate.onsize` | `10MB` | 10MB, 50MB, 100MB, 1GB |
| `log.rotate.ontime` | `120` | Minutes |
| `audit.logfile` | `null` | File path |

Stored in `config/adoc-toolkit-config.json`. Details: [set-config](docs/set_config.md).

## Data export

### `export-execution-metrics`

Exports rule-level execution metrics for one or more policy types. Supports incremental runs via a tracking file.

```bash
ADOC > export-execution-metrics
ADOC > export-execution-metrics --backload -7d --policy-types DATA_QUALITY,EQUALITY
ADOC > export-execution-metrics --output-type parquet --page-size 500
ADOC > export-execution-metrics --output-dir ./reports --output-filename exec-%d-%m-%y
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output-type` | `csv` | `csv` or `parquet` |
| `--output-dir` | `./output/execution-metrics/` | Output directory |
| `--output-filename` | `execution-metrics-%d-%m-%y-%h-%M` | Filename template; env name appended |
| `--backload` | *(none)* | Override tracking: `-7d`, `-12h`, `2024-01-15`, etc. (max 60 days) |
| `--policy-types` | `DATA_QUALITY,EQUALITY` | Comma-separated: `DATA_QUALITY`, `EQUALITY`, `DATA_DRIFT`, `PROFILE_ANOMALY`, `SCHEMA_DRIFT`, `FRESHNESS` |
| `--page-size` | `100` | API page size (1–1000) |

**Outputs (per run):**
- Main consolidated file: `{filename}_{env}.csv|parquet`
- Per-policy-type files when data exists (e.g. `data-quality-metrics-…`, `reconciliation-metrics-…`)
- Tracking file: `.last_run_tracking.json`

**Incremental behavior:**
- With `--backload` → uses that start time (ignores tracking file)
- Without `--backload` and no tracking file → last **30 days**
- Without `--backload` and tracking file exists → since last successful run

**N/A / applicability:** Policy-specific columns are filled with `"N/A"` when not applicable. Per-type files drop columns that are entirely N/A. Full matrix: [Customer Guide PDF](docs/ADOC_Toolkit_Customer_Guide.pdf) and [export-execution-metrics](docs/export_execution_metrics.md).

Key derived columns:
- `Datasource_Name` — first segment of `Table_Asset_Name` (not used for EQUALITY)
- `Left_Datasource_Name` / `Right_Datasource_Name` — from asset UIDs (EQUALITY only)
- `Rule_Identifier`, `Total_Failed_Records`, `Metric_Anomalous` (PROFILE_ANOMALY)

Note: **Labels** (`Label_Key` / `Label_Value`) are exported here. **Tags** are exported by `export-metrics` only.

### `export-metrics`

Exports enabled/active rules with latest execution metrics, asset info, and related alerts.

```bash
ADOC > export-metrics --output-type csv
ADOC > export-metrics --page-size 500 --output-dir ./reports
```

| Flag | Default | Description |
|------|---------|-------------|
| `--output-type` | `csv` | `csv`, `parquet`, or `avro` |
| `--output-dir` | `./output/export-metrics/` | Output directory |
| `--output-filename` | `ad-metrics-%d-%m-%y-%h-%M` | Filename template |
| `--page-size` | `100` | API page size (1–1000) |

**Columns include:** Rule Name, Rule ID, Rule Type, Asset ID, Execution Status, Execution Date ({timezone}), Quality Score, Records Processed, Execution Duration (ms), Open Alerts, **Tags**, plus asset and alert fields when available.

Tags are tag **names** only (not IDs), e.g. `{'critical', 'prod'}`, or `N/A` if none.

## API access

```bash
ADOC > get /catalog-server/api/asset-types
ADOC > get /catalog-server/api/assets/search name=Snowflake
ADOC > find-asset CALL_CENTER
```

Authentication uses `accessKey` and `secretKey` headers from the active environment.

### Endpoints used by exports

**export-execution-metrics**
- `GET /catalog-server/api/rules/executions`
- Result APIs: `…/data-quality|reconciliation|data-drift|profile-anomaly|schema-drift|data-cadence/executions/{id}/result`
- Policy detail APIs for each type
- `GET /catalog-server/api/assets/{id}/overview`, `…/assets/search`

**export-metrics**
- `GET /catalog-server/api/assets/list`
- `GET /catalog-server/api/rules?withLatestExecution=true&ruleStatus=ENABLED,ACTIVE`
- Incidents listing API for alerts

Full endpoint catalog: `config/adoc-toolkit-api-reference.json`.

## Project structure

```
adoc-toolkit/
├── adoc_toolkit/           # Main package
│   ├── cli/commands/       # Interactive commands
│   ├── models/             # Pydantic models
│   ├── http/               # HTTP client & response formatter
│   ├── audit/              # Audit logging
│   └── tracing/            # Tracing / monitoring
├── bin/                    # Launchers + S3 offline install scripts
├── config/                 # Config & API reference
├── docs/                   # Guides (incl. customer PDF)
├── tests/
├── Makefile
└── pyproject.toml
```

## Development

```bash
make dev-setup      # Install + dev deps
make test           # Run tests
make format lint type-check
make run            # Interactive shell
make s3-push S3_PATH=s3://bucket/path
make s3-pull S3_PATH=s3://bucket/path
```

See `make help` for all targets. Contribution guide: conventional commits, type hints, tests, ruff.

## Documentation

| Doc | Description |
|-----|-------------|
| [Customer Guide (PDF)](docs/ADOC_Toolkit_Customer_Guide.pdf) | Full customer-facing guide + column applicability |
| [Environment Setup](docs/environment-setup.md) | `environments.yaml` |
| [export-execution-metrics](docs/export_execution_metrics.md) | Execution metrics export |
| [set-config](docs/set_config.md) | Configuration reference |
| [get](docs/get.md) / [use](docs/use.md) / [find-asset](docs/find-asset.md) | Command guides |
| [HTTP Client](docs/http_client.md) | HTTP behavior |
| [Command Development](docs/command-development.md) | Adding commands |

## Optional export formats

```bash
uv sync --extra export
```

Enables **Parquet** (`pyarrow`) and **Avro** (`fastavro`) for `export-metrics`.  
`export-execution-metrics` supports **CSV** and **Parquet** only.

## License

Apache License 2.0 — see [LICENSE](LICENSE).

## Support

- Docs: `docs/` and the [Customer Guide PDF](docs/ADOC_Toolkit_Customer_Guide.pdf)
- Interactive help: `help` / `help <command>`
- Issues: report via your project repository
