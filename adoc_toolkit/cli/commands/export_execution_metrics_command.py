"""Export execution metrics command implementation."""

import re
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import pandas as pd
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn

from ...http import ADOCHTTPClient, HTTPError
from ...logs import log_error, log_info
from ...models import ExecutionMetricsArgs, ExecutionMetricsRecord, LastRunInfo, ReconciliationRecord
from ...tracing import TraceableMixin, trace_method
from .base import Command
from .execution_metrics_service import ExecutionMetricsService, get_current_datetime, get_timezone


# Pure functional utilities
def parse_backload_option(backload_str: str, timezone: str = "UTC") -> datetime:
    """Parse backload option string into a datetime.

    Args:
        backload_str: Backload string like "-30d", "-10d", "-12h", "-1h", 
            "2024-01-15", "2024-01-15T10:30:00"
        timezone: Timezone to use for relative dates (default: UTC)

    Returns:
        Parsed datetime object (timezone-aware)

    Raises:
        ValueError: If parsing fails or constraints are violated
    """
    if not backload_str:
        raise ValueError("Backload option cannot be empty")

    # Check for relative hours format: -Nh where N is 1-1440 (60 days)
    hours_pattern = r"^-(\d+)h$"
    hours_match = re.match(hours_pattern, backload_str.strip())
    
    if hours_match:
        hours = int(hours_match.group(1))
        if hours > 1440:  # 60 days = 1440 hours
            raise ValueError("Backload cannot be more than 1440 hours (-1440h / 60 days)")
        if hours == 0:
            raise ValueError("Backload hours must be positive")

        return get_current_datetime(timezone) - timedelta(hours=hours)

    # Check for relative day format: -Nd where N is 1-60
    days_pattern = r"^-(\d+)d$"
    days_match = re.match(days_pattern, backload_str.strip())

    if days_match:
        days = int(days_match.group(1))
        if days > 60:
            raise ValueError("Backload cannot be more than 60 days (-60d)")
        if days == 0:
            raise ValueError("Backload days must be positive")

        return get_current_datetime(timezone) - timedelta(days=days)

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
                
                # Make parsed_date timezone-aware
                tz = get_timezone(timezone)
                if parsed_date.tzinfo is None:
                    parsed_date = parsed_date.replace(tzinfo=tz)

                # Validate that the date is not more than 60 days ago
                current_dt = get_current_datetime(timezone)
                sixty_days_ago = current_dt - timedelta(days=60)
                if parsed_date < sixty_days_ago:
                    raise ValueError("Backload date cannot be more than 60 days ago")

                # Validate that the date is not in the future
                if parsed_date > current_dt:
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
            "Use formats like: -1h, -12h, -1d, -30d, 2024-01-15, 2024-01-15T10:30:00"
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


def convert_reconciliation_to_execution_metrics(
    recon_record: ReconciliationRecord,
) -> ExecutionMetricsRecord:
    """Convert ReconciliationRecord to ExecutionMetricsRecord format for consolidated export.
    
    Args:
        recon_record: ReconciliationRecord to convert
        
    Returns:
        ExecutionMetricsRecord with standardized column names
    """
    # Map ReconciliationRecord fields to ExecutionMetricsRecord fields
    # Standardize: Recon_Type -> item_measurement_type, Result_Percentage -> result
    return ExecutionMetricsRecord(
        policy_name=recon_record.Policy_Name,
        policy_id=recon_record.Policy_ID,
        rule_version=recon_record.Rule_Version,
        exec_id=recon_record.Execution_ID,  # Standardized: Execution_ID
        table_asset_name=None,  # Not available in reconciliation
        item_column_name=None,  # Use Left_Column/Right_Column separately if needed
        pde=None,  # Not available in reconciliation
        item_measurement_type=recon_record.Recon_Type,  # Map Recon_Type to item_measurement_type
        rule_strategy=None,  # Not available in reconciliation
        rule_lower_threshold=None,  # Not available in reconciliation
        rule_upper_threshold=None,  # Not available in reconciliation
        item_id=recon_record.Rule_ID,  # Standardized: Rule_ID
        result=str(recon_record.Result_Percentage) if recon_record.Result_Percentage is not None else None,
        rows_scanned=None,  # Use Total_Rows or Left_Rows_Scanned/Right_Rows_Scanned separately
        rows_failed=recon_record.Rows_Failed,
        startedAt=None,  # Will be excluded from export
        started_at=recon_record.Started_At_UTC,
        finishedAt=None,  # Will be excluded from export
        finished_at=recon_record.Finished_At_UTC,
        execution_date=recon_record.Execution_Date_UTC,
        execution_status=recon_record.Execution_Status,
        policy_type=recon_record.Policy_Type,
        policy_enabled=recon_record.Policy_Enabled,
        label_key=recon_record.Label_Key,
        label_value=recon_record.Label_Value,
    )


def convert_column_names_to_title_case(df: pd.DataFrame) -> pd.DataFrame:
    """Convert all column names to Title Case (first letter of each word capitalized).
    
    Args:
        df: DataFrame with column names to convert
        
    Returns:
        DataFrame with converted column names
    """
    new_columns = {}
    for col in df.columns:
        # Handle columns with timezone info like "started_at (UTC)"
        if " (" in col:
            base_name, tz_info = col.rsplit(" (", 1)
            tz_info = "(" + tz_info  # Restore the parenthesis
            # Convert base name to title case
            title_base = "_".join(word.capitalize() for word in base_name.split("_"))
            new_columns[col] = f"{title_base} {tz_info}"
        else:
            # Convert snake_case to Title_Case
            new_columns[col] = "_".join(word.capitalize() for word in col.split("_"))
    
    df_renamed = df.rename(columns=new_columns)
    return df_renamed


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
                "-1h",
                "-6h",
                "-12h",
                "-24h",
                "-1d",
                "-7d",
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
                "FRESHNESS",
            ]
            # Handle comma-separated completion
            if "," in current_word:
                parts = current_word.split(",")
                prefix = ",".join(parts[:-1]) + ","
                last_part = parts[-1].strip()
                # Filter out already selected policy types
                already_selected = [p.strip().upper() for p in parts[:-1] if p.strip()]
                available_types = [pt for pt in policy_types if pt not in already_selected]
                return [
                    prefix + pt
                    for pt in available_types
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
  --backload OPTION       Backload option to override tracking file (e.g. -1h, -12h, -1d,
                         -30d, 2024-01-15)
                         Supports: -Nh (hours), -Nd (days), date formats, datetime strings
                         Maximum: 1440 hours (60 days). Always overrides tracking file.
  --policy-types TYPES    Comma-separated policy types to export
                         (default: DATA_QUALITY,EQUALITY)
                         Available: DATA_QUALITY, EQUALITY, DATA_DRIFT, PROFILE_ANOMALY,
                         SCHEMA_DRIFT, FRESHNESS
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
  {self.name} --backload -1h  # Override tracking file: backload from 1 hour ago
  {self.name} --backload -12h  # Override tracking file: backload from 12 hours ago
  {self.name} --backload -1d  # Override tracking file: backload from 1 day ago
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
                page_size=parsed_args.get("page_size", 100),
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
                    backload_datetime = parse_backload_option(args_model.backload, timezone)
                    console.print(
                        f"📅 Backload option: {args_model.backload} → "
                        f"{backload_datetime.strftime('%Y-%m-%d %H:%M:%S')} ({timezone})",
                        style="cyan"
                    )
                except ValueError as e:
                    console.print(f"Error parsing backload option: {e}", style="red")
                    return True

            # Load last run info for incremental processing
            last_run_info = service.load_last_run_info(tracking_file, backload_datetime)
            start_ts_marker = last_run_info.last_run_timestamp
            
            # Show what timestamp range we're fetching
            start_dt = datetime.fromtimestamp(start_ts_marker / 1000, tz=get_timezone(timezone))
            console.print(
                f"📊 Fetching executions since: {start_dt.strftime('%Y-%m-%d %H:%M:%S')} "
                f"(timestamp: {start_ts_marker})",
                style="cyan"
            )

            # Capture new checkpoint timestamp at START (before fetching data)
            # This prevents race condition where jobs complete during processing
            new_checkpoint_dt = get_current_datetime(timezone)
            new_checkpoint_timestamp = int(new_checkpoint_dt.timestamp() * 1000)

            self.trace(
                "execution_metrics_started",
                output_type=args_model.output_type,
                output_dir=str(output_dir),
                filename_template=args_model.output_filename
                or "execution-metrics-%d-%m-%y-%h-%M",
                start_ts_marker=start_ts_marker,
                new_checkpoint_timestamp=new_checkpoint_timestamp,
            )

            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                BarColumn(complete_style="green", finished_style="green"),
                TaskProgressColumn(style="bold green"),
                console=console,
                transient=False,
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
                
                # Get reconciliation records
                reconciliation_records = getattr(service, '_reconciliation_records', [])

                # Create separate DataFrames for execution records and reconciliation records
                # to preserve ALL columns from both
                
                # Convert execution records to DataFrame (exclude epoch timestamps)
                exec_df_data = [record.model_dump(exclude={"startedAt", "finishedAt"}) for record in execution_records]
                exec_df = pd.DataFrame(exec_df_data) if exec_df_data else pd.DataFrame()
                
                # Convert reconciliation records to DataFrame (keep all columns)
                recon_df_data = [record.model_dump() for record in reconciliation_records]
                recon_df_raw = pd.DataFrame(recon_df_data) if recon_df_data else pd.DataFrame()
                
                # Process execution records DataFrame
                if not exec_df.empty:
                    # Add timezone info to datetime column headers
                    datetime_columns = ["started_at", "finished_at", "execution_date"]
                    for col in datetime_columns:
                        if col in exec_df.columns:
                            new_col_name = f"{col} ({timezone})"
                            exec_df.rename(columns={col: new_col_name}, inplace=True)
                    
                    # Convert all column names to Title Case
                    exec_df = convert_column_names_to_title_case(exec_df)
                    
                    # Standardize datetime column format to use (UTC) without space
                    datetime_rename_map = {
                        "Started_At (UTC)": "Started_At(UTC)",
                        "Finished_At (UTC)": "Finished_At(UTC)",
                        "Execution_Date (UTC)": "Execution_Date(UTC)",
                    }
                    exec_df.rename(columns=datetime_rename_map, inplace=True)
                    
                    # Standardize column names
                    if "Exec_Id" in exec_df.columns:
                        exec_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                    if "Policy_Id" in exec_df.columns:
                        exec_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                    if "Item_Id" in exec_df.columns:
                        exec_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                    if "Result" in exec_df.columns:
                        exec_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                    # Ensure left_column and right_column are properly named (Title Case conversion should handle this, but check anyway)
                    if "left_column" in exec_df.columns:
                        exec_df.rename(columns={"left_column": "Left_Column"}, inplace=True)
                    if "right_column" in exec_df.columns:
                        exec_df.rename(columns={"right_column": "Right_Column"}, inplace=True)
                    # Rename Overall_Policy_Quality_Score to Overall_Policy_Quality_Score(Percentage)
                    if "Overall_Policy_Quality_Score" in exec_df.columns:
                        exec_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                    # Rename Result_Status to Rule_Result_Status
                    if "Result_Status" in exec_df.columns:
                        exec_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                    
                    # Map any "ACCURACY" or "TIMELINESS" values to standardized values for EQUALITY policies
                    if "Item_Measurement_Type" in exec_df.columns and "Policy_Type" in exec_df.columns:
                        equality_mask = exec_df["Policy_Type"] == "EQUALITY"
                        exec_df.loc[equality_mask & (exec_df["Item_Measurement_Type"] == "ACCURACY"), "Item_Measurement_Type"] = "EQUALITY_MATCH"
                        exec_df.loc[equality_mask & (exec_df["Item_Measurement_Type"] == "TIMELINESS"), "Item_Measurement_Type"] = "ROW_COUNT_MATCH"
                
                # Process reconciliation records DataFrame
                if not recon_df_raw.empty:
                    # Rename Recon_Type to Item_Measurement_Type
                    if "Recon_Type" in recon_df_raw.columns:
                        recon_df_raw.rename(columns={"Recon_Type": "Item_Measurement_Type"}, inplace=True)
                    
                    # Map any remaining "ACCURACY" or "TIMELINESS" values to standardized values
                    if "Item_Measurement_Type" in recon_df_raw.columns:
                        recon_df_raw["Item_Measurement_Type"] = recon_df_raw["Item_Measurement_Type"].replace({
                            "ACCURACY": "EQUALITY_MATCH",
                            "TIMELINESS": "ROW_COUNT_MATCH"
                        })
                    
                    # Rename datetime columns to match standardized format
                    recon_datetime_map = {
                        "Started_At_UTC": "Started_At(UTC)",
                        "Finished_At_UTC": "Finished_At(UTC)",
                        "Execution_Date_UTC": "Execution_Date(UTC)",
                    }
                    recon_df_raw.rename(columns=recon_datetime_map, inplace=True)
                    
                    # Rename Result_Percentage to Rule_Success_Rate
                    if "Result_Percentage" in recon_df_raw.columns:
                        recon_df_raw.rename(columns={"Result_Percentage": "Rule_Success_Rate"}, inplace=True)
                    # Rename Overall_Policy_Quality_Score to Overall_Policy_Quality_Score(Percentage)
                    if "Overall_Policy_Quality_Score" in recon_df_raw.columns:
                        recon_df_raw.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                    # Rename Result_Status to Rule_Result_Status
                    if "Result_Status" in recon_df_raw.columns:
                        recon_df_raw.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                
                # Merge both DataFrames to include ALL columns from both
                # This will create a DataFrame with all columns, with NaN for missing values
                if not exec_df.empty and not recon_df_raw.empty:
                    df = pd.concat([exec_df, recon_df_raw], ignore_index=True, sort=False)
                elif not exec_df.empty:
                    df = exec_df.copy()
                elif not recon_df_raw.empty:
                    df = recon_df_raw.copy()
                else:
                    df = pd.DataFrame()
                
                self.trace("creating_dataframe", records_count=len(df), exec_records=len(execution_records), recon_records=len(reconciliation_records))
                
                # Map any remaining "ACCURACY" or "TIMELINESS" values to standardized values for EQUALITY policies
                if not df.empty and "Item_Measurement_Type" in df.columns and "Policy_Type" in df.columns:
                    equality_mask = df["Policy_Type"] == "EQUALITY"
                    df.loc[equality_mask & (df["Item_Measurement_Type"] == "ACCURACY"), "Item_Measurement_Type"] = "EQUALITY_MATCH"
                    df.loc[equality_mask & (df["Item_Measurement_Type"] == "TIMELINESS"), "Item_Measurement_Type"] = "ROW_COUNT_MATCH"
                
                # Remove PDE column if it exists
                if "Pde" in df.columns:
                    df = df.drop(columns=["Pde"])
                
                # Fill unique columns with "NOT_APPLICABLE" based on policy type
                if not df.empty and "Policy_Type" in df.columns:
                    # Reconciliation-specific columns (should be NOT_APPLICABLE for DATA_QUALITY)
                    # Note: Policy_Description and Rule_Description are applicable for both DATA_QUALITY and RECONCILIATION
                    recon_unique_columns = [
                        "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                        "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                    ]
                    
                    # For DATA_QUALITY records, set reconciliation-specific columns to NOT_APPLICABLE
                    dq_mask = df["Policy_Type"] == "DATA_QUALITY"
                    for col in recon_unique_columns:
                        if col in df.columns:
                            # Fill NaN values with NOT_APPLICABLE for DATA_QUALITY records
                            df.loc[dq_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For RECONCILIATION (EQUALITY) records, set DATA_QUALITY-specific columns to NOT_APPLICABLE
                    # Note: Most columns are shared, but any columns that only exist in DATA_QUALITY
                    # should be set to NOT_APPLICABLE for RECONCILIATION records
                    recon_mask = df["Policy_Type"] == "EQUALITY"
                    # Get all columns that exist in the DataFrame
                    all_columns = df.columns.tolist()
                    # Find columns that are not in reconciliation unique columns and not common columns
                    # These might be DATA_QUALITY-specific
                    # DATA_DRIFT-specific columns (should be NOT_APPLICABLE for other policy types)
                    drift_unique_columns = [
                        "Drift_Threshold"
                    ]
                    
                    common_columns = [
                        "Policy_Name", "Policy_ID", "Rule_Version", "Execution_ID", "Rule_ID",
                        "Item_Measurement_Type", "Rule_Success_Rate", "Rows_Scanned", "Rows_Failed",
                        "Started_At(UTC)", "Finished_At(UTC)", "Execution_Date(UTC)", "Execution_Status",
                        "Rule_Result_Status", "Overall_Policy_Status", "Overall_Policy_Quality_Score(Percentage)",
                        "Policy_Type", "Policy_Enabled", "Label_Key", "Label_Value", "Policy_Description", "Rule_Description"
                    ]
                    
                    # For DATA_DRIFT records, set reconciliation-specific columns to NOT_APPLICABLE
                    drift_mask = df["Policy_Type"] == "DATA_DRIFT"
                    for col in recon_unique_columns:
                        if col in df.columns:
                            df.loc[drift_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For DATA_QUALITY records, set reconciliation-specific and DATA_DRIFT-specific columns to NOT_APPLICABLE
                    for col in recon_unique_columns + drift_unique_columns:
                        if col in df.columns:
                            df.loc[dq_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For RECONCILIATION (EQUALITY) records, set DATA_QUALITY-specific and DATA_DRIFT-specific columns to NOT_APPLICABLE
                    # Set Drift_Threshold to NOT_APPLICABLE for RECONCILIATION records
                    for col in drift_unique_columns:
                        if col in df.columns:
                            df.loc[recon_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For FRESHNESS records, set reconciliation-specific, DATA_DRIFT-specific, and other NOT_APPLICABLE columns
                    freshness_mask = df["Policy_Type"] == "FRESHNESS"
                    # Set Rows_Scanned, Rows_Failed, Rule_Description, Item_Column_Name to NOT_APPLICABLE for FRESHNESS
                    freshness_not_applicable_columns = ["Rows_Scanned", "Rows_Failed", "Rule_Description", "Item_Column_Name"]
                    for col in freshness_not_applicable_columns:
                        if col in df.columns:
                            df.loc[freshness_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    # Set reconciliation-specific columns to NOT_APPLICABLE for FRESHNESS
                    for col in recon_unique_columns:
                        if col in df.columns:
                            df.loc[freshness_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    # Set DATA_DRIFT-specific columns to NOT_APPLICABLE for FRESHNESS
                    for col in drift_unique_columns:
                        if col in df.columns:
                            df.loc[freshness_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For SCHEMA_DRIFT records, set NOT_APPLICABLE columns
                    schema_drift_mask = df["Policy_Type"] == "SCHEMA_DRIFT"
                    schema_drift_not_applicable_columns = [
                        "Rule_Success_Rate", "Item_Column_Name", "Item_Measurement_Type",
                        "Rule_Strategy", "Rule_Lower_Threshold", "Rule_Upper_Threshold",
                        "Rows_Scanned", "Rows_Failed", "Rule_Description"
                    ]
                    for col in schema_drift_not_applicable_columns:
                        if col in df.columns:
                            df.loc[schema_drift_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For non-FRESHNESS records, set Anomaly_Detected and Threshold_Breached to NOT_APPLICABLE
                    non_freshness_mask = df["Policy_Type"] != "FRESHNESS"
                    freshness_specific_columns = ["Anomaly_Detected", "Threshold_Breached"]
                    for col in freshness_specific_columns:
                        if col in df.columns:
                            df.loc[non_freshness_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For non-PROFILE_ANOMALY records, set Metric_Anomalous to NOT_APPLICABLE
                    non_profile_anomaly_mask = df["Policy_Type"] != "PROFILE_ANOMALY"
                    if "Metric_Anomalous" in df.columns:
                        df.loc[non_profile_anomaly_mask & df["Metric_Anomalous"].isna(), "Metric_Anomalous"] = "NOT_APPLICABLE"
                    
                    # For PROFILE_ANOMALY records, set NOT_APPLICABLE columns
                    profile_anomaly_mask = df["Policy_Type"] == "PROFILE_ANOMALY"
                    profile_anomaly_not_applicable_columns = [
                        "Rule_Strategy", "Rule_Lower_Threshold", "Rule_Upper_Threshold",
                        "Label_Key", "Label_Value", "Rule_Success_Rate", "Rule_Result_Status",
                        "Rows_Scanned", "Rows_Failed", "Asset_Addition", "Asset_Deletion",
                        "Data_Type", "Asset_Relation_Change", "Asset_Metadata", "Metadata_Configs",
                        "Policy_Description", "Rule_Description"
                    ]
                    for col in profile_anomaly_not_applicable_columns:
                        if col in df.columns:
                            df.loc[profile_anomaly_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    # For any column that's not common and not reconciliation-specific and not DATA_DRIFT-specific, 
                    # set to NOT_APPLICABLE for RECONCILIATION records
                    for col in all_columns:
                        if col not in recon_unique_columns and col not in drift_unique_columns and col not in common_columns and col != "Policy_Type":
                            if col in df.columns:
                                df.loc[recon_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For DATA_DRIFT records, set Rows_Scanned, Rows_Failed, and Rule_Description to NOT_APPLICABLE
                    # (these are NOT_APPLICABLE for DATA_DRIFT but should be included in main CSV)
                    drift_not_applicable_columns = ["Rows_Scanned", "Rows_Failed", "Rule_Description"]
                    for col in drift_not_applicable_columns:
                        if col in df.columns:
                            # Set to NOT_APPLICABLE for all DATA_DRIFT records (including those with NaN)
                            df.loc[drift_mask, col] = "NOT_APPLICABLE"
                    
                    # For DATA_DRIFT records, set DATA_QUALITY-specific columns to NOT_APPLICABLE
                    # (columns that are not common, not reconciliation-specific, and not DATA_DRIFT-specific)
                    for col in all_columns:
                        if col not in recon_unique_columns and col not in drift_unique_columns and col not in common_columns and col != "Policy_Type":
                            if col in df.columns:
                                df.loc[drift_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                    
                    # For other policy types (not DATA_QUALITY, EQUALITY, DATA_DRIFT), set both reconciliation and DATA_DRIFT columns to NOT_APPLICABLE
                    other_mask = ~(dq_mask | recon_mask | drift_mask)
                    for col in recon_unique_columns + drift_unique_columns:
                        if col in df.columns:
                            df.loc[other_mask & df[col].isna(), col] = "NOT_APPLICABLE"
                
                # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                if "Rule_ID" in df.columns:
                    cols = list(df.columns)
                    # Remove Label_Key and Label_Value if they exist
                    label_cols = []
                    if "Label_Key" in cols:
                        cols.remove("Label_Key")
                        label_cols.append("Label_Key")
                    if "Label_Value" in cols:
                        cols.remove("Label_Value")
                        label_cols.append("Label_Value")
                    
                        # Find Rule_ID position and insert Label_Key and Label_Value after it
                        if label_cols and "Rule_ID" in cols:
                            rule_id_idx = cols.index("Rule_ID")
                            # Insert after Rule_ID
                            cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                            df = df[cols]

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
                
                # Export DATA_QUALITY records separately if available
                dq_records = [record for record in execution_records if record.policy_type == "DATA_QUALITY"]
                if dq_records:
                    dq_task = progress.add_task(
                        "📊 Exporting DATA_QUALITY records...", total=None
                    )
                    self.trace(
                        "starting_data_quality_export",
                        records_count=len(dq_records),
                    )
                    
                    # Create DataFrame for DATA_QUALITY records
                    # Exclude epoch timestamp columns (startedAt, finishedAt) - keep only human-readable dates
                    dq_df_data = [record.model_dump(exclude={"startedAt", "finishedAt"}) for record in dq_records]
                    dq_df = pd.DataFrame(dq_df_data)
                    
                    # Add timezone info to datetime column headers
                    datetime_columns = ["started_at", "finished_at", "execution_date"]
                    for col in datetime_columns:
                        if col in dq_df.columns:
                            new_col_name = f"{col} ({timezone})"
                            dq_df.rename(columns={col: new_col_name}, inplace=True)
                    
                    # Convert all column names to Title Case
                    dq_df = convert_column_names_to_title_case(dq_df)
                    
                    # Standardize datetime column format to use (UTC) without space
                    datetime_rename_map = {
                        "Started_At (UTC)": "Started_At(UTC)",
                        "Finished_At (UTC)": "Finished_At(UTC)",
                        "Execution_Date (UTC)": "Execution_Date(UTC)",
                    }
                    dq_df.rename(columns=datetime_rename_map, inplace=True)
                    
                    # Standardize column names for DATA_QUALITY
                    # Exec_Id → Execution_ID
                    if "Exec_Id" in dq_df.columns:
                        dq_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                    # Policy_Id → Policy_ID
                    if "Policy_Id" in dq_df.columns:
                        dq_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                    # Item_Id → Rule_ID
                    if "Item_Id" in dq_df.columns:
                        dq_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                    
                    # Standardize Result column to Rule_Success_Rate for DATA_QUALITY
                    if "Result" in dq_df.columns:
                        dq_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                    
                    # Rename Overall_Policy_Quality_Score to Overall_Policy_Quality_Score(Percentage)
                    if "Overall_Policy_Quality_Score" in dq_df.columns:
                        dq_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                    
                    # Rename Result_Status to Rule_Result_Status
                    if "Result_Status" in dq_df.columns:
                        dq_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                    
                    # Remove PDE column if it exists
                    if "Pde" in dq_df.columns:
                        dq_df = dq_df.drop(columns=["Pde"])
                    
                    # For DATA_QUALITY CSV, exclude NOT_APPLICABLE columns and DATA_DRIFT-specific columns
                    # Exclude reconciliation-specific columns
                    recon_columns_to_exclude = [
                        "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                        "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                    ]
                    # Exclude DATA_DRIFT-specific columns
                    drift_columns_to_exclude = ["Drift_Threshold"]
                    # Exclude columns that are NOT_APPLICABLE for DATA_QUALITY
                    for col in recon_columns_to_exclude + drift_columns_to_exclude:
                        if col in dq_df.columns:
                            dq_df = dq_df.drop(columns=[col])
                    
                    # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                    for col in dq_df.columns:
                        # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                        if col in dq_df.columns:
                            non_null_values = dq_df[col].dropna()
                            if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                dq_df = dq_df.drop(columns=[col])
                            elif len(non_null_values) == 0:
                                # Column is all NaN/None, exclude it
                                dq_df = dq_df.drop(columns=[col])
                    
                    # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                    if "Rule_ID" in dq_df.columns:
                        cols = list(dq_df.columns)
                        # Remove Label_Key and Label_Value if they exist
                        label_cols = []
                        if "Label_Key" in cols:
                            cols.remove("Label_Key")
                            label_cols.append("Label_Key")
                        if "Label_Value" in cols:
                            cols.remove("Label_Value")
                            label_cols.append("Label_Value")
                        
                        # Find Rule_ID position and insert Label_Key and Label_Value after it
                        if label_cols and "Rule_ID" in cols:
                            rule_id_idx = cols.index("Rule_ID")
                            # Insert after Rule_ID
                            cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                            dq_df = dq_df[cols]
                    
                    # Generate DATA_QUALITY filename
                    dq_filename = generate_execution_metrics_filename(
                        "data-quality-metrics-%d-%m-%y-%h-%M",
                        args_model.output_type,
                        env_name,
                    )
                    dq_output_path = output_dir / dq_filename
                    
                    # Export DATA_QUALITY data
                    export_execution_metrics_to_format(
                        dq_df, dq_output_path, args_model.output_type
                    )
                    
                    progress.update(
                        dq_task, description="DATA_QUALITY export completed!", completed=True
                    )
                    
                    console.print(
                        f"✅ Successfully exported {len(dq_df)} DATA_QUALITY records to "
                        f"{dq_output_path}",
                        style="green",
                    )
                    
                    self.trace(
                        "data_quality_export_completed",
                        records_count=len(dq_df),
                        output_file=str(dq_output_path),
                    )
                
                # Export reconciliation records separately if available
                # Use the reconciliation_records from service (these should be ReconciliationRecord objects)
                reconciliation_records = getattr(service, '_reconciliation_records', [])
                
                log_info(f"DEBUG: reconciliation_records count: {len(reconciliation_records) if reconciliation_records else 0}")
                
                if reconciliation_records:
                    recon_task = progress.add_task(
                        "📊 Exporting reconciliation records...", total=None
                    )
                    self.trace(
                        "starting_reconciliation_export",
                        records_count=len(reconciliation_records),
                    )
                    
                    # Create DataFrame for reconciliation records
                    # reconciliation_records should be ReconciliationRecord objects from process_reconciliation_records
                    # Check if records are ReconciliationRecord by checking the actual fields in model_dump
                    from ...models import ReconciliationRecord
                    first_record = reconciliation_records[0] if reconciliation_records else None
                    
                    # Check if this is a ReconciliationRecord by examining the fields
                    # ReconciliationRecord has unique fields like Left_Column, Right_Column, Left_Rows_Scanned, etc.
                    is_reconciliation_record = False
                    if first_record:
                        # Try to get the fields from model_dump to check
                        try:
                            sample_dump = first_record.model_dump()
                            log_info(f"DEBUG: First record type: {type(first_record).__name__}")
                            log_info(f"DEBUG: First record fields (first 15): {list(sample_dump.keys())[:15]}")
                            
                            # Check for ReconciliationRecord-specific fields (these are the key differentiators)
                            # ReconciliationRecord uses capitalized field names like Left_Column, Right_Column, etc.
                            has_recon_fields = (
                                'Left_Column' in sample_dump or
                                'Right_Column' in sample_dump or
                                'Left_Rows_Scanned' in sample_dump or
                                'Right_Rows_Scanned' in sample_dump or
                                'Use_For_Joining' in sample_dump or
                                'Left_ASSET_UID' in sample_dump or
                                'Right_ASSET_UID' in sample_dump or
                                'Join_Type' in sample_dump or
                                'Operation' in sample_dump or
                                'Recon_Type' in sample_dump
                            )
                            
                            # ExecutionMetricsRecord uses lowercase field names like table_asset_name, item_column_name, etc.
                            has_exec_fields = (
                                'table_asset_name' in sample_dump or
                                'item_column_name' in sample_dump or
                                'rule_strategy' in sample_dump or
                                'pde' in sample_dump
                            )
                            
                            # If it has ReconciliationRecord fields, it's definitely a ReconciliationRecord
                            # ExecutionMetricsRecord will NOT have Left_Column, Right_Column, etc.
                            is_reconciliation_record = has_recon_fields
                            
                            log_info(f"DEBUG: Field check - has_recon_fields: {has_recon_fields}, has_exec_fields: {has_exec_fields}, is_reconciliation_record: {is_reconciliation_record}")
                        except Exception as e:
                            log_info(f"DEBUG: Error checking record fields: {e}")
                            import traceback
                            log_info(f"DEBUG: Traceback: {traceback.format_exc()}")
                            # Fallback to isinstance check
                            is_reconciliation_record = isinstance(first_record, ReconciliationRecord)
                    
                    if is_reconciliation_record:
                        # These are ReconciliationRecord objects - preserve ALL columns from ReconciliationRecord model:
                        # Policy_Name, Policy_ID, Rule_Version, Execution_ID, Left_Column, Right_Column, Rule_ID,
                        # Recon_Type, Result_Percentage, Rows_Scanned, Rows_Failed, Left_Rows_Scanned, Right_Rows_Scanned,
                        # Use_For_Joining, Policy_Description, Rule_Description, Left_ASSET_UID, Right_ASSET_UID,
                        # Join_Type, Started_At_UTC, Finished_At_UTC, Execution_Date_UTC, Execution_Status,
                        # Rule_Result_Status, Overall_Policy_Status, Overall_Policy_Quality_Score, Policy_Type,
                        # Policy_Enabled, Operation, Label_Key, Label_Value
                        recon_df_data = [record.model_dump() for record in reconciliation_records]
                        recon_df = pd.DataFrame(recon_df_data)
                        
                        # Rename Recon_Type to Item_Measurement_Type for consistency
                        if "Recon_Type" in recon_df.columns:
                            recon_df.rename(columns={"Recon_Type": "Item_Measurement_Type"}, inplace=True)
                        
                        # Rename datetime columns to match standardized format (with parentheses, no space)
                        recon_datetime_map = {
                            "Started_At_UTC": "Started_At(UTC)",
                            "Finished_At_UTC": "Finished_At(UTC)",
                            "Execution_Date_UTC": "Execution_Date(UTC)",
                        }
                        recon_df.rename(columns=recon_datetime_map, inplace=True)
                        
                        # Rename Result_Percentage to Rule_Success_Rate
                        if "Result_Percentage" in recon_df.columns:
                            recon_df.rename(columns={"Result_Percentage": "Rule_Success_Rate"}, inplace=True)
                        
                        # Rename Overall_Policy_Quality_Score to Overall_Policy_Quality_Score(Percentage)
                        if "Overall_Policy_Quality_Score" in recon_df.columns:
                            recon_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        
                        # Rename Result_Status to Rule_Result_Status (if it exists, otherwise it's already Rule_Result_Status)
                        if "Result_Status" in recon_df.columns:
                            recon_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                    else:
                        # Fallback: These are ExecutionMetricsRecord objects (EQUALITY type from execution_records)
                        # This should not happen if reconciliation_records are properly stored as ReconciliationRecord objects
                        # These are ExecutionMetricsRecord objects (EQUALITY type from execution_records)
                        # Convert to DataFrame, excluding epoch timestamps
                        recon_df_data = [record.model_dump(exclude={"startedAt", "finishedAt"}) for record in reconciliation_records]
                        recon_df = pd.DataFrame(recon_df_data)
                        
                        # Add timezone info to datetime column headers
                        datetime_columns = ["started_at", "finished_at", "execution_date"]
                        for col in datetime_columns:
                            if col in recon_df.columns:
                                new_col_name = f"{col} ({timezone})"
                                recon_df.rename(columns={col: new_col_name}, inplace=True)
                        
                        # Convert all column names to Title Case
                        recon_df = convert_column_names_to_title_case(recon_df)
                        
                        # Standardize datetime column format to use (UTC) without space
                        datetime_rename_map = {
                            "Started_At (UTC)": "Started_At(UTC)",
                            "Finished_At (UTC)": "Finished_At(UTC)",
                            "Execution_Date (UTC)": "Execution_Date(UTC)",
                        }
                        recon_df.rename(columns=datetime_rename_map, inplace=True)
                        
                        # Standardize column names for RECONCILIATION
                        if "Exec_Id" in recon_df.columns:
                            recon_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                        if "Policy_Id" in recon_df.columns:
                            recon_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                        if "Item_Id" in recon_df.columns:
                            recon_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                        if "Result" in recon_df.columns:
                            recon_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                        if "Overall_Policy_Quality_Score" in recon_df.columns:
                            recon_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        if "Result_Status" in recon_df.columns:
                            recon_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                        # Item_Measurement_Type should already be set from ExecutionMetricsRecord
                    
                    # Rename Rows_Failed to Rows_Failed/Drift if any records have ROW_COUNT_MATCH
                    # The column will contain drift for ROW_COUNT_MATCH and failedRows for EQUALITY_MATCH
                    # Only apply this if we're working with ReconciliationRecord (which has Item_Measurement_Type)
                    if is_reconciliation_record and "Item_Measurement_Type" in recon_df.columns and "Rows_Failed" in recon_df.columns:
                        row_count_match_mask = recon_df["Item_Measurement_Type"] == "ROW_COUNT_MATCH"
                        if row_count_match_mask.any():
                            # Rename the column for all records
                            recon_df.rename(columns={"Rows_Failed": "Rows_Failed/Drift"}, inplace=True)
                    
                    # Skip the duplicate rename map if we already processed ReconciliationRecord columns above
                    if not is_reconciliation_record:
                        # Rename columns to match user requirements (with parentheses) - only for ExecutionMetricsRecord fallback
                        column_rename_map = {
                            "Result_Percentage": "Rule_Success_Rate",
                            "Started_At_UTC": "Started_At(UTC)",
                            "Finished_At_UTC": "Finished_At(UTC)",
                            "Execution_Date_UTC": "Execution_Date(UTC)",
                            "Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)",
                            "Result_Status": "Rule_Result_Status",
                        }
                        recon_df.rename(columns=column_rename_map, inplace=True)
                    
                    # For RECONCILIATION CSV, ONLY exclude DATA_DRIFT-specific columns
                    # Keep ALL reconciliation-specific columns (Left_Column, Right_Column, Left_Rows_Scanned, 
                    # Right_Rows_Scanned, Use_For_Joining, Left_ASSET_UID, Right_ASSET_UID, Join_Type, Operation, etc.)
                    # Only exclude Drift_Threshold (DATA_DRIFT-specific)
                    drift_columns_to_exclude = ["Drift_Threshold"]
                    for col in drift_columns_to_exclude:
                        if col in recon_df.columns:
                            recon_df = recon_df.drop(columns=[col])
                    
                    # Remove PDE column if it exists
                    if "Pde" in recon_df.columns:
                        recon_df = recon_df.drop(columns=["Pde"])
                    
                    # Exclude DATA_QUALITY-specific columns that are NOT_APPLICABLE for reconciliation
                    # These would be columns like Rule_Strategy, Rule_Lower_Threshold, Rule_Upper_Threshold, Table_Asset_Name, Item_Column_Name
                    dq_specific_columns = [
                        "Rule_Strategy", "Rule_Lower_Threshold", "Rule_Upper_Threshold", 
                        "Table_Asset_Name", "Item_Column_Name"
                    ]
                    for col in dq_specific_columns:
                        if col in recon_df.columns:
                            recon_df = recon_df.drop(columns=[col])
                    
                    # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                    for col in recon_df.columns:
                        # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                        if col in recon_df.columns:
                            non_null_values = recon_df[col].dropna()
                            if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                recon_df = recon_df.drop(columns=[col])
                            elif len(non_null_values) == 0:
                                # Column is all NaN/None, exclude it
                                recon_df = recon_df.drop(columns=[col])
                    
                    # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                    if "Rule_ID" in recon_df.columns:
                        cols = list(recon_df.columns)
                        # Remove Label_Key and Label_Value if they exist
                        label_cols = []
                        if "Label_Key" in cols:
                            cols.remove("Label_Key")
                            label_cols.append("Label_Key")
                        if "Label_Value" in cols:
                            cols.remove("Label_Value")
                            label_cols.append("Label_Value")
                        
                        # Find Rule_ID position and insert Label_Key and Label_Value after it
                        if label_cols and "Rule_ID" in cols:
                            rule_id_idx = cols.index("Rule_ID")
                            # Insert after Rule_ID
                            cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                            recon_df = recon_df[cols]
                    
                    # Generate reconciliation filename
                    recon_filename = generate_execution_metrics_filename(
                        "reconciliation-metrics-%d-%m-%y-%h-%M",
                        args_model.output_type,
                        env_name,
                    )
                    recon_output_path = output_dir / recon_filename
                    
                    # Export reconciliation data
                    export_execution_metrics_to_format(
                        recon_df, recon_output_path, args_model.output_type
                    )
                    
                    progress.update(
                        recon_task, description="Reconciliation export completed!", completed=True
                    )
                    
                    console.print(
                        f"✅ Successfully exported {len(recon_df)} reconciliation records to "
                        f"{recon_output_path}",
                        style="green",
                    )
                    
                    self.trace(
                        "reconciliation_export_completed",
                        records_count=len(recon_df),
                        output_file=str(recon_output_path),
                    )
                
                # Export DATA_DRIFT records separately if available
                if not df.empty and "Policy_Type" in df.columns:
                    drift_mask = df["Policy_Type"] == "DATA_DRIFT"
                    if drift_mask.any():
                        drift_task = progress.add_task(
                            "📊 Exporting DATA_DRIFT records...", total=None
                        )
                        self.trace(
                            "starting_data_drift_export",
                            records_count=drift_mask.sum(),
                        )
                        
                        # Create DataFrame for DATA_DRIFT records
                        drift_df = df[drift_mask].copy()
                        
                        # Apply datetime renaming if needed
                        datetime_rename_map = {
                            "Started_At (UTC)": "Started_At(UTC)",
                            "Finished_At (UTC)": "Finished_At(UTC)",
                            "Execution_Date (UTC)": "Execution_Date(UTC)",
                        }
                        drift_df.rename(columns=datetime_rename_map, inplace=True)
                        
                        # Standardize column names for DATA_DRIFT
                        if "Exec_Id" in drift_df.columns:
                            drift_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                        if "Policy_Id" in drift_df.columns:
                            drift_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                        if "Item_Id" in drift_df.columns:
                            drift_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                        if "Result" in drift_df.columns:
                            drift_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                        if "Overall_Policy_Quality_Score" in drift_df.columns:
                            drift_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        if "Result_Status" in drift_df.columns:
                            drift_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                        
                        # Remove PDE column if it exists
                        if "Pde" in drift_df.columns:
                            drift_df = drift_df.drop(columns=["Pde"])
                        
                        # For DATA_DRIFT CSV, exclude Rows_Scanned, Rows_Failed, and Rule_Description
                        # (these are NOT_APPLICABLE for DATA_DRIFT)
                        columns_to_exclude = ["Rows_Scanned", "Rows_Failed", "Rule_Description"]
                        for col in columns_to_exclude:
                            if col in drift_df.columns:
                                drift_df = drift_df.drop(columns=[col])
                        
                        # Exclude reconciliation-specific columns that are NOT_APPLICABLE for DATA_DRIFT
                        recon_columns_to_exclude = [
                            "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                            "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                        ]
                        for col in recon_columns_to_exclude:
                            if col in drift_df.columns:
                                drift_df = drift_df.drop(columns=[col])
                        
                        # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                        for col in drift_df.columns:
                            # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                            if col in drift_df.columns:
                                non_null_values = drift_df[col].dropna()
                                if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                    drift_df = drift_df.drop(columns=[col])
                                elif len(non_null_values) == 0:
                                    # Column is all NaN/None, exclude it
                                    drift_df = drift_df.drop(columns=[col])
                        
                        # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                        if "Rule_ID" in drift_df.columns:
                            cols = list(drift_df.columns)
                            label_cols = []
                            if "Label_Key" in cols:
                                cols.remove("Label_Key")
                                label_cols.append("Label_Key")
                            if "Label_Value" in cols:
                                cols.remove("Label_Value")
                                label_cols.append("Label_Value")
                            
                            if label_cols and "Rule_ID" in cols:
                                rule_id_idx = cols.index("Rule_ID")
                                cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                                drift_df = drift_df[cols]
                        
                        # Generate DATA_DRIFT filename
                        drift_filename = generate_execution_metrics_filename(
                            "data-drift-metrics-%d-%m-%y-%h-%M",
                            args_model.output_type,
                            env_name,
                        )
                        drift_output_path = output_dir / drift_filename
                        
                        # Export DATA_DRIFT data
                        export_execution_metrics_to_format(
                            drift_df, drift_output_path, args_model.output_type
                        )
                        
                        progress.update(
                            drift_task, description="DATA_DRIFT export completed!", completed=True
                        )
                        
                        console.print(
                            f"✅ Successfully exported {len(drift_df)} DATA_DRIFT records to "
                            f"{drift_output_path}",
                            style="green",
                        )
                        
                        self.trace(
                            "data_drift_export_completed",
                            records_count=len(drift_df),
                            output_file=str(drift_output_path),
                        )
                
                # Export FRESHNESS records separately if available
                if not df.empty and "Policy_Type" in df.columns:
                    freshness_mask = df["Policy_Type"] == "FRESHNESS"
                    if freshness_mask.any():
                        freshness_task = progress.add_task(
                            "📊 Exporting FRESHNESS records...", total=None
                        )
                        self.trace(
                            "starting_freshness_export",
                            records_count=freshness_mask.sum(),
                        )
                        
                        # Create DataFrame for FRESHNESS records
                        freshness_df = df[freshness_mask].copy()
                        
                        # Apply datetime renaming if needed
                        datetime_rename_map = {
                            "Started_At (UTC)": "Started_At(UTC)",
                            "Finished_At (UTC)": "Finished_At(UTC)",
                            "Execution_Date (UTC)": "Execution_Date(UTC)",
                        }
                        freshness_df.rename(columns=datetime_rename_map, inplace=True)
                        
                        # Standardize column names for FRESHNESS
                        if "Exec_Id" in freshness_df.columns:
                            freshness_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                        if "Policy_Id" in freshness_df.columns:
                            freshness_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                        if "Item_Id" in freshness_df.columns:
                            freshness_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                        if "Result" in freshness_df.columns:
                            freshness_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                        if "Overall_Policy_Quality_Score" in freshness_df.columns:
                            freshness_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        if "Result_Status" in freshness_df.columns:
                            freshness_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                        
                        # Remove PDE column if it exists
                        if "Pde" in freshness_df.columns:
                            freshness_df = freshness_df.drop(columns=["Pde"])
                        
                        # For FRESHNESS CSV, exclude Rows_Scanned, Rows_Failed, Rule_Description, and Item_Column_Name
                        # (these are NOT_APPLICABLE for FRESHNESS)
                        columns_to_exclude = ["Rows_Scanned", "Rows_Failed", "Rule_Description", "Item_Column_Name"]
                        for col in columns_to_exclude:
                            if col in freshness_df.columns:
                                freshness_df = freshness_df.drop(columns=[col])
                        
                        # Exclude reconciliation-specific columns that are NOT_APPLICABLE for FRESHNESS
                        recon_columns_to_exclude = [
                            "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                            "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                        ]
                        for col in recon_columns_to_exclude:
                            if col in freshness_df.columns:
                                freshness_df = freshness_df.drop(columns=[col])
                        
                        # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                        for col in freshness_df.columns:
                            # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                            if col in freshness_df.columns:
                                non_null_values = freshness_df[col].dropna()
                                if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                    freshness_df = freshness_df.drop(columns=[col])
                                elif len(non_null_values) == 0:
                                    # Column is all NaN/None, exclude it
                                    freshness_df = freshness_df.drop(columns=[col])
                        
                        # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                        if "Rule_ID" in freshness_df.columns:
                            cols = list(freshness_df.columns)
                            label_cols = []
                            if "Label_Key" in cols:
                                cols.remove("Label_Key")
                                label_cols.append("Label_Key")
                            if "Label_Value" in cols:
                                cols.remove("Label_Value")
                                label_cols.append("Label_Value")
                            
                            if label_cols and "Rule_ID" in cols:
                                rule_id_idx = cols.index("Rule_ID")
                                cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                                freshness_df = freshness_df[cols]
                        
                        # Generate FRESHNESS filename
                        freshness_filename = generate_execution_metrics_filename(
                            "freshness-metrics-%d-%m-%y-%h-%M",
                            args_model.output_type,
                            env_name,
                        )
                        freshness_output_path = output_dir / freshness_filename
                        
                        # Export FRESHNESS data
                        export_execution_metrics_to_format(
                            freshness_df, freshness_output_path, args_model.output_type
                        )
                        
                        progress.update(
                            freshness_task, description="FRESHNESS export completed!", completed=True
                        )
                        
                        console.print(
                            f"✅ Successfully exported {len(freshness_df)} FRESHNESS records to "
                            f"{freshness_output_path}",
                            style="green",
                        )
                        
                        self.trace(
                            "freshness_export_completed",
                            records_count=len(freshness_df),
                            output_file=str(freshness_output_path),
                        )
                
                # Export SCHEMA_DRIFT records separately if available
                if not df.empty and "Policy_Type" in df.columns:
                    schema_drift_mask = df["Policy_Type"] == "SCHEMA_DRIFT"
                    if schema_drift_mask.any():
                        schema_drift_task = progress.add_task(
                            "📊 Exporting SCHEMA_DRIFT records...", total=None
                        )
                        self.trace(
                            "starting_schema_drift_export",
                            records_count=schema_drift_mask.sum(),
                        )
                        
                        # Create DataFrame for SCHEMA_DRIFT records
                        schema_drift_df = df[schema_drift_mask].copy()
                        
                        # Apply datetime renaming if needed
                        datetime_rename_map = {
                            "Started_At (UTC)": "Started_At(UTC)",
                            "Finished_At (UTC)": "Finished_At(UTC)",
                            "Execution_Date (UTC)": "Execution_Date(UTC)",
                        }
                        schema_drift_df.rename(columns=datetime_rename_map, inplace=True)
                        
                        # Standardize column names for SCHEMA_DRIFT
                        if "Exec_Id" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                        if "Policy_Id" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                        if "Item_Id" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                        if "Result" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                        if "Overall_Policy_Quality_Score" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        if "Result_Status" in schema_drift_df.columns:
                            schema_drift_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                        
                        # Remove PDE column if it exists
                        if "Pde" in schema_drift_df.columns:
                            schema_drift_df = schema_drift_df.drop(columns=["Pde"])
                        
                        # For SCHEMA_DRIFT CSV, exclude NOT_APPLICABLE columns
                        columns_to_exclude = [
                            "Rule_Success_Rate", "Item_Column_Name", "Item_Measurement_Type",
                            "Rule_Strategy", "Rule_Lower_Threshold", "Rule_Upper_Threshold",
                            "Rows_Scanned", "Rows_Failed", "Rule_Description"
                        ]
                        for col in columns_to_exclude:
                            if col in schema_drift_df.columns:
                                schema_drift_df = schema_drift_df.drop(columns=[col])
                        
                        # Exclude reconciliation-specific columns that are NOT_APPLICABLE for SCHEMA_DRIFT
                        recon_columns_to_exclude = [
                            "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                            "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                        ]
                        for col in recon_columns_to_exclude:
                            if col in schema_drift_df.columns:
                                schema_drift_df = schema_drift_df.drop(columns=[col])
                        
                        # Exclude DATA_DRIFT-specific columns that are NOT_APPLICABLE for SCHEMA_DRIFT
                        drift_columns_to_exclude = ["Drift_Threshold"]
                        for col in drift_columns_to_exclude:
                            if col in schema_drift_df.columns:
                                schema_drift_df = schema_drift_df.drop(columns=[col])
                        
                        # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                        for col in schema_drift_df.columns:
                            # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                            if col in schema_drift_df.columns:
                                non_null_values = schema_drift_df[col].dropna()
                                if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                    schema_drift_df = schema_drift_df.drop(columns=[col])
                                elif len(non_null_values) == 0:
                                    # Column is all NaN/None, exclude it
                                    schema_drift_df = schema_drift_df.drop(columns=[col])
                        
                        # Reorder columns: put Label_Key and Label_Value right after Rule_ID
                        if "Rule_ID" in schema_drift_df.columns:
                            cols = list(schema_drift_df.columns)
                            label_cols = []
                            if "Label_Key" in cols:
                                cols.remove("Label_Key")
                                label_cols.append("Label_Key")
                            if "Label_Value" in cols:
                                cols.remove("Label_Value")
                                label_cols.append("Label_Value")
                            
                            if label_cols and "Rule_ID" in cols:
                                rule_id_idx = cols.index("Rule_ID")
                                cols = cols[:rule_id_idx + 1] + label_cols + cols[rule_id_idx + 1:]
                                schema_drift_df = schema_drift_df[cols]
                        
                        # Generate SCHEMA_DRIFT filename
                        schema_drift_filename = generate_execution_metrics_filename(
                            "schema-drift-metrics-%d-%m-%y-%h-%M",
                            args_model.output_type,
                            env_name,
                        )
                        schema_drift_output_path = output_dir / schema_drift_filename
                        
                        # Export SCHEMA_DRIFT data
                        export_execution_metrics_to_format(
                            schema_drift_df, schema_drift_output_path, args_model.output_type
                        )
                        
                        progress.update(
                            schema_drift_task, description="SCHEMA_DRIFT export completed!", completed=True
                        )
                        
                        console.print(
                            f"✅ Successfully exported {len(schema_drift_df)} SCHEMA_DRIFT records to "
                            f"{schema_drift_output_path}",
                            style="green",
                        )
                        
                        self.trace(
                            "schema_drift_export_completed",
                            records_count=len(schema_drift_df),
                            output_file=str(schema_drift_output_path),
                        )
                
                # Export PROFILE_ANOMALY records separately if available
                if not df.empty and "Policy_Type" in df.columns:
                    profile_anomaly_mask = df["Policy_Type"] == "PROFILE_ANOMALY"
                    if profile_anomaly_mask.any():
                        profile_anomaly_task = progress.add_task(
                            "📊 Exporting PROFILE_ANOMALY records...", total=None
                        )
                        self.trace(
                            "starting_profile_anomaly_export",
                            records_count=profile_anomaly_mask.sum(),
                        )
                        
                        # Create DataFrame for PROFILE_ANOMALY records
                        profile_anomaly_df = df[profile_anomaly_mask].copy()
                        
                        # Apply datetime renaming if needed
                        datetime_rename_map = {
                            "Started_At (UTC)": "Started_At(UTC)",
                            "Finished_At (UTC)": "Finished_At(UTC)",
                            "Execution_Date (UTC)": "Execution_Date(UTC)",
                        }
                        profile_anomaly_df.rename(columns=datetime_rename_map, inplace=True)
                        
                        # Standardize column names for PROFILE_ANOMALY
                        if "Exec_Id" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Exec_Id": "Execution_ID"}, inplace=True)
                        if "Policy_Id" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Policy_Id": "Policy_ID"}, inplace=True)
                        if "Item_Id" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Item_Id": "Rule_ID"}, inplace=True)
                        if "Result" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Result": "Rule_Success_Rate"}, inplace=True)
                        if "Overall_Policy_Quality_Score" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Overall_Policy_Quality_Score": "Overall_Policy_Quality_Score(Percentage)"}, inplace=True)
                        if "Result_Status" in profile_anomaly_df.columns:
                            profile_anomaly_df.rename(columns={"Result_Status": "Rule_Result_Status"}, inplace=True)
                        
                        # Remove PDE column if it exists
                        if "Pde" in profile_anomaly_df.columns:
                            profile_anomaly_df = profile_anomaly_df.drop(columns=["Pde"])
                        
                        # For PROFILE_ANOMALY CSV, exclude NOT_APPLICABLE columns
                        columns_to_exclude = [
                            "Rule_Strategy", "Rule_Lower_Threshold", "Rule_Upper_Threshold",
                            "Label_Key", "Label_Value", "Rule_Success_Rate", "Rule_Result_Status",
                            "Rows_Scanned", "Rows_Failed", "Asset_Addition", "Asset_Deletion",
                            "Data_Type", "Asset_Relation_Change", "Asset_Metadata", "Metadata_Configs",
                            "Policy_Description", "Rule_Description"
                        ]
                        for col in columns_to_exclude:
                            if col in profile_anomaly_df.columns:
                                profile_anomaly_df = profile_anomaly_df.drop(columns=[col])
                        
                        # Exclude reconciliation-specific columns that are NOT_APPLICABLE for PROFILE_ANOMALY
                        recon_columns_to_exclude = [
                            "Left_Column", "Right_Column", "Left_Rows_Scanned", "Right_Rows_Scanned",
                            "Use_For_Joining", "Left_ASSET_UID", "Right_ASSET_UID", "Join_Type", "Operation"
                        ]
                        for col in recon_columns_to_exclude:
                            if col in profile_anomaly_df.columns:
                                profile_anomaly_df = profile_anomaly_df.drop(columns=[col])
                        
                        # Exclude DATA_DRIFT-specific columns that are NOT_APPLICABLE for PROFILE_ANOMALY
                        drift_columns_to_exclude = ["Drift_Threshold"]
                        for col in drift_columns_to_exclude:
                            if col in profile_anomaly_df.columns:
                                profile_anomaly_df = profile_anomaly_df.drop(columns=[col])
                        
                        # Also exclude any columns that are entirely "NOT_APPLICABLE" (including NaN that were filled)
                        for col in list(profile_anomaly_df.columns):
                            # Check if all non-null values are "NOT_APPLICABLE" or if column is all NaN/None
                            non_null_values = profile_anomaly_df[col].dropna()
                            if len(non_null_values) > 0 and (non_null_values == "NOT_APPLICABLE").all():
                                profile_anomaly_df = profile_anomaly_df.drop(columns=[col])
                            elif len(non_null_values) == 0:
                                # Column is all NaN/None, exclude it
                                profile_anomaly_df = profile_anomaly_df.drop(columns=[col])
                        
                        # Generate PROFILE_ANOMALY filename
                        profile_anomaly_filename = generate_execution_metrics_filename(
                            "profile-anomaly-metrics-%d-%m-%y-%h-%M",
                            args_model.output_type,
                            env_name,
                        )
                        profile_anomaly_output_path = output_dir / profile_anomaly_filename
                        
                        # Export PROFILE_ANOMALY data
                        export_execution_metrics_to_format(
                            profile_anomaly_df, profile_anomaly_output_path, args_model.output_type
                        )
                        
                        progress.update(
                            profile_anomaly_task, description="PROFILE_ANOMALY export completed!", completed=True
                        )
                        
                        console.print(
                            f"✅ Successfully exported {len(profile_anomaly_df)} PROFILE_ANOMALY records to "
                            f"{profile_anomaly_output_path}",
                            style="green",
                        )
                        
                        self.trace(
                            "profile_anomaly_export_completed",
                            records_count=len(profile_anomaly_df),
                            output_file=str(profile_anomaly_output_path),
                        )

                # Update tracking information using checkpoint captured at START
                # This prevents data loss from jobs that complete during processing
                new_last_run_info = LastRunInfo(
                    last_run_timestamp=new_checkpoint_timestamp,
                    last_run_datetime=new_checkpoint_dt,
                    timezone=timezone,  # Store timezone separately for clarity
                    total_records_processed=len(df),  # Use final count after dedup
                )
                service.save_last_run_info(tracking_file, new_last_run_info)
                
                self.trace(
                    "checkpoint_saved",
                    checkpoint_timestamp=new_checkpoint_timestamp,
                    checkpoint_datetime=new_checkpoint_dt.isoformat(),
                    records_processed=len(df),
                )

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
