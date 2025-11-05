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
    
    def __len__(self) -> int:
        """Get the number of items in the collection."""
        with self._lock:
            return len(self._data)

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
        if task_id:
            progress.update(task_id, description=f"Fetching page {page + 1}...", advance=0)

        rule_types_param = ",".join(policy_types)
        endpoint = (
            f"/catalog-server/api/rules/executions"
            f"?page={page}&size={exec_count}&sortBy=execution.startedAt:DESC"
            "&executionStatus=SUCCESSFUL,ERRORED,ABORTED,WARNING"
            f"&ruleType={rule_types_param}"
        )
        log_info(f"Fetching page {page} with size={exec_count}")

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

        # Log policy types in the raw API response
        policy_type_counts = {}
        for execution in executions:
            ex = safe_get(execution, "execution", {})
            policy_type = safe_get(ex, "ruleType")
            if policy_type:
                policy_type_counts[policy_type] = policy_type_counts.get(policy_type, 0) + 1
        
        log_info(f"Page {page} API response: {len(executions)} total executions")
        log_info(f"Page {page} policy type breakdown: {policy_type_counts}")

        # Process the executions (we'll filter by timestamp later)
        page_executions = process_policy_executions(exec_data, 0, policy_types, timezone)
        
        # Log how many passed the filter
        filtered_type_counts = {}
        for exec in page_executions:
            filtered_type_counts[exec.policy_type] = filtered_type_counts.get(exec.policy_type, 0) + 1
        log_info(f"Page {page} after filtering: {len(page_executions)} executions, breakdown: {filtered_type_counts}")

        if task_id:
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
        if task_id:
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
            # EQUALITY uses the reconciliation endpoint
            endpoint = (
                f"/catalog-server/api/rules/reconciliation/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "DATA_DRIFT":
            endpoint = (
                f"/catalog-server/api/rules/data-drift/executions/"
                f"{execution.execution_id}"
            )
        elif execution.policy_type == "PROFILE_ANOMALY":
            # PROFILE_ANOMALY requires /result suffix
            endpoint = (
                f"/catalog-server/api/rules/profile-anomaly/executions/"
                f"{execution.execution_id}/result"
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
        items = safe_get(exec_result_data, "items", [])
        
        log_info(
            f"Fetched execution details for {execution.policy_type} "
            f"exec_id={execution.execution_id}: {len(items)} items"
        )
        
        # Log the first item structure for non-DATA_QUALITY to debug the merge issue
        if items and execution.policy_type != "DATA_QUALITY":
            first_item = items[0]
            log_info(
                f"DEBUG {execution.policy_type} item structure - "
                f"keys: {list(first_item.keys())}, "
                f"has 'item' nested: {bool(first_item.get('item'))}, "
                f"direct id: {first_item.get('id')}, "
                f"nested id: {first_item.get('item', {}).get('id') if isinstance(first_item.get('item'), dict) else 'N/A'}"
            )

        for item in items:
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
            
            # For non-DATA_QUALITY policies, item structure is different
            # SCHEMA_DRIFT, EQUALITY, etc. don't have nested 'item' objects
            if not item_data and execution.policy_type != "DATA_QUALITY":
                # Use the item itself as item_data
                item_data = item
            
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
            
            # For SCHEMA_DRIFT and other non-DATA_QUALITY policies:
            # - Execution details use "ruleItemId" to reference the policy item
            # - Policy details use "id" for the item ID
            # For DATA_QUALITY:
            # - Both use nested item.id
            if execution.policy_type != "DATA_QUALITY":
                # Use ruleItemId from the top-level item for non-DATA_QUALITY policies
                extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                # Default version depends on policy type:
                # - DATA_DRIFT uses version 0
                # - EQUALITY and PROFILE_ANOMALY use version 1
                default_version = 0 if execution.policy_type == "DATA_DRIFT" else 1
                extracted_item_ver = safe_get(item, "ruleVersion", default_version)
            else:
                # Use nested item.id for DATA_QUALITY
                extracted_item_id = safe_get(item_data, "id", "")
                extracted_item_ver = safe_get(item_data, "ruleVersion", 1)
            
            # Log extraction details for first item of each execution (for debugging merge)
            if execution_details == [] and execution.policy_type != "DATA_QUALITY":
                log_info(
                    f"DEBUG {execution.policy_type} extracted - "
                    f"item_id: '{extracted_item_id}', item_ver: {extracted_item_ver}, "
                    f"merge key will be: ('{extracted_item_id}', {extracted_item_ver})"
                )
            
            # Log if we're getting empty IDs (this indicates a structure mismatch)
            if not extracted_item_id:
                log_info(
                    f"WARNING: Empty item_id for {execution.policy_type} exec_id={execution.execution_id}, "
                    f"item keys: {list(item.keys())}"
                )

            execution_detail = ExecutionDetail(
                item_id=extracted_item_id,
                item_column_name=safe_get(item_data, "columnName"),
                item_ver=extracted_item_ver,
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

        if task_id:
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
        if task_id:
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
            # EQUALITY uses the reconciliation endpoint
            endpoint = (
                f"/catalog-server/api/rules/reconciliation/{execution.policy_id}"
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

            # For non-DATA_QUALITY types, use id to match execution details' ruleItemId
            # For DATA_QUALITY, the nested item.item.id is used via parallel path
            if execution.policy_type == "DATA_QUALITY":
                item_id = str(safe_get(item, "id", ""))
            else:
                # For EQUALITY, DATA_DRIFT, PROFILE_ANOMALY, SCHEMA_DRIFT
                # Policy details have "id" field that matches execution details' "ruleItemId"
                item_id = str(safe_get(item, "id", ""))
                log_info(
                    f"DEBUG {execution.policy_type} policy detail - "
                    f"item keys: {list(item.keys())}, "
                    f"id: {safe_get(item, 'id')}, "
                    f"using item_id: '{item_id}'"
                )

            policy_detail = PolicyDetail(
                policy_name=execution.policy_name,
                policy_id=execution.policy_id,
                policy_type=execution.policy_type,
                id=item_id,
                rule_version=safe_get(item, "ruleVersion", 1),
                column_name=safe_get(item, "columnName"),
                pde_value=pde_value,
                table_asset_id=table_asset_id,
                table_asset_name=table_asset_name,
            )
            policy_details.append(policy_detail)

        if task_id:
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
                # EQUALITY uses the reconciliation endpoint
                endpoint = (
                    f"/catalog-server/api/rules/reconciliation/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "DATA_DRIFT":
                endpoint = (
                    f"/catalog-server/api/rules/data-drift/executions/"
                    f"{execution.execution_id}"
                )
            elif execution.policy_type == "PROFILE_ANOMALY":
                # PROFILE_ANOMALY requires /result suffix
                endpoint = (
                    f"/catalog-server/api/rules/profile-anomaly/executions/"
                    f"{execution.execution_id}/result"
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

                # Extract item_id and item_ver based on policy type
                if execution.policy_type != "DATA_QUALITY":
                    # Use ruleItemId from top-level for non-DATA_QUALITY policies
                    extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                    # Default version depends on policy type
                    default_version = 0 if execution.policy_type == "DATA_DRIFT" else 1
                    extracted_item_ver = safe_get(item, "ruleVersion", default_version)
                else:
                    # Use nested item.id for DATA_QUALITY
                    extracted_item_id = safe_get(item_data, "id", "")
                    extracted_item_ver = safe_get(item_data, "ruleVersion", 1)

                execution_detail = ExecutionDetail(
                    item_id=extracted_item_id,
                    item_column_name=safe_get(item_data, "columnName"),
                    item_ver=extracted_item_ver,
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
                # EQUALITY uses the reconciliation endpoint
                endpoint = (
                    f"/catalog-server/api/rules/reconciliation/{execution.policy_id}"
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
            items = safe_get(details_data, "items", [])
            
            log_info(
                f"Fetched policy details for {execution.policy_type} "
                f"policy_id={execution.policy_id}: {len(items)} items"
            )
            
            for item in items:
                pde_value = next(
                    (
                        safe_get(label, "value")
                        for label in safe_get(item, "labels", [])
                        if safe_get(label, "key") == "PDE"
                    ),
                    None,
                )

                # Convert ID to string for consistent merge key matching
                # For non-DATA_QUALITY types, use id to match execution details' ruleItemId
                if execution.policy_type == "DATA_QUALITY":
                    item_id = str(safe_get(item, "id", ""))
                else:
                    # For EQUALITY, DATA_DRIFT, PROFILE_ANOMALY, SCHEMA_DRIFT
                    # Policy details have "id" field that matches execution details' "ruleItemId"
                    item_id = str(safe_get(item, "id", ""))
                    log_info(
                        f"DEBUG {execution.policy_type} policy detail (non-parallel) - "
                        f"item keys: {list(item.keys())}, "
                        f"id: {safe_get(item, 'id')}, "
                        f"using item_id: '{item_id}'"
                    )
                
                policy_detail = PolicyDetail(
                    policy_name=execution.policy_name,
                    policy_id=execution.policy_id,
                    policy_type=execution.policy_type,
                    id=item_id,
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
    # Log input counts by policy type
    exec_type_counts = {}
    for detail in execution_details:
        # We don't have policy_type on ExecutionDetail, so we'll count all
        exec_id = str(detail.exec_id)
        if exec_id not in exec_type_counts:
            exec_type_counts[exec_id] = 0
        exec_type_counts[exec_id] += 1
    
    policy_type_counts = {}
    for detail in policy_details:
        policy_type_counts[detail.policy_type] = policy_type_counts.get(detail.policy_type, 0) + 1
    
    log_info(f"Merge input: {len(execution_details)} execution details from {len(exec_type_counts)} unique exec_ids")
    log_info(f"Merge input: {len(policy_details)} policy details, breakdown: {policy_type_counts}")
    
    # Create lookup dictionary for policy details
    policy_lookup = {}
    for detail in policy_details:
        key = (detail.id, detail.rule_version)
        policy_lookup[key] = detail

    merged_records = []
    unmatched_exec_details = 0
    
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
        else:
            unmatched_exec_details += 1
    
    # Log output counts by policy type
    merged_type_counts = {}
    for record in merged_records:
        merged_type_counts[record.policy_type] = merged_type_counts.get(record.policy_type, 0) + 1
    
    log_info(f"Merge output: {len(merged_records)} merged records, breakdown: {merged_type_counts}")
    if unmatched_exec_details > 0:
        log_info(f"Merge warning: {unmatched_exec_details} execution details had no matching policy details")

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
        task1 = progress.add_task("📥 Fetching policy executions...", total=None)
        self.trace("fetching_policy_executions", start_ts_marker=start_ts_marker)

        try:
            policy_executions = self._fetch_policy_executions(
                start_ts_marker, progress, task1, policy_types, page_size
            )
            
            # Count by policy type
            exec_type_counts = {}
            for exec in policy_executions:
                exec_type_counts[exec.policy_type] = exec_type_counts.get(exec.policy_type, 0) + 1
            
            # Remove the fetching task and show completion message
            progress.remove_task(task1)

            if not policy_executions:
                log_info("No new policy executions found")
                return []

            # Print breakdown
            from rich.console import Console
            console = Console()
            console.print(f"\n📊 [bold cyan]Executions by Policy Type:[/bold cyan]")
            for ptype, count in sorted(exec_type_counts.items()):
                console.print(f"   • {ptype}: [bold]{count}[/bold]")
            console.print()

            # Step 2: Fetch execution details in parallel
            task2 = progress.add_task(
                "📊 Fetching execution details", 
                total=len(policy_executions)
            )
            execution_details = self._fetch_execution_details_parallel(
                policy_executions, progress, task2
            )
            # Remove the task after completion
            progress.remove_task(task2)

            # Step 3: Fetch policy details in parallel
            # Get unique policies
            unique_policies = {}
            for execution in policy_executions:
                key = (execution.policy_id, execution.policy_version)
                if key not in unique_policies:
                    unique_policies[key] = execution
            
            task3 = progress.add_task(
                "📋 Fetching policy details",
                total=len(unique_policies)
            )
            policy_details = self._fetch_policy_details_parallel(
                policy_executions, progress, task3
            )
            
            # Count policy details by type
            policy_detail_counts = {}
            for detail in policy_details:
                policy_detail_counts[detail.policy_type] = policy_detail_counts.get(detail.policy_type, 0) + 1
            
            # Remove the task after completion
            progress.remove_task(task3)
            
            console.print(f"\n📋 [bold cyan]Policy Details by Type:[/bold cyan]")
            for ptype, count in sorted(policy_detail_counts.items()):
                console.print(f"   • {ptype}: [bold]{count}[/bold]")
            console.print()

            # Step 4: Merge data
            task4 = progress.add_task("🔄 Merging data", total=None)
            merged_records = merge_execution_data(execution_details, policy_details, self.timezone)
            # Remove the task after completion
            progress.remove_task(task4)

            # Final summary by policy type
            final_type_counts = {}
            for record in merged_records:
                final_type_counts[record.policy_type] = final_type_counts.get(record.policy_type, 0) + 1
            
            # Print final summary to console
            console.print(f"\n{'='*70}")
            console.print(f"[bold green]✅ FINAL SUMMARY:[/bold green]")
            console.print(f"{'='*70}")
            console.print(f"[cyan]Total Executions Found:[/cyan]       {len(policy_executions)}")
            console.print(f"[cyan]Execution Details Fetched:[/cyan]   {len(execution_details)}")
            console.print(f"[cyan]Policy Details Fetched:[/cyan]      {len(policy_details)}")
            console.print(f"[bold cyan]Records Ready for Export:[/bold cyan]   [bold green]{len(merged_records)}[/bold green]")
            console.print()
            console.print(f"[bold cyan]📊 Records by Policy Type:[/bold cyan]")
            for ptype in sorted(final_type_counts.keys()):
                count = final_type_counts[ptype]
                percentage = (count / len(merged_records) * 100) if merged_records else 0
                console.print(f"   • {ptype:20s}: [bold]{count:5d}[/bold] ({percentage:5.1f}%)")
            console.print(f"{'='*70}\n")
            
            # Also log to file
            log_info("=" * 60)
            log_info("FINAL SUMMARY:")
            log_info(f"  Total policy executions fetched: {len(policy_executions)}")
            log_info(f"  Total execution details fetched: {len(execution_details)}")
            log_info(f"  Total policy details fetched: {len(policy_details)}")
            log_info(f"  Total merged records: {len(merged_records)}")
            log_info(f"  Breakdown by policy type: {final_type_counts}")
            log_info("=" * 60)

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
        log_info(f"Fetching policy executions with page_size={page_size}")
        
        # Create a thread-safe data collector
        data_collector = ThreadSafeDataCollector()

        # First, let's determine how many pages we need to fetch
        # We'll start with a small batch to estimate the total
        initial_pages = 3
        max_workers = min(initial_pages, 10)  # Limit concurrent workers

        # Track pages fetched for progress display
        pages_fetched = 0

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

                    future = executor.submit(
                        fetch_execution_page,
                        page,
                        page_size,  # exec_count
                        policy_types,
                        self.http_client,
                        progress,
                        None,  # No individual task progress
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
                            # DEBUG: Log sample timestamps BEFORE filtering
                            if page_executions:
                                sample_exec = page_executions[0]
                                sample_dt = datetime.fromtimestamp(sample_exec.start_ts / 1000, tz=get_timezone("UTC")) if sample_exec.start_ts else None
                                marker_dt = datetime.fromtimestamp(start_ts_marker / 1000, tz=get_timezone("UTC"))
                                log_info(
                                    f"Page {page_num}: Sample exec start_ts={sample_exec.start_ts} "
                                    f"({sample_dt.strftime('%Y-%m-%d %H:%M:%S') if sample_dt else 'None'}), "
                                    f"marker={start_ts_marker} ({marker_dt.strftime('%Y-%m-%d %H:%M:%S')})"
                                )
                            
                            # Filter by timestamp marker
                            filtered_executions = [
                                exec
                                for exec in page_executions
                                if exec.start_ts is None
                                or exec.start_ts > start_ts_marker
                            ]
                            
                            # Log timestamp filtering results
                            if len(filtered_executions) != len(page_executions):
                                filtered_out_count = len(page_executions) - len(filtered_executions)
                                log_info(
                                    f"Page {page_num}: Timestamp filter removed {filtered_out_count} "
                                    f"executions (kept {len(filtered_executions)} of {len(page_executions)})"
                                )
                            else:
                                log_info(f"Page {page_num}: All {len(page_executions)} executions passed timestamp filter")

                            if filtered_executions:
                                data_collector.extend(filtered_executions)

                            # Check if we've reached the timestamp marker
                            if any(
                                exec.start_ts is not None
                                and exec.start_ts <= start_ts_marker
                                for exec in page_executions
                            ):
                                stop_fetching = True
                                log_info(f"Page {page_num}: Reached timestamp marker, stopping pagination")

                        # Update main progress
                        pages_fetched += 1
                        progress.update(
                            task_id,
                            description=f"📥 Fetching executions (Pages: {pages_fetched}, Total: {len(data_collector)})"
                        )

                    except Exception as e:
                        log_error(f"Error processing page {page_num}: {e}")
                        pages_fetched += 1
                        progress.update(
                            task_id,
                            description=f"📥 Fetching executions (Pages: {pages_fetched}, Total: {len(data_collector)})"
                        )
                    finally:
                        release_worker(worker_id)

                # If we didn't get any data, stop
                if not futures:
                    break

        policy_executions = data_collector.get_all()
        
        # Log final count by policy type after pagination
        final_exec_type_counts = {}
        for exec in policy_executions:
            final_exec_type_counts[exec.policy_type] = final_exec_type_counts.get(exec.policy_type, 0) + 1
        
        log_info(f"Total executions after pagination: {len(policy_executions)}, breakdown: {final_exec_type_counts}")

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

                future = executor.submit(
                    process_execution_details_parallel,
                    execution,
                    self.http_client,
                    progress,
                    None,  # No individual task progress
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

                            # Update main progress bar
                            progress.advance(task_id, advance=1)

                        except Exception as e:
                            log_error(f"Error processing execution details: {e}")
                            # Still advance the main progress bar
                            progress.advance(task_id, advance=1)
                        finally:
                            release_worker(worker_id)

                # Submit new tasks if we have more executions to process
                while execution_index < len(policy_executions):
                    worker_id = get_available_worker()
                    if worker_id is None:
                        break

                    execution = policy_executions[execution_index]

                    future = executor.submit(
                        process_execution_details_parallel,
                        execution,
                        self.http_client,
                        progress,
                        None,  # No individual task progress
                    )
                    futures.append((future, worker_id, execution_index))
                    execution_index += 1

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

                future = executor.submit(
                    process_policy_details_parallel,
                    execution,
                    self.http_client,
                    progress,
                    None,  # No individual task progress
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

                            # Update main progress bar
                            progress.advance(task_id, advance=1)

                        except Exception as e:
                            log_error(f"Error processing policy details: {e}")
                            # Still advance the main progress bar
                            progress.advance(task_id, advance=1)
                        finally:
                            release_worker(worker_id)

                # Submit new tasks if we have more policies to process
                while policy_index < len(unique_executions):
                    worker_id = get_available_worker()
                    if worker_id is None:
                        break

                    execution = unique_executions[policy_index]

                    future = executor.submit(
                        process_policy_details_parallel,
                        execution,
                        self.http_client,
                        progress,
                        None,  # No individual task progress
                    )
                    futures.append((future, worker_id, policy_index))
                    policy_index += 1

        policy_details = data_collector.get_all()

        self.trace(
            "policy_details_parallel_completed",
            total_details=len(policy_details),
            policies_processed=len(unique_executions),
        )

        return policy_details
