# ADOC Toolkit — Customer Guide

**Acceldata Observability Cloud (ADOC) Toolkit**  
Interactive CLI for ADOC API access and policy metrics export

Version: 0.1.0  
Document type: Customer-facing user guide

---

## 1. Overview

The ADOC Toolkit is a command-line application that connects to your Acceldata Observability Cloud instance to:

- Explore ADOC APIs interactively
- Export **rule-level execution metrics** across multiple policy types
- Export **rule / asset / alert summary metrics**
- Manage environments, HTTP settings, logging, and audit trails

This guide describes installation, configuration, commands, export options, and **which CSV columns are applicable vs N/A** for each policy type.

---

## 2. Prerequisites

| Requirement | Notes |
|-------------|--------|
| Python 3.10+ | Required |
| [uv](https://docs.astral.sh/uv/) (recommended) or pip | Dependency management |
| Network access to ADOC | Or offline install via S3 |
| ADOC API credentials | Access key + secret key |
| AWS CLI | Only for S3 offline package install |

---

## 3. Installation

### 3.1 Standard install

```bash
git clone <repository-url>
cd adoc-toolkit
uv sync
uv sync --extra export   # optional: Parquet / Avro
uv run adoc-toolkit
```

Launchers:

- Unix: `bin/adoc-toolkit`
- Windows: `bin\adoc-toolkit.bat`

### 3.2 Offline / air-gapped install (S3)

**Publish packages** (machine with internet):

```bash
make s3-push S3_PATH=s3://your-bucket/adoc-toolkit/packages
```

**Install on target machine**:

```bash
make s3-pull S3_PATH=s3://your-bucket/adoc-toolkit/packages
```

Scripts: `bin/s3-push-packages.sh`, `bin/s3-pull-install.sh`.

---

## 4. Environment configuration

Create `config/environments.yaml`:

```yaml
environments:
  production:
    name: "production"
    base_url: "https://your-instance.acceldata.app"
    access_key: "YOUR_ACCESS_KEY"
    secret_key: "YOUR_SECRET_KEY"
    timezone: "UTC"

default_environment: "production"
```

| Field | Required | Description |
|-------|----------|-------------|
| `name` | Yes | Must match the YAML key |
| `base_url` | Yes | ADOC base URL |
| `access_key` | Yes | API access key |
| `secret_key` | Yes | API secret key |
| `timezone` | No | IANA timezone (default `UTC`). Use `Asia/Kolkata`, **not** `IST` |

Supports `${ADOC_ACCESS_KEY}` / `${ADOC_SECRET_KEY}` substitution.

**Timezone affects:** export datetime column headers (e.g. `Started_At(Asia/Kolkata)`), tracking-file timestamps.

---

## 5. Getting started

```bash
uv run adoc-toolkit

ADOC > use production
ADOC (production) > help
ADOC (production) > show-env
ADOC (production) > export-execution-metrics --backload -7d
```

You must select an environment with `use` before running API or export commands.

---

## 6. Command reference

| Command | Aliases | Purpose |
|---------|---------|---------|
| `help` | `h`, `?` | List commands or detailed help |
| `exit` | `quit`, `q` | Exit the shell |
| `use` | — | Switch environment |
| `show-env` | `env` | Show current environment (keys masked) |
| `history` | `hist` | Command / execution history |
| `set-config` | `config`, `set` | Configure toolkit settings |
| `get` | `g` | HTTP GET to ADOC APIs |
| `find-asset` | `search`, `search-asset`, `asset-search` | Search assets by name |
| `export-metrics` | `export`, `metrics` | Export rule/asset/alert summary |
| `export-execution-metrics` | `exec-metrics`, `execution-metrics` | Export rule-level execution metrics |
| `example` | `ex`, `demo` | Developer template (internal) |

**Note:** There is no separate `show-config` command. Use:

```bash
set-config --list
set-config --show http.timeout
```

---

## 7. Configuration (`set-config`)

| Key | Default | Options / notes |
|-----|---------|-----------------|
| `http.timeout` | 120 | 30, 60, 120, 300 (seconds) |
| `http.retries` | 3 | 0, 1, 3, 5 |
| `http.proxy` | null | Proxy URL; `none` to clear |
| `http.response.type` | json | `json`, `table`, `csv` |
| `log.level` | TRACE | `TRACE`, `DEBUG`, `INFO`, `ERROR` |
| `log.filepath` | null | Log file path |
| `log.rotate.onsize` | 10MB | 10MB, 50MB, 100MB, 1GB |
| `log.rotate.ontime` | 120 | Minutes |
| `audit.logfile` | null | Audit log path |

Examples:

```bash
set-config http.timeout 120
set-config http.response.type table
set-config log.level INFO
set-config audit.logfile ./audit.log
```

---

## 8. export-execution-metrics

### 8.1 Purpose

Exports detailed **rule-level** performance metrics for ADOC policies, for operational monitoring, compliance, and analytics.

Supported policy types:

| CLI value | Notes |
|-----------|--------|
| `DATA_QUALITY` | Default |
| `EQUALITY` | Reconciliation policies (default) |
| `DATA_DRIFT` | |
| `PROFILE_ANOMALY` | |
| `SCHEMA_DRIFT` | |
| `FRESHNESS` | Uses DATA_CADENCE APIs internally |

### 8.2 Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output-type` | `csv` | `csv` or `parquet` |
| `--output-dir` | `./output/execution-metrics/` | Output directory |
| `--output-filename` | `execution-metrics-%d-%m-%y-%h-%M` | Template; env name appended |
| `--backload` | none | Override start time (see below) |
| `--policy-types` | `DATA_QUALITY,EQUALITY` | Comma-separated list |
| `--page-size` | `100` | API page size 1–1000 |

Filename template variables: `%y` year, `%m` month, `%d` day, `%h` hour, `%M` minute.

### 8.3 Backload formats

| Format | Example | Limits |
|--------|---------|--------|
| Relative hours | `-12h` | 1–1440 hours |
| Relative days | `-7d` | 1–60 days |
| ISO date | `2024-01-15` | Not in the future |
| ISO datetime | `2024-01-15T10:30:00` | |
| US date | `01/15/2024` | |
| EU date | `15/01/2024` | |

### 8.4 Incremental tracking

File: `{output-dir}/.last_run_tracking.json`

| Scenario | Start time used |
|----------|-----------------|
| `--backload` provided | Backload value (tracking ignored) |
| No tracking file | 30 days ago |
| Tracking file exists | `last_run_timestamp` from file |

### 8.5 Output files

| File | When |
|------|------|
| `{filename}_{env}.csv\|parquet` | Always — consolidated |
| `data-quality-metrics-…` | DATA_QUALITY rows exist |
| `reconciliation-metrics-…` | EQUALITY rows exist |
| `data-drift-metrics-…` | DATA_DRIFT rows exist |
| `freshness-metrics-…` | FRESHNESS rows exist |
| `schema-drift-metrics-…` | SCHEMA_DRIFT rows exist |
| `profile-anomaly-metrics-…` | PROFILE_ANOMALY rows exist |
| `.last_run_tracking.json` | Updated after successful run |

Per-policy-type files **drop columns that are entirely N/A** for that type.

### 8.6 Examples

```bash
export-execution-metrics
export-execution-metrics --backload -7d
export-execution-metrics --policy-types DATA_QUALITY,EQUALITY,DATA_DRIFT,FRESHNESS
export-execution-metrics --output-type parquet --page-size 500
export-execution-metrics --output-dir ./reports --backload 2024-06-01
```

---

## 9. Column applicability & N/A rules

### 9.1 How N/A works

| Situation | Export behavior |
|-----------|-----------------|
| Column not applicable to a policy type | Literal `"N/A"` in the **consolidated** CSV |
| Column applicable but value missing | Empty / null (not forced to N/A) |
| Null datetime | String `"null"` |
| Within EQUALITY only | Some fields use `"NOT_APPLICABLE"` (see §9.3) |
| Per-type CSV | Columns that are all N/A or all null are **removed** |

### 9.2 Consolidated CSV — applicability matrix

**Legend:** P = Populated when data exists · N/A = Explicitly not applicable · S = Synthetic label · — = empty/null if missing

#### Common / shared columns

| Column | DATA_QUALITY | EQUALITY | DATA_DRIFT | FRESHNESS | SCHEMA_DRIFT | PROFILE_ANOMALY |
|--------|:------------:|:--------:|:----------:|:---------:|:------------:|:---------------:|
| Policy_Name | P | P | P | P | P | P |
| Policy_ID | P | P | P | P | P | P |
| Rule_Version | P | P | P | P | P | P |
| Execution_ID | P | P | P | P | P | P |
| Rule_ID | P | P | P | P | P | P |
| Label_Key | P | P | S | S | S | N/A |
| Label_Value | P | P | S | S | S | N/A |
| Item_Measurement_Type | P | P* | P | P | N/A | P |
| Rule_Identifier | P | P | P | P | N/A | P |
| Rule_Success_Rate | P | P | P | P | N/A | N/A |
| Rows_Scanned | P | P | N/A | N/A | N/A | N/A |
| Rows_Failed | P | P | N/A | N/A | N/A | N/A |
| Total_Failed_Records | P | P | N/A | N/A | N/A | N/A |
| Rule_Result_Status | P | P | P | P | P | N/A |
| Overall_Policy_Status | P | P | P | P | P | P |
| Overall_Policy_Quality_Score(Percentage) | P | P | P | P | P | P |
| Started_At({tz}) | P | P | P | P | P | P |
| Finished_At({tz}) | P | P | P | P | P | P |
| Execution_Date({tz}) | P | P | P | P | P | P |
| Execution_Status | P | P | P | P | P | P |
| Policy_Type | P | P | P | P | P | P |
| Policy_Enabled | P | P | P | P | P | P |
| Policy_Description | P | P | P | P | P | N/A |
| Rule_Description | P | P | N/A | N/A | N/A | N/A |

\* EQUALITY measurement types: `EQUALITY_MATCH` or `ROW_COUNT_MATCH`.

#### DATA_QUALITY–oriented columns

| Column | DATA_QUALITY | EQUALITY | DATA_DRIFT | FRESHNESS | SCHEMA_DRIFT | PROFILE_ANOMALY |
|--------|:------------:|:--------:|:----------:|:---------:|:------------:|:---------------:|
| Datasource_Name | P (derived) | N/A | P | P | P | P |
| Table_Asset_Name | P | N/A | P | P | P | P |
| Item_Column_Name | P | N/A | P | N/A | N/A | P |
| Rule_Strategy | P | N/A | P | P | N/A | N/A |
| Rule_Lower_Threshold | P | N/A | P | P | N/A | N/A |
| Rule_Upper_Threshold | P | N/A | P | P | N/A | N/A |

#### EQUALITY / reconciliation columns

| Column | DATA_QUALITY | EQUALITY | Others |
|--------|:------------:|:--------:|:------:|
| Left_Column | N/A | P† | N/A |
| Right_Column | N/A | P† | N/A |
| Left_Rows_Scanned | N/A | P‡ | N/A |
| Right_Rows_Scanned | N/A | P‡ | N/A |
| Use_For_Joining | N/A | P† | N/A |
| Operation | N/A | P | N/A |
| Join_Type | N/A | P | N/A |
| Left_Datasource_Name | N/A | P (derived) | N/A |
| Left_ASSET_UID | N/A | P | N/A |
| Right_Datasource_Name | N/A | P (derived) | N/A |
| Right_ASSET_UID | N/A | P | N/A |

† For `ROW_COUNT_MATCH` rows: `Left_Column`, `Right_Column`, `Use_For_Joining` = `"NOT_APPLICABLE"`.  
‡ For `EQUALITY_MATCH` rows: `Left_Rows_Scanned`, `Right_Rows_Scanned` = `"NOT_APPLICABLE"`.

#### Policy-type–specific columns

| Column | Applicable only for |
|--------|---------------------|
| Drift_Threshold | DATA_DRIFT |
| Anomaly_Detected | FRESHNESS |
| Threshold_Breached | FRESHNESS |
| Metric_Anomalous | PROFILE_ANOMALY |
| Asset_Addition | SCHEMA_DRIFT |
| Asset_Deletion | SCHEMA_DRIFT |
| Data_Type | SCHEMA_DRIFT |
| Asset_Relation_Change | SCHEMA_DRIFT |
| Asset_Metadata | SCHEMA_DRIFT |
| Metadata_Configs | SCHEMA_DRIFT |

All other policy types get `"N/A"` for these columns in the consolidated file.

### 9.3 EQUALITY internal NOT_APPLICABLE values

| Item_Measurement_Type | Fields set to NOT_APPLICABLE |
|-----------------------|------------------------------|
| `ROW_COUNT_MATCH` | Left_Column, Right_Column, Use_For_Joining |
| `EQUALITY_MATCH` | Left_Rows_Scanned, Right_Rows_Scanned |

In reconciliation-only files, `Rows_Failed` may be renamed to `Rows_Failed/Drift` when ROW_COUNT_MATCH rows are present.

### 9.4 Derived columns

| Column | How derived | When N/A |
|--------|-------------|----------|
| Datasource_Name | First segment before `.` in Table_Asset_Name | EQUALITY |
| Left_Datasource_Name | First segment of Left_ASSET_UID | Non-EQUALITY |
| Right_Datasource_Name | First segment of Right_ASSET_UID | Non-EQUALITY |
| Rule_Identifier | From policy item / mapping / display name | SCHEMA_DRIFT |
| Total_Failed_Records | Execution `failedRows` | Drift / Freshness / Schema / Profile |
| Metric_Anomalous | `isMetricAnomalous` from profile anomaly details | All except PROFILE_ANOMALY |

### 9.5 Labels vs tags

| Concept | Command | Columns | Source |
|---------|---------|---------|--------|
| Labels | export-execution-metrics | Label_Key, Label_Value | Policy detail labels (one CSV row per label) |
| Tags | export-metrics | Tags | `rule.tags[].name` only (names, not IDs) |

Synthetic labels:

- DATA_DRIFT: `{columnName}-{metricType}`
- FRESHNESS: `{measurementType}-{strategy}`
- SCHEMA_DRIFT: Policy_Name / item id

---

## 10. export-metrics

### 10.1 Purpose

Exports a summary of **enabled/active rules** with latest execution metrics, catalog asset attributes, and related alert/incident data.

### 10.2 Options

| Flag | Default | Description |
|------|---------|-------------|
| `--output-type` | `csv` | `csv`, `parquet`, `avro` |
| `--output-dir` | `./output/export-metrics/` | Output directory |
| `--output-filename` | `ad-metrics-%d-%m-%y-%h-%M` | Template + env suffix |
| `--page-size` | `100` | 1–1000 |

Parquet requires `pyarrow`; Avro requires `fastavro` (`uv sync --extra export`).

### 10.3 Columns

**Always present**

| Column | Notes |
|--------|--------|
| Rule Name | |
| Rule ID | |
| Rule Type | |
| Asset ID | |
| Execution Status | |
| Execution Date ({timezone}) | `"null"` if missing |
| Quality Score | N/A if missing |
| Records Processed | N/A if missing |
| Execution Duration (ms) | N/A if missing |
| Open Alerts | N/A if missing |
| Tags | Tag **names** as a set string, or N/A |

**When asset found in catalog**

Asset Name, Asset UID, Source Type, Asset Type, Asset Quality Score, Open Alert Count, Open Alert ID, Open Alert States

**When alert/incident found**

Alert ID, Alert Total Count, Alert Created At ({timezone}), Alert Updated At ({timezone}), Alert Status, Alert Assignee, Alert Updated By, Alert Severity

### 10.4 Examples

```bash
export-metrics
export-metrics --output-type csv --page-size 500
export-metrics --output-dir ./reports --output-filename summary-%d-%m-%y
```

---

## 11. API endpoints used

### export-execution-metrics

- `GET /catalog-server/api/rules/executions`
- Result: `/catalog-server/api/rules/{data-quality|reconciliation|data-drift|profile-anomaly|schema-drift|data-cadence}/executions/{id}/result`
- Policy details for each type
- `GET /catalog-server/api/assets/{id}/overview`
- `GET /catalog-server/api/assets/search`

### export-metrics

- `GET /catalog-server/api/assets/list`
- `GET /catalog-server/api/rules?withLatestExecution=true&ruleStatus=ENABLED,ACTIVE`
- Incidents listing API for alerts

### Other

- `find-asset` → `/catalog-server/api/assets/search?name=…`
- `get` → any documented path in `config/adoc-toolkit-api-reference.json`

Auth headers: `accessKey`, `secretKey` from the active environment.

---

## 12. Recommended workflows

### Daily incremental execution metrics

```bash
ADOC > use production
ADOC (production) > export-execution-metrics
```

### Weekly historical refresh

```bash
ADOC (production) > export-execution-metrics --backload -7d --policy-types DATA_QUALITY,EQUALITY,DATA_DRIFT,FRESHNESS,SCHEMA_DRIFT,PROFILE_ANOMALY
```

### Summary metrics for dashboards

```bash
ADOC (production) > export-metrics --output-type csv --page-size 500
```

### Explore APIs

```bash
ADOC (production) > get /catalog-server/api/asset-types
ADOC (production) > find-asset CALL_CENTER
```

---

## 13. Troubleshooting

| Issue | What to check |
|-------|----------------|
| “No environment selected” | Run `use <environment>` |
| Empty export | Broaden `--backload`, check `--policy-types`, verify policies ran in ADOC |
| Many N/A columns | Expected in consolidated CSV; use per-type files for cleaner schemas |
| Parquet/Avro fails | `uv sync --extra export` |
| Auth / 401 | Credentials in `environments.yaml`; key format |
| Timezone wrong | Use IANA names (`Asia/Kolkata`), not `IST` |
| Offline install | AWS CLI credentials; correct `S3_PATH` |

---

## 14. Support & related docs

- Interactive help: `help`, `help <command>`
- Environment setup: `docs/environment-setup.md`
- Execution metrics detail: `docs/export_execution_metrics.md`
- Configuration: `docs/set_config.md`
- HTTP client: `docs/http_client.md`

---

*Generated for customer use from the ADOC Toolkit codebase. Column applicability reflects current export implementation.*
