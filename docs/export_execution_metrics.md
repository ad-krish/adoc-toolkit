# Export Execution Metrics Command

## Overview

The `export-execution-metrics` command exports detailed execution metrics data from the ADOC platform, focusing on DATA_QUALITY and EQUALITY (reconciliation) policy types. It provides comprehensive rule-level performance metrics for data quality policies with incremental processing capabilities.

## Usage

```
export-execution-metrics [OPTIONS]
```

## Options

- `--output-type TYPE`: Output format: csv, parquet (default: csv)
- `--output-dir DIR`: Output directory (default: ./output/execution-metrics/)
- `--output-filename NAME`: Output filename template (default: execution-metrics-%d-%m-%y-%h-%M)
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

### Data Sources

The command fetches and combines data from multiple ADOC API endpoints:

1. **Policy Executions**: Overall execution status and metadata
2. **Execution Details**: Detailed rule-level performance metrics for DQ policies
3. **Policy Details**: Policy configuration and asset information
4. **Asset Information**: Table asset names and metadata

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

## Examples

### Basic Usage

Export to CSV with default settings:
```
ADOC (prod) > export-execution-metrics
```

### Export to Parquet

Export to Parquet format:
```
ADOC (prod) > export-execution-metrics --output-type parquet
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
ADOC (prod) > export-execution-metrics --output-type parquet --output-dir ./reports --output-filename "detailed-metrics-%y-%m-%d"
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

1. **Environment Configuration**: Use the `use <environment>` command to set the active environment
2. **Credentials**: Ensure the environment has valid `accessKey` and `secretKey` configured
3. **Permissions**: The API keys must have access to:
   - Rules execution endpoints
   - Data quality policy endpoints
   - Asset catalog endpoints

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
**Solution**: Check if there are new policy executions since the last run, or delete the tracking file to force a full export.

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