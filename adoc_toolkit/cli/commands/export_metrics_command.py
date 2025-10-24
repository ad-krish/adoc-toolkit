"""Export metrics command implementation."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table

from ...http import ADOCHTTPClient, HTTPError
from ...logs import log_error, log_info
from ...tracing import TraceableMixin, trace_method
from .base import Command


# Pure functional utilities
def parse_command_args(args: list[str]) -> dict[str, Any]:
    """Parse command line arguments into a dictionary.

    Args:
        args: List of command line arguments

    Returns:
        Dictionary of parsed arguments

    Raises:
        ValueError: If argument parsing fails
    """
    parsed = {}
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--help":
            parsed["help"] = True
        elif arg in ["--output-type", "--output-dir", "--output-filename"]:
            if i + 1 >= len(args):
                raise ValueError(f"{arg} requires a value")
            # Convert --output-type to output_type, --output-dir to output_dir, etc.
            key = arg.replace("--", "").replace("-", "_")
            parsed[key] = args[i + 1]
            i += 1
        else:
            raise ValueError(f"Unknown argument: {arg}")
        i += 1
    return parsed


def generate_filename_from_template(
    template: str, output_type: str, env_name: str | None = None
) -> str:
    """Generate filename from template with date/time variables and env suffix.

    Args:
        template: Filename template with date/time variables
        output_type: Output file type (csv, parquet, avro)
        env_name: Optional environment name to append

    Returns:
        Generated filename with extension
    """
    now = datetime.now()
    filename = (
        template.replace("%y", now.strftime("%Y"))
        .replace("%m", now.strftime("%m"))
        .replace("%d", now.strftime("%d"))
        .replace("%h", now.strftime("%H"))
        .replace("%M", now.strftime("%M"))
    )

    if env_name:
        filename += f"_{env_name}"

    extensions = {"csv": ".csv", "parquet": ".parquet", "avro": ".avro"}
    return filename + extensions[output_type]


def check_output_dependencies(output_type: str) -> tuple[bool, str | None]:
    """Check if required dependencies are available for the output format.

    Args:
        output_type: Output format to check

    Returns:
        Tuple of (is_available, error_message)
    """
    if output_type == "parquet":
        try:
            import pyarrow  # noqa: F401

            return True, None
        except ImportError:
            return False, (
                "Error: pyarrow is required for Parquet format. Install "
                "with: uv sync --extra export or uv add pyarrow"
            )
    elif output_type == "avro":
        try:
            import fastavro  # noqa: F401

            return True, None
        except ImportError:
            return False, (
                "Error: fastavro is required for Avro format. Install "
                "with: uv sync --extra export or uv add fastavro"
            )
    return True, None


def preprocess_dataframe_for_format(df: pd.DataFrame, output_type: str) -> pd.DataFrame:
    """Preprocess DataFrame for export, handling data types and null values.

    Args:
        df: Input DataFrame
        output_type: Output format (csv, parquet, avro)

    Returns:
        Preprocessed DataFrame
    """
    processed_df = df.replace("N/A", pd.NA).copy()

    numeric_columns = [
        "Quality Score",
        "Records Processed",
        "Execution Duration (s)",
        "Open Alerts",
        "Asset Quality Score",
        "Open Alert Count",
        "Alert Total Count",
    ]

    # Apply numeric conversion
    for col in numeric_columns:
        if col in processed_df.columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors="coerce")

    datetime_columns = ["Execution Date", "Alert Created At", "Alert Updated At"]

    # Apply datetime conversion
    for col in datetime_columns:
        if col in processed_df.columns:
            processed_df[col] = pd.to_datetime(processed_df[col], errors="coerce")
            if output_type == "avro":
                processed_df[col] = processed_df[col].apply(
                    lambda x: x.strftime("%Y-%m-%dT%H:%M:%S.%fZ")
                    if pd.notna(x)
                    else None
                )

    string_list_columns = ["Tags", "Open Alert ID", "Open Alert States"]

    # Apply string conversion
    for col in string_list_columns:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].astype(str).replace("nan", None)

    if output_type == "avro":
        processed_df = processed_df.where(pd.notna(processed_df), None)

    return processed_df


def create_asset_lookup(catalog_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Create asset lookup dictionary from catalog data.

    Args:
        catalog_json: Catalog JSON data

    Returns:
        Dictionary mapping asset IDs to asset data
    """
    return {asset["assetId"]: asset for asset in catalog_json.get("assets", [])}


def create_alert_lookup(alert_json: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """Create alert lookup dictionary from alert data.

    Args:
        alert_json: Alert JSON data

    Returns:
        Dictionary mapping asset IDs to alert data
    """
    return {
        asset["assetId"]: incident
        for incident in alert_json.get("incidents", [])
        for asset in incident.get("assets", [])
    }


def extract_rule_data(
    rule: dict[str, Any],
    catalog_assets: dict[str, dict[str, Any]],
    alert_assets: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    """Extract and format rule data into a record.

    Args:
        rule: Rule data from API
        catalog_assets: Asset lookup dictionary
        alert_assets: Alert lookup dictionary

    Returns:
        Formatted rule record
    """
    rule_info = rule.get("rule", {})
    execution = rule.get("execution", {}) or {}
    metrics = rule.get("executionMetrics", {}) or {}

    asset_id = rule_info.get("backingAssets", [{}])[0].get("tableAssetId", "N/A")
    tags = {tag["name"] for tag in rule_info.get("tags", [])} or "N/A"

    record = {
        "Rule Name": rule_info.get("name", "N/A"),
        "Rule ID": rule_info.get("id", "N/A"),
        "Rule Type": rule_info.get("type", "N/A"),
        "Asset ID": asset_id,
        "Execution Status": execution.get("executionStatus", "NOT EXECUTED"),
        "Execution Date": execution.get("finishedAt", "N/A"),
        "Quality Score": metrics.get("qualityScore", "N/A"),
        "Records Processed": metrics.get("totalRecordsProcessed", "N/A"),
        "Execution Duration (s)": metrics.get("lastExecutionDuration", "N/A"),
        "Open Alerts": metrics.get("openAlertsCount", "N/A"),
        "Tags": str(tags) if tags != "N/A" else "N/A",
    }

    # Add asset information if available
    if asset := catalog_assets.get(asset_id):
        record.update(
            {
                "Asset Name": asset.get("name", "N/A"),
                "Asset UID": asset.get("assetUid", "N/A"),
                "Source Type": asset.get("sourceType", "N/A"),
                "Asset Type": asset.get("assetType", "N/A"),
                "Asset Quality Score": asset.get("qualityScore", "N/A"),
                "Open Alert Count": asset.get("openAlertCount", "N/A"),
                "Open Alert ID": str(asset.get("openAlertIds", "N/A")),
                "Open Alert States": str(asset.get("openAlertStates", "N/A")),
            }
        )

    # Add alert information if available
    if alert := alert_assets.get(asset_id):
        record.update(
            {
                "Alert ID": alert.get("id", "N/A"),
                "Alert Total Count": alert.get("totalCount", "N/A"),
                "Alert Created At": alert.get("createdAt", "N/A"),
                "Alert Updated At": alert.get("updatedAt", "N/A"),
                "Alert Status": alert.get("status", "N/A"),
                "Alert Assignee": alert.get("assignee", "N/A"),
                "Alert Updated By": alert.get("updatedBy", "N/A"),
                "Alert Severity": alert.get("severity", "N/A"),
            }
        )

    return record


def process_metrics_data(data: dict[str, Any]) -> list[dict[str, Any]]:
    """Process and combine the fetched data into report records.

    Args:
        data: Raw data from API endpoints

    Returns:
        List of processed report records
    """
    catalog_json = data.get("catalog", {})
    dq_policies_json = data.get("dq_policies", {})
    alert_json = data.get("alerts", {})

    # Create lookup dictionaries
    catalog_assets = create_asset_lookup(catalog_json)
    alert_assets = create_alert_lookup(alert_json)

    # Process each rule
    report_data = [
        extract_rule_data(rule, catalog_assets, alert_assets)
        for rule in dq_policies_json.get("rules", [])
    ]

    return report_data


def calculate_quality_statistics(df: pd.DataFrame) -> dict[str, Any]:
    """Calculate quality score statistics from DataFrame.

    Args:
        df: DataFrame with quality data

    Returns:
        Dictionary of quality statistics
    """
    quality_scores_numeric = pd.to_numeric(
        df["Quality Score"], errors="coerce"
    ).dropna()

    if quality_scores_numeric.empty:
        return {}

    return {
        "avg_quality_score": quality_scores_numeric.mean(),
        "min_quality_score": quality_scores_numeric.min(),
        "max_quality_score": quality_scores_numeric.max(),
        "high_quality_count": len(quality_scores_numeric[quality_scores_numeric >= 90]),
        "low_quality_count": len(quality_scores_numeric[quality_scores_numeric < 70]),
        "total_quality_records": len(quality_scores_numeric),
    }


def calculate_alert_statistics(df: pd.DataFrame) -> dict[str, Any]:
    """Calculate alert statistics from DataFrame.

    Args:
        df: DataFrame with alert data

    Returns:
        Dictionary of alert statistics
    """
    open_alerts_numeric = pd.to_numeric(df["Open Alerts"], errors="coerce").dropna()

    if open_alerts_numeric.empty:
        return {}

    return {
        "total_open_alerts": open_alerts_numeric.sum(),
        "avg_alerts_per_rule": open_alerts_numeric.mean(),
        "high_alert_count": len(open_alerts_numeric[open_alerts_numeric > 5]),
        "total_alert_records": len(open_alerts_numeric),
    }


def create_summary_table(
    df: pd.DataFrame, quality_stats: dict[str, Any], alert_stats: dict[str, Any]
) -> Table:
    """Create summary statistics table.

    Args:
        df: DataFrame with export data
        quality_stats: Quality score statistics
        alert_stats: Alert statistics

    Returns:
        Rich Table with summary statistics
    """
    summary_table = Table(
        title="Export Summary", show_header=True, header_style="bold magenta"
    )
    summary_table.add_column("Metric", style="cyan")
    summary_table.add_column("Value", style="white")

    summary_table.add_row("Total Records", f"{len(df):,}")
    summary_table.add_row("Total Columns", f"{len(df.columns)}")

    if quality_stats:
        summary_table.add_row(
            "Avg Quality Score", f"{quality_stats['avg_quality_score']:.1f}"
        )
        summary_table.add_row(
            "Min Quality Score", f"{quality_stats['min_quality_score']:.1f}"
        )
        summary_table.add_row(
            "Max Quality Score", f"{quality_stats['max_quality_score']:.1f}"
        )

    if alert_stats:
        summary_table.add_row(
            "Total Open Alerts", f"{alert_stats['total_open_alerts']:.0f}"
        )
        summary_table.add_row(
            "Avg Alerts per Rule", f"{alert_stats['avg_alerts_per_rule']:.1f}"
        )

    return summary_table


def create_distribution_table(
    df: pd.DataFrame, column: str, title: str
) -> Table | None:
    """Create distribution table for a specific column.

    Args:
        df: DataFrame with data
        column: Column name to analyze
        title: Table title

    Returns:
        Rich Table with distribution data or None if column doesn't exist
    """
    if column not in df.columns:
        return None

    dist = df[column].value_counts()
    table = Table(title=title, show_header=True, header_style="bold blue")
    table.add_column(column, style="cyan")
    table.add_column("Count", style="white")

    for value, count in dist.items():
        table.add_row(str(value), str(count))

    return table


def create_quality_distribution_table(df: pd.DataFrame) -> Table | None:
    """Create quality score distribution table.

    Args:
        df: DataFrame with quality data

    Returns:
        Rich Table with quality distribution or None if no quality data
    """
    quality_scores_numeric = pd.to_numeric(
        df["Quality Score"], errors="coerce"
    ).dropna()

    if quality_scores_numeric.empty:
        return None

    quality_table = Table(
        title="Quality Score Distribution", show_header=True, header_style="bold yellow"
    )
    quality_table.add_column("Range", style="cyan")
    quality_table.add_column("Count", style="white")

    # Define quality score ranges
    ranges = [
        (0, 50, "0-50"),
        (50, 70, "50-70"),
        (70, 85, "70-85"),
        (85, 95, "85-95"),
        (95, 101, "95-100"),
    ]

    for min_score, max_score, range_label in ranges:
        count = len(
            quality_scores_numeric[
                (quality_scores_numeric >= min_score)
                & (quality_scores_numeric < max_score)
            ]
        )
        quality_table.add_row(range_label, str(count))

    return quality_table


def create_insights_table(
    quality_stats: dict[str, Any], alert_stats: dict[str, Any]
) -> Table:
    """Create data quality insights table.

    Args:
        quality_stats: Quality score statistics
        alert_stats: Alert statistics

    Returns:
        Rich Table with insights
    """
    insights_table = Table(
        title="Data Quality Insights", show_header=True, header_style="bold red"
    )
    insights_table.add_column("Insight", style="cyan")
    insights_table.add_column("Value", style="white")

    if quality_stats:
        high_quality_pct = (
            quality_stats["high_quality_count"] / quality_stats["total_quality_records"]
        ) * 100
        insights_table.add_row("High Quality Rules (≥90%)", f"{high_quality_pct:.1f}%")

        low_quality_pct = (
            quality_stats["low_quality_count"] / quality_stats["total_quality_records"]
        ) * 100
        insights_table.add_row("Low Quality Rules (<70%)", f"{low_quality_pct:.1f}%")

    if alert_stats:
        high_alert_pct = (
            alert_stats["high_alert_count"] / alert_stats["total_alert_records"]
        ) * 100
        insights_table.add_row("Rules with High Alerts (>5)", f"{high_alert_pct:.1f}%")

    return insights_table


def export_dataframe_to_format(
    df: pd.DataFrame, output_path: Path, output_type: str
) -> None:
    """Export DataFrame to specified format.

    Args:
        df: DataFrame to export
        output_path: Output file path
        output_type: Output format (csv, parquet, avro)
    """
    processed_df = preprocess_dataframe_for_format(df, output_type)

    if output_type == "csv":
        processed_df.to_csv(output_path, index=False)
    elif output_type == "parquet":
        processed_df.to_parquet(output_path, index=False, compression="snappy")
    elif output_type == "avro":
        export_dataframe_to_avro(processed_df, output_path)


def export_dataframe_to_avro(df: pd.DataFrame, output_path: Path) -> None:
    """Export DataFrame to Avro format.

    Args:
        df: DataFrame to export
        output_path: Output file path
    """
    import fastavro

    records = df.to_dict("records")
    schema = {"type": "record", "name": "MetricsRecord", "fields": []}

    for column, dtype in zip(df.columns, df.dtypes, strict=True):
        field_name = column.replace(" ", "_").replace("(", "").replace(")", "").lower()
        if pd.api.types.is_integer_dtype(dtype):
            field_type = ["null", "long"]
        elif pd.api.types.is_float_dtype(dtype):
            field_type = ["null", "double"]
        else:
            field_type = ["null", "string"]
        schema["fields"].append(
            {"name": field_name, "type": field_type, "default": None}
        )

    converted_records = [
        {
            col.replace(" ", "_").replace("(", "").replace(")", "").lower(): (
                None if pd.isna(val) else val
            )
            for col, val in record.items()
        }
        for record in records
    ]

    # Try to use snappy codec, fall back to null if not available
    try:
        with open(output_path, "wb") as f:
            fastavro.writer(f, schema, converted_records, codec="snappy")
    except ValueError as e:
        if "snappy codec" in str(e):
            # Fall back to null codec if snappy is not available
            with open(output_path, "wb") as f:
                fastavro.writer(f, schema, converted_records, codec="null")
        else:
            raise


def cleanup_debug_files(debug_files: list[Path]) -> None:
    """Clean up temporary debug files.

    Args:
        debug_files: List of debug file paths to clean up
    """
    for debug_file in debug_files:
        try:
            if debug_file.exists():
                debug_file.unlink()
                log_info(f"Cleaned up debug file: {debug_file}")
        except Exception as e:
            log_error(f"Failed to clean up debug file {debug_file}", error=str(e))


def get_completion_suggestions(current_input: str, cursor_position: int) -> list[str]:
    """Get auto-completion suggestions for export-metrics command.

    Args:
        current_input: Current input text
        cursor_position: Current cursor position

    Returns:
        List of completion suggestions
    """
    words = current_input.split()

    # If we're typing a new word (input ends with space) or continuing a word
    if current_input.endswith(" "):
        current_word = ""
        word_index = len(words)
    else:
        current_word = words[-1] if words else ""
        word_index = len(words) - 1 if words else 0

    # Skip the command name itself
    if word_index == 0:
        return []

    # Available options
    options = ["--help", "--output-type", "--output-dir", "--output-filename"]

    # If the previous word was an option that expects a value, provide completions
    if len(words) >= 2:
        prev_word = (
            words[-1]
            if current_input.endswith(" ")
            else words[-2]
            if len(words) >= 2
            else ""
        )
        if prev_word == "--output-type":
            output_types = ["csv", "parquet", "avro"]
            return [ot for ot in output_types if ot.startswith(current_word.lower())]
        elif prev_word == "--output-dir":
            return []
        elif prev_word == "--output-filename":
            templates = [
                "ad-metrics-%d-%m-%y-%h-%M",
                "metrics-%y%m%d",
                "export-%d%m%y-%h%M",
                "data-%y-%m-%d",
            ]
            return [t for t in templates if t.startswith(current_word)]

    # Filter options based on current word and already used options
    used_options = set(words[1:])  # Skip command name
    available_options = [opt for opt in options if opt not in used_options]

    return [opt for opt in available_options if opt.startswith(current_word)]


class ExportMetricsCommand(Command, TraceableMixin):
    """Command to export metrics data from ADOC platform."""

    def __init__(self, environment_info_callback=None):
        """Initialize ExportMetricsCommand.

        Args:
            environment_info_callback: Function to get current environment info
        """
        self.environment_info_callback = environment_info_callback

    @property
    def trace_prefix(self) -> str | None:
        """Get the trace prefix for this command."""
        return "export_metrics"

    @property
    def name(self) -> str:
        return "export-metrics"

    @property
    def description(self) -> str:
        return "Export metrics data to CSV, Parquet, or Avro format"

    @property
    def aliases(self) -> list[str]:
        return ["export", "metrics"]

    def get_help(self) -> str:
        return f"""{self.name}: {self.description}

Usage: {self.name} [OPTIONS]

Options:
  --output-type TYPE      Output format: csv, parquet, avro (default: csv)
  --output-dir DIR        Output directory (default: ./output/export-metrics/)
  --output-filename NAME  Output filename template (default: ad-metrics-%d-%m-%y-%h-%M)
                         Variables: %y=year, %m=month, %d=day, %h=hour, %M=minute
                         Environment name is automatically added as suffix
  --help                  Show this help message

Description:
  Fetches data quality metrics from ADOC platform including:
  - Catalog assets
  - Data quality policies
  - Alerts and incidents

  Combines the data and exports to specified format with configurable filename.

  Requires environment to be set with 'use <environment>' command.
  Environment must have accessKey and secretKey configured.

  Optional Dependencies:
  - For Parquet format: uv sync --extra export (or uv add pyarrow)
  - For Avro format: uv sync --extra export (or uv add fastavro)

Examples:
  {self.name}                                    # Export to CSV with env suffix
  {self.name} --output-type parquet              # Export to Parquet format
  {self.name} --output-dir ./reports             # Save to reports directory
  {self.name} --output-filename "metrics-%y%m%d" # Custom filename template
"""

    @trace_method("command_execute", "export_metrics")
    def execute(self, args: list[str]) -> bool:
        """Execute the export-metrics command."""
        console = Console()

        # Parse arguments using functional approach
        try:
            parsed_args = parse_command_args(args)
        except ValueError as e:
            console.print(f"Error: {e}", style="red")
            return True

        if parsed_args.get("help"):
            console.print(self.get_help())
            return True

        # Validate output type
        output_type = parsed_args.get("output_type", "csv").lower()
        if output_type not in ["csv", "parquet", "avro"]:
            console.print(
                "Error: output-type must be csv, parquet, or avro", style="red"
            )
            return True

        # Check required dependencies using functional approach
        is_available, error_message = check_output_dependencies(output_type)
        if not is_available:
            console.print(error_message, style="red")
            return True

        data = None  # Ensure data is defined for finally block
        try:
            # Initialize HTTP client
            self.trace(
                "initializing_http_client",
                environment_callback=bool(self.environment_info_callback),
            )
            http_client = ADOCHTTPClient(
                environment_info_callback=self._get_environment_info
            )

            # Log the export operation start
            self.trace(
                "export_metrics_started",
                output_type=output_type,
                output_dir=parsed_args.get("output_dir", "."),
                filename_template=parsed_args.get(
                    "output_filename", "ad-metrics-%d-%m-%y-%h-%M"
                ),
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                # Fetch data
                task = progress.add_task(
                    "Fetching data from ADOC platform...", total=None
                )
                self.trace("starting_data_fetch", endpoints_count=3)
                data = self._fetch_all_data(http_client, progress, task)

                # Process data using functional approach
                progress.update(task, description="Processing and combining data...")
                self.trace("starting_data_processing", raw_data_keys=list(data.keys()))
                report_data = process_metrics_data(data)

                # Create DataFrame
                progress.update(task, description="Creating DataFrame...")
                self.trace("creating_dataframe", records_count=len(report_data))
                df = pd.DataFrame(report_data)

                if df.empty:
                    console.print(
                        "Warning: No data retrieved. Check your environment "
                        "configuration.",
                        style="yellow",
                    )
                    return True

                # Generate output filename using functional approach
                self.trace(
                    "generating_filename",
                    template=parsed_args.get(
                        "output_filename", "ad-metrics-%d-%m-%y-%h-%M"
                    ),
                    output_type=output_type,
                )
                env_info = self._get_environment_info()
                env_name = env_info.get("name") if env_info else None
                output_filename = generate_filename_from_template(
                    parsed_args.get("output_filename", "ad-metrics-%d-%m-%y-%h-%M"),
                    output_type,
                    env_name,
                )

                # Create output path
                default_output_dir = Path.cwd() / "output" / "export-metrics"
                output_dir = Path(parsed_args.get("output_dir", default_output_dir))
                output_dir.mkdir(parents=True, exist_ok=True)
                output_path = output_dir / output_filename

                self.trace(
                    "creating_output_path",
                    output_path=str(output_path),
                    output_dir=str(output_dir),
                    filename=output_filename,
                )

                # Export data using functional approach
                progress.update(
                    task, description=f"Exporting to {output_type.upper()}..."
                )
                self.trace(
                    "starting_data_export",
                    output_type=output_type,
                    records_count=len(df),
                    columns_count=len(df.columns),
                    output_path=str(output_path),
                )
                export_dataframe_to_format(df, output_path, output_type)

                progress.update(task, description="Export completed!", completed=True)

            console.print(
                f"✅ Successfully exported {len(df)} records to {output_path}",
                style="green",
            )
            console.print("📊 Export Statistics:")
            self.trace(
                "displaying_statistics",
                records_count=len(df),
                columns_count=len(df.columns),
            )
            self._display_statistics(df, console)

            self.trace(
                "export_metrics_completed_successfully",
                records_count=len(df),
                output_file=str(output_path),
                format=output_type,
                file_size_bytes=output_path.stat().st_size
                if output_path.exists()
                else 0,
            )
            log_info(
                "Export metrics completed",
                records_count=len(df),
                output_file=str(output_path),
                format=output_type,
            )

        except HTTPError as e:
            error_msg = f"HTTP error during data fetch: {e}"
            self.trace(
                "export_metrics_http_error",
                error_type="HTTPError",
                error_message=str(e),
            )
            console.print(f"Error: {error_msg}", style="red")
            log_error("Export metrics failed", error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.trace(
                "export_metrics_unexpected_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            console.print(f"Error: {error_msg}", style="red")
            log_error("Export metrics failed", error=error_msg)
        finally:
            # Clean up temporary debug files using functional approach
            if data:
                debug_files = data.get("_debug_files", [])
                self.trace("starting_cleanup", debug_files_count=len(debug_files))
                cleanup_debug_files(debug_files)

        return True

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions for export-metrics command."""
        return get_completion_suggestions(current_input, cursor_position)

    @trace_method("get_environment_info", "export_metrics")
    def _get_environment_info(self) -> dict[str, Any]:
        """Get current environment information."""
        return (
            self.environment_info_callback() if self.environment_info_callback else {}
        )

    @trace_method("fetch_paginated_data", "export_metrics")
    def _fetch_paginated_data(
        self, http_client: ADOCHTTPClient, base_url: str, endpoint_name: str, progress: Progress, task, page_size: int = 100
    ) -> dict[str, Any]:
        """Fetch paginated data from an endpoint."""
        all_items = []
        page = 0
        total_fetched = 0
        response_format = None  # Track the response format from first page
        
        while True:
            progress.update(task, description=f"Fetching {endpoint_name} data (page {page + 1})...")
            self.trace(
                f"fetching_{endpoint_name}_page",
                page=page,
                page_size=page_size,
                total_fetched=total_fetched,
            )
            
            headers = {"accept": "application/json, text/plain, */*"}
            response = http_client.get(f"{base_url}&page={page}&size={page_size}", headers=headers)
            
            if not response.is_success:
                self.trace(
                    f"fetch_{endpoint_name}_failed",
                    page=page,
                    status_code=response.status_code,
                    error_type="HTTP_ERROR",
                )
                raise HTTPError(
                    f"Failed to fetch {endpoint_name} data: HTTP {response.status_code}"
                )
            
            json_data = response.json()
            
            # Determine response format on first page
            if response_format is None:
                if isinstance(json_data, dict) and "items" in json_data:
                    response_format = "items"
                elif isinstance(json_data, dict) and "content" in json_data:
                    response_format = "content"
                elif isinstance(json_data, list):
                    response_format = "list"
                else:
                    response_format = "unknown"
            
            # Extract items based on response format
            if response_format == "items":
                items = json_data.get("items", [])
            elif response_format == "content":
                items = json_data.get("content", [])
            elif response_format == "list":
                items = json_data if isinstance(json_data, list) else []
            else:
                items = []
            
            if not items:
                # No more data
                self.trace(
                    f"fetch_{endpoint_name}_complete",
                    total_pages=page + 1,
                    total_items=total_fetched,
                )
                break
            
            all_items.extend(items)
            total_fetched += len(items)
            
            self.trace(
                f"fetch_{endpoint_name}_page_success",
                page=page,
                items_in_page=len(items),
                total_fetched=total_fetched,
            )
            
            # If we got fewer items than page_size, we've reached the end
            if len(items) < page_size:
                break
            
            page += 1
        
        # Return in the same format as original response
        if response_format == "items":
            return {"items": all_items}
        elif response_format == "content":
            return {"content": all_items}
        else:
            return all_items

    @trace_method("fetch_all_data", "export_metrics")
    def _fetch_all_data(
        self, http_client: ADOCHTTPClient, progress: Progress, task
    ) -> dict[str, Any]:
        """Fetch all required data from ADOC platform with pagination."""
        # Base URLs without pagination parameters
        endpoints_config = {
            "catalog": (
                "/catalog-server/api/assets/list?"
                "sortBy=dataQualityPolicyCount:DESC&"
                "asset_type_ids=2,4,9,11,18,23,24,6,53,55"
            ),
            "dq_policies": (
                "/catalog-server/api/rules?"
                "withLatestExecution=true&ruleStatus=ENABLED,ACTIVE"
            ),
        }

        # Fetch paginated endpoints
        data = {}
        for name, base_url in endpoints_config.items():
            try:
                data[name] = self._fetch_paginated_data(
                    http_client, base_url, name, progress, task, page_size=100
                )
            except HTTPError as e:
                self.trace(
                    f"fetch_{name}_error",
                    error=str(e),
                    error_type="HTTPError",
                )
                raise

        # Fetch alerts (non-paginated, already has size limit)
        @trace_method("fetch_single_endpoint", "export_metrics")
        def fetch_alerts():
            endpoint = "/api/incidents/api/v1/550191433/incidents/listing?size=100"
            progress.update(task, description=f"Fetching alerts data...")
            self.trace(f"fetching_alerts_endpoint", endpoint=endpoint, data_source="alerts")
            headers = {"accept": "application/json, text/plain, */*"}
            response = http_client.get(endpoint, headers=headers)
            if not response.is_success:
                self.trace(
                    f"fetch_alerts_failed",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    error_type="HTTP_ERROR",
                )
                raise HTTPError(
                    f"Failed to fetch alerts data: HTTP {response.status_code}"
                )
            self.trace(
                f"fetch_alerts_success",
                endpoint=endpoint,
                status_code=response.status_code,
                has_data=bool(response.json()),
            )
            return response.json()

        data["alerts"] = fetch_alerts()
        data["_debug_files"] = []

        # Optional debug file saving (e.g., enabled via env var DEBUG_EXPORT=True)
        import os

        if os.getenv("DEBUG_EXPORT", "False").lower() == "true":
            for name, json_data in data.items():
                if name == "_debug_files":
                    continue
                debug_file = Path(f"debug_{name}.json")
                data["_debug_files"].append(debug_file)
                try:
                    with open(debug_file, "w") as f:
                        json.dump(json_data, f, indent=2)
                    log_info(f"Saved debug data to {debug_file}")
                except Exception as e:
                    log_error(f"Failed to save debug data for {name}", error=str(e))

        return data

    @trace_method("display_statistics", "export_metrics")
    def _display_statistics(self, df: pd.DataFrame, console: Console) -> None:
        """Display comprehensive statistics about the exported data."""
        # Calculate statistics using functional approach
        quality_stats = calculate_quality_statistics(df)
        alert_stats = calculate_alert_statistics(df)

        # Create tables using functional approach
        summary_table = create_summary_table(df, quality_stats, alert_stats)
        console.print(summary_table)

        # Rule Type Distribution
        rule_type_table = create_distribution_table(
            df, "Rule Type", "Rule Type Distribution"
        )
        if rule_type_table:
            console.print(rule_type_table)

        # Execution Status Distribution
        status_table = create_distribution_table(
            df, "Execution Status", "Execution Status Distribution"
        )
        if status_table:
            console.print(status_table)

        # Quality Score Distribution
        quality_table = create_quality_distribution_table(df)
        if quality_table:
            console.print(quality_table)

        # Data Quality Insights
        insights_table = create_insights_table(quality_stats, alert_stats)
        console.print(insights_table)
