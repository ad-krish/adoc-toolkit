"""Export execution metrics command implementation."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn

from ...http import ADOCHTTPClient, HTTPError
from ...logs import log_error, log_info
from ...models import ExecutionMetricsArgs, LastRunInfo
from ...tracing import TraceableMixin, trace_method
from .base import Command
from .execution_metrics_service import ExecutionMetricsService, get_current_datetime


# Pure functional utilities
def parse_backload_option(backload_str: str) -> datetime:
    """Parse backload option string into a datetime.

    Args:
        backload_str: Backload string like "-30d", "-10d", "2024-01-15",
            "2024-01-15T10:30:00"

    Returns:
        Parsed datetime object

    Raises:
        ValueError: If parsing fails or constraints are violated
    """
    if not backload_str:
        raise ValueError("Backload option cannot be empty")

    # Check for relative day format: -Nd where N is 1-60
    relative_pattern = r"^-(\d+)d$"
    match = re.match(relative_pattern, backload_str.strip())

    if match:
        days = int(match.group(1))
        if days > 60:
            raise ValueError("Backload cannot be more than 60 days (-60d)")
        if days == 0:
            raise ValueError("Backload days must be positive")

        return datetime.now() - timedelta(days=days)

    # Try parsing as date or datetime string
    try:
        # Try various date formats
        date_formats = [
            "%Y-%m-%d",  # 2024-01-15
            "%Y-%m-%dT%H:%M:%S",  # 2024-01-15T10:30:00
            "%Y-%m-%d %H:%M:%S",  # 2024-01-15 10:30:00
            "%m/%d/%Y",  # 01/15/2024
            "%d/%m/%Y",  # 15/01/2024
        ]

        for fmt in date_formats:
            try:
                parsed_date = datetime.strptime(backload_str.strip(), fmt)

                # Validate that the date is not more than 60 days ago
                sixty_days_ago = datetime.now() - timedelta(days=60)
                if parsed_date < sixty_days_ago:
                    raise ValueError("Backload date cannot be more than 60 days ago")

                # Validate that the date is not in the future
                if parsed_date > datetime.now():
                    raise ValueError("Backload date cannot be in the future")

                return parsed_date
            except ValueError as e:
                # If this is a validation error (not a format parsing error),
                # re-raise it
                if "60 days ago" in str(e) or "future" in str(e):
                    raise
                # Otherwise, continue trying other formats
                continue

        # If no format worked, raise error
        raise ValueError(
            f"Invalid backload format: {backload_str}. "
            "Use formats like: -30d, 2024-01-15, 2024-01-15T10:30:00"
        )

    except Exception as e:
        raise ValueError(f"Error parsing backload option: {e}") from e


def parse_execution_metrics_args(args: list[str]) -> dict[str, Any]:
    """Parse command line arguments for export-execution-metrics command.

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
        elif arg in [
            "--output-type",
            "--output-dir",
            "--output-filename",
            "--backload",
        ]:
            if i + 1 >= len(args):
                raise ValueError(f"{arg} requires a value")
            # Convert --output-type to output_type, --output-dir to output_dir, etc.
            key = arg.replace("--", "").replace("-", "_")
            parsed[key] = args[i + 1]
            i += 1
        elif arg == "--page-size":
            if i + 1 >= len(args):
                raise ValueError(f"{arg} requires a value")
            try:
                page_size = int(args[i + 1])
                parsed["page_size"] = page_size
            except ValueError:
                raise ValueError("--page-size must be a valid integer")
            i += 1
        elif arg == "--policy-types":
            if i + 1 >= len(args):
                raise ValueError(f"{arg} requires a value")
            # Handle multiple policy types (comma-separated)
            policy_types_str = args[i + 1]
            policy_types = [
                pt.strip() for pt in policy_types_str.split(",") if pt.strip()
            ]
            if not policy_types:
                raise ValueError(f"{arg} requires at least one policy type")
            parsed["policy_types"] = policy_types
            i += 1
        else:
            raise ValueError(f"Unknown argument: {arg}")
        i += 1
    return parsed


def generate_execution_metrics_filename(
    template: str, output_type: str, env_name: str | None = None
) -> str:
    """Generate filename from template with date/time variables and env suffix.

    Args:
        template: Filename template with date/time variables
        output_type: Output file type (csv, parquet)
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

    extensions = {"csv": ".csv", "parquet": ".parquet"}
    return filename + extensions[output_type]


def check_execution_metrics_dependencies(output_type: str) -> tuple[bool, str | None]:
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
                "with: uv add pyarrow"
            )
    return True, None


def preprocess_execution_metrics_dataframe(
    df: pd.DataFrame, output_type: str
) -> pd.DataFrame:
    """Preprocess DataFrame for export, handling data types and null values.

    Args:
        df: Input DataFrame
        output_type: Output format (csv, parquet)

    Returns:
        Preprocessed DataFrame
    """
    processed_df = df.replace("N/A", pd.NA).copy()

    # Convert numeric columns
    numeric_columns = [
        "rule_version",
        "rows_scanned",
        "rows_failed",
        "rule_lower_threshold",
        "rule_upper_threshold",
    ]

    for col in numeric_columns:
        if col in processed_df.columns:
            processed_df[col] = pd.to_numeric(processed_df[col], errors="coerce")

    # Convert datetime columns (handle both with and without timezone suffix)
    datetime_column_patterns = ["started_at", "finished_at", "execution_date"]

    for col in processed_df.columns:
        # Check if column matches any datetime pattern (with or without timezone suffix)
        for pattern in datetime_column_patterns:
            if col == pattern or col.startswith(f"{pattern} ("):
                processed_df[col] = pd.to_datetime(processed_df[col], errors="coerce")
                # Replace NaT (Not a Time) / None with "null" string for clarity
                processed_df[col] = processed_df[col].apply(
                    lambda x: "null" if pd.isna(x) else x
                )
                break

    # Convert string columns
    string_columns = [
        "policy_name",
        "policy_id",
        "exec_id",
        "table_asset_name",
        "item_column_name",
        "pde",
        "item_measurement_type",
        "rule_strategy",
        "item_id",
        "result",
        "execution_status",
        "policy_type",
    ]

    for col in string_columns:
        if col in processed_df.columns:
            processed_df[col] = processed_df[col].astype(str).replace("nan", None)

    return processed_df


def export_execution_metrics_to_format(
    df: pd.DataFrame, output_path: Path, output_type: str
) -> None:
    """Export DataFrame to specified format.

    Args:
        df: DataFrame to export
        output_path: Output file path
        output_type: Output format (csv, parquet)
    """
    processed_df = preprocess_execution_metrics_dataframe(df, output_type)

    if output_type == "csv":
        processed_df.to_csv(output_path, index=False)
    elif output_type == "parquet":
        processed_df.to_parquet(output_path, index=False, compression="snappy")


def get_execution_metrics_completion_suggestions(
    current_input: str, cursor_position: int
) -> list[str]:
    """Get auto-completion suggestions for export-execution-metrics command.

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
    options = [
        "--help",
        "--output-type",
        "--output-dir",
        "--output-filename",
        "--backload",
        "--policy-types",
        "--page-size",
    ]

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
            output_types = ["csv", "parquet"]
            return [ot for ot in output_types if ot.startswith(current_word.lower())]
        elif prev_word == "--output-dir":
            return []
        elif prev_word == "--output-filename":
            templates = [
                "execution-metrics-%d-%m-%y-%h-%M",
                "exec-metrics-%y%m%d",
                "execution-%d%m%y-%h%M",
                "metrics-%y-%m-%d",
            ]
            return [t for t in templates if t.startswith(current_word)]
        elif prev_word == "--backload":
            backload_options = [
                "-10d",
                "-30d",
                "-60d",
                "2024-01-15",
                "2024-01-15T10:30:00",
            ]
            return [opt for opt in backload_options if opt.startswith(current_word)]
        elif prev_word == "--policy-types":
            policy_types = [
                "DATA_QUALITY",
                "EQUALITY",
                "DATA_DRIFT",
                "PROFILE_ANOMALY",
                "SCHEMA_DRIFT",
            ]
            # Handle comma-separated completion
            if "," in current_word:
                parts = current_word.split(",")
                prefix = ",".join(parts[:-1]) + ","
                last_part = parts[-1].strip()
                return [
                    prefix + pt
                    for pt in policy_types
                    if pt.startswith(last_part.upper())
                ]
            else:
                return [
                    pt for pt in policy_types if pt.startswith(current_word.upper())
                ]
        elif prev_word == "--page-size":
            page_sizes = ["100", "200", "500", "1000"]
            return [ps for ps in page_sizes if ps.startswith(current_word)]

    # Filter options based on current word and already used options
    used_options = set(words[1:])  # Skip command name
    available_options = [opt for opt in options if opt not in used_options]

    return [opt for opt in available_options if opt.startswith(current_word)]


class ExportExecutionMetricsCommand(Command, TraceableMixin):
    """Command to export execution metrics data from ADOC platform.

    This command gathers statistics on overall policy performance for DATA_QUALITY
    and EQUALITY (reconciliation) policy types and assembles detailed rule level
    performance for DQ policies. It runs incrementally on every run keeping track
    of last run start time in a file.
    """

    def __init__(self, environment_info_callback=None):
        """Initialize ExportExecutionMetricsCommand.

        Args:
            environment_info_callback: Function to get current environment info
        """
        self.environment_info_callback = environment_info_callback

    @property
    def trace_prefix(self) -> str | None:
        """Get the trace prefix for this command."""
        return "export_execution_metrics"

    @property
    def name(self) -> str:
        return "export-execution-metrics"

    @property
    def description(self) -> str:
        return (
            "Export execution metrics data to CSV or Parquet format "
            "with incremental processing"
        )

    @property
    def aliases(self) -> list[str]:
        return ["exec-metrics", "execution-metrics"]

    def get_help(self) -> str:
        return f"""{self.name}: {self.description}

Usage: {self.name} [OPTIONS]

Options:
  --output-type TYPE      Output format: csv, parquet (default: csv)
  --output-dir DIR        Output directory (default: ./output/execution-metrics/)
  --output-filename NAME  Output filename template (default:
                         execution-metrics-%d-%m-%y-%h-%M)
                         Variables: %y=year, %m=month, %d=day, %h=hour, %M=minute
                         Environment name is automatically added as suffix
  --backload OPTION       Backload option to override tracking file (e.g. -30d, -10d,
                         2024-01-15)
                         Supports: -Nd (1-60 days), date formats, datetime strings
                         Maximum: 60 days ago. Always overrides existing tracking file.
  --policy-types TYPES    Comma-separated policy types to export
                         (default: DATA_QUALITY,EQUALITY)
                         Available: DATA_QUALITY, EQUALITY, DATA_DRIFT, PROFILE_ANOMALY,
                         SCHEMA_DRIFT
  --page-size SIZE        Number of items to fetch per API call (default: 100, max: 1000)
                         Higher values fetch data faster but may cause server timeouts
                         for large datasets
  --help                  Show this help message

Description:
  Fetches execution metrics data from ADOC platform including:
  - Policy executions for specified policy types (default: DATA_QUALITY, EQUALITY)
  - Detailed rule-level performance for DQ policies
  - Asset information and threshold configurations

  Supports incremental processing by tracking the last run timestamp in a file.
  Only processes executions that occurred after the last run.

  Backload Behavior:
  - If --backload is specified, always uses that as the start time
    (ignores tracking file)
  - If no --backload, uses tracking file if exists, otherwise defaults to 30 days ago
    (-30d)
  - Without --backload, subsequent runs use the timestamp from the previous run

  Combines the data and exports to specified format with configurable filename.

  Requires environment to be set with 'use <environment>' command.
  Environment must have accessKey and secretKey configured.

  Optional Dependencies:
  - For Parquet format: uv add pyarrow

Examples:
  {self.name}  # Export to CSV with env suffix (uses tracking file or -30d default)
  {self.name} --backload -10d  # Override tracking file: backload from 10 days ago
  {self.name} --backload 2024-01-15  # Override tracking file: start from specific date
  {self.name} --backload "2024-01-15T10:30:00"  # Override tracking file:
  # start from specific datetime
  {self.name} --policy-types DATA_QUALITY  # Export only DATA_QUALITY policies
  {self.name} --policy-types DATA_QUALITY,DATA_DRIFT  # Export DATA_QUALITY and
  # DATA_DRIFT policies
  {self.name} --policy-types DATA_DRIFT,PROFILE_ANOMALY,SCHEMA_DRIFT  # Export drift and
  # anomaly policies
  {self.name} --output-type parquet  # Export to Parquet format
  {self.name} --output-dir ./reports  # Save to reports directory
  {self.name} --output-filename "exec-metrics-%y%m%d"  # Custom filename template
  {self.name} --page-size 500  # Fetch 500 items per page (faster for large datasets)
  {self.name} --backload -30d --page-size 1000  # Large backload with max page size
"""

    @trace_method("command_execute", "export_execution_metrics")
    def execute(self, args: list[str]) -> bool:
        """Execute the export-execution-metrics command."""
        console = Console()

        # Parse arguments using functional approach
        try:
            parsed_args = parse_execution_metrics_args(args)
        except ValueError as e:
            console.print(f"Error: {e}", style="red")
            return True

        if parsed_args.get("help"):
            console.print(self.get_help())
            return True

        # Validate arguments using Pydantic model
        try:
            args_model = ExecutionMetricsArgs(
                output_type=parsed_args.get("output_type", "csv"),
                output_dir=parsed_args.get("output_dir"),
                output_filename=parsed_args.get("output_filename"),
                backload=parsed_args.get("backload"),
                policy_types=parsed_args.get(
                    "policy_types", ["DATA_QUALITY", "EQUALITY"]
                ),
                help=parsed_args.get("help", False),
            )
        except Exception as e:
            console.print(f"Error: {e}", style="red")
            return True

        # Check required dependencies
        is_available, error_message = check_execution_metrics_dependencies(
            args_model.output_type
        )
        if not is_available:
            console.print(error_message, style="red")
            return True

        # Check if environment is set
        environment_info = self._get_environment_info()
        if not environment_info or not environment_info.get("environment"):
            console.print(
                "Error: No environment selected. Use 'use <environment>' command to "
                "set an environment first.",
                style="red",
            )
            return True

        try:
            # Get environment info for timezone configuration
            env_info = self._get_environment_info()
            timezone = env_info.get("timezone", "UTC") if env_info else "UTC"
            
            # Initialize HTTP client
            self.trace(
                "initializing_http_client",
                environment_callback=bool(self.environment_info_callback),
                timezone=timezone,
            )
            http_client = ADOCHTTPClient(
                environment_info_callback=self._get_environment_info
            )

            # Initialize execution metrics service with timezone
            service = ExecutionMetricsService(http_client, timezone)

            # Setup tracking
            default_output_dir = Path.cwd() / "output" / "execution-metrics"
            output_dir = Path(args_model.output_dir or default_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            tracking_file = output_dir / ".last_run_tracking.json"

            # Parse backload option if provided
            backload_datetime = None
            if args_model.backload:
                try:
                    backload_datetime = parse_backload_option(args_model.backload)
                except ValueError as e:
                    console.print(f"Error parsing backload option: {e}", style="red")
                    return True

            # Load last run info for incremental processing
            last_run_info = service.load_last_run_info(tracking_file, backload_datetime)
            start_ts_marker = last_run_info.last_run_timestamp

            self.trace(
                "execution_metrics_started",
                output_type=args_model.output_type,
                output_dir=str(output_dir),
                filename_template=args_model.output_filename
                or "execution-metrics-%d-%m-%y-%h-%M",
                start_ts_marker=start_ts_marker,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console,
                transient=True,
            ) as progress:
                # Fetch execution metrics data
                self.trace("starting_execution_metrics_fetch", page_size=args_model.page_size)
                execution_records = service.fetch_execution_metrics(
                    start_ts_marker, progress, args_model.policy_types, args_model.page_size
                )

                if not execution_records:
                    console.print(
                        "No new execution metrics data found since last run.",
                        style="yellow",
                    )
                    return True

                # Create DataFrame
                progress_task = progress.add_task("Creating DataFrame...", total=None)
                self.trace("creating_dataframe", records_count=len(execution_records))

                # Convert Pydantic models to dictionaries for DataFrame
                # Exclude epoch timestamp columns (startedAt, finishedAt) - keep only human-readable dates
                df_data = [record.model_dump(exclude={"startedAt", "finishedAt"}) for record in execution_records]
                df = pd.DataFrame(df_data)
                
                # Add timezone info to datetime column headers
                datetime_columns = ["started_at", "finished_at", "execution_date"]
                for col in datetime_columns:
                    if col in df.columns:
                        # Rename column to include timezone (e.g., "started_at (UTC)")
                        new_col_name = f"{col} ({timezone})"
                        df.rename(columns={col: new_col_name}, inplace=True)

                progress.update(
                    progress_task, description="DataFrame created", completed=True
                )

                # Generate output filename
                env_info = self._get_environment_info()
                env_name = env_info.get("name") if env_info else None
                output_filename = generate_execution_metrics_filename(
                    args_model.output_filename or "execution-metrics-%d-%m-%y-%h-%M",
                    args_model.output_type,
                    env_name,
                )

                output_path = output_dir / output_filename

                self.trace(
                    "creating_output_path",
                    output_path=str(output_path),
                    output_dir=str(output_dir),
                    filename=output_filename,
                )

                # Export data
                export_task = progress.add_task(
                    f"Exporting to {args_model.output_type.upper()}...", total=None
                )
                self.trace(
                    "starting_data_export",
                    output_type=args_model.output_type,
                    records_count=len(df),
                    columns_count=len(df.columns),
                    output_path=str(output_path),
                )

                export_execution_metrics_to_format(
                    df, output_path, args_model.output_type
                )
                progress.update(
                    export_task, description="Export completed!", completed=True
                )

                # Update tracking information
                current_dt = get_current_datetime(timezone)
                current_timestamp = int(current_dt.timestamp() * 1000)
                new_last_run_info = LastRunInfo(
                    last_run_timestamp=current_timestamp,
                    last_run_datetime=current_dt,
                    total_records_processed=len(execution_records),
                )
                service.save_last_run_info(tracking_file, new_last_run_info)

            console.print(
                f"✅ Successfully exported {len(df)} execution metrics records to "
                f"{output_path}",
                style="green",
            )
            console.print(
                f"📈 Processed {len(execution_records)} new records since last run"
            )
            console.print(f"🔄 Tracking file updated: {tracking_file}")

            self.trace(
                "export_execution_metrics_completed_successfully",
                records_count=len(df),
                output_file=str(output_path),
                format=args_model.output_type,
                file_size_bytes=output_path.stat().st_size
                if output_path.exists()
                else 0,
                tracking_file=str(tracking_file),
            )

            log_info(
                "Export execution metrics completed",
                records_count=len(df),
                output_file=str(output_path),
                format=args_model.output_type,
            )

        except HTTPError as e:
            error_msg = f"HTTP error during data fetch: {e}"
            self.trace(
                "export_execution_metrics_http_error",
                error_type="HTTPError",
                error_message=str(e),
            )
            console.print(f"Error: {error_msg}", style="red")
            log_error("Export execution metrics failed", error=error_msg)
        except ImportError as e:
            error_msg = f"Missing required dependency: {e}"
            self.trace(
                "export_execution_metrics_import_error",
                error_type="ImportError",
                error_message=str(e),
            )
            console.print(f"Error: {error_msg}", style="red")
            log_error("Export execution metrics failed", error=error_msg)
        except Exception as e:
            error_msg = f"Unexpected error: {e}"
            self.trace(
                "export_execution_metrics_unexpected_error",
                error_type=type(e).__name__,
                error_message=str(e),
            )
            console.print(f"Error: {error_msg}", style="red")
            log_error("Export execution metrics failed", error=error_msg)

        return True

    def get_completions(self, current_input: str, cursor_position: int) -> list[str]:
        """Get auto-completion suggestions for export-execution-metrics command."""
        return get_execution_metrics_completion_suggestions(
            current_input, cursor_position
        )

    @trace_method("get_environment_info", "export_execution_metrics")
    def _get_environment_info(self) -> dict[str, Any]:
        """Get current environment information."""
        return (
            self.environment_info_callback() if self.environment_info_callback else {}
        )
