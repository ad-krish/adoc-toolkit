"""Service for handling execution metrics data fetching and processing."""

import decimal
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any

from rich.progress import Progress, SpinnerColumn, TextColumn

from ...http import ADOCHTTPClient
from ...logs import log_error, log_info
from ...models import (
    ExecutionDetail,
    ExecutionMetricsRecord,
    LastRunInfo,
    PolicyDetail,
    PolicyExecution,
)
from ...tracing import TraceableMixin, trace_method

# Try to import zoneinfo (Python 3.9+), fall back to pytz
try:
    from zoneinfo import ZoneInfo

    def get_timezone(tz_name: str):
        """Get timezone object using zoneinfo."""
        return ZoneInfo(tz_name)

except ImportError:
    try:
        import pytz

        def get_timezone(tz_name: str):
            """Get timezone object using pytz."""
            return pytz.timezone(tz_name)

    except ImportError:

        def get_timezone(tz_name: str):
            """Fallback: return None if no timezone library available."""
            return None


def safe_get(data: dict[str, Any], key: str, default: Any = None) -> Any:
    """Safely get value from dictionary with default fallback.

    Args:
        data: Dictionary to get value from
        key: Key to look up
        default: Default value if key not found

    Returns:
        Value from dictionary or default
    """
    return data.get(key, default) if data else default


def get_current_datetime(timezone: str = "UTC") -> datetime:
    """Get current datetime in specified timezone (timezone-aware).

    Args:
        timezone: Timezone name (e.g., UTC, US/Eastern, Asia/Kolkata)

    Returns:
        Timezone-aware datetime object in specified timezone
    """
    try:
        from zoneinfo import ZoneInfo
        return datetime.now(ZoneInfo(timezone))
    except ImportError:
        import pytz
        tz = pytz.timezone(timezone)
        return datetime.now(tz)
    except Exception:
        # Fallback to UTC if timezone is invalid
        try:
            from zoneinfo import ZoneInfo
            return datetime.now(ZoneInfo("UTC"))
        except ImportError:
            import pytz
            return datetime.now(pytz.UTC)


def convert_timestamp_to_datetime(
    timestamp: int | str | None, timezone: str = "UTC"
) -> datetime | None:
    """Convert millisecond timestamp or ISO string to datetime in specified timezone.

    Args:
        timestamp: Timestamp in milliseconds (int) or ISO format string (str)
        timezone: Timezone name (e.g., UTC, US/Eastern, Asia/Kolkata)

    Returns:
        Datetime object in specified timezone or None
    """
    # Return None for missing timestamps
    if timestamp is None:
        return None
    
    try:
        # Handle string timestamps (ISO format)
        if isinstance(timestamp, str):
            # Try parsing as ISO format datetime string
            dt_utc = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
            if dt_utc.tzinfo is None:
                # Assume UTC if no timezone info
                try:
                    from zoneinfo import ZoneInfo
                    dt_utc = dt_utc.replace(tzinfo=ZoneInfo("UTC"))
                except ImportError:
                    import pytz
                    dt_utc = pytz.UTC.localize(dt_utc)
        else:
            # Handle numeric timestamps
            # Return None for zero or invalid timestamps
            if timestamp <= 0:
                return None
            
            # Convert from milliseconds to seconds and create UTC datetime
            try:
                from zoneinfo import ZoneInfo
                dt_utc = datetime.fromtimestamp(timestamp / 1000, tz=ZoneInfo("UTC"))
            except ImportError:
                import pytz
                dt_utc = datetime.utcfromtimestamp(timestamp / 1000)
                dt_utc = pytz.UTC.localize(dt_utc)
        
        # If timezone is not UTC, convert to target timezone
        if timezone != "UTC":
            tz = get_timezone(timezone)
            if tz:
                return dt_utc.astimezone(tz)
            # If timezone conversion fails, return UTC datetime without tzinfo
            return dt_utc.replace(tzinfo=None)
        
        # Return UTC datetime without tzinfo for consistency
        return dt_utc.replace(tzinfo=None)
    except (ValueError, OSError, AttributeError):
        return None


def calculate_failed_rows(rows_scanned: int | None, result: str | None) -> int:
    """Calculate number of failed rows based on scanned and result.

    Args:
        rows_scanned: Total rows scanned
        result: Result percentage as string

    Returns:
        Number of failed rows
    """
    if rows_scanned is None or result is None:
        return 0

    try:
        d_rows_scanned = Decimal(str(rows_scanned))
        d_result = Decimal(str(result))
        return int((1 - d_result) * d_rows_scanned)
    except (ValueError, TypeError, decimal.InvalidOperation):
        return 0


class ThreadSafeDataCollector:
    """Thread-safe data collector for parallel processing."""

    def __init__(self) -> None:
        """Initialize the thread-safe data collector."""
        self._lock = threading.Lock()
        self._data = []

    def add(self, item: Any) -> None:
        """Add an item to the collection in a thread-safe manner."""
        with self._lock:
            self._data.append(item)

    def extend(self, items: list[Any]) -> None:
        """Add multiple items to the collection in a thread-safe manner."""
        with self._lock:
            self._data.extend(items)

    def get_all(self) -> list[Any]:
        """Get all collected data."""
        with self._lock:
            return self._data.copy()

    def clear(self) -> None:
        """Clear all collected data."""
        with self._lock:
            self._data.clear()


def fetch_execution_page(
    page: int,
    exec_count: int,
    policy_types: list[str],
    http_client: ADOCHTTPClient,
    progress: Progress,
    task_id: str,
    timezone: str = "UTC",
) -> tuple[int, list[PolicyExecution], bool]:
    """Fetch a single page of policy executions.

    Args:
        page: Page number to fetch
        exec_count: Number of executions per page
        policy_types: List of policy types to filter
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID for this thread

    Returns:
        Tuple of (page_number, list_of_executions, should_stop)
    """
    try:
        progress.update(task_id, description=f"Fetching page {page + 1}...", advance=0)

        rule_types_param = ",".join(policy_types)
        endpoint = (
            f"/catalog-server/api/rules/executions"
            f"?page={page}&size={exec_count}&sortBy=execution.startedAt:DESC"
            "&executionStatus=SUCCESSFUL,ERRORED,ABORTED,WARNING"
            f"&ruleType={rule_types_param}"
        )

        response = http_client.get(endpoint)
        if not response.is_success:
            log_error(
                f"Failed to fetch executions page {page}: HTTP {response.status_code}"
            )
            return page, [], False

        exec_data = response.json()
        executions = safe_get(exec_data, "executions", [])

        if not executions:
            return page, [], True  # No more data, stop

        # Process the executions (we'll filter by timestamp later)
        page_executions = process_policy_executions(exec_data, 0, policy_types, timezone)

        progress.update(
            task_id,
            description=f"Page {page + 1}: {len(page_executions)} executions",
            advance=1,
        )

        return page, page_executions, False

    except Exception as e:
        log_error(f"Error fetching executions page {page}: {e}")
        return page, [], False


def process_execution_details_parallel(
    execution: PolicyExecution,
    http_client: ADOCHTTPClient,
    progress: Progress,
    task_id: str,
) -> list[ExecutionDetail]:
    """Process execution details for a single execution in parallel.

    Args:
        execution: Policy execution to process
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID for this thread

    Returns:
        List of ExecutionDetail models
    """
    execution_details = []

    try:
        progress.update(
            task_id,
            description=(
                f"Processing {execution.policy_type} execution "
                f"{execution.execution_id}..."
            ),
            advance=0,
        )

        # Build endpoint based on policy type
        if execution.policy_type == "DATA_QUALITY":
            endpoint = (
                f"/catalog-server/api/rules/data-quality/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "EQUALITY":
            endpoint = (
                f"/catalog-server/api/rules/equality/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "DATA_DRIFT":
            endpoint = (
                f"/catalog-server/api/rules/data-drift/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "PROFILE_ANOMALY":
            endpoint = (
                f"/catalog-server/api/rules/profile-anomaly/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "SCHEMA_DRIFT":
            endpoint = (
                f"/catalog-server/api/rules/schema-drift/executions/"
                f"{execution.execution_id}"
            )
        else:
            log_error(f"Unsupported policy type: {execution.policy_type}")
            return execution_details

        response = http_client.get(endpoint)

        if not response.is_success:
            log_error(f"Failed to fetch execution details for {execution.execution_id}")
            return execution_details

        exec_result_data = response.json()

        for item in safe_get(exec_result_data, "items", []):
            labels = safe_get(item, "labels", [])
            pde_value = next(
                (
                    safe_get(label, "value")
                    for label in labels
                    if safe_get(label, "key") == "PDE"
                ),
                None,
            )

            item_data = safe_get(item, "item", {})
            item_labels = safe_get(item_data, "labels", [])
            pde_label = next(
                (
                    safe_get(label, "value")
                    for label in item_labels
                    if safe_get(label, "key") == "PDE"
                ),
                None,
            )

            rows_scanned = safe_get(item, "rowsScanned")
            rule_result = safe_get(item, "result")

            threshold_config = safe_get(item, "thresholdConfig", {})

            execution_detail = ExecutionDetail(
                item_id=safe_get(item_data, "id", ""),
                item_column_name=safe_get(item_data, "columnName"),
                item_ver=safe_get(item_data, "ruleVersion", 1),
                pde_name=pde_value,
                pde=pde_label,
                item_measurement_type=safe_get(item_data, "measurementType"),
                rule_item_id=safe_get(item, "ruleItemId"),
                rule_strategy=safe_get(threshold_config, "strategy"),
                rule_lower_threshold=safe_get(threshold_config, "lower"),
                rule_upper_threshold=safe_get(threshold_config, "upper"),
                result=rule_result,
                rows_scanned=rows_scanned,
                rows_failed=calculate_failed_rows(rows_scanned, rule_result),
                exec_id=execution.execution_id,
                start_ts=execution.start_ts,
                end_ts=execution.end_ts,
                execution_status=execution.execution_status,
            )
            execution_details.append(execution_detail)

        progress.update(
            task_id,
            description=(
                f"Processed {execution.policy_type} execution: "
                f"{len(execution_details)} details"
            ),
            advance=1,
        )

    except Exception as e:
        log_error(f"Error processing execution {execution.execution_id}: {e}")

    return execution_details


def process_policy_details_parallel(
    execution: PolicyExecution,
    http_client: ADOCHTTPClient,
    progress: Progress,
    task_id: str,
) -> list[PolicyDetail]:
    """Process policy details for a single execution in parallel.

    Args:
        execution: Policy execution to process
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID for this thread

    Returns:
        List of PolicyDetail models
    """
    policy_details = []

    try:
        progress.update(
            task_id,
            description=(
                f"Processing {execution.policy_type} policy details "
                f"{execution.policy_id}..."
            ),
            advance=0,
        )

        # Build endpoint based on policy type
        if execution.policy_type == "DATA_QUALITY":
            endpoint = (
                f"/catalog-server/api/rules/data-quality/{execution.policy_id}"
                f"?version={execution.policy_version}"
            )
        elif execution.policy_type == "EQUALITY":
            endpoint = (
                f"/catalog-server/api/rules/equality/{execution.policy_id}"
                f"?version={execution.policy_version}"
            )
        elif execution.policy_type == "DATA_DRIFT":
            endpoint = (
                f"/catalog-server/api/rules/data-drift/{execution.policy_id}"
                f"?version={execution.policy_version}"
            )
        elif execution.policy_type == "PROFILE_ANOMALY":
            endpoint = (
                f"/catalog-server/api/rules/profile-anomaly/{execution.policy_id}"
                f"?version={execution.policy_version}"
            )
        elif execution.policy_type == "SCHEMA_DRIFT":
            endpoint = (
                f"/catalog-server/api/rules/schema-drift/{execution.policy_id}"
                f"?version={execution.policy_version}"
            )
        else:
            log_error(f"Unsupported policy type: {execution.policy_type}")
            return policy_details

        response = http_client.get(endpoint)

        if not response.is_success:
            log_error(f"Failed to fetch policy details for {execution.policy_id}")
            return policy_details

        policy_detail_data = response.json()
        rule_data = safe_get(policy_detail_data, "rule", {})
        backing_asset = safe_get(rule_data, "backingAsset", {})
        table_asset_id = safe_get(backing_asset, "tableAssetId")

        # Fetch table asset name
        table_asset_name = (
            fetch_asset_name(table_asset_id, http_client) if table_asset_id else None
        )

        details_data = safe_get(policy_detail_data, "details", {})
        for item in safe_get(details_data, "items", []):
            pde_value = next(
                (
                    safe_get(label, "value")
                    for label in safe_get(item, "labels", [])
                    if safe_get(label, "key") == "PDE"
                ),
                None,
            )

            policy_detail = PolicyDetail(
                policy_name=execution.policy_name,
                policy_id=execution.policy_id,
                policy_type=execution.policy_type,
                id=safe_get(item, "id", ""),
                rule_version=safe_get(item, "ruleVersion", 1),
                column_name=safe_get(item, "columnName"),
                pde_value=pde_value,
                table_asset_id=table_asset_id,
                table_asset_name=table_asset_name,
            )
            policy_details.append(policy_detail)

        progress.update(
            task_id,
            description=(
                f"Processed {execution.policy_type} policy: "
                f"{len(policy_details)} details"
            ),
            advance=1,
        )

    except Exception as e:
        log_error(f"Error processing policy details for {execution.policy_id}: {e}")

    return policy_details


def process_policy_executions(
    executions_data: dict[str, Any],
    start_ts_marker: int,
    policy_types: list[str] | None = None,
    timezone: str = "UTC",
) -> list[PolicyExecution]:
    """Process policy executions data into PolicyExecution models.

    Args:
        executions_data: Raw execution data from API
        start_ts_marker: Timestamp marker for incremental processing
        policy_types: List of policy types to filter (default: all supported types)

    Returns:
        List of PolicyExecution models
    """
    if policy_types is None:
        policy_types = [
            "DATA_QUALITY",
            "EQUALITY",
            "DATA_DRIFT",
            "PROFILE_ANOMALY",
            "SCHEMA_DRIFT",
        ]

    policy_executions = []

    for execution in safe_get(executions_data, "executions", []):
        ex = safe_get(execution, "execution", {})
        start_ts = safe_get(ex, "startedAt")

        # Skip if timestamp is before marker (incremental processing)
        if start_ts is not None and start_ts <= start_ts_marker:
            continue

        policy_type = safe_get(ex, "ruleType")
        if policy_type in policy_types:
            result = safe_get(execution, "result") or {}

            policy_execution = PolicyExecution(
                policy_name=safe_get(ex, "ruleName", ""),
                policy_version=safe_get(ex, "ruleVersion", 1),
                policy_id=safe_get(ex, "ruleId", ""),
                policy_type=policy_type,
                execution_id=safe_get(ex, "id", ""),
                execution_status=safe_get(ex, "executionStatus", ""),
                result_status=safe_get(ex, "resultStatus"),
                score=safe_get(result, "qualityScore"),
                rows=safe_get(result, "rows"),
                failed_rows=safe_get(result, "failedRows"),
                success_rules=safe_get(result, "successCount"),
                failure_rules=safe_get(result, "failureCount"),
                start_timestamp=convert_timestamp_to_datetime(start_ts, timezone),
                start_ts=start_ts,
                end_timestamp=convert_timestamp_to_datetime(safe_get(ex, "finishedAt"), timezone),
                end_ts=safe_get(ex, "finishedAt"),
            )
            policy_executions.append(policy_execution)

    return policy_executions


def process_execution_details(
    policy_executions: list[PolicyExecution],
    http_client: ADOCHTTPClient,
    progress: Progress,
    task_id,
) -> list[ExecutionDetail]:
    """Process execution details for policies.

    Args:
        policy_executions: List of policy executions
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID

    Returns:
        List of ExecutionDetail models
    """
    execution_details = []
    processed_count = 0

    for execution in policy_executions:
        try:
            progress.update(
                task_id,
                description=(
                    f"Processing {execution.policy_type} execution "
                    f"{processed_count + 1}..."
                ),
            )

            # Build endpoint based on policy type
            if execution.policy_type == "DATA_QUALITY":
                endpoint = (
                    f"/catalog-server/api/rules/data-quality/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "EQUALITY":
                endpoint = (
                    f"/catalog-server/api/rules/equality/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "DATA_DRIFT":
                endpoint = (
                    f"/catalog-server/api/rules/data-drift/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "PROFILE_ANOMALY":
                endpoint = (
                    f"/catalog-server/api/rules/profile-anomaly/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "SCHEMA_DRIFT":
                endpoint = (
                    f"/catalog-server/api/rules/schema-drift/executions/"
                    f"{execution.execution_id}"
                )
            else:
                log_error(f"Unsupported policy type: {execution.policy_type}")
                continue

            response = http_client.get(endpoint)

            if not response.is_success:
                log_error(
                    f"Failed to fetch execution details for "
                    f"{execution.execution_id}"
                )
                continue

            exec_result_data = response.json()

            for item in safe_get(exec_result_data, "items", []):
                labels = safe_get(item, "labels", [])
                pde_value = next(
                    (
                        safe_get(label, "value")
                        for label in labels
                        if safe_get(label, "key") == "PDE"
                    ),
                    None,
                )

                item_data = safe_get(item, "item", {})
                item_labels = safe_get(item_data, "labels", [])
                pde_label = next(
                    (
                        safe_get(label, "value")
                        for label in item_labels
                        if safe_get(label, "key") == "PDE"
                    ),
                    None,
                )

                rows_scanned = safe_get(item, "rowsScanned")
                rule_result = safe_get(item, "result")

                threshold_config = safe_get(item, "thresholdConfig", {})

                execution_detail = ExecutionDetail(
                    item_id=safe_get(item_data, "id", ""),
                    item_column_name=safe_get(item_data, "columnName"),
                    item_ver=safe_get(item_data, "ruleVersion", 1),
                    pde_name=pde_value,
                    pde=pde_label,
                    item_measurement_type=safe_get(item_data, "measurementType"),
                    rule_item_id=safe_get(item, "ruleItemId"),
                    rule_strategy=safe_get(threshold_config, "strategy"),
                    rule_lower_threshold=safe_get(threshold_config, "lower"),
                    rule_upper_threshold=safe_get(threshold_config, "upper"),
                    result=rule_result,
                    rows_scanned=rows_scanned,
                    rows_failed=calculate_failed_rows(rows_scanned, rule_result),
                    exec_id=execution.execution_id,
                    start_ts=execution.start_ts,
                    end_ts=execution.end_ts,
                    execution_status=execution.execution_status,
                )
                execution_details.append(execution_detail)

        except Exception as e:
            log_error(f"Error processing execution {execution.execution_id}: {e}")
            continue

        processed_count += 1
        if processed_count % 25 == 0:
            progress.update(
                task_id, description=f"Processed {processed_count} executions..."
            )

    return execution_details


def fetch_asset_name(asset_id: str, http_client: ADOCHTTPClient) -> str | None:
    """Fetch asset name from asset ID.

    Args:
        asset_id: Asset identifier
        http_client: HTTP client for API calls

    Returns:
        Asset name or None if not found
    """
    try:
        endpoint = f"/catalog-server/api/assets/{asset_id}/overview"
        response = http_client.get(endpoint)

        if not response.is_success:
            return None

        data = response.json()
        asset_overview = safe_get(data, "assetOverview", {})
        asset_data = safe_get(asset_overview, "asset", {})
        return safe_get(asset_data, "uid")

    except Exception as e:
        log_error(f"Error fetching asset name for {asset_id}: {e}")
        return None


def process_policy_details(
    policy_executions: list[PolicyExecution],
    http_client: ADOCHTTPClient,
    progress: Progress,
    task_id,
) -> list[PolicyDetail]:
    """Process policy details for policies.

    Args:
        policy_executions: List of policy executions
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID

    Returns:
        List of PolicyDetail models
    """
    policy_details = []
    processed_count = 0

    # Get unique policies (deduplicate by policy_id and policy_version)
    unique_policies = {}
    for execution in policy_executions:
        key = (execution.policy_id, execution.policy_version)
        if key not in unique_policies:
            unique_policies[key] = execution

    for execution in unique_policies.values():
        try:
            progress.update(
                task_id,
                description=(
                    f"Processing {execution.policy_type} policy details "
                    f"{processed_count + 1}..."
                ),
            )

            # Build endpoint based on policy type
            if execution.policy_type == "DATA_QUALITY":
                endpoint = (
                    f"/catalog-server/api/rules/data-quality/{execution.policy_id}"
                    f"?version={execution.policy_version}"
                )
            elif execution.policy_type == "EQUALITY":
                endpoint = (
                    f"/catalog-server/api/rules/equality/{execution.policy_id}"
                    f"?version={execution.policy_version}"
                )
            elif execution.policy_type == "DATA_DRIFT":
                endpoint = (
                    f"/catalog-server/api/rules/data-drift/{execution.policy_id}"
                    f"?version={execution.policy_version}"
                )
            elif execution.policy_type == "PROFILE_ANOMALY":
                endpoint = (
                    f"/catalog-server/api/rules/profile-anomaly/{execution.policy_id}"
                    f"?version={execution.policy_version}"
                )
            elif execution.policy_type == "SCHEMA_DRIFT":
                endpoint = (
                    f"/catalog-server/api/rules/schema-drift/{execution.policy_id}"
                    f"?version={execution.policy_version}"
                )
            else:
                log_error(f"Unsupported policy type: {execution.policy_type}")
                continue

            response = http_client.get(endpoint)

            if not response.is_success:
                log_error(f"Failed to fetch policy details for {execution.policy_id}")
                continue

            policy_detail_data = response.json()
            rule_data = safe_get(policy_detail_data, "rule", {})
            backing_asset = safe_get(rule_data, "backingAsset", {})
            table_asset_id = safe_get(backing_asset, "tableAssetId")

            # Fetch table asset name
            table_asset_name = (
                fetch_asset_name(table_asset_id, http_client)
                if table_asset_id
                else None
            )

            details_data = safe_get(policy_detail_data, "details", {})
            for item in safe_get(details_data, "items", []):
                pde_value = next(
                    (
                        safe_get(label, "value")
                        for label in safe_get(item, "labels", [])
                        if safe_get(label, "key") == "PDE"
                    ),
                    None,
                )

                policy_detail = PolicyDetail(
                    policy_name=execution.policy_name,
                    policy_id=execution.policy_id,
                    policy_type=execution.policy_type,
                    id=safe_get(item, "id", ""),
                    rule_version=safe_get(item, "ruleVersion", 1),
                    column_name=safe_get(item, "columnName"),
                    pde_value=pde_value,
                    table_asset_id=table_asset_id,
                    table_asset_name=table_asset_name,
                )
                policy_details.append(policy_detail)

        except Exception as e:
            log_error(f"Error processing policy details for {execution.policy_id}: {e}")
            continue

        processed_count += 1
        if processed_count % 10 == 0:
            progress.update(
                task_id, description=f"Processed {processed_count} policy details..."
            )

    return policy_details


def merge_execution_data(
    execution_details: list[ExecutionDetail], policy_details: list[PolicyDetail], timezone: str = "UTC"
) -> list[ExecutionMetricsRecord]:
    """Merge execution details with policy details.

    Args:
        execution_details: List of execution details
        policy_details: List of policy details

    Returns:
        List of merged ExecutionMetricsRecord models
    """
    # Create lookup dictionary for policy details
    policy_lookup = {}
    for detail in policy_details:
        key = (detail.id, detail.rule_version)
        policy_lookup[key] = detail

    merged_records = []
    for exec_detail in execution_details:
        key = (exec_detail.item_id, exec_detail.item_ver)
        policy_detail = policy_lookup.get(key)

        if policy_detail:
            record = ExecutionMetricsRecord(
                policy_name=policy_detail.policy_name,
                policy_id=policy_detail.policy_id,
                rule_version=exec_detail.item_ver,
                exec_id=exec_detail.exec_id,
                table_asset_name=policy_detail.table_asset_name,
                item_column_name=exec_detail.item_column_name,
                pde=exec_detail.pde,
                item_measurement_type=exec_detail.item_measurement_type,
                rule_strategy=exec_detail.rule_strategy,
                rule_lower_threshold=exec_detail.rule_lower_threshold,
                rule_upper_threshold=exec_detail.rule_upper_threshold,
                item_id=exec_detail.item_id,
                result=exec_detail.result,
                rows_scanned=exec_detail.rows_scanned,
                rows_failed=exec_detail.rows_failed,
                startedAt=exec_detail.start_ts,
                started_at=convert_timestamp_to_datetime(exec_detail.start_ts, timezone),
                finishedAt=exec_detail.end_ts,
                finished_at=convert_timestamp_to_datetime(exec_detail.end_ts, timezone),
                execution_date=convert_timestamp_to_datetime(exec_detail.end_ts, timezone),
                execution_status=exec_detail.execution_status,
                policy_type=policy_detail.policy_type,
            )
            merged_records.append(record)

    return merged_records


class ExecutionMetricsService(TraceableMixin):
    """Service for fetching and processing execution metrics data."""

    def __init__(self, http_client: ADOCHTTPClient, timezone: str = "UTC"):
        """Initialize ExecutionMetricsService.

        Args:
            http_client: HTTP client for API interactions
            timezone: Timezone for datetime conversions (default: UTC)
        """
        self.http_client = http_client
        self.timezone = timezone

    @property
    def trace_prefix(self) -> str | None:
        """Get the trace prefix for this service."""
        return "execution_metrics_service"

    @trace_method("load_last_run_info", "execution_metrics_service")
    def load_last_run_info(
        self, tracking_file: Path, backload_datetime: datetime | None = None
    ) -> LastRunInfo:
        """Load last run information from tracking file.

        Args:
            tracking_file: Path to tracking file
            backload_datetime: Optional datetime to override tracking file behavior

        Returns:
            LastRunInfo model with tracking data
        """
        # If backload_datetime is provided, always use it (override tracking file)
        if backload_datetime:
            start_datetime = backload_datetime
            start_timestamp = int(start_datetime.timestamp() * 1000)
            log_info(
                f"Using backload datetime (overriding tracking file): {start_datetime}"
            )
            return LastRunInfo(
                last_run_timestamp=start_timestamp,
                last_run_datetime=start_datetime,
                total_records_processed=0,
            )

        # No backload specified, use tracking file if it exists
        if not tracking_file.exists():
            # First run without backload - default to 30 days ago
            start_datetime = datetime.now() - timedelta(days=30)
            start_timestamp = int(start_datetime.timestamp() * 1000)
            log_info(f"First run detected. Defaulting to 30 days ago: {start_datetime}")
            return LastRunInfo(
                last_run_timestamp=start_timestamp,
                last_run_datetime=start_datetime,
                total_records_processed=0,
            )

        # Load from tracking file
        try:
            with open(tracking_file, encoding="utf-8") as f:
                data = json.load(f)

            return LastRunInfo(
                last_run_timestamp=data.get("last_run_timestamp"),
                last_run_datetime=datetime.fromisoformat(data.get("last_run_datetime"))
                if data.get("last_run_datetime")
                else None,
                total_records_processed=data.get("total_records_processed", 0),
            )
        except (json.JSONDecodeError, ValueError, OSError) as e:
            log_error(f"Error loading last run info: {e}")
            # Default to 30 days ago on error
            thirty_days_ago = datetime.now() - timedelta(days=30)
            thirty_days_ago_ts = int(thirty_days_ago.timestamp() * 1000)

            return LastRunInfo(
                last_run_timestamp=thirty_days_ago_ts,
                last_run_datetime=thirty_days_ago,
                total_records_processed=0,
            )

    @trace_method("save_last_run_info", "execution_metrics_service")
    def save_last_run_info(
        self, tracking_file: Path, last_run_info: LastRunInfo
    ) -> None:
        """Save last run information to tracking file.

        Args:
            tracking_file: Path to tracking file
            last_run_info: LastRunInfo model to save
        """
        try:
            tracking_file.parent.mkdir(parents=True, exist_ok=True)

            # Format datetime without timezone suffix (timezone is stored separately)
            last_run_dt_str = None
            if last_run_info.last_run_datetime:
                # Remove timezone info from string representation
                dt = last_run_info.last_run_datetime.replace(tzinfo=None)
                last_run_dt_str = dt.isoformat()
            
            data = {
                "last_run_timestamp": last_run_info.last_run_timestamp,
                "last_run_datetime": last_run_dt_str,
                "timezone": last_run_info.timezone,
                "total_records_processed": last_run_info.total_records_processed,
            }

            with open(tracking_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            log_info(f"Saved last run info to {tracking_file}")
        except OSError as e:
            log_error(f"Error saving last run info: {e}")

    @trace_method("fetch_execution_metrics", "execution_metrics_service")
    def fetch_execution_metrics(
        self,
        start_ts_marker: int,
        progress: Progress,
        policy_types: list[str] | None = None,
        page_size: int = 100,
    ) -> list[ExecutionMetricsRecord]:
        """Fetch and process execution metrics data with parallel processing.

        Args:
            start_ts_marker: Timestamp marker for incremental processing
            progress: Progress tracker
            policy_types: List of policy types to filter
            (default: DATA_QUALITY, EQUALITY)

        Returns:
            List of ExecutionMetricsRecord models
        """
        if policy_types is None:
            policy_types = ["DATA_QUALITY", "EQUALITY"]

        # Step 1: Fetch policy executions
        task1 = progress.add_task("Fetching policy executions...", total=None)
        self.trace("fetching_policy_executions", start_ts_marker=start_ts_marker)

        try:
            policy_executions = self._fetch_policy_executions(
                start_ts_marker, progress, task1, policy_types, page_size
            )
            progress.update(
                task1,
                description=f"Found {len(policy_executions)} executions",
                completed=True,
            )

            if not policy_executions:
                log_info("No new policy executions found")
                return []

            # Step 2: Fetch execution details in parallel
            task2 = progress.add_task("Fetching execution details...", total=None)
            execution_details = self._fetch_execution_details_parallel(
                policy_executions, progress, task2
            )
            progress.update(
                task2,
                description=f"Processed {len(execution_details)} execution details",
                completed=True,
            )

            # Step 3: Fetch policy details in parallel
            task3 = progress.add_task("Fetching policy details...", total=None)
            policy_details = self._fetch_policy_details_parallel(
                policy_executions, progress, task3
            )
            progress.update(
                task3,
                description=f"Processed {len(policy_details)} policy details",
                completed=True,
            )

            # Step 4: Merge data
            task4 = progress.add_task("Merging execution data...", total=None)
            merged_records = merge_execution_data(execution_details, policy_details, self.timezone)
            progress.update(
                task4,
                description=f"Created {len(merged_records)} merged records",
                completed=True,
            )

            self.trace(
                "execution_metrics_fetch_completed",
                executions_count=len(policy_executions),
                details_count=len(execution_details),
                policy_details_count=len(policy_details),
                merged_records_count=len(merged_records),
            )

            return merged_records

        except Exception as e:
            self.trace("execution_metrics_fetch_error", error=str(e))
            raise

    @trace_method("fetch_policy_executions_api", "execution_metrics_service")
    def _fetch_policy_executions(
        self, start_ts_marker: int, progress: Progress, task_id, policy_types: list[str], page_size: int = 100
    ) -> list[PolicyExecution]:
        """Fetch policy executions from API with parallel pagination.

        Args:
            start_ts_marker: Timestamp marker for incremental processing
            progress: Progress tracker
            task_id: Progress task ID
            policy_types: List of policy types to filter
            page_size: Number of items per page (default: 100, max: 1000)

        Returns:
            List of PolicyExecution models
        """
        # Create a thread-safe data collector
        data_collector = ThreadSafeDataCollector()

        # First, let's determine how many pages we need to fetch
        # We'll start with a small batch to estimate the total
        initial_pages = 3
        max_workers = min(initial_pages, 10)  # Limit concurrent workers

        # Create progress tasks for parallel fetching
        progress_tasks = {}
        for i in range(max_workers):
            task_name = f"fetch_page_{i}"
            progress_tasks[task_name] = progress.add_task(
                f"[cyan]Thread {i + 1}: Waiting...",
                total=None,
                columns=[
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                ],
            )

        # Track which worker is available
        available_workers = list(range(max_workers))
        worker_lock = threading.Lock()

        def get_available_worker() -> int | None:
            """Get an available worker ID in a thread-safe manner."""
            with worker_lock:
                if available_workers:
                    return available_workers.pop(0)
                return None

        def release_worker(worker_id: int) -> None:
            """Release a worker ID back to the pool."""
            with worker_lock:
                available_workers.append(worker_id)

        # Fetch initial pages in parallel
        page = 0
        stop_fetching = False

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while not stop_fetching and page < 50:  # Safety limit
                # Submit tasks for parallel execution
                futures = []

                for _ in range(max_workers):
                    if stop_fetching:
                        break

                    worker_id = get_available_worker()
                    if worker_id is None:
                        break

                    task_name = f"fetch_page_{worker_id}"
                    task_progress_id = progress_tasks[task_name]

                    future = executor.submit(
                        fetch_execution_page,
                        page,
                        page_size,  # exec_count
                        policy_types,
                        self.http_client,
                        progress,
                        task_progress_id,
                        self.timezone,
                    )
                    futures.append((future, worker_id, page))
                    page += 1

                # Wait for all submitted tasks to complete
                for future, worker_id, page_num in futures:
                    try:
                        result_page, page_executions, should_stop = future.result(
                            timeout=30
                        )

                        if should_stop:
                            stop_fetching = True

                        if page_executions:
                            # Filter by timestamp marker
                            filtered_executions = [
                                exec
                                for exec in page_executions
                                if exec.start_ts is None
                                or exec.start_ts > start_ts_marker
                            ]

                            if filtered_executions:
                                data_collector.extend(filtered_executions)

                            # Check if we've reached the timestamp marker
                            if any(
                                exec.start_ts is not None
                                and exec.start_ts <= start_ts_marker
                                for exec in page_executions
                            ):
                                stop_fetching = True

                        # Update progress
                        task_name = f"fetch_page_{worker_id}"
                        task_progress_id = progress_tasks[task_name]
                        progress.update(
                            task_progress_id,
                            description=(
                                f"Thread {worker_id + 1}: Page {page_num + 1} complete"
                            ),
                            completed=True,
                        )

                    except Exception as e:
                        log_error(f"Error processing page {page_num}: {e}")
                        task_name = f"fetch_page_{worker_id}"
                        task_progress_id = progress_tasks[task_name]
                        progress.update(
                            task_progress_id,
                            description=(
                                f"Thread {worker_id + 1}: Error on page {page_num + 1}"
                            ),
                            completed=True,
                        )
                    finally:
                        release_worker(worker_id)

                # If we didn't get any data, stop
                if not futures:
                    break

        # Clean up progress tasks
        for task_id in progress_tasks.values():
            progress.remove_task(task_id)

        policy_executions = data_collector.get_all()

        self.trace(
            "fetched_executions_parallel",
            total_executions=len(policy_executions),
            pages_processed=page,
        )

        return policy_executions

    @trace_method("fetch_execution_details_parallel", "execution_metrics_service")
    def _fetch_execution_details_parallel(
        self, policy_executions: list[PolicyExecution], progress: Progress, task_id
    ) -> list[ExecutionDetail]:
        """Fetch execution details in parallel.

        Args:
            policy_executions: List of policy executions
            progress: Progress tracker
            task_id: Progress task ID

        Returns:
            List of ExecutionDetail models
        """
        if not policy_executions:
            return []

        # Create thread-safe data collector
        data_collector = ThreadSafeDataCollector()

        # Determine number of workers (limit to avoid overwhelming the API)
        max_workers = min(len(policy_executions), 10)

        # Create progress tasks for parallel processing
        progress_tasks = {}
        for i in range(max_workers):
            task_name = f"exec_details_{i}"
            progress_tasks[task_name] = progress.add_task(
                f"[green]Exec Thread {i + 1}: Waiting...",
                total=None,
                columns=[
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                ],
            )

        # Track which worker is available
        available_workers = list(range(max_workers))
        worker_lock = threading.Lock()

        def get_available_worker() -> int | None:
            """Get an available worker ID in a thread-safe manner."""
            with worker_lock:
                if available_workers:
                    return available_workers.pop(0)
                return None

        def release_worker(worker_id: int) -> None:
            """Release a worker ID back to the pool."""
            with worker_lock:
                available_workers.append(worker_id)

        # Process executions in parallel
        execution_index = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            # Submit initial batch of tasks
            while execution_index < len(policy_executions):
                worker_id = get_available_worker()
                if worker_id is None:
                    break

                execution = policy_executions[execution_index]
                task_name = f"exec_details_{worker_id}"
                task_progress_id = progress_tasks[task_name]

                future = executor.submit(
                    process_execution_details_parallel,
                    execution,
                    self.http_client,
                    progress,
                    task_progress_id,
                )
                futures.append((future, worker_id, execution_index))
                execution_index += 1

            # Process completed tasks and submit new ones
            while futures or execution_index < len(policy_executions):
                # Wait for at least one task to complete
                if futures:
                    # Wait for any future to complete
                    done_futures, not_done = [], []
                    for future, worker_id, _exec_idx in futures:
                        if future.done():
                            done_futures.append((future, worker_id, _exec_idx))
                        else:
                            not_done.append((future, worker_id, _exec_idx))

                    futures = not_done

                    for future, worker_id, _exec_idx in done_futures:
                        try:
                            execution_details = future.result(timeout=30)
                            data_collector.extend(execution_details)

                            # Update progress
                            task_name = f"exec_details_{worker_id}"
                            task_progress_id = progress_tasks[task_name]
                            progress.update(
                                task_progress_id,
                                description=(
                                    f"Exec Thread {worker_id + 1}: "
                                    f"{len(execution_details)} details"
                                ),
                                completed=True,
                            )

                        except Exception as e:
                            log_error(f"Error processing execution details: {e}")
                            task_name = f"exec_details_{worker_id}"
                            task_progress_id = progress_tasks[task_name]
                            progress.update(
                                task_progress_id,
                                description=f"Exec Thread {worker_id + 1}: Error",
                                completed=True,
                            )
                        finally:
                            release_worker(worker_id)

                # Submit new tasks if we have more executions to process
                while execution_index < len(policy_executions):
                    worker_id = get_available_worker()
                    if worker_id is None:
                        break

                    execution = policy_executions[execution_index]
                    task_name = f"exec_details_{worker_id}"
                    task_progress_id = progress_tasks[task_name]

                    future = executor.submit(
                        process_execution_details_parallel,
                        execution,
                        self.http_client,
                        progress,
                        task_progress_id,
                    )
                    futures.append((future, worker_id, execution_index))
                    execution_index += 1

        # Clean up progress tasks
        for task_id in progress_tasks.values():
            progress.remove_task(task_id)

        execution_details = data_collector.get_all()

        self.trace(
            "execution_details_parallel_completed",
            total_details=len(execution_details),
            executions_processed=len(policy_executions),
        )

        return execution_details

    @trace_method("fetch_policy_details_parallel", "execution_metrics_service")
    def _fetch_policy_details_parallel(
        self, policy_executions: list[PolicyExecution], progress: Progress, task_id
    ) -> list[PolicyDetail]:
        """Fetch policy details in parallel.

        Args:
            policy_executions: List of policy executions
            progress: Progress tracker
            task_id: Progress task ID

        Returns:
            List of PolicyDetail models
        """
        # Get unique policies (deduplicate by policy_id and policy_version)
        unique_policies = {}
        for execution in policy_executions:
            key = (execution.policy_id, execution.policy_version)
            if key not in unique_policies:
                unique_policies[key] = execution

        unique_executions = list(unique_policies.values())

        if not unique_executions:
            return []

        # Create thread-safe data collector
        data_collector = ThreadSafeDataCollector()

        # Determine number of workers (limit to avoid overwhelming the API)
        max_workers = min(
            len(unique_executions), 8
        )  # Slightly fewer workers for policy details

        # Create progress tasks for parallel processing
        progress_tasks = {}
        for i in range(max_workers):
            task_name = f"policy_details_{i}"
            progress_tasks[task_name] = progress.add_task(
                f"[yellow]Policy Thread {i + 1}: Waiting...",
                total=None,
                columns=[
                    SpinnerColumn(),
                    TextColumn("[progress.description]{task.description}"),
                ],
            )

        # Track which worker is available
        available_workers = list(range(max_workers))
        worker_lock = threading.Lock()

        def get_available_worker() -> int | None:
            """Get an available worker ID in a thread-safe manner."""
            with worker_lock:
                if available_workers:
                    return available_workers.pop(0)
                return None

        def release_worker(worker_id: int) -> None:
            """Release a worker ID back to the pool."""
            with worker_lock:
                available_workers.append(worker_id)

        # Process policies in parallel
        policy_index = 0

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = []

            # Submit initial batch of tasks
            while policy_index < len(unique_executions):
                worker_id = get_available_worker()
                if worker_id is None:
                    break

                execution = unique_executions[policy_index]
                task_name = f"policy_details_{worker_id}"
                task_progress_id = progress_tasks[task_name]

                future = executor.submit(
                    process_policy_details_parallel,
                    execution,
                    self.http_client,
                    progress,
                    task_progress_id,
                )
                futures.append((future, worker_id, policy_index))
                policy_index += 1

            # Process completed tasks and submit new ones
            while futures or policy_index < len(unique_executions):
                # Wait for at least one task to complete
                if futures:
                    # Wait for any future to complete
                    done_futures, not_done = [], []
                    for future, worker_id, _policy_idx in futures:
                        if future.done():
                            done_futures.append((future, worker_id, _policy_idx))
                        else:
                            not_done.append((future, worker_id, _policy_idx))

                    futures = not_done

                    for future, worker_id, _policy_idx in done_futures:
                        try:
                            policy_details = future.result(timeout=30)
                            data_collector.extend(policy_details)

                            # Update progress
                            task_name = f"policy_details_{worker_id}"
                            task_progress_id = progress_tasks[task_name]
                            progress.update(
                                task_progress_id,
                                description=(
                                    f"Policy Thread {worker_id + 1}: "
                                    f"{len(policy_details)} details"
                                ),
                                completed=True,
                            )

                        except Exception as e:
                            log_error(f"Error processing policy details: {e}")
                            task_name = f"policy_details_{worker_id}"
                            task_progress_id = progress_tasks[task_name]
                            progress.update(
                                task_progress_id,
                                description=f"Policy Thread {worker_id + 1}: Error",
                                completed=True,
                            )
                        finally:
                            release_worker(worker_id)

                # Submit new tasks if we have more policies to process
                while policy_index < len(unique_executions):
                    worker_id = get_available_worker()
                    if worker_id is None:
                        break

                    execution = unique_executions[policy_index]
                    task_name = f"policy_details_{worker_id}"
                    task_progress_id = progress_tasks[task_name]

                    future = executor.submit(
                        process_policy_details_parallel,
                        execution,
                        self.http_client,
                        progress,
                        task_progress_id,
                    )
                    futures.append((future, worker_id, policy_index))
                    policy_index += 1

        # Clean up progress tasks
        for task_id in progress_tasks.values():
            progress.remove_task(task_id)

        policy_details = data_collector.get_all()

        self.trace(
            "policy_details_parallel_completed",
            total_details=len(policy_details),
            policies_processed=len(unique_executions),
        )

        return policy_details
