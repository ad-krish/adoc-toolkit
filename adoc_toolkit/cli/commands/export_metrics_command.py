"""Export metrics command for ADOC toolkit."""

import json
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.panel import Panel
from rich.table import Table

from ...http import ADOCHTTPClient, HTTPError
from ...logs import log_error, log_info
from ...tracing import TraceableMixin, trace_method
from .base import Command


class ExportMetricsCommand(Command, TraceableMixin):
    """Command to export metrics data from ADOC platform."""

    def __init__(self, environment_info_callback=None):
        """Initialize ExportMetricsCommand.

        Args:
            environment_info_callback: Function to get current environment info
        """
        self.environment_info_callback = environment_info_callback

    @property
    def trace_prefix(self) -> Optional[str]:
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

        # Parse arguments
        try:
            parsed_args = self._parse_args(args)
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

        # Check required dependencies for output formats
        if not self._check_dependencies(output_type, console):
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

                # Process data
                progress.update(task, description="Processing and combining data...")
                self.trace("starting_data_processing", raw_data_keys=list(data.keys()))
                report_data = self._process_data(data)

                # Create DataFrame
                progress.update(task, description="Creating DataFrame...")
                self.trace("creating_dataframe", records_count=len(report_data))
                df = pd.DataFrame(report_data)

                if df.empty:
                    console.print(
                        "Warning: No data retrieved. Check your environment configuration.",
                        style="yellow",
                    )
                    return True

                # Generate output filename
                self.trace(
                    "generating_filename",
                    template=parsed_args.get(
                        "output_filename", "ad-metrics-%d-%m-%y-%h-%M"
                    ),
                    output_type=output_type,
                )
                output_filename = self._generate_filename(
                    parsed_args.get("output_filename", "ad-metrics-%d-%m-%y-%h-%M"),
                    output_type,
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

                # Export data
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
                self._export_data(df, output_path, output_type)

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
            # Clean up temporary debug files
            if data:
                debug_files = data.get("_debug_files", [])
                self.trace("starting_cleanup", debug_files_count=len(debug_files))
                self._cleanup_debug_files(debug_files)

        return True

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
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
                return [
                    ot for ot in output_types if ot.startswith(current_word.lower())
                ]
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

    @trace_method("parse_arguments", "export_metrics")
    def _parse_args(self, args: list[str]) -> dict[str, Any]:
        """Parse command line arguments."""
        parsed = {}
        i = 0
        while i < len(args):
            arg = args[i]
            if arg == "--help":
                parsed["help"] = True
            elif arg in ["--output-type", "--output-dir", "--output-filename"]:
                if i + 1 >= len(args):
                    raise ValueError(f"{arg} requires a value")
                parsed[arg.strip("--")] = args[i + 1]
                i += 1
            else:
                raise ValueError(f"Unknown argument: {arg}")
            i += 1
        return parsed

    @trace_method("check_dependencies", "export_metrics")
    def _check_dependencies(self, output_type: str, console: Console) -> bool:
        """Check if required dependencies are available for the output format."""
        if output_type == "parquet":
            try:
                import pyarrow  # noqa: F401
            except ImportError:
                console.print(
                    "Error: pyarrow is required for Parquet format. Install with: uv sync --extra export or uv add pyarrow",
                    style="red",
                )
                return False
        elif output_type == "avro":
            try:
                import fastavro  # noqa: F401
            except ImportError:
                console.print(
                    "Error: fastavro is required for Avro format. Install with: uv sync --extra export or uv add fastavro",
                    style="red",
                )
                return False
        return True

    @trace_method("get_environment_info", "export_metrics")
    def _get_environment_info(self) -> dict[str, Any]:
        """Get current environment information."""
        return (
            self.environment_info_callback() if self.environment_info_callback else {}
        )

    @trace_method("fetch_all_data", "export_metrics")
    def _fetch_all_data(
        self, http_client: ADOCHTTPClient, progress: Progress, task
    ) -> dict[str, Any]:
        """Fetch all required data from ADOC platform in parallel."""
        endpoints = {
            "catalog": (
                "/catalog-server/api/assets/list?page=-1&size=-1&"
                "sortBy=dataQualityPolicyCount:DESC&"
                "asset_type_ids=2,4,9,11,18,23,24,6,53,55"
            ),
            "dq_policies": (
                "/catalog-server/api/rules?page=-1&size=-1&"
                "withLatestExecution=true&ruleStatus=ENABLED,ACTIVE"
            ),
            "alerts": "/api/incidents/api/v1/550191433/incidents/listing?size=100",
        }

        @trace_method("fetch_single_endpoint", "export_metrics")
        def fetch_endpoint(name_endpoint):
            name, endpoint = name_endpoint
            progress.update(task, description=f"Fetching {name} data...")
            self.trace(f"fetching_{name}_endpoint", endpoint=endpoint, data_source=name)
            headers = {"accept": "application/json, text/plain, */*"}
            response = http_client.get(endpoint, headers=headers)
            if not response.is_success:
                self.trace(
                    f"fetch_{name}_failed",
                    endpoint=endpoint,
                    status_code=response.status_code,
                    error_type="HTTP_ERROR",
                )
                raise HTTPError(
                    f"Failed to fetch {name} data: HTTP {response.status_code}"
                )
            self.trace(
                f"fetch_{name}_success",
                endpoint=endpoint,
                status_code=response.status_code,
                has_data=bool(response.json()),
            )
            return name, response.json()

        with ThreadPoolExecutor(max_workers=3) as executor:
            results = list(executor.map(fetch_endpoint, endpoints.items()))

        data = dict(results)
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

    @trace_method("process_data", "export_metrics")
    def _process_data(self, data: dict[str, Any]) -> list[dict[str, Any]]:
        """Process and combine the fetched data."""
        catalog_json = data.get("catalog", {})
        dq_policies_json = data.get("dq_policies", {})
        alert_json = data.get("alerts", {})

        # Quick lookups
        catalog_assets = {
            asset["assetId"]: asset for asset in catalog_json.get("assets", [])
        }
        alert_assets = {
            asset["assetId"]: incident
            for incident in alert_json.get("incidents", [])
            for asset in incident.get("assets", [])
        }

        report_data = []
        for rule in dq_policies_json.get("rules", []):
            rule_info = rule.get("rule", {})
            execution = rule.get("execution", {}) or {}
            metrics = rule.get("executionMetrics", {}) or {}

            asset_id = rule_info.get("backingAssets", [{}])[0].get(
                "tableAssetId", "N/A"
            )
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

            report_data.append(record)

        log_info("Data processing completed", rules_processed=len(report_data))
        return report_data

    @trace_method("generate_filename", "export_metrics")
    def _generate_filename(self, template: str, output_type: str) -> str:
        """Generate filename from template with date/time variables and env suffix."""
        now = datetime.now()
        filename = (
            template.replace("%y", now.strftime("%Y"))
            .replace("%m", now.strftime("%m"))
            .replace("%d", now.strftime("%d"))
            .replace("%h", now.strftime("%H"))
            .replace("%M", now.strftime("%M"))
        )

        env_info = self._get_environment_info()
        if env_name := env_info.get("name"):
            filename += f"_{env_name}"

        extensions = {"csv": ".csv", "parquet": ".parquet", "avro": ".avro"}
        return filename + extensions[output_type]

    @trace_method("export_data", "export_metrics")
    def _export_data(
        self, df: pd.DataFrame, output_path: Path, output_type: str
    ) -> None:
        """Export DataFrame to specified format."""
        processed_df = self._preprocess_dataframe(df, output_type)
        if output_type == "csv":
            processed_df.to_csv(output_path, index=False)
        elif output_type == "parquet":
            processed_df.to_parquet(output_path, index=False, compression="snappy")
        elif output_type == "avro":
            self._export_avro(processed_df, output_path)
        log_info(f"Data exported to {output_type}", file_path=str(output_path))

    @trace_method("preprocess_dataframe", "export_metrics")
    def _preprocess_dataframe(self, df: pd.DataFrame, output_type: str) -> pd.DataFrame:
        """Preprocess DataFrame for export, handling data types and null values."""
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
        for col in numeric_columns:
            if col in processed_df.columns:
                processed_df[col] = pd.to_numeric(processed_df[col], errors="coerce")

        datetime_columns = ["Execution Date", "Alert Created At", "Alert Updated At"]
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
        for col in string_list_columns:
            if col in processed_df.columns:
                processed_df[col] = processed_df[col].astype(str).replace("nan", None)

        if output_type == "avro":
            processed_df = processed_df.where(pd.notna(processed_df), None)

        return processed_df

    @trace_method("export_avro", "export_metrics")
    def _export_avro(self, df: pd.DataFrame, output_path: Path) -> None:
        """Export DataFrame to Avro format."""
        import fastavro

        records = df.to_dict("records")
        schema = {"type": "record", "name": "MetricsRecord", "fields": []}

        for column, dtype in zip(df.columns, df.dtypes):
            field_name = (
                column.replace(" ", "_").replace("(", "").replace(")", "").lower()
            )
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

        with open(output_path, "wb") as f:
            fastavro.writer(f, schema, converted_records, codec="snappy")

    @trace_method("cleanup_debug_files", "export_metrics")
    def _cleanup_debug_files(self, debug_files: list[Path]) -> None:
        """Clean up temporary debug files."""
        for debug_file in debug_files:
            try:
                if debug_file.exists():
                    debug_file.unlink()
                    log_info(f"Cleaned up debug file: {debug_file}")
            except Exception as e:
                log_error(f"Failed to clean up debug file {debug_file}", error=str(e))

    @trace_method("display_statistics", "export_metrics")
    def _display_statistics(self, df: pd.DataFrame, console: Console) -> None:
        """Display comprehensive statistics about the exported data."""
        total_records = len(df)
        total_columns = len(df.columns)

        rule_types = df["Rule Type"].value_counts()
        execution_statuses = df["Execution Status"].value_counts()
        quality_scores_numeric = pd.to_numeric(
            df["Quality Score"], errors="coerce"
        ).dropna()
        asset_types = df["Asset Type"].value_counts()
        open_alerts_numeric = pd.to_numeric(df["Open Alerts"], errors="coerce").dropna()

        # Summary Table
        summary_table = Table(
            title="Export Summary", show_header=True, header_style="bold magenta"
        )
        summary_table.add_column("Metric", style="cyan")
        summary_table.add_column("Value", style="white")
        summary_table.add_row("Total Records", f"{total_records:,}")
        summary_table.add_row("Total Columns", f"{total_columns}")
        if not quality_scores_numeric.empty:
            summary_table.add_row(
                "Avg Quality Score", f"{quality_scores_numeric.mean():.1f}"
            )
            summary_table.add_row(
                "Min Quality Score", f"{quality_scores_numeric.min():.1f}"
            )
            summary_table.add_row(
                "Max Quality Score", f"{quality_scores_numeric.max():.1f}"
            )
        if not open_alerts_numeric.empty:
            summary_table.add_row(
                "Total Open Alerts", f"{open_alerts_numeric.sum():.0f}"
            )
            summary_table.add_row(
                "Avg Alerts per Rule", f"{open_alerts_numeric.mean():.1f}"
            )
        console.print(summary_table)

        # Rule Type Distribution
        if not rule_types.empty:
            rule_table = Table(
                title="Rule Type Distribution",
                show_header=True,
                header_style="bold green",
            )
            rule_table.add_column("Rule Type", style="cyan")
            rule_table.add_column("Count", justify="right", style="white")
            rule_table.add_column("Percentage", justify="right", style="yellow")
            for rule_type, count in rule_types.head(10).items():
                percentage = (count / total_records) * 100
                rule_table.add_row(str(rule_type), f"{count:,}", f"{percentage:.1f}%")
            console.print(rule_table)

        # Execution Status Distribution
        if not execution_statuses.empty:
            status_table = Table(
                title="Execution Status Distribution",
                show_header=True,
                header_style="bold blue",
            )
            status_table.add_column("Status", style="cyan")
            status_table.add_column("Count", justify="right", style="white")
            status_table.add_column("Percentage", justify="right", style="yellow")
            for status, count in execution_statuses.items():
                percentage = (count / total_records) * 100
                status_table.add_row(str(status), f"{count:,}", f"{percentage:.1f}%")
            console.print(status_table)

        # Asset Type Distribution
        if not asset_types.empty:
            asset_table = Table(
                title="Top Asset Types", show_header=True, header_style="bold cyan"
            )
            asset_table.add_column("Asset Type", style="cyan")
            asset_table.add_column("Count", justify="right", style="white")
            asset_table.add_column("Percentage", justify="right", style="yellow")
            for asset_type, count in asset_types.head(5).items():
                percentage = (count / total_records) * 100
                asset_table.add_row(str(asset_type), f"{count:,}", f"{percentage:.1f}%")
            console.print(asset_table)

        # Quality Score Distribution
        if not quality_scores_numeric.empty:
            score_ranges = pd.cut(
                quality_scores_numeric,
                bins=[0, 50, 70, 85, 95, 100],
                labels=[
                    "Poor (0-50)",
                    "Fair (51-70)",
                    "Good (71-85)",
                    "Very Good (86-95)",
                    "Excellent (96-100)",
                ],
                include_lowest=True,
            ).value_counts()
            quality_table = Table(
                title="Quality Score Distribution",
                show_header=True,
                header_style="bold yellow",
            )
            quality_table.add_column("Quality Range", style="cyan")
            quality_table.add_column("Count", justify="right", style="white")
            quality_table.add_column("Percentage", justify="right", style="yellow")
            for range_name, count in score_ranges.items():
                percentage = (count / len(quality_scores_numeric)) * 100
                quality_table.add_row(
                    str(range_name), f"{count:,}", f"{percentage:.1f}%"
                )
            console.print(quality_table)

        # Data Quality Insights
        insights = []
        if not quality_scores_numeric.empty:
            avg_score = quality_scores_numeric.mean()
            if avg_score >= 90:
                insights.append("🟢 Excellent overall data quality (avg score ≥ 90)")
            elif avg_score >= 80:
                insights.append("🟡 Good overall data quality (avg score ≥ 80)")
            else:
                insights.append("🔴 Data quality needs attention (avg score < 80)")
        if not execution_statuses.empty:
            success_rate = (execution_statuses.get("SUCCESS", 0) / total_records) * 100
            if success_rate >= 95:
                insights.append(f"🟢 High execution success rate ({success_rate:.1f}%)")
            elif success_rate >= 80:
                insights.append(
                    f"🟡 Moderate execution success rate ({success_rate:.1f}%)"
                )
            else:
                insights.append(f"🔴 Low execution success rate ({success_rate:.1f}%)")
        if not open_alerts_numeric.empty:
            high_alert_rules = (open_alerts_numeric > 5).sum()
            if high_alert_rules > 0:
                insights.append(f"⚠️  {high_alert_rules} rules have > 5 open alerts")
        if insights:
            console.print(
                Panel(
                    "\n".join(insights),
                    title="Data Quality Insights",
                    border_style="bright_blue",
                )
            )
