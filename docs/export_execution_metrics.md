# Export Execution Metrics Command

## Overview

The `export-execution-metrics` command exports comprehensive execution metrics data from the ADOC platform, providing detailed rule-level performance metrics for policies. This command is designed for operational monitoring, compliance reporting, and performance analysis of data quality policies.

### Key Features

- **Multi-Policy Support**: Exports DATA_QUALITY, EQUALITY, DATA_DRIFT, PROFILE_ANOMALY, and SCHEMA_DRIFT policy types
- **Incremental Processing**: Efficient processing using tracking files to only export new data since the last run
- **Flexible Backloading**: Support for historical data retrieval with multiple date formats and relative time periods
- **Multiple Export Formats**: CSV (default) and Parquet formats with automatic data type handling
- **Comprehensive Data**: Combines policy executions, detailed rule performance, and asset information
- **Environment Integration**: Leverages the active environment configuration for API access
- **Progress Tracking**: Real-time progress indicators with detailed status updates
- **Data Validation**: Robust Pydantic-based validation with automatic type conversion and error handling

## Usage

```
export-execution-metrics [OPTIONS]
```

## Options

- `--output-type TYPE`: Output format: csv, parquet (default: csv)
- `--output-dir DIR`: Output directory (default: ./output/execution-metrics/)
- `--output-filename NAME`: Output filename template (default: execution-metrics-%d-%m-%y-%h-%M)
- `--backload OPTION`: Backload option to override tracking file (e.g., -30d, -10d, 2024-01-15)
- `--policy-types TYPES`: Comma-separated policy types to export (default: DATA_QUALITY,EQUALITY)
- `--help`: Show help message

### Filename Template Variables

The filename template supports the following variables:
- `%y`: Year (4 digits)
- `%m`: Month (2 digits)
- `%d`: Day (2 digits)
- `%h`: Hour (2 digits)
- `%M`: Minute (2 digits)

The environment name is automatically appended as a suffix if available.

## Features

### Incremental Processing

The command supports incremental processing by maintaining a tracking file (`.last_run_tracking.json`) in the output directory. This file stores:
- Last run timestamp
- Last run datetime
- Total records processed in the last run

On subsequent runs, only new execution data since the last run is processed, making the command efficient for regular scheduled exports.

### Backload Functionality

The `--backload` option provides flexible data retrieval from historical periods:

#### Supported Formats
- **Relative days**: `-10d`, `-30d`, `-60d` (1-60 days ago)
- **ISO dates**: `2024-01-15`
- **ISO datetime**: `2024-01-15T10:30:00`
- **US format**: `01/15/2024`
- **European format**: `15/01/2024`

#### Backload Behavior
- **With `--backload`**: Always overrides existing tracking file and starts from the specified time
- **Without `--backload`**: Uses existing tracking file for incremental processing, or defaults to 30 days ago for first run
- **Maximum range**: 60 days ago (configurable limit for performance)
- **Future dates**: Not allowed (validation prevents future date specification)

#### Use Cases
- **Data reprocessing**: Re-export data from a specific point in time
- **Historical analysis**: Get data from a particular date range
- **Recovery scenarios**: Recover from processing gaps or errors
- **Initial setup**: Configure the starting point for first-time runs

### Policy Type Support

The command supports multiple policy types with comprehensive data processing for each type:

#### Supported Policy Types
- **DATA_QUALITY**: Data quality rules and checks with detailed rule-level metrics
- **EQUALITY**: Reconciliation and comparison policies with threshold analysis
- **DATA_DRIFT**: Data drift detection policies with statistical analysis
- **PROFILE_ANOMALY**: Data profiling anomaly detection with pattern analysis
- **SCHEMA_DRIFT**: Schema change detection policies with structural analysis

#### Policy Type Processing
- **Multi-Type Support**: Each policy type is processed using its specific API endpoints
- **Unified Output**: All policy types are exported with consistent schema and format
- **Type-Specific Details**: Each policy type includes relevant metrics and configuration data
- **Cross-Type Analysis**: Enables comparison and analysis across different policy types

#### Policy Type Filtering

The `--policy-types` option allows you to specify which types of policies to export:

##### Available Policy Types
- **DATA_QUALITY**: Data quality rules and checks
- **EQUALITY**: Reconciliation and comparison policies  
- **DATA_DRIFT**: Data drift detection policies
- **PROFILE_ANOMALY**: Data profiling anomaly detection
- **SCHEMA_DRIFT**: Schema change detection policies

##### Policy Type Behavior
- **Default types**: DATA_QUALITY and EQUALITY (most commonly used)
- **Multiple types**: Specify comma-separated values (e.g., `DATA_QUALITY,DATA_DRIFT`)
- **Case insensitive**: Input is automatically converted to uppercase
- **Validation**: Only valid policy types are accepted

##### Use Cases
- **Focused analysis**: Export only specific policy types for targeted analysis
- **Performance optimization**: Reduce data volume by filtering to relevant policies
- **Compliance reporting**: Export only compliance-related policies (DATA_QUALITY, EQUALITY)
- **Monitoring dashboards**: Create specialized dashboards for specific policy types

### Data Sources

The command fetches and combines data from multiple ADOC API endpoints using efficient parallel processing:

1. **Policy Executions API**: Retrieves overall execution status, metadata, and performance scores
2. **Execution Details API**: Fetches detailed rule-level performance metrics for data quality policies
3. **Policy Details API**: Retrieves policy configuration, threshold settings, and rule versions
4. **Asset Catalog API**: Resolves table asset names and metadata from asset identifiers

The service intelligently merges data from these sources to create comprehensive execution metrics records with full context about policies, rules, assets, and performance outcomes.

### Export Formats

#### CSV Format
- Human-readable comma-separated values
- Compatible with Excel and other spreadsheet applications
- Automatic data type conversion and null value handling

#### Parquet Format
- Columnar storage format for efficient compression and querying
- Preserves data types and handles large datasets efficiently
- Requires `pyarrow` dependency: `uv add pyarrow`

### Output Data Schema

The exported data includes the following columns:

| Column | Description |
|--------|-------------|
| policy_name | Name of the data quality policy |
| policy_id | Unique identifier for the policy |
| rule_version | Version of the rule |
| exec_id | Execution identifier |
| table_asset_name | Name of the table asset |
| item_column_name | Column name being evaluated |
| pde | PDE (Physical Data Element) identifier |
| item_measurement_type | Type of measurement |
| rule_strategy | Threshold strategy |
| rule_lower_threshold | Lower threshold value |
| rule_upper_threshold | Upper threshold value |
| item_id | Rule item identifier |
| result | Execution result value |
| rows_scanned | Number of rows scanned |
| rows_failed | Number of rows that failed |
| end_ts | End timestamp (milliseconds) |
| execution_date | Execution datetime |
| execution_status | Status of the execution |
| policy_type | Type of policy |

### Progress Tracking

The command provides real-time progress updates with spinners for:
- Fetching policy executions with pagination
- Processing execution details for DQ policies
- Fetching policy details and asset information
- Merging and combining data
- Exporting to the specified format

### Parallel Processing

The command uses efficient parallel processing for:
- Paginated API calls for large datasets
- Concurrent fetching of policy and asset details
- Optimized data processing pipelines

### Data Validation and Type Safety

The command includes comprehensive data validation using Pydantic models with automatic type conversion and robust error handling:

#### Automatic Type Conversion
- **Integer IDs to Strings**: Policy IDs, execution IDs, and item IDs are automatically converted from integers to strings for consistency
- **Simple Values to Dictionaries**: API responses with simple numeric values are automatically wrapped in `{"value": <number>}` format
- **Timestamp Conversion**: Millisecond timestamps are converted to datetime objects for better readability
- **Data Type Validation**: All fields are validated according to their expected types with clear error messages

#### Robust Error Handling
- **API Data Inconsistencies**: Handles variations in API response formats gracefully
- **Missing Fields**: Provides default values for optional fields with proper null handling
- **Invalid Data**: Validates constraints like positive timestamps, valid enum values, and date ranges
- **Policy Type Validation**: Ensures only valid policy types are processed
- **Backload Validation**: Prevents future dates and enforces 60-day maximum range

#### Field Validation Examples
```json
// API returns integer ID
"policy_id": 70381
// Automatically converted to
"policy_id": "70381"

// API returns simple numeric value
"score": 100.0
// Automatically converted to
"score": {"value": 100.0}

// API returns millisecond timestamp
"end_ts": 1703505600000
// Automatically converted to
"execution_date": "2023-12-25T10:00:00"
```

### Command Auto-Completion

The command supports intelligent auto-completion for all options and values:

#### Option Completion
- `--output-type` completes with: `csv`, `parquet`
- `--backload` suggests: `-10d`, `-30d`, `-60d`, `2024-01-15`, `2024-01-15T10:30:00`
- `--policy-types` completes with: `DATA_QUALITY`, `EQUALITY`, `DATA_DRIFT`, `PROFILE_ANOMALY`, `SCHEMA_DRIFT`
- `--output-filename` provides template examples: `execution-metrics-%d-%m-%y-%h-%M`, `exec-metrics-%y%m%d`

#### Smart Context Awareness
- Only suggests unused options to avoid duplicates
- Provides contextual help based on current input
- Supports partial matching for faster typing
- Policy types support comma-separated completion (e.g., typing `DATA_QUALITY,E` suggests `DATA_QUALITY,EQUALITY`)

## Examples

### Basic Usage

Export to CSV with default settings (uses tracking file or defaults to 30 days ago):
```
ADOC (prod) > export-execution-metrics
```

### Backload Examples

Override tracking file and backload from 10 days ago:
```
ADOC (prod) > export-execution-metrics --backload -10d
```

Start from a specific date (overrides tracking file):
```
ADOC (prod) > export-execution-metrics --backload 2024-01-15
```

Start from a specific datetime (overrides tracking file):
```
ADOC (prod) > export-execution-metrics --backload "2024-01-15T10:30:00"
```

Backload with different date formats:
```
ADOC (prod) > export-execution-metrics --backload 01/15/2024  # US format
ADOC (prod) > export-execution-metrics --backload 15/01/2024  # European format
```

### Policy Type Examples

Export only DATA_QUALITY policies:
```
ADOC (prod) > export-execution-metrics --policy-types DATA_QUALITY
```

Export multiple policy types:
```
ADOC (prod) > export-execution-metrics --policy-types DATA_QUALITY,DATA_DRIFT
```

Export all drift and anomaly detection policies:
```
ADOC (prod) > export-execution-metrics --policy-types DATA_DRIFT,PROFILE_ANOMALY,SCHEMA_DRIFT
```

### Export Format Examples

Export to Parquet format:
```
ADOC (prod) > export-execution-metrics --output-type parquet
```

Combine policy types with Parquet export:
```
ADOC (prod) > export-execution-metrics --policy-types DATA_QUALITY --output-type parquet
```

Combine backload with policy types and Parquet export:
```
ADOC (prod) > export-execution-metrics --backload -30d --policy-types DATA_QUALITY,EQUALITY --output-type parquet
```

### Custom Output Directory

Save to a specific directory:
```
ADOC (prod) > export-execution-metrics --output-dir ./reports/execution-metrics
```

### Custom Filename Template

Use a custom filename template:
```
ADOC (prod) > export-execution-metrics --output-filename "exec-metrics-%y%m%d"
```

### Complete Example

Export with all custom options:
```
ADOC (prod) > export-execution-metrics --backload -15d --output-type parquet --output-dir ./reports --output-filename "detailed-metrics-%y-%m-%d"
```

## Output Files

### Data Export File

The main export file contains the execution metrics data in the specified format:
- CSV: `execution-metrics-25-12-2023-14-30_prod.csv`
- Parquet: `execution-metrics-25-12-2023-14-30_prod.parquet`

### Tracking File

The tracking file (`.last_run_tracking.json`) stores incremental processing state:
```json
{
  "last_run_timestamp": 1703505600000,
  "last_run_datetime": "2023-12-25T10:00:00",
  "total_records_processed": 1247
}
```

## Prerequisites

### Environment Setup

1. **Environment Configuration**: **REQUIRED** - Use the `use <environment>` command to set the active environment before running this command
2. **Credentials**: Ensure the environment has valid `accessKey` and `secretKey` configured
3. **Permissions**: The API keys must have access to:
   - Rules execution endpoints (`/api/v1/rules/executions`)
   - Data quality policy endpoints (`/api/v1/rules/executions/{executionId}/details`)
   - Policy details endpoints (`/api/v1/rules/{policyId}/details`)
   - Asset catalog endpoints (`/api/v1/assets/{assetId}`)

### Important Note
The `export-execution-metrics` command will not run unless an environment has been selected using the `use <environment>` command. If no environment is set, the command will display an error message prompting you to set an environment first.

### Dependencies

#### Required Dependencies
- pandas: Data processing and export
- rich: Progress tracking and console output
- httpx: HTTP client for API calls
- pydantic: Data validation and modeling

#### Optional Dependencies
- pyarrow: Required for Parquet format support
  ```bash
  uv add pyarrow
  ```

## Error Handling

The command includes comprehensive error handling for:

### HTTP Errors
- API endpoint failures with retry logic
- Authentication and authorization errors
- Network connectivity issues

### Data Processing Errors
- Invalid API response formats
- Missing or corrupted data fields
- Data type conversion failures

### File System Errors
- Permission issues with output directories
- Disk space limitations
- File locking conflicts

### Dependency Errors
- Missing required packages
- Version compatibility issues

## Performance Considerations

### Large Datasets
- Uses pagination for efficient memory usage
- Processes data in batches to avoid memory overflow
- Implements streaming data processing where possible

### API Rate Limiting
- Includes built-in retry logic with exponential backoff
- Respects API rate limits with appropriate delays
- Logs API performance metrics for monitoring

### Incremental Processing
- Only processes new data since last run
- Maintains state in tracking files
- Optimizes for regular scheduled execution

## Monitoring and Logging

### Tracing
The command supports distributed tracing with automatic instrumentation:
- HTTP request tracing
- Data processing step tracing
- Performance metrics collection

### Logging
Comprehensive logging includes:
- Command execution start/end
- Data processing statistics
- Error conditions and recovery
- Performance metrics

## Troubleshooting

### Common Issues

#### No Data Retrieved
```
Warning: No new execution metrics data found since last run.
```
**Solutions**: 
- Check if there are new policy executions since the last run
- Use `--backload` option to specify a different time range (e.g., `--backload -7d`)
- Delete the tracking file (`.last_run_tracking.json`) to reset incremental processing

#### Backload Validation Errors
```
Error: Backload cannot be more than 60 days (-60d)
```
**Solution**: Use a backload period within the 60-day limit.

```
Error: Backload date cannot be in the future
```
**Solution**: Ensure the specified date/time is in the past.

```
Error: Invalid backload format: xyz
```
**Solution**: Use supported formats like `-30d`, `2024-01-15`, or `2024-01-15T10:30:00`.

#### Policy Type Validation Errors
```
Error: Invalid policy types: ['INVALID_TYPE']. Valid types: ['DATA_DRIFT', 'DATA_QUALITY', 'EQUALITY', 'PROFILE_ANOMALY', 'SCHEMA_DRIFT']
```
**Solution**: Use only valid policy types from the supported list.

```
Error: At least one policy type must be specified
```
**Solution**: Provide at least one policy type in the comma-separated list.

```
Error: --policy-types requires a value
```
**Solution**: Specify policy types after the `--policy-types` option (e.g., `--policy-types DATA_QUALITY`).

#### Missing Dependencies
```
Error: pyarrow is required for Parquet format. Install with: uv add pyarrow
```
**Solution**: Install the required dependency or use CSV format instead.

#### Permission Errors
```
Error: HTTP error during data fetch: HTTP 403
```
**Solution**: Verify the environment credentials have the required API permissions.

#### Output Directory Issues
```
Error: Permission denied: ./output/execution-metrics/
```
**Solution**: Ensure write permissions for the output directory or specify a different directory.

### Debugging Options

#### Environment Variables
- `DEBUG_EXPORT=true`: Enable debug logging and temporary file retention
- `TRACE_ENABLED=true`: Enable detailed tracing output

#### Verbose Output
Use the logging configuration to increase verbosity for troubleshooting.

## Integration

### Scheduled Execution
The command is designed for regular scheduled execution:
- Use cron jobs or task schedulers
- Leverage incremental processing for efficiency
- Monitor tracking files for successful runs

### Data Pipeline Integration
- Export files can be consumed by ETL pipelines
- Parquet format provides efficient downstream processing
- Standardized schema supports automated data ingestion

### Monitoring Integration
- Tracing data can be exported to monitoring systems
- Log files support structured logging formats
- Performance metrics enable operational monitoring

## Related Commands

- [`export-metrics`](export_metrics.md): Export general metrics data
- [`use`](use.md): Set the active environment
- [`show-env`](show_env.md): Display current environment information

## Aliases

- `exec-metrics`
- `execution-metrics`