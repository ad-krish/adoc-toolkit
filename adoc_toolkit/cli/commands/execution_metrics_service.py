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
    ReconciliationRecord,
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

        # Map FRESHNESS (internal) to DATA_CADENCE (API) for API calls
        api_policy_types = []
        for pt in policy_types:
            if pt == "FRESHNESS":
                api_policy_types.append("DATA_CADENCE")
            else:
                api_policy_types.append(pt)
        rule_types_param = ",".join(api_policy_types)
        # Include all execution statuses to ensure we don't miss any executions
        # Previously filtered to SUCCESSFUL,ERRORED,ABORTED,WARNING which excluded RUNNING, STARTED, etc.
        endpoint = (
            f"/catalog-server/api/rules/executions"
            f"?page={page}&size={exec_count}&sortBy=execution.startedAt:DESC"
            f"&ruleType={rule_types_param}"
        )
        log_info(f"Fetching page {page} with size={exec_count} (all execution statuses)")

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
        
        # Log EQUALITY executions specifically for debugging
        equality_count = policy_type_counts.get("EQUALITY", 0)
        if equality_count > 0:
            log_info(f"Page {page}: Found {equality_count} EQUALITY (reconciliation) executions in API response")
            # Log execution IDs for debugging
            equality_ids = []
            for execution in executions:
                ex = safe_get(execution, "execution", {})
                if safe_get(ex, "ruleType") == "EQUALITY":
                    exec_id = safe_get(ex, "id")
                    if exec_id:
                        equality_ids.append(str(exec_id))
            if equality_ids:
                log_info(f"Page {page}: EQUALITY execution IDs: {equality_ids[:10]}")  # Log first 10

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
    timezone: str = "UTC",
) -> tuple[list[ExecutionDetail], list[ReconciliationRecord]]:
    """Process execution details for a single execution in parallel.

    Args:
        execution: Policy execution to process
        http_client: HTTP client for API calls
        progress: Progress tracker
        task_id: Progress task ID for this thread

    Returns:
        Tuple of (list of ExecutionDetail models, list of ReconciliationRecord models)
    """
    execution_details = []
    reconciliation_records = []

    try:
        # Log specific execution ID for debugging
        if execution.execution_id == "10410555":
            log_info(f"🔍 DEBUG: Processing execution 10410555 - policy_type={execution.policy_type}, start_ts={execution.start_ts}")
        
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
            # DATA_QUALITY requires /result suffix to get resultPercent
            endpoint = (
                f"/catalog-server/api/rules/data-quality/executions/"
                f"{execution.execution_id}/result"
            )
        elif execution.policy_type == "EQUALITY":
            # EQUALITY uses the reconciliation endpoint with /result suffix
            endpoint = (
                f"/catalog-server/api/rules/reconciliation/executions/"
                f"{execution.execution_id}/result"
            )
        elif execution.policy_type == "DATA_DRIFT":
            # DATA_DRIFT requires /result suffix to get execution.ruleVersion
            endpoint = (
                f"/catalog-server/api/rules/data-drift/executions/"
                f"{execution.execution_id}/result"
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
        elif execution.policy_type == "FRESHNESS":
            # FRESHNESS uses DATA_CADENCE endpoint with /result suffix
            endpoint = (
                f"/catalog-server/api/rules/data-cadence/executions/"
                f"{execution.execution_id}/result"
            )
        else:
            log_error(f"Unsupported policy type: {execution.policy_type}")
            return execution_details, reconciliation_records

        # Log specific execution ID for debugging
        if execution.execution_id == "10410555":
            log_info(f"🔍 DEBUG: Fetching execution details for 10410555 from endpoint: {endpoint}")
        
        response = http_client.get(endpoint)

        if not response.is_success:
            log_error(
                f"Failed to fetch execution details for {execution.policy_type} "
                f"execution {execution.execution_id}: HTTP {response.status_code}, "
                f"endpoint: {endpoint}"
            )
            if execution.execution_id == "10410555":
                log_error(f"🔍 DEBUG: Execution 10410555 failed to fetch details - HTTP {response.status_code}")
            return execution_details, reconciliation_records

        exec_result_data = response.json()
        items = safe_get(exec_result_data, "items", [])
        
        # For DATA_DRIFT and FRESHNESS, extract execution.ruleVersion from the result and update execution object
        if execution.policy_type == "DATA_DRIFT" or execution.policy_type == "FRESHNESS":
            execution_data = safe_get(exec_result_data, "execution", {})
            rule_version = safe_get(execution_data, "ruleVersion")
            if rule_version is not None:
                execution.policy_version = rule_version
                log_info(
                    f"Updated {execution.policy_type} execution {execution.execution_id} policy_version "
                    f"to {rule_version} from execution result"
                )
        
        # Extract result-level fields (same for all items in this execution)
        result_data = safe_get(exec_result_data, "result", {})
        overall_policy_status = safe_get(result_data, "status")
        overall_policy_quality_score = safe_get(result_data, "qualityScore")
        
        # Log if no items found (might indicate incomplete execution)
        if not items and execution.policy_type == "EQUALITY":
            log_info(
                f"⚠️  EQUALITY execution {execution.execution_id} returned no items "
                f"(may be incomplete or still processing)"
            )
        
        # For EQUALITY, check if items might be in a different location
        if execution.policy_type == "EQUALITY" and not items:
            # Try alternative locations for reconciliation data
            items = safe_get(exec_result_data, "results", []) or safe_get(exec_result_data, "comparisons", []) or safe_get(exec_result_data, "matches", [])
            if items:
                log_info(
                    f"DEBUG EQUALITY: Found items in alternative location "
                    f"(results/comparisons/matches): {len(items)} items"
                )
        
        # Log execution status and items count for debugging
        execution_status = safe_get(exec_result_data, "execution", {}).get("executionStatus")
        log_info(
            f"Fetched execution details for {execution.policy_type} "
            f"exec_id={execution.execution_id} (status: {execution_status}): {len(items)} items"
        )
        
        # Warn if execution is still running and has no items
        if execution_status in ["RUNNING", "STARTED"] and not items:
            log_info(
                f"⚠️  Execution {execution.execution_id} is still {execution_status} "
                f"and has no items yet (may need to wait for completion)"
            )
        
        # Enhanced logging for EQUALITY to debug empty items issue
        if execution.policy_type == "EQUALITY":
            log_info(
                f"DEBUG EQUALITY API response structure - "
                f"response keys: {list(exec_result_data.keys())}, "
                f"items count: {len(items)}, "
                f"has 'items' key: {'items' in exec_result_data}, "
                f"has 'results' key: {'results' in exec_result_data}, "
                f"has 'comparisons' key: {'comparisons' in exec_result_data}"
            )
            if not items:
                log_info(
                    f"WARNING: EQUALITY execution {execution.execution_id} returned 0 items. "
                    f"Response structure: {list(exec_result_data.keys())}"
                )
                # Log the full response structure (but limit size)
                import json
                try:
                    response_json = json.dumps(exec_result_data, indent=2, default=str)[:2000]
                    log_info(f"DEBUG EQUALITY full response: {response_json}")
                except Exception:
                    response_str = str(exec_result_data)[:2000]
                    log_info(f"DEBUG EQUALITY response sample: {response_str}")
        
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
            # Enhanced logging for field extraction debugging
            log_info(
                f"DEBUG {execution.policy_type} field locations - "
                f"rowsScanned: {first_item.get('rowsScanned')}, "
                f"result: {first_item.get('result')}, "
                f"thresholdConfig: {bool(first_item.get('thresholdConfig'))}, "
                f"columnName: {first_item.get('columnName')}, "
                f"measurementType: {first_item.get('measurementType')}, "
                f"labels: {len(first_item.get('labels', []))} labels"
            )

        # For EQUALITY, get rows_scanned from result object (not items)
        result_data = safe_get(exec_result_data, "result", {})
        equality_rows_scanned = None
        if execution.policy_type == "EQUALITY" and result_data:
            # For reconciliation, use result.rows (same as DATA_QUALITY)
            equality_rows_scanned = safe_get(result_data, "rows")

        # Log DATA_QUALITY items count for debugging
        if execution.policy_type == "DATA_QUALITY":
            log_info(f"DEBUG DATA_QUALITY execution {execution.execution_id}: Processing {len(items)} items from /result endpoint")
        
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

            # For DATA_QUALITY and FRESHNESS with /result endpoint, items don't have nested "item" structure
            # Items are flat: items[].id, items[].ruleItemId, etc.
            # For non-DATA_QUALITY policies, item structure is different
            if execution.policy_type == "DATA_QUALITY" or execution.policy_type == "FRESHNESS":
                # DATA_QUALITY and FRESHNESS items are flat - use item directly
                item_data = item
            else:
                # For other policies, check for nested item structure
                item_data = safe_get(item, "item", {})
                if not item_data:
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

            # For EQUALITY (reconciliation), fields are in different locations
            if execution.policy_type == "EQUALITY":
                # Rows scanned comes from result object (shared across all items)
                rows_scanned = equality_rows_scanned
                
                # Result is resultPercent (not result)
                rule_result = safe_get(item, "resultPercent")
                if rule_result is not None:
                    # Convert to string percentage format
                    rule_result = str(rule_result)
                
                # Threshold is a float, not a dict - create empty config
                threshold_value = safe_get(item, "threshold")
                threshold_config = {}
                # Store threshold as upper threshold if available
                if threshold_value is not None:
                    threshold_config = {"upper": threshold_value}
            else:
                # For DATA_QUALITY, use result.rows for rows_scanned and items[].rowsFailed for rows_failed
                if execution.policy_type == "DATA_QUALITY":
                    # Rows scanned comes from result object (shared across all items)
                    rows_scanned = safe_get(result_data, "rows")
                    # Use resultPercent for rule_result
                    rule_result = safe_get(item, "resultPercent")
                    if rule_result is not None:
                        # Convert to string percentage format
                        rule_result = str(rule_result)
                elif execution.policy_type == "DATA_DRIFT":
                    # For DATA_DRIFT, use resultPercent (same as DATA_QUALITY and EQUALITY)
                    rule_result = safe_get(item, "resultPercent")
                    if rule_result is not None:
                        # Convert to string percentage format
                        rule_result = str(rule_result)
                    # Rows_Scanned and Rows_Failed are NOT_APPLICABLE for DATA_DRIFT
                    rows_scanned = None
                    rows_failed = None
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, use resultPercent (same as DATA_QUALITY, EQUALITY, and DATA_DRIFT)
                    rule_result = safe_get(item, "resultPercent")
                    if rule_result is not None:
                        # Convert to string percentage format
                        rule_result = str(rule_result)
                    # Rows_Scanned and Rows_Failed are NOT_APPLICABLE for FRESHNESS
                    rows_scanned = None
                    rows_failed = None
                else:
                    # For other policy types, use standard extraction
                    rows_scanned = safe_get(item, "rowsScanned")
                    # For other non-EQUALITY policy types, use result
                    rule_result = safe_get(item, "result")
                
                # Safely extract threshold_config - handle both dict and primitive types
                threshold_config_raw = safe_get(item, "thresholdConfig")
                
                # Ensure threshold_config is a dict, not a primitive type
                if threshold_config_raw is None:
                    threshold_config = {}
                elif isinstance(threshold_config_raw, dict):
                    threshold_config = threshold_config_raw
                else:
                    # If it's a primitive (float, int, etc.), wrap it or create empty dict
                    log_info(
                        f"WARNING: thresholdConfig is not a dict for {execution.policy_type} "
                        f"exec_id={execution.execution_id}, type: {type(threshold_config_raw)}, value: {threshold_config_raw}"
                    )
                    threshold_config = {}
            
            # For SCHEMA_DRIFT and other non-DATA_QUALITY policies:
            # - Execution details use "ruleItemId" to reference the policy item
            # - Policy details use "id" for the item ID
            # For EQUALITY:
            # - Execution details use item.columnMapping.id to match details.columnMappings[].id
            # - Policy details use details.columnMappings[].id
            # For DATA_QUALITY:
            # - Both use nested item.id
            if execution.policy_type == "EQUALITY":
                # For EQUALITY, use items[].id and execution.ruleVersion for merging
                # items[].id matches columnMapping.id, but we use the top-level id directly
                extracted_item_id = str(safe_get(item, "id", ""))
                if not extracted_item_id:
                    # Fallback to columnMapping.id if item.id is not available
                    column_mapping = safe_get(item_data, "columnMapping", {})
                    if column_mapping and isinstance(column_mapping, dict):
                        extracted_item_id = str(safe_get(column_mapping, "id", ""))
                    else:
                        # Final fallback to ruleItemId
                        extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                # For EQUALITY, use execution.ruleVersion (execution.policy_version)
                extracted_item_ver = execution.policy_version
                log_info(f"DEBUG: EQUALITY exec {execution.execution_id} - extracted_item_id='{extracted_item_id}' (from items[].id), extracted_item_ver={extracted_item_ver} (from execution.ruleVersion)")
            elif execution.policy_type == "DATA_DRIFT":
                # For DATA_DRIFT, use ruleItemId from the top-level item
                extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                # For DATA_DRIFT, use execution.ruleVersion (already extracted and updated in execution.policy_version)
                extracted_item_ver = execution.policy_version
            elif execution.policy_type == "FRESHNESS":
                # For FRESHNESS, use ruleItemId for merge key (similar to DATA_QUALITY)
                rule_item_id = safe_get(item, "ruleItemId", "")
                execution_item_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID display
                
                # Use ruleItemId for merge key (extracted_item_id)
                if rule_item_id:
                    extracted_item_id = str(rule_item_id)
                else:
                    # Fallback to top-level item.id if ruleItemId is missing
                    extracted_item_id = execution_item_id
                
                # For FRESHNESS, use execution.ruleVersion (execution.policy_version)
                extracted_item_ver = execution.policy_version
            elif execution.policy_type != "DATA_QUALITY":
                # Use ruleItemId from the top-level item for other non-DATA_QUALITY policies
                extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                # Default version depends on policy type:
                # - PROFILE_ANOMALY uses version 1
                default_version = 1
                extracted_item_ver = safe_get(item, "ruleVersion", default_version)
            else:
                # For DATA_QUALITY:
                # - Use ruleItemId for merge key (to match policy details item.id)
                # - Use items.id for Rule_ID display (user requirement)
                rule_item_id = safe_get(item, "ruleItemId", "")
                execution_item_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID display
                
                # Use ruleItemId for merge key (extracted_item_id)
                if rule_item_id:
                    extracted_item_id = str(rule_item_id)
                else:
                    # Fallback to top-level item.id if ruleItemId is missing
                    extracted_item_id = execution_item_id
                
                # For DATA_QUALITY, items don't have ruleVersion - use execution-level policy_version
                # This matches the policy details ruleVersion which comes from the policy API
                extracted_item_ver = execution.policy_version
                
                # Debug log for first item of each DATA_QUALITY execution
                if execution.execution_id not in getattr(process_execution_details_parallel, '_logged_exec_ids', set()):
                    if not hasattr(process_execution_details_parallel, '_logged_exec_ids'):
                        process_execution_details_parallel._logged_exec_ids = set()
                    process_execution_details_parallel._logged_exec_ids.add(execution.execution_id)
                    log_info(f"DEBUG DATA_QUALITY execution detail: ruleItemId={rule_item_id} (for merge), item.id={execution_item_id} (for Rule_ID), using item_id={extracted_item_id} (merge key), item_ver={extracted_item_ver}")
            
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

            # Extract column name - for DATA_QUALITY, use top-level item.columnName (no nested structure)
            # For FRESHNESS, column name is NOT_APPLICABLE (asset-level policy, not column-level)
            if execution.policy_type == "DATA_QUALITY":
                column_name = safe_get(item, "columnName")
            elif execution.policy_type == "FRESHNESS":
                column_name = None  # Will be set to NOT_APPLICABLE later
            else:
                column_name = safe_get(item_data, "columnName")
            
            # For EQUALITY, extract left_column and right_column from columnMapping
            left_column = None
            right_column = None
            if execution.policy_type == "EQUALITY":
                # EQUALITY items don't have columnName - extract from columnMapping or use dimension
                column_mapping = safe_get(item_data, "columnMapping", {})
                if column_mapping and isinstance(column_mapping, dict):
                    # Extract left and right column names
                    left_column = safe_get(column_mapping, "leftColumnName")
                    right_column = safe_get(column_mapping, "rightColumnName")
                    # Try to get leftColumnName or rightColumnName for column_name
                    column_name = left_column or right_column
                # If still no column name, use dimension as fallback
                if not column_name:
                    column_name = safe_get(item_data, "dimension")
            
            # Extract measurement type - for DATA_QUALITY, use top-level item.dimension (no nested structure)
            # For FRESHNESS, measurement type comes from policy details (not execution details)
            # Execution details have dimension="OTHERS" which is not useful, so we'll get it from policy details
            if execution.policy_type == "DATA_QUALITY":
                measurement_type = safe_get(item, "dimension")
            elif execution.policy_type == "FRESHNESS":
                # For FRESHNESS, measurement type will come from policy details merge
                # Set to None here, will be populated during merge
                measurement_type = None
            else:
                measurement_type = safe_get(item_data, "measurementType")
                if not measurement_type and execution.policy_type == "EQUALITY":
                    # EQUALITY uses dimension field instead of measurementType
                    # Map dimension to standardized Recon_Type values
                    dimension = safe_get(item_data, "dimension", "")
                    if dimension == "ACCURACY":
                        measurement_type = "EQUALITY_MATCH"
                    elif dimension == "TIMELINESS":
                        measurement_type = "ROW_COUNT_MATCH"
                    else:
                        measurement_type = dimension  # Fallback to raw dimension if not recognized
            
            # For EQUALITY, use items[].leftRowsFailed for rows_failed
            if execution.policy_type == "EQUALITY":
                # For reconciliation, use items[].leftRowsFailed only (not the sum)
                rows_failed = safe_get(item, "leftRowsFailed")
            elif execution.policy_type == "DATA_QUALITY":
                # For DATA_QUALITY, use items[].rowsFailed directly
                rows_failed = safe_get(item, "rowsFailed")
            elif execution.policy_type == "DATA_DRIFT" or execution.policy_type == "FRESHNESS":
                # For DATA_DRIFT and FRESHNESS, Rows_Failed is NOT_APPLICABLE (already set to None above)
                rows_failed = None
            else:
                rows_failed = calculate_failed_rows(rows_scanned, rule_result)
            
            # Extract Result_Status from items[].success
            # If items.success is true then "SUCCESSFUL", else "FAILED" (all caps for consistency)
            item_success = safe_get(item, "success")
            if item_success is True:
                result_status = "SUCCESSFUL"
            elif item_success is False:
                result_status = "FAILED"
            else:
                result_status = None

            # For DATA_QUALITY and FRESHNESS, store items.id in rule_item_id for Rule_ID display
            # Keep item_id as ruleItemId for merge key
            if execution.policy_type == "DATA_QUALITY" or execution.policy_type == "FRESHNESS":
                display_rule_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID
            else:
                display_rule_id = safe_get(item, "ruleItemId")
            
            # Extract anomaly_detected and threshold_breached for FRESHNESS only
            anomaly_detected = None
            threshold_breached = None
            if execution.policy_type == "FRESHNESS":
                anomaly_detected = safe_get(item, "anomalyDetected")
                threshold_breached = safe_get(item, "thresholdBreached")
            
            execution_detail = ExecutionDetail(
                item_id=extracted_item_id,
                item_column_name=column_name,
                left_column=left_column,
                right_column=right_column,
                item_ver=extracted_item_ver,
                pde_name=pde_value,
                pde=pde_label,
                item_measurement_type=measurement_type,
                rule_item_id=display_rule_id,  # For DATA_QUALITY: items.id, for others: ruleItemId
                rule_strategy=safe_get(threshold_config, "strategy"),
                rule_lower_threshold=safe_get(threshold_config, "lower"),
                rule_upper_threshold=safe_get(threshold_config, "upper"),
                result=rule_result,
                result_status=result_status,
                overall_policy_status=overall_policy_status,
                overall_policy_quality_score=overall_policy_quality_score,
                rows_scanned=rows_scanned,
                rows_failed=rows_failed,
                exec_id=execution.execution_id,
                start_ts=execution.start_ts,
                end_ts=execution.end_ts,
                execution_status=execution.execution_status,
                anomaly_detected=anomaly_detected,
                threshold_breached=threshold_breached,
            )
            execution_details.append(execution_detail)
        
        # Log DATA_QUALITY execution details count
        if execution.policy_type == "DATA_QUALITY":
            log_info(f"DEBUG DATA_QUALITY execution {execution.execution_id}: Created {len(execution_details)} execution details from {len(items)} items")
        
        # For EQUALITY, also create reconciliation records
        if execution.policy_type == "EQUALITY":
            if items:
                log_info(f"DEBUG: Processing reconciliation records for EQUALITY execution {execution.execution_id} - {len(items)} items")
                recon_records = process_reconciliation_records(
                    exec_result_data, execution, http_client, timezone
                )
                log_info(f"DEBUG: Created {len(recon_records)} reconciliation records for EQUALITY execution {execution.execution_id}")
                reconciliation_records.extend(recon_records)
            else:
                log_info(f"DEBUG: EQUALITY execution {execution.execution_id} has no items, skipping reconciliation records")

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
        log_error(
            f"Error processing execution {execution.execution_id} "
            f"(type: {execution.policy_type}): {e}"
        )
        import traceback
        log_error(f"Traceback: {traceback.format_exc()}")

    return execution_details, reconciliation_records


def fetch_data_drift_version_mapping(
    policy_id: str,
    max_version: int,
    http_client: ADOCHTTPClient,
) -> dict[tuple[str, str], str]:
    """Fetch DATA_DRIFT policy versions and track (columnName, metricType) -> item.id mapping.

    Only returns item.id for NEW (columnName, metricType) combinations that weren't in previous versions.
    Compares version N with version N-1 sequentially (1->2, 2->3, etc.), not 1->5.

    Args:
        policy_id: Policy ID
        max_version: Maximum version to fetch (from execution.ruleVersion)
        http_client: HTTP client for API calls

    Returns:
        Dictionary mapping (columnName, metricType) -> item.id for new combinations only
    """
    version_mapping: dict[tuple[str, str], str] = {}
    seen_combinations: set[tuple[str, str]] = set()

    if max_version < 1:
        return version_mapping

    log_info(f"Fetching DATA_DRIFT policy {policy_id} versions 1 to {max_version} for version comparison")

    for version in range(1, max_version + 1):
        endpoint = f"/catalog-server/api/rules/data-drift/{policy_id}?version={version}"
        response = http_client.get(endpoint)

        if not response.is_success:
            log_error(f"Failed to fetch DATA_DRIFT policy {policy_id} version {version}")
            continue

        policy_data = response.json()
        details_data = safe_get(policy_data, "details", {})
        items = safe_get(details_data, "items", [])

        # Track combinations in this version
        current_version_combinations: set[tuple[str, str]] = set()

        for item in items:
            column_name = safe_get(item, "columnName", "")
            metric_type = safe_get(item, "metricType", "")
            item_id = str(safe_get(item, "id", ""))

            if not column_name or not metric_type or not item_id:
                continue

            combination = (column_name, metric_type)
            current_version_combinations.add(combination)

            # Only add to mapping if this combination is NEW (not seen in previous versions)
            if combination not in seen_combinations:
                version_mapping[combination] = item_id
                log_info(
                    f"DATA_DRIFT version {version}: New combination ({column_name}, {metric_type}) -> item.id={item_id}"
                )

        # Count new combinations before updating seen_combinations
        new_count = len([c for c in current_version_combinations if c not in seen_combinations])

        # Update seen combinations for next version comparison (after checking for new ones)
        seen_combinations.update(current_version_combinations)
        log_info(
            f"DATA_DRIFT version {version}: {len(current_version_combinations)} combinations, "
            f"{new_count} new"
        )

    log_info(
        f"DATA_DRIFT policy {policy_id}: Total {len(version_mapping)} new (columnName, metricType) -> item.id mappings"
    )
    return version_mapping


def fetch_freshness_version_mapping(
    policy_id: str,
    max_version: int,
    http_client: ADOCHTTPClient,
) -> dict[tuple[str, str], str]:
    """Fetch FRESHNESS policy versions and track (measurementType, strategy) -> item.id mapping.

    Only returns item.id for NEW (measurementType, strategy) combinations that weren't in previous versions.
    Compares version N with version N-1 sequentially (1->2, 2->3, etc.), not 1->5.

    Args:
        policy_id: Policy ID
        max_version: Maximum version to fetch (from execution.ruleVersion)
        http_client: HTTP client for API calls

    Returns:
        Dictionary mapping (measurementType, strategy) -> item.id for new combinations only
    """
    version_mapping: dict[tuple[str, str], str] = {}
    seen_combinations: set[tuple[str, str]] = set()

    if max_version < 1:
        return version_mapping

    log_info(f"Fetching FRESHNESS policy {policy_id} versions 1 to {max_version} for version comparison")

    for version in range(1, max_version + 1):
        endpoint = f"/catalog-server/api/rules/data-cadence/{policy_id}?version={version}"
        response = http_client.get(endpoint)

        if not response.is_success:
            log_error(f"Failed to fetch FRESHNESS policy {policy_id} version {version}")
            continue

        policy_data = response.json()
        details_data = safe_get(policy_data, "details", {})
        items = safe_get(details_data, "items", [])

        # Track combinations in this version
        current_version_combinations: set[tuple[str, str]] = set()

        for item in items:
            measurement_type = safe_get(item, "measurementType", "")
            threshold_config = safe_get(item, "thresholdConfig", {})
            strategy = safe_get(threshold_config, "strategy", "")
            item_id = str(safe_get(item, "id", ""))

            if not measurement_type or not strategy or not item_id:
                continue

            combination = (measurement_type, strategy)
            current_version_combinations.add(combination)

            # Only add to mapping if this combination is NEW (not seen in previous versions)
            if combination not in seen_combinations:
                version_mapping[combination] = item_id
                log_info(
                    f"FRESHNESS version {version}: New combination ({measurement_type}, {strategy}) -> item.id={item_id}"
                )

        # Count new combinations before updating seen_combinations
        new_count = len([c for c in current_version_combinations if c not in seen_combinations])

        # Update seen combinations for next version comparison (after checking for new ones)
        seen_combinations.update(current_version_combinations)
        log_info(
            f"FRESHNESS version {version}: {len(current_version_combinations)} combinations, "
            f"{new_count} new"
        )

    log_info(
        f"FRESHNESS policy {policy_id}: Total {len(version_mapping)} new (measurementType, strategy) -> item.id mappings"
    )
    return version_mapping


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
        elif execution.policy_type == "FRESHNESS":
            # FRESHNESS uses DATA_CADENCE endpoint
            endpoint = (
                f"/catalog-server/api/rules/data-cadence/{execution.policy_id}"
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

        # Extract policy enabled status from rule.enabled
        policy_enabled = safe_get(rule_data, "enabled")
        
        # Extract policy description from rule.description
        policy_description = safe_get(rule_data, "description")

        # Fetch table asset name
        table_asset_name = (
            fetch_asset_name(table_asset_id, http_client) if table_asset_id else None
        )

        details_data = safe_get(policy_detail_data, "details", {})
        
        # For EQUALITY (reconciliation), use columnMappings instead of items
        if execution.policy_type == "EQUALITY":
            # Iterate over columnMappings for EQUALITY policies
            column_mappings = safe_get(details_data, "columnMappings", [])
            log_info(f"DEBUG: EQUALITY policy {execution.policy_id} v{execution.policy_version} - {len(column_mappings)} columnMappings")
            for col_map in column_mappings:
                # Use columnMapping.id as item_id for EQUALITY (matches items[].id)
                item_id = str(safe_get(col_map, "id", ""))
                # Use execution.ruleVersion (not columnMapping.ruleVersion) to match execution details
                rule_version = execution.policy_version
                log_info(f"DEBUG: EQUALITY policy detail - item_id='{item_id}' (from columnMapping.id), rule_version={rule_version} (from execution.ruleVersion)")
                
                # Extract PDE value from labels
                pde_value = next(
                    (
                        safe_get(label, "value")
                        for label in safe_get(col_map, "labels", [])
                        if safe_get(label, "key") == "PDE"
                    ),
                    None,
                )
                
                # Extract column name (use leftColumnName for EQUALITY)
                column_name = safe_get(col_map, "leftColumnName")
                
                # Extract labels from columnMapping - create one PolicyDetail per label
                item_labels = safe_get(col_map, "labels", [])
                if item_labels:
                    # Create one PolicyDetail per label (flatten labels)
                    for label in item_labels:
                        label_key = safe_get(label, "key")
                        label_value = safe_get(label, "value")
                        
                        policy_detail = PolicyDetail(
                            policy_name=execution.policy_name,
                            policy_id=execution.policy_id,
                            policy_type=execution.policy_type,
                            id=item_id,
                            rule_version=rule_version,  # Use execution.ruleVersion (not columnMapping.ruleVersion)
                            column_name=column_name,
                            pde_value=pde_value,
                            table_asset_id=table_asset_id,
                            table_asset_name=table_asset_name,
                            policy_enabled=policy_enabled,
                            label_key=label_key,
                            label_value=label_value,
                        )
                        policy_details.append(policy_detail)
                else:
                    # If no labels, create one PolicyDetail without label fields
                    policy_detail = PolicyDetail(
                        policy_name=execution.policy_name,
                        policy_id=execution.policy_id,
                        policy_type=execution.policy_type,
                        id=item_id,
                        rule_version=rule_version,  # Use execution.ruleVersion (not columnMapping.ruleVersion)
                        column_name=column_name,
                        pde_value=pde_value,
                        table_asset_id=table_asset_id,
                        table_asset_name=table_asset_name,
                        policy_enabled=policy_enabled,
                        label_key=None,
                        label_value=None,
                    )
                    policy_details.append(policy_detail)
        else:
            # For other policy types (DATA_QUALITY, DATA_DRIFT, etc.), use items
            items = safe_get(details_data, "items", [])
            if execution.policy_type == "DATA_QUALITY":
                log_info(f"DEBUG DATA_QUALITY policy {execution.policy_id}: Processing {len(items)} items from policy details endpoint")
            
            # For DATA_DRIFT and FRESHNESS, fetch version mapping once before processing items
            version_mapping: dict[tuple[str, str], str] = {}
            if execution.policy_type == "DATA_DRIFT":
                version_mapping = fetch_data_drift_version_mapping(
                    execution.policy_id,
                    execution.policy_version,
                    http_client,
                )
            elif execution.policy_type == "FRESHNESS":
                version_mapping = fetch_freshness_version_mapping(
                    execution.policy_id,
                    execution.policy_version,
                    http_client,
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

                # For DATA_QUALITY, policy details API uses top-level item.id (not nested)
                # This matches execution details top-level item.id for merge key
                if execution.policy_type == "DATA_QUALITY":
                    item_id = str(safe_get(item, "id", ""))
                    rule_version = safe_get(item, "ruleVersion", 1)
                elif execution.policy_type == "DATA_DRIFT":
                    # For DATA_DRIFT, policy details have "id" field that matches execution details' "ruleItemId"
                    item_id = str(safe_get(item, "id", ""))
                    # For DATA_DRIFT, use execution.policy_version (from execution.ruleVersion) to match execution details
                    rule_version = execution.policy_version
                    log_info(
                        f"DEBUG {execution.policy_type} policy detail - "
                        f"item keys: {list(item.keys())}, "
                        f"id: {safe_get(item, 'id')}, "
                        f"using item_id: '{item_id}', rule_version: {rule_version} (from execution.policy_version)"
                    )
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, policy details have "id" field that matches execution details' "ruleItemId"
                    item_id = str(safe_get(item, "id", ""))
                    # For FRESHNESS, use execution.policy_version (from execution.ruleVersion) to match execution details
                    rule_version = execution.policy_version
                else:
                    # For PROFILE_ANOMALY, SCHEMA_DRIFT
                    # Policy details have "id" field that matches execution details' "ruleItemId"
                    item_id = str(safe_get(item, "id", ""))
                    rule_version = safe_get(item, "ruleVersion", 1)
                    log_info(
                        f"DEBUG {execution.policy_type} policy detail - "
                        f"item keys: {list(item.keys())}, "
                        f"id: {safe_get(item, 'id')}, "
                        f"using item_id: '{item_id}'"
                    )

                # Extract rule description from details.items.businessExplanation (for DATA_QUALITY)
                rule_description = safe_get(item, "businessExplanation") if execution.policy_type == "DATA_QUALITY" else None
                
                # Extract column_name for all policies (existing behavior)
                # For FRESHNESS, column_name is NOT_APPLICABLE (asset-level policy, not column-level)
                if execution.policy_type == "FRESHNESS":
                    column_name = None  # Will be set to NOT_APPLICABLE later
                else:
                    column_name = safe_get(item, "columnName")
                
                # Extract DATA_DRIFT-specific fields (only for DATA_DRIFT)
                item_measurement_type = None
                drift_threshold = None
                if execution.policy_type == "DATA_DRIFT":
                    item_measurement_type = safe_get(item, "metricType")
                    drift_threshold = safe_get(item, "driftThreshold")
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, extract measurementType from policy details
                    item_measurement_type = safe_get(item, "measurementType")
                    # Extract threshold config for FRESHNESS
                    threshold_config = safe_get(item, "thresholdConfig", {})
                    rule_strategy = safe_get(threshold_config, "strategy")
                    rule_lower_threshold = safe_get(threshold_config, "lower")
                    rule_upper_threshold = safe_get(threshold_config, "upper")
                    drift_threshold = None  # Not applicable for FRESHNESS
                
                # For DATA_DRIFT, set Label_Key and Label_Value based on version mapping
                if execution.policy_type == "DATA_DRIFT":
                    # Label_Key = Item_Column_Name-Item_Measurement_Type
                    label_key = f"{column_name or ''}-{item_measurement_type or ''}" if column_name and item_measurement_type else None
                    # Label_Value = item.id from version mapping (only for new combinations)
                    combination = (column_name or "", item_measurement_type or "")
                    label_value = version_mapping.get(combination)
                    
                    # Create PolicyDetail with DATA_DRIFT-specific Label_Key and Label_Value
                    policy_detail = PolicyDetail(
                        policy_name=execution.policy_name,
                        policy_id=execution.policy_id,
                        policy_type=execution.policy_type,
                        id=item_id,
                        rule_version=rule_version,
                        column_name=column_name,
                        pde_value=pde_value,
                        table_asset_id=table_asset_id,
                        table_asset_name=table_asset_name,
                        policy_enabled=policy_enabled,
                        label_key=label_key,
                        label_value=label_value,
                        policy_description=policy_description,
                        rule_description=None,  # Rule_Description is NOT_APPLICABLE for DATA_DRIFT
                        item_measurement_type=item_measurement_type,
                        drift_threshold=drift_threshold,
                    )
                    policy_details.append(policy_detail)
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, set Label_Key and Label_Value based on version mapping
                    # Label_Key = Item_Measurement_Type-Rule_Strategy
                    label_key = f"{item_measurement_type or ''}-{rule_strategy or ''}" if item_measurement_type and rule_strategy else None
                    # Label_Value = item.id from version mapping (only for new combinations)
                    combination = (item_measurement_type or "", rule_strategy or "")
                    label_value = version_mapping.get(combination)
                    
                    # Create PolicyDetail with FRESHNESS-specific Label_Key and Label_Value
                    policy_detail = PolicyDetail(
                        policy_name=execution.policy_name,
                        policy_id=execution.policy_id,
                        policy_type=execution.policy_type,
                        id=item_id,
                        rule_version=rule_version,
                        column_name=column_name,
                        pde_value=None,  # NOT_APPLICABLE for FRESHNESS
                        table_asset_id=table_asset_id,
                        table_asset_name=table_asset_name,
                        policy_enabled=policy_enabled,
                        label_key=label_key,
                        label_value=label_value,
                        policy_description=policy_description,
                        rule_description=None,  # Rule_Description is NOT_APPLICABLE for FRESHNESS
                        item_measurement_type=item_measurement_type,
                        drift_threshold=drift_threshold,
                        rule_strategy=rule_strategy,
                        rule_lower_threshold=rule_lower_threshold,
                        rule_upper_threshold=rule_upper_threshold,
                    )
                    policy_details.append(policy_detail)
                else:
                    # For other policy types, use existing label extraction logic
                    # Extract labels from item - create one PolicyDetail per label
                    item_labels = safe_get(item, "labels", [])
                    if item_labels:
                        # Create one PolicyDetail per label (flatten labels)
                        for label in item_labels:
                            label_key = safe_get(label, "key")
                            label_value = safe_get(label, "value")
                            
                            policy_detail = PolicyDetail(
                                policy_name=execution.policy_name,
                                policy_id=execution.policy_id,
                                policy_type=execution.policy_type,
                                id=item_id,
                                rule_version=rule_version,
                                column_name=column_name,
                                pde_value=pde_value,
                                table_asset_id=table_asset_id,
                                table_asset_name=table_asset_name,
                                policy_enabled=policy_enabled,
                                label_key=label_key,
                                label_value=label_value,
                                policy_description=policy_description,
                                rule_description=rule_description,
                                item_measurement_type=item_measurement_type,
                                drift_threshold=drift_threshold,
                            )
                            policy_details.append(policy_detail)
                    else:
                        # If no labels, create one PolicyDetail without label fields
                        policy_detail = PolicyDetail(
                            policy_name=execution.policy_name,
                            policy_id=execution.policy_id,
                            policy_type=execution.policy_type,
                            id=item_id,
                            rule_version=rule_version,
                            column_name=column_name,
                            pde_value=pde_value,
                            table_asset_id=table_asset_id,
                            table_asset_name=table_asset_name,
                            policy_enabled=policy_enabled,
                            label_key=None,
                            label_value=None,
                            policy_description=policy_description,
                            rule_description=rule_description,
                            item_measurement_type=item_measurement_type,
                            drift_threshold=drift_threshold,
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
            "FRESHNESS",  # API uses DATA_CADENCE
        ]

    policy_executions = []

    for execution in safe_get(executions_data, "executions", []):
        ex = safe_get(execution, "execution", {})
        start_ts = safe_get(ex, "startedAt")
        exec_id = str(safe_get(ex, "id", ""))  # Convert to string for consistency

        # Debug logging for specific execution
        if exec_id == "10410555":
            log_info(
                f"🔍 DEBUG process_policy_executions: Found execution 10410555 - "
                f"start_ts={start_ts}, marker={start_ts_marker}, "
                f"will_skip={start_ts is not None and start_ts <= start_ts_marker}"
            )

        # Skip if timestamp is before marker (incremental processing)
        if start_ts is not None and start_ts <= start_ts_marker:
            if exec_id == "10410555":
                log_info(f"🔍 DEBUG: Execution 10410555 SKIPPED - start_ts={start_ts} <= marker={start_ts_marker}")
            continue

        policy_type = safe_get(ex, "ruleType")
        # Map DATA_CADENCE (API) to FRESHNESS (internal)
        if policy_type == "DATA_CADENCE":
            policy_type = "FRESHNESS"
        if policy_type in policy_types:
            result = safe_get(execution, "result") or {}

            policy_execution = PolicyExecution(
                policy_name=safe_get(ex, "ruleName", ""),
                policy_version=safe_get(ex, "ruleVersion", 1),
                policy_id=str(safe_get(ex, "ruleId", "")),  # Convert to string
                policy_type=policy_type,
                execution_id=exec_id,
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
                # DATA_QUALITY requires /result suffix to get resultPercent
                endpoint = (
                    f"/catalog-server/api/rules/data-quality/executions/"
                    f"{execution.execution_id}/result"
                )
            elif execution.policy_type == "EQUALITY":
                # EQUALITY uses the reconciliation endpoint with /result suffix
                endpoint = (
                    f"/catalog-server/api/rules/reconciliation/executions/"
                    f"{execution.execution_id}/result"
                )
            elif execution.policy_type == "DATA_DRIFT":
                # DATA_DRIFT requires /result suffix to get execution.ruleVersion
                endpoint = (
                    f"/catalog-server/api/rules/data-drift/executions/"
                    f"{execution.execution_id}/result"
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
            elif execution.policy_type == "FRESHNESS":
                # FRESHNESS uses DATA_CADENCE endpoint with /result suffix
                endpoint = (
                    f"/catalog-server/api/rules/data-cadence/executions/"
                    f"{execution.execution_id}/result"
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
            
            # For DATA_DRIFT and FRESHNESS, extract execution.ruleVersion from the result and update execution object
            if execution.policy_type == "DATA_DRIFT" or execution.policy_type == "FRESHNESS":
                execution_data = safe_get(exec_result_data, "execution", {})
                rule_version = safe_get(execution_data, "ruleVersion")
                if rule_version is not None:
                    execution.policy_version = rule_version
                    log_info(
                        f"Updated {execution.policy_type} execution {execution.execution_id} policy_version "
                        f"to {rule_version} from execution result"
                    )
            
            # Extract result-level fields (same for all items in this execution)
            result_data = safe_get(exec_result_data, "result", {})
            overall_policy_status = safe_get(result_data, "status")
            overall_policy_quality_score = safe_get(result_data, "qualityScore")
            
            # For EQUALITY, get rows_scanned from result object (not items)
            equality_rows_scanned = None
            if execution.policy_type == "EQUALITY" and result_data:
                # For reconciliation, use result.rows (same as DATA_QUALITY)
                equality_rows_scanned = safe_get(result_data, "rows")

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

                # For DATA_QUALITY and FRESHNESS with /result endpoint, items don't have nested "item" structure
                # Items are flat: items[].id, items[].ruleItemId, etc.
                # For non-DATA_QUALITY policies, item structure is different
                if execution.policy_type == "DATA_QUALITY" or execution.policy_type == "FRESHNESS":
                    # DATA_QUALITY and FRESHNESS items are flat - use item directly
                    item_data = item
                else:
                    # For other policies, check for nested item structure
                    item_data = safe_get(item, "item", {})
                    if not item_data:
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

                # For EQUALITY (reconciliation), fields are in different locations
                if execution.policy_type == "EQUALITY":
                    # Rows scanned comes from result object (shared across all items)
                    rows_scanned = equality_rows_scanned
                    
                    # Result is resultPercent (not result)
                    rule_result = safe_get(item, "resultPercent")
                    if rule_result is not None:
                        # Convert to string percentage format
                        rule_result = str(rule_result)
                    
                    # Threshold is a float, not a dict - create empty config
                    threshold_value = safe_get(item, "threshold")
                    threshold_config = {}
                    # Store threshold as upper threshold if available
                    if threshold_value is not None:
                        threshold_config = {"upper": threshold_value}
                else:
                    # For DATA_QUALITY, use result.rows for rows_scanned and items[].rowsFailed for rows_failed
                    if execution.policy_type == "DATA_QUALITY":
                        # Rows scanned comes from result object (shared across all items)
                        rows_scanned = safe_get(result_data, "rows")
                        # Use resultPercent for rule_result
                        rule_result = safe_get(item, "resultPercent")
                        if rule_result is not None:
                            # Convert to string percentage format
                            rule_result = str(rule_result)
                    elif execution.policy_type == "DATA_DRIFT":
                        # For DATA_DRIFT, use resultPercent (same as DATA_QUALITY and EQUALITY)
                        rule_result = safe_get(item, "resultPercent")
                        if rule_result is not None:
                            # Convert to string percentage format
                            rule_result = str(rule_result)
                        # Rows_Scanned and Rows_Failed are NOT_APPLICABLE for DATA_DRIFT
                        rows_scanned = None
                        rows_failed = None
                    elif execution.policy_type == "FRESHNESS":
                        # For FRESHNESS, use resultPercent (same as DATA_QUALITY, EQUALITY, and DATA_DRIFT)
                        rule_result = safe_get(item, "resultPercent")
                        if rule_result is not None:
                            # Convert to string percentage format
                            rule_result = str(rule_result)
                        # Rows_Scanned and Rows_Failed are NOT_APPLICABLE for FRESHNESS
                        rows_scanned = None
                        rows_failed = None
                    else:
                        # For other policy types, use standard extraction
                        rows_scanned = safe_get(item, "rowsScanned")
                        # For other non-EQUALITY policy types, use result
                        rule_result = safe_get(item, "result")
                    
                    # Safely extract threshold_config - handle both dict and primitive types
                    threshold_config_raw = safe_get(item, "thresholdConfig")
                    
                    # Ensure threshold_config is a dict, not a primitive type
                    if threshold_config_raw is None:
                        threshold_config = {}
                    elif isinstance(threshold_config_raw, dict):
                        threshold_config = threshold_config_raw
                    else:
                        # If it's a primitive (float, int, etc.), wrap it or create empty dict
                        log_info(
                            f"WARNING: thresholdConfig is not a dict for {execution.policy_type} "
                            f"exec_id={execution.execution_id}, type: {type(threshold_config_raw)}, value: {threshold_config_raw}"
                        )
                        threshold_config = {}

                # Extract item_id and item_ver based on policy type
                if execution.policy_type == "EQUALITY":
                    # For EQUALITY, use items[].id and execution.ruleVersion for merging
                    # items[].id matches columnMapping.id, but we use the top-level id directly
                    extracted_item_id = str(safe_get(item, "id", ""))
                    if not extracted_item_id:
                        # Fallback to columnMapping.id if item.id is not available
                        column_mapping = safe_get(item_data, "columnMapping", {})
                        if column_mapping and isinstance(column_mapping, dict):
                            extracted_item_id = str(safe_get(column_mapping, "id", ""))
                        else:
                            # Final fallback to ruleItemId
                            extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                    # For EQUALITY, use execution.ruleVersion (execution.policy_version)
                    extracted_item_ver = execution.policy_version
                elif execution.policy_type == "DATA_DRIFT":
                    # For DATA_DRIFT, use ruleItemId from top-level item
                    extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                    # For DATA_DRIFT, use execution.ruleVersion (already extracted and updated in execution.policy_version)
                    extracted_item_ver = execution.policy_version
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, use ruleItemId for merge key (similar to DATA_QUALITY)
                    rule_item_id = safe_get(item, "ruleItemId", "")
                    execution_item_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID display
                    
                    # Use ruleItemId for merge key (extracted_item_id)
                    if rule_item_id:
                        extracted_item_id = str(rule_item_id)
                    else:
                        # Fallback to top-level item.id if ruleItemId is missing
                        extracted_item_id = execution_item_id
                    
                    # For FRESHNESS, use execution.ruleVersion (execution.policy_version)
                    extracted_item_ver = execution.policy_version
                elif execution.policy_type != "DATA_QUALITY":
                    # Use ruleItemId from top-level for other non-DATA_QUALITY policies
                    extracted_item_id = str(safe_get(item, "ruleItemId", ""))
                    # Default version depends on policy type
                    default_version = 1
                    extracted_item_ver = safe_get(item, "ruleVersion", default_version)
                else:
                    # For DATA_QUALITY:
                    # - Use ruleItemId for merge key (to match policy details item.id)
                    # - Use items.id for Rule_ID display (user requirement)
                    rule_item_id = safe_get(item, "ruleItemId", "")
                    execution_item_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID display
                    
                    # Use ruleItemId for merge key (extracted_item_id)
                    if rule_item_id:
                        extracted_item_id = str(rule_item_id)
                    else:
                        # Fallback to top-level item.id if ruleItemId is missing
                        extracted_item_id = execution_item_id
                    
                    # For DATA_QUALITY, items don't have ruleVersion - use execution-level policy_version
                    # This matches the policy details ruleVersion which comes from the policy API
                    extracted_item_ver = execution.policy_version

                # Extract column name - for DATA_QUALITY, use top-level item.columnName (no nested structure)
                # For FRESHNESS, column name is NOT_APPLICABLE (asset-level policy, not column-level)
                if execution.policy_type == "DATA_QUALITY":
                    column_name = safe_get(item, "columnName")
                elif execution.policy_type == "FRESHNESS":
                    column_name = None  # Will be set to NOT_APPLICABLE later
                else:
                    column_name = safe_get(item_data, "columnName")
                
                # For EQUALITY, extract left_column and right_column from columnMapping
                left_column = None
                right_column = None
                if execution.policy_type == "EQUALITY":
                    # EQUALITY items don't have columnName - extract from columnMapping or use dimension
                    column_mapping = safe_get(item_data, "columnMapping", {})
                    if column_mapping and isinstance(column_mapping, dict):
                        # Extract left and right column names
                        left_column = safe_get(column_mapping, "leftColumnName")
                        right_column = safe_get(column_mapping, "rightColumnName")
                        # Try to get leftColumnName or rightColumnName for column_name
                        column_name = left_column or right_column
                    # If still no column name, use dimension as fallback
                    if not column_name:
                        column_name = safe_get(item_data, "dimension")
                
                # Extract measurement type - for DATA_QUALITY, use top-level item.dimension (no nested structure)
                # For FRESHNESS, measurement type comes from policy details (not execution details)
                # Execution details have dimension="OTHERS" which is not useful, so we'll get it from policy details
                if execution.policy_type == "DATA_QUALITY":
                    measurement_type = safe_get(item, "dimension")
                elif execution.policy_type == "FRESHNESS":
                    # For FRESHNESS, measurement type will come from policy details merge
                    # Set to None here, will be populated during merge
                    measurement_type = None
                else:
                    measurement_type = safe_get(item_data, "measurementType")
                    if not measurement_type and execution.policy_type == "EQUALITY":
                        # EQUALITY uses dimension field instead of measurementType
                        # Map dimension to standardized Recon_Type values
                        dimension = safe_get(item_data, "dimension", "")
                        if dimension == "ACCURACY":
                            measurement_type = "EQUALITY_MATCH"
                        elif dimension == "TIMELINESS":
                            measurement_type = "ROW_COUNT_MATCH"
                        else:
                            measurement_type = dimension  # Fallback to raw dimension if not recognized
                
                # For EQUALITY, use items[].leftRowsFailed for rows_failed
                if execution.policy_type == "EQUALITY":
                    # For reconciliation, use items[].leftRowsFailed only (not the sum)
                    rows_failed = safe_get(item, "leftRowsFailed")
                elif execution.policy_type == "DATA_QUALITY":
                    # For DATA_QUALITY, use items[].rowsFailed directly
                    rows_failed = safe_get(item, "rowsFailed")
                else:
                    rows_failed = calculate_failed_rows(rows_scanned, rule_result)
                
                # Extract Result_Status from items[].success
                # If items.success is true then "SUCCESSFUL", else "FAILED" (all caps for consistency)
                item_success = safe_get(item, "success")
                if item_success is True:
                    result_status = "SUCCESSFUL"
                elif item_success is False:
                    result_status = "FAILED"
                else:
                    result_status = None

                # For DATA_QUALITY and FRESHNESS, store items.id in rule_item_id for Rule_ID display
                # Keep item_id as ruleItemId for merge key
                if execution.policy_type == "DATA_QUALITY" or execution.policy_type == "FRESHNESS":
                    display_rule_id = str(safe_get(item, "id", ""))  # items.id for Rule_ID
                else:
                    display_rule_id = safe_get(item, "ruleItemId")
                
                # Extract anomaly_detected and threshold_breached for FRESHNESS only
                anomaly_detected = None
                threshold_breached = None
                if execution.policy_type == "FRESHNESS":
                    anomaly_detected = safe_get(item, "anomalyDetected")
                    threshold_breached = safe_get(item, "thresholdBreached")
                
                execution_detail = ExecutionDetail(
                    item_id=extracted_item_id,
                    item_column_name=column_name,
                    left_column=left_column,
                    right_column=right_column,
                    item_ver=extracted_item_ver,
                    pde_name=pde_value,
                    pde=pde_label,
                    item_measurement_type=measurement_type,
                    rule_item_id=display_rule_id,  # For DATA_QUALITY: items.id, for others: ruleItemId
                    rule_strategy=safe_get(threshold_config, "strategy"),
                    rule_lower_threshold=safe_get(threshold_config, "lower"),
                    rule_upper_threshold=safe_get(threshold_config, "upper"),
                    result=rule_result,
                    result_status=result_status,
                    overall_policy_status=overall_policy_status,
                    overall_policy_quality_score=overall_policy_quality_score,
                    rows_scanned=rows_scanned,
                    rows_failed=rows_failed,
                    exec_id=execution.execution_id,
                    start_ts=execution.start_ts,
                    end_ts=execution.end_ts,
                    execution_status=execution.execution_status,
                    anomaly_detected=anomaly_detected,
                    threshold_breached=threshold_breached,
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


def fetch_asset_uids(asset_ids: list[str], http_client: ADOCHTTPClient) -> dict[str, str]:
    """Fetch asset UIDs from asset IDs using the asset search API.
    
    Args:
        asset_ids: List of asset IDs to look up
        http_client: HTTP client for API calls
        
    Returns:
        Dictionary mapping asset_id -> asset_uid
    """
    if not asset_ids:
        return {}
    
    asset_uid_map = {}
    
    try:
        # Use asset search API with ids parameter
        ids_param = ",".join(str(aid) for aid in asset_ids if aid)
        endpoint = f"/catalog-server/api/assets/search"
        response = http_client.get(endpoint, params={"ids": ids_param})
        
        if not response.is_success:
            log_error(f"Failed to fetch asset UIDs: HTTP {response.status_code}")
            return asset_uid_map
        
        data = response.json()
        assets = safe_get(data, "assets", [])
        
        for asset in assets:
            asset_id = str(safe_get(asset, "id", ""))
            asset_uid = safe_get(asset, "uid", "")
            if asset_id and asset_uid:
                asset_uid_map[asset_id] = asset_uid
        
        log_info(f"Fetched {len(asset_uid_map)} asset UIDs from {len(asset_ids)} IDs")
        
    except Exception as e:
        log_error(f"Error fetching asset UIDs: {e}")
    
    return asset_uid_map


def fetch_reconciliation_policy_details(
    policy_id: str, policy_version: int, http_client: ADOCHTTPClient
) -> dict[str, Any] | None:
    """Fetch reconciliation policy details from API.
    
    Args:
        policy_id: Policy ID
        policy_version: Policy version
        http_client: HTTP client for API calls
        
    Returns:
        Policy details data or None if fetch fails
    """
    try:
        endpoint = f"/catalog-server/api/rules/reconciliation/{policy_id}?version={policy_version}"
        response = http_client.get(endpoint)
        
        if not response.is_success:
            log_error(f"Failed to fetch reconciliation policy details for {policy_id}: HTTP {response.status_code}")
            return None
        
        return response.json()
        
    except Exception as e:
        log_error(f"Error fetching reconciliation policy details for {policy_id}: {e}")
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
            elif execution.policy_type == "FRESHNESS":
                # FRESHNESS uses DATA_CADENCE endpoint
                endpoint = (
                    f"/catalog-server/api/rules/data-cadence/{execution.policy_id}"
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

            # Extract policy enabled status from rule.enabled
            policy_enabled = safe_get(rule_data, "enabled")
            
            # Extract policy description from rule.description
            policy_description = safe_get(rule_data, "description")

            # Fetch table asset name
            table_asset_name = (
                fetch_asset_name(table_asset_id, http_client)
                if table_asset_id
                else None
            )

            details_data = safe_get(policy_detail_data, "details", {})
            
            # For EQUALITY (reconciliation), use columnMappings instead of items
            if execution.policy_type == "EQUALITY":
                # Iterate over columnMappings for EQUALITY policies
                column_mappings = safe_get(details_data, "columnMappings", [])
                log_info(
                    f"Fetched policy details for {execution.policy_type} "
                    f"policy_id={execution.policy_id}: {len(column_mappings)} columnMappings"
                )
                
                for col_map in column_mappings:
                    # Use columnMapping.id as item_id for EQUALITY (matches items[].id)
                    item_id = str(safe_get(col_map, "id", ""))
                    # Use execution.ruleVersion (not columnMapping.ruleVersion) to match execution details
                    rule_version = execution.policy_version
                    
                    # Extract PDE value from labels
                    pde_value = next(
                        (
                            safe_get(label, "value")
                            for label in safe_get(col_map, "labels", [])
                            if safe_get(label, "key") == "PDE"
                        ),
                        None,
                    )
                    
                    # Extract column name (use leftColumnName for EQUALITY)
                    column_name = safe_get(col_map, "leftColumnName")
                    
                    # Extract labels from columnMapping - create one PolicyDetail per label
                    item_labels = safe_get(col_map, "labels", [])
                    if item_labels:
                        # Create one PolicyDetail per label (flatten labels)
                        for label in item_labels:
                            label_key = safe_get(label, "key")
                            label_value = safe_get(label, "value")
                            
                            policy_detail = PolicyDetail(
                                policy_name=execution.policy_name,
                                policy_id=execution.policy_id,
                                policy_type=execution.policy_type,
                                id=item_id,
                                rule_version=rule_version,  # Use execution.ruleVersion (not columnMapping.ruleVersion)
                                column_name=column_name,
                                pde_value=pde_value,
                                table_asset_id=table_asset_id,
                                table_asset_name=table_asset_name,
                                policy_enabled=policy_enabled,
                                label_key=label_key,
                                label_value=label_value,
                            )
                            policy_details.append(policy_detail)
                    else:
                        # If no labels, create one PolicyDetail without label fields
                        policy_detail = PolicyDetail(
                            policy_name=execution.policy_name,
                            policy_id=execution.policy_id,
                            policy_type=execution.policy_type,
                            id=item_id,
                            rule_version=rule_version,  # Use execution.ruleVersion (not columnMapping.ruleVersion)
                            column_name=column_name,
                            pde_value=pde_value,
                            table_asset_id=table_asset_id,
                            table_asset_name=table_asset_name,
                            policy_enabled=policy_enabled,
                            label_key=None,
                            label_value=None,
                        )
                        policy_details.append(policy_detail)
            else:
                # For other policy types (DATA_QUALITY, DATA_DRIFT, etc.), use items
                items = safe_get(details_data, "items", [])
                log_info(
                    f"Fetched policy details for {execution.policy_type} "
                    f"policy_id={execution.policy_id}: {len(items)} items"
                )
                
                # For DATA_DRIFT and FRESHNESS, fetch version mapping once before processing items
                version_mapping: dict[tuple[str, str], str] = {}
                if execution.policy_type == "DATA_DRIFT":
                    version_mapping = fetch_data_drift_version_mapping(
                        execution.policy_id,
                        execution.policy_version,
                        http_client,
                    )
                elif execution.policy_type == "FRESHNESS":
                    version_mapping = fetch_freshness_version_mapping(
                        execution.policy_id,
                        execution.policy_version,
                        http_client,
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

                    # For DATA_QUALITY, policy details API uses top-level item.id (not nested)
                    # This matches execution details top-level item.id for merge key
                    if execution.policy_type == "DATA_QUALITY":
                        item_id = str(safe_get(item, "id", ""))
                        rule_version = safe_get(item, "ruleVersion", 1)
                    elif execution.policy_type == "DATA_DRIFT":
                        # For DATA_DRIFT, policy details have "id" field that matches execution details' "ruleItemId"
                        item_id = str(safe_get(item, "id", ""))
                        # For DATA_DRIFT, use execution.policy_version (from execution.ruleVersion) to match execution details
                        rule_version = execution.policy_version
                        log_info(
                            f"DEBUG {execution.policy_type} policy detail (non-parallel) - "
                            f"item keys: {list(item.keys())}, "
                            f"id: {safe_get(item, 'id')}, "
                            f"using item_id: '{item_id}', rule_version: {rule_version} (from execution.policy_version)"
                        )
                    elif execution.policy_type == "FRESHNESS":
                        # For FRESHNESS, policy details have "id" field that matches execution details' "ruleItemId"
                        item_id = str(safe_get(item, "id", ""))
                        # For FRESHNESS, use execution.policy_version (from execution.ruleVersion) to match execution details
                        rule_version = execution.policy_version
                    else:
                        # For PROFILE_ANOMALY, SCHEMA_DRIFT
                        # Policy details have "id" field that matches execution details' "ruleItemId"
                        item_id = str(safe_get(item, "id", ""))
                        rule_version = safe_get(item, "ruleVersion", 1)
                        log_info(
                            f"DEBUG {execution.policy_type} policy detail (non-parallel) - "
                            f"item keys: {list(item.keys())}, "
                            f"id: {safe_get(item, 'id')}, "
                            f"using item_id: '{item_id}'"
                        )

                    # Extract rule description from details.items.businessExplanation (for DATA_QUALITY)
                    rule_description = safe_get(item, "businessExplanation") if execution.policy_type == "DATA_QUALITY" else None
                    
                    # Extract column_name for all policies (existing behavior)
                    # For FRESHNESS, column_name is NOT_APPLICABLE (asset-level policy, not column-level)
                    if execution.policy_type == "FRESHNESS":
                        column_name = None  # Will be set to NOT_APPLICABLE later
                    else:
                        column_name = safe_get(item, "columnName")
                    
                    # Extract DATA_DRIFT-specific fields (only for DATA_DRIFT)
                    item_measurement_type = None
                    drift_threshold = None
                    if execution.policy_type == "DATA_DRIFT":
                        item_measurement_type = safe_get(item, "metricType")
                        drift_threshold = safe_get(item, "driftThreshold")
                    elif execution.policy_type == "FRESHNESS":
                        # For FRESHNESS, extract measurementType from policy details
                        item_measurement_type = safe_get(item, "measurementType")
                        # Extract threshold config for FRESHNESS
                        threshold_config = safe_get(item, "thresholdConfig", {})
                        rule_strategy = safe_get(threshold_config, "strategy")
                        rule_lower_threshold = safe_get(threshold_config, "lower")
                        rule_upper_threshold = safe_get(threshold_config, "upper")
                        drift_threshold = None  # Not applicable for FRESHNESS
                    
                    # For DATA_DRIFT, set Label_Key and Label_Value based on version mapping
                    if execution.policy_type == "DATA_DRIFT":
                        # Label_Key = Item_Column_Name-Item_Measurement_Type
                        label_key = f"{column_name or ''}-{item_measurement_type or ''}" if column_name and item_measurement_type else None
                        # Label_Value = item.id from version mapping (only for new combinations)
                        combination = (column_name or "", item_measurement_type or "")
                        label_value = version_mapping.get(combination)
                        
                        # Create PolicyDetail with DATA_DRIFT-specific Label_Key and Label_Value
                        policy_detail = PolicyDetail(
                            policy_name=execution.policy_name,
                            policy_id=execution.policy_id,
                            policy_type=execution.policy_type,
                            id=item_id,
                            rule_version=rule_version,
                            column_name=column_name,
                            pde_value=pde_value,
                            table_asset_id=table_asset_id,
                            table_asset_name=table_asset_name,
                            policy_enabled=policy_enabled,
                            label_key=label_key,
                            label_value=label_value,
                            policy_description=policy_description,
                            rule_description=None,  # Rule_Description is NOT_APPLICABLE for DATA_DRIFT
                            item_measurement_type=item_measurement_type,
                            drift_threshold=drift_threshold,
                        )
                        policy_details.append(policy_detail)
                    elif execution.policy_type == "FRESHNESS":
                        # For FRESHNESS, set Label_Key and Label_Value based on version mapping
                        # Label_Key = Item_Measurement_Type-Rule_Strategy
                        label_key = f"{item_measurement_type or ''}-{rule_strategy or ''}" if item_measurement_type and rule_strategy else None
                        # Label_Value = item.id from version mapping (only for new combinations)
                        combination = (item_measurement_type or "", rule_strategy or "")
                        label_value = version_mapping.get(combination)
                        
                        # Create PolicyDetail with FRESHNESS-specific Label_Key and Label_Value
                        policy_detail = PolicyDetail(
                            policy_name=execution.policy_name,
                            policy_id=execution.policy_id,
                            policy_type=execution.policy_type,
                            id=item_id,
                            rule_version=rule_version,
                            column_name=column_name,
                            pde_value=None,  # NOT_APPLICABLE for FRESHNESS
                            table_asset_id=table_asset_id,
                            table_asset_name=table_asset_name,
                            policy_enabled=policy_enabled,
                            label_key=label_key,
                            label_value=label_value,
                            policy_description=policy_description,
                            rule_description=None,  # Rule_Description is NOT_APPLICABLE for FRESHNESS
                            item_measurement_type=item_measurement_type,
                            drift_threshold=drift_threshold,
                            rule_strategy=rule_strategy,
                            rule_lower_threshold=rule_lower_threshold,
                            rule_upper_threshold=rule_upper_threshold,
                        )
                        policy_details.append(policy_detail)
                    else:
                        # For other policy types, use existing label extraction logic
                        # Extract labels from item - create one PolicyDetail per label
                        item_labels = safe_get(item, "labels", [])
                        if item_labels:
                            # Create one PolicyDetail per label (flatten labels)
                            for label in item_labels:
                                label_key = safe_get(label, "key")
                                label_value = safe_get(label, "value")
                                
                                policy_detail = PolicyDetail(
                                    policy_name=execution.policy_name,
                                    policy_id=execution.policy_id,
                                    policy_type=execution.policy_type,
                                    id=item_id,
                                    rule_version=rule_version,
                                    column_name=column_name,
                                    pde_value=pde_value,
                                    table_asset_id=table_asset_id,
                                    table_asset_name=table_asset_name,
                                    policy_enabled=policy_enabled,
                                    label_key=label_key,
                                    label_value=label_value,
                                    policy_description=policy_description,
                                    rule_description=rule_description,
                                    item_measurement_type=item_measurement_type,
                                    drift_threshold=drift_threshold,
                                )
                                policy_details.append(policy_detail)
                        else:
                            # If no labels, create one PolicyDetail without label fields
                            policy_detail = PolicyDetail(
                                policy_name=execution.policy_name,
                                policy_id=execution.policy_id,
                                policy_type=execution.policy_type,
                                id=item_id,
                                rule_version=rule_version,
                                column_name=column_name,
                                pde_value=pde_value,
                                table_asset_id=table_asset_id,
                                table_asset_name=table_asset_name,
                                policy_enabled=policy_enabled,
                                label_key=None,
                                label_value=None,
                                policy_description=policy_description,
                                rule_description=rule_description,
                                item_measurement_type=item_measurement_type,
                                drift_threshold=drift_threshold,
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


def process_reconciliation_records(
    exec_result_data: dict[str, Any],
    execution: PolicyExecution,
    http_client: ADOCHTTPClient,
    timezone: str = "UTC",
) -> list[ReconciliationRecord]:
    """Process reconciliation API response into ReconciliationRecord models.
    
    Args:
        exec_result_data: Raw API response data
        execution: PolicyExecution model with execution metadata
        http_client: HTTP client for API calls
        timezone: Timezone for datetime conversions
        
    Returns:
        List of ReconciliationRecord models
    """
    from ...models import ReconciliationRecord
    
    records = []
    execution_data = safe_get(exec_result_data, "execution", {})
    result_data = safe_get(exec_result_data, "result", {})
    items = safe_get(exec_result_data, "items", [])
    
    # Fetch policy details to get additional fields
    policy_id = str(safe_get(execution_data, "ruleId", ""))
    rule_version = safe_get(execution_data, "ruleVersion", 1)
    policy_details_data = fetch_reconciliation_policy_details(policy_id, rule_version, http_client)
    
    # Extract policy-level fields
    policy_description = None
    join_type = None
    left_asset_id = None
    right_asset_id = None
    column_mappings_lookup = {}  # Map by columnMapping id or ruleItemId
    
    # Extract policy enabled status
    policy_enabled = None
    if policy_details_data:
        rule_data = safe_get(policy_details_data, "rule", {})
        policy_description = safe_get(rule_data, "description")
        policy_enabled = safe_get(rule_data, "enabled")
        
        # Extract backing assets
        left_backing_asset = safe_get(rule_data, "leftBackingAsset", {})
        right_backing_asset = safe_get(rule_data, "rightBackingAsset", {})
        left_asset_id = str(safe_get(left_backing_asset, "tableAssetId", "")) if left_backing_asset else None
        right_asset_id = str(safe_get(right_backing_asset, "tableAssetId", "")) if right_backing_asset else None
        
        # Extract details
        details_data = safe_get(policy_details_data, "details", {})
        join_type = safe_get(details_data, "joinType")
        column_mappings = safe_get(details_data, "columnMappings", [])
        
        # Build lookup by id (columnMapping.id matches item.columnMapping.id)
        for col_map in column_mappings:
            col_map_id = str(safe_get(col_map, "id", ""))
            if col_map_id:
                column_mappings_lookup[col_map_id] = col_map
    
    # Fetch asset UIDs if we have asset IDs
    asset_ids_to_fetch = []
    if left_asset_id:
        asset_ids_to_fetch.append(left_asset_id)
    if right_asset_id:
        asset_ids_to_fetch.append(right_asset_id)
    
    asset_uid_map = fetch_asset_uids(asset_ids_to_fetch, http_client) if asset_ids_to_fetch else {}
    left_asset_uid = asset_uid_map.get(left_asset_id) if left_asset_id else None
    right_asset_uid = asset_uid_map.get(right_asset_id) if right_asset_id else None
    
    # Extract execution-level fields
    policy_name = safe_get(execution_data, "ruleName", "")
    policy_id = str(safe_get(execution_data, "ruleId", ""))
    rule_version = safe_get(execution_data, "ruleVersion", 1)
    execution_id = str(safe_get(execution_data, "id", ""))
    execution_status = safe_get(execution_data, "executionStatus", "")
    # Note: result_status will be extracted per item from items[].success
    policy_type = safe_get(execution_data, "ruleType", "EQUALITY")
    # Map DATA_CADENCE (API) to FRESHNESS (internal)
    if policy_type == "DATA_CADENCE":
        policy_type = "FRESHNESS"
    
    # Extract result-level fields
    # For reconciliation, Rows_Scanned = result.rows
    rows_scanned = safe_get(result_data, "rows")
    left_rows_scanned = safe_get(result_data, "leftRowsScanned")
    right_rows_scanned = safe_get(result_data, "rightRowsScanned")
    overall_policy_status = safe_get(result_data, "status")
    overall_policy_quality_score = safe_get(result_data, "qualityScore")
    
    # Extract timestamps
    started_at_ts = safe_get(execution_data, "startedAt")
    finished_at_ts = safe_get(execution_data, "finishedAt")
    
    started_at = convert_timestamp_to_datetime(started_at_ts, timezone)
    finished_at = convert_timestamp_to_datetime(finished_at_ts, timezone)
    execution_date = finished_at  # Use finishedAt as execution date
    
    # Process each item
    for item in items:
        # For reconciliation, Rows_Failed comes from items[].leftRowsFailed
        rows_failed = safe_get(item, "leftRowsFailed")
        # Determine Recon_Type based on dimension first (all caps for consistency)
        dimension = safe_get(item, "dimension", "")
        if dimension == "ACCURACY":
            recon_type = "EQUALITY_MATCH"
        elif dimension == "TIMELINESS":
            recon_type = "ROW_COUNT_MATCH"
        else:
            recon_type = None
        
        # Extract column mapping from item
        column_mapping = safe_get(item, "columnMapping", {})
        
        # Extract column names - only for EQUALITY_MATCH
        if recon_type == "EQUALITY_MATCH":
            left_column = safe_get(column_mapping, "leftColumnName") if column_mapping else None
            right_column = safe_get(column_mapping, "rightColumnName") if column_mapping else None
        else:
            # For ROW_COUNT_MATCH, set to "NOT_APPLICABLE" (all caps for consistency)
            left_column = "NOT_APPLICABLE"
            right_column = "NOT_APPLICABLE"
        
        # Extract rule item ID from items.columnMapping.id (not items.ruleItemId)
        if column_mapping:
            rule_id = str(safe_get(column_mapping, "id", ""))
        else:
            # Fallback to ruleItemId if columnMapping is not available
            rule_id = str(safe_get(item, "ruleItemId", ""))
        
        # Extract result percentage
        result_percentage = safe_get(item, "resultPercent")
        
        # Extract Result_Status from items[].success (same as DATA_QUALITY)
        # If items.success is true then "SUCCESSFUL", else "FAILED" (all caps for consistency)
        item_success = safe_get(item, "success")
        if item_success is True:
            result_status = "SUCCESSFUL"
        elif item_success is False:
            result_status = "FAILED"
        else:
            result_status = None
        
        # Find matching columnMapping from policy details for this item
        # Match by item.columnMapping.id
        matched_col_map = None
        if column_mapping:
            col_map_id = str(safe_get(column_mapping, "id", ""))
            if col_map_id and col_map_id in column_mappings_lookup:
                matched_col_map = column_mappings_lookup[col_map_id]
        
        # Extract Operation, Use_For_Joining and Rule_Description from columnMapping
        operation = None
        if recon_type == "ROW_COUNT_MATCH":
            use_for_joining = "NOT_APPLICABLE"  # All caps for consistency
            rule_description = None
        else:
            # For EQUALITY_MATCH, get from matched columnMapping (from policy details) or item.columnMapping
            if matched_col_map:
                # Prefer policy details columnMapping
                operation = safe_get(matched_col_map, "operation")
                use_for_joining_val = safe_get(matched_col_map, "useForJoining")
                # Convert boolean to string (True/False) or keep as string
                if use_for_joining_val is not None:
                    if isinstance(use_for_joining_val, bool):
                        use_for_joining = "True" if use_for_joining_val else "False"
                    else:
                        use_for_joining = str(use_for_joining_val)
                else:
                    use_for_joining = None
                rule_description = safe_get(matched_col_map, "businessExplanation")
            elif column_mapping:
                # Fallback to item.columnMapping
                operation = safe_get(column_mapping, "operation")
                use_for_joining_val = safe_get(column_mapping, "useForJoining")
                # Convert boolean to string (True/False) or keep as string
                if use_for_joining_val is not None:
                    if isinstance(use_for_joining_val, bool):
                        use_for_joining = "True" if use_for_joining_val else "False"
                    else:
                        use_for_joining = str(use_for_joining_val)
                else:
                    use_for_joining = None
                rule_description = safe_get(column_mapping, "businessExplanation")
            else:
                use_for_joining = None
                rule_description = None
        
        # Calculate rows_failed/drift based on Recon_Type
        # For reconciliation, Rows_Failed always uses items[].leftRowsFailed (already extracted above)
        if recon_type == "ROW_COUNT_MATCH":
            # Calculate drift: abs(rightRowsScanned - leftRowsScanned)
            if left_rows_scanned is not None and right_rows_scanned is not None:
                drift = abs(right_rows_scanned - left_rows_scanned)
            else:
                drift = None
            # Use items[].leftRowsFailed for Rows_Failed (not drift calculation)
            rows_failed_value = rows_failed
            # Set Left_Rows_Scanned and Right_Rows_Scanned
            left_rows_value = left_rows_scanned
            right_rows_value = right_rows_scanned
        else:
            # For EQUALITY_MATCH, use items[].leftRowsFailed
            rows_failed_value = rows_failed
            # Set to "NOT_APPLICABLE" for EQUALITY_MATCH (all caps for consistency)
            left_rows_value = "NOT_APPLICABLE"
            right_rows_value = "NOT_APPLICABLE"
        
        # Extract labels from matched columnMapping (from policy details)
        # Create one ReconciliationRecord per label (flatten labels)
        col_map_labels = []
        if matched_col_map:
            col_map_labels = safe_get(matched_col_map, "labels", [])
        
        if col_map_labels:
            # Create one record per label
            for label in col_map_labels:
                label_key = safe_get(label, "key")
                label_value = safe_get(label, "value")
                
                record = ReconciliationRecord(
                    Policy_Name=policy_name,
                    Policy_ID=policy_id,
                    Rule_Version=rule_version,
                    Execution_ID=execution_id,
                    Left_Column=left_column,
                    Right_Column=right_column,
                    Rule_ID=rule_id,
                    Recon_Type=recon_type,
                    Result_Percentage=result_percentage,
                    Rows_Scanned=rows_scanned,
                    Rows_Failed=rows_failed_value,
                    Left_Rows_Scanned=left_rows_value,
                    Right_Rows_Scanned=right_rows_value,
                    Use_For_Joining=use_for_joining,
                    Policy_Description=policy_description,
                    Rule_Description=rule_description,
                    Left_ASSET_UID=left_asset_uid,
                    Right_ASSET_UID=right_asset_uid,
                    Join_Type=join_type,
                    Started_At_UTC=started_at,
                    Finished_At_UTC=finished_at,
                    Execution_Date_UTC=execution_date,
                    Execution_Status=execution_status,
                    Rule_Result_Status=result_status,
                    Overall_Policy_Status=overall_policy_status,
                    Overall_Policy_Quality_Score=overall_policy_quality_score,
                    Policy_Type=policy_type,
                    Policy_Enabled=policy_enabled,
                    Operation=operation,
                    Label_Key=label_key,
                    Label_Value=label_value,
                )
                records.append(record)
        else:
            # If no labels, create one record without label fields
            record = ReconciliationRecord(
                Policy_Name=policy_name,
                Policy_ID=policy_id,
                Rule_Version=rule_version,
                Execution_ID=execution_id,
                Left_Column=left_column,
                Right_Column=right_column,
                Rule_ID=rule_id,
                Recon_Type=recon_type,
                Result_Percentage=result_percentage,
                Rows_Scanned=rows_scanned,
                Rows_Failed=rows_failed_value,
                Left_Rows_Scanned=left_rows_value,
                Right_Rows_Scanned=right_rows_value,
                Use_For_Joining=use_for_joining,
                Policy_Description=policy_description,
                Rule_Description=rule_description,
                Left_ASSET_UID=left_asset_uid,
                Right_ASSET_UID=right_asset_uid,
                Join_Type=join_type,
                Started_At_UTC=started_at,
                Finished_At_UTC=finished_at,
                Execution_Date_UTC=execution_date,
                Execution_Status=execution_status,
                Rule_Result_Status=result_status,
                Overall_Policy_Status=overall_policy_status,
                Overall_Policy_Quality_Score=overall_policy_quality_score,
                Policy_Type=policy_type,
                Policy_Enabled=policy_enabled,
                Operation=operation,
                Label_Key=None,
                Label_Value=None,
            )
            records.append(record)
    
    return records


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
    
    # Create lookup dictionary for policy details - handle multiple labels per item
    # Use list to store all PolicyDetail records for the same (id, rule_version) key
    policy_lookup: dict[tuple[str, int], list[PolicyDetail]] = {}
    for detail in policy_details:
        key = (detail.id, detail.rule_version)
        if key not in policy_lookup:
            policy_lookup[key] = []
        policy_lookup[key].append(detail)
    
    # Debug: Log EQUALITY policy keys
    equality_policy_keys = [(k, v[0].policy_type) for k, v in policy_lookup.items() if v and v[0].policy_type == "EQUALITY"]
    if equality_policy_keys:
        log_info(f"DEBUG Merge: EQUALITY policy keys (first 10): {equality_policy_keys[:10]}")

    merged_records = []
    unmatched_exec_details = 0
    unmatched_keys = []
    
    # Build a set of DATA_QUALITY execution IDs from policy_details
    # This helps us identify which execution_details are for DATA_QUALITY
    dq_policy_details = [d for d in policy_details if d.policy_type == "DATA_QUALITY"]
    dq_policy_count = len(dq_policy_details)
    
    # Create a set of DATA_QUALITY item keys for quick lookup
    dq_policy_keys = {(d.id, d.rule_version) for d in dq_policy_details}
    
    # Debug: Log sample keys from both sides for DATA_QUALITY
    dq_exec_details = [d for d in execution_details if (d.item_id, d.item_ver) in dq_policy_keys][:10]
    
    if dq_exec_details:
        log_info(f"DEBUG Merge: Sample DATA_QUALITY execution detail keys (first 10): {[(d.item_id, d.item_ver, getattr(d, 'rule_item_id', None)) for d in dq_exec_details]}")
    if dq_policy_details:
        log_info(f"DEBUG Merge: Sample DATA_QUALITY policy detail keys (first 10): {[(d.id, d.rule_version) for d in dq_policy_details[:10]]}")
    
    # Also check if ruleItemId matches policy details id
    if dq_exec_details and dq_policy_details:
        exec_rule_item_ids = [getattr(d, 'rule_item_id', None) for d in dq_exec_details if hasattr(d, 'rule_item_id')]
        policy_ids = [d.id for d in dq_policy_details[:5]]
        log_info(f"DEBUG Merge: Execution ruleItemId sample: {exec_rule_item_ids[:5]}")
        log_info(f"DEBUG Merge: Policy id sample: {policy_ids}")
    
    # Count DATA_QUALITY records specifically
    dq_exec_count = 0
    dq_merged_count = 0
    dq_unmatched_count = 0
    
    # Debug: Track EQUALITY execution details - collect all exec details from EQUALITY executions
    equality_exec_keys_all = []  # All EQUALITY exec detail keys (matched or not)
    
    for exec_detail in execution_details:
        key = (exec_detail.item_id, exec_detail.item_ver)
        
        # Debug: Track all execution detail keys from EQUALITY executions
        # We'll determine if it's EQUALITY by checking after the lookup
        policy_detail_list_for_key = policy_lookup.get(key, [])
        if policy_detail_list_for_key and policy_detail_list_for_key[0].policy_type == "EQUALITY":
            equality_exec_keys_all.append((key, exec_detail.exec_id, "matched"))
        
        # Check if this is a DATA_QUALITY record by checking if key exists in DQ policy keys
        is_dq = key in dq_policy_keys
        if is_dq:
            dq_exec_count += 1
        
        policy_detail_list = policy_lookup.get(key, [])
        
        # Debug: Track EQUALITY execution details that don't match
        if not policy_detail_list:
            # Check if this might be an EQUALITY exec detail by looking for a pattern
            # We'll log unmatched keys and then analyze them
            pass

        if policy_detail_list:
            # Skip EQUALITY records - they are handled separately as ReconciliationRecord
            # ReconciliationRecord has all the necessary fields and more reconciliation-specific data
            if policy_detail_list[0].policy_type == "EQUALITY":
                # Skip creating ExecutionMetricsRecord for EQUALITY - use ReconciliationRecord instead
                continue
            
            # Create one ExecutionMetricsRecord per PolicyDetail (to handle multiple labels)
            for policy_detail in policy_detail_list:
                if policy_detail.policy_type == "DATA_QUALITY":
                    dq_merged_count += 1
                # For DATA_QUALITY, use rule_item_id (items.id) for Rule_ID display
                # For other policy types, use item_id (which is already correct)
                if policy_detail.policy_type == "DATA_QUALITY" and exec_detail.rule_item_id:
                    display_item_id = str(exec_detail.rule_item_id)  # items.id for Rule_ID
                else:
                    display_item_id = exec_detail.item_id  # Use merge key for other types
                
                # For DATA_DRIFT and FRESHNESS, use item_measurement_type from policy_detail
                # DATA_DRIFT: from details.items.metricType
                # FRESHNESS: from details.items.measurementType (execution details have dimension="OTHERS" which is not useful)
                # For other policy types, use from exec_detail (they have their own field paths)
                if policy_detail.policy_type in ["DATA_DRIFT", "FRESHNESS"] and policy_detail.item_measurement_type:
                    measurement_type = policy_detail.item_measurement_type
                else:
                    measurement_type = exec_detail.item_measurement_type
                
                # For DATA_DRIFT, use column_name from policy_detail (from details.items.columnName)
                # For FRESHNESS, column_name is NOT_APPLICABLE (asset-level policy, not column-level)
                # For other types, use from exec_detail
                if policy_detail.policy_type == "DATA_DRIFT" and policy_detail.column_name:
                    column_name = policy_detail.column_name
                elif policy_detail.policy_type == "FRESHNESS":
                    column_name = None  # Will be set to NOT_APPLICABLE later
                else:
                    column_name = exec_detail.item_column_name
                
                # For EQUALITY, extract left_column and right_column from exec_detail
                left_column = exec_detail.left_column if policy_detail.policy_type == "EQUALITY" else None
                right_column = exec_detail.right_column if policy_detail.policy_type == "EQUALITY" else None
                
                record = ExecutionMetricsRecord(
                    policy_name=policy_detail.policy_name,
                    policy_id=policy_detail.policy_id,
                    rule_version=exec_detail.item_ver,
                    exec_id=exec_detail.exec_id,
                    table_asset_name=policy_detail.table_asset_name,
                    item_column_name=column_name,
                    left_column=left_column,
                    right_column=right_column,
                    pde=exec_detail.pde,
                    item_measurement_type=measurement_type,
                    # For FRESHNESS, use threshold config from policy_detail (execution details don't have it)
                    # For other policy types, use from exec_detail
                    rule_strategy=policy_detail.rule_strategy if policy_detail.policy_type == "FRESHNESS" and policy_detail.rule_strategy else exec_detail.rule_strategy,
                    rule_lower_threshold=policy_detail.rule_lower_threshold if policy_detail.policy_type == "FRESHNESS" and policy_detail.rule_lower_threshold is not None else exec_detail.rule_lower_threshold,
                    rule_upper_threshold=policy_detail.rule_upper_threshold if policy_detail.policy_type == "FRESHNESS" and policy_detail.rule_upper_threshold is not None else exec_detail.rule_upper_threshold,
                    item_id=display_item_id,  # For DATA_QUALITY: items.id, for others: merge key
                    result=exec_detail.result,
                    result_status=exec_detail.result_status,
                    overall_policy_status=exec_detail.overall_policy_status,
                    overall_policy_quality_score=exec_detail.overall_policy_quality_score,
                    rows_scanned=exec_detail.rows_scanned,
                    rows_failed=exec_detail.rows_failed,
                    startedAt=exec_detail.start_ts,
                    started_at=convert_timestamp_to_datetime(exec_detail.start_ts, timezone),
                    finishedAt=exec_detail.end_ts,
                    finished_at=convert_timestamp_to_datetime(exec_detail.end_ts, timezone),
                    execution_date=convert_timestamp_to_datetime(exec_detail.end_ts, timezone),
                    execution_status=exec_detail.execution_status,
                    policy_type=policy_detail.policy_type,
                    policy_enabled=policy_detail.policy_enabled,
                    label_key=policy_detail.label_key,
                    label_value=policy_detail.label_value,
                    policy_description=policy_detail.policy_description,
                    rule_description=policy_detail.rule_description,
                    drift_threshold=policy_detail.drift_threshold,
                    anomaly_detected=exec_detail.anomaly_detected,
                    threshold_breached=exec_detail.threshold_breached,
                )
                merged_records.append(record)
        else:
            unmatched_exec_details += 1
            unmatched_keys.append(key)
            if is_dq:
                dq_unmatched_count += 1
            # Even if no policy detail found, we might want to create a record with execution data only
            # For now, we skip it to maintain backward compatibility
    
    # Log output counts by policy type
    merged_type_counts = {}
    for record in merged_records:
        merged_type_counts[record.policy_type] = merged_type_counts.get(record.policy_type, 0) + 1
    
    log_info(f"Merge output: {len(merged_records)} merged records, breakdown: {merged_type_counts}")
    log_info(f"Merge unmatched: {unmatched_exec_details} execution details without policy match")
    
    # Log DATA_QUALITY specific statistics
    log_info(f"DATA_QUALITY merge stats: {dq_exec_count} execution details (with matching policy keys), {dq_policy_count} policy details, {dq_merged_count} merged, {dq_unmatched_count} unmatched")
    
    # Find all DATA_QUALITY execution details that don't match (by checking rule_item_id)
    dq_unmatched_details = []
    for exec_detail in execution_details:
        key = (exec_detail.item_id, exec_detail.item_ver)
        if key not in policy_lookup:
            # Check if this might be DATA_QUALITY by checking if rule_item_id exists
            if hasattr(exec_detail, 'rule_item_id') and exec_detail.rule_item_id:
                # Check if rule_item_id matches any policy detail id
                matches_any = any(
                    detail.id == exec_detail.rule_item_id 
                    for detail_list in policy_lookup.values() 
                    for detail in detail_list 
                    if detail.policy_type == "DATA_QUALITY"
                )
                if not matches_any:
                    dq_unmatched_details.append((exec_detail.rule_item_id, exec_detail.item_id, exec_detail.item_ver))
    
    if dq_unmatched_count > 0 or dq_unmatched_details:
        log_info(f"DATA_QUALITY unmatched keys (first 10): {unmatched_keys[:10]}")
        if dq_unmatched_details:
            log_info(f"DATA_QUALITY execution details with rule_item_id but no match (first 10): {dq_unmatched_details[:10]}")
        # Show sample unmatched keys vs available policy keys
        available_policy_keys = list(policy_lookup.keys())[:20]
        log_info(f"Available DATA_QUALITY policy keys (first 20): {[k for k in available_policy_keys if any(d.policy_type == 'DATA_QUALITY' for d in policy_lookup.get(k, []))]}")
    if unmatched_exec_details > 0:
        log_info(f"Merge warning: {unmatched_exec_details} execution details had no matching policy details")
        # Log the unmatched keys to see if they're EQUALITY
        log_info(f"DEBUG Merge: Unmatched execution detail keys (first 20): {unmatched_keys[:20]}")
    
    # Debug: Log EQUALITY merge statistics
    if equality_exec_keys_all:
        log_info(f"DEBUG Merge: EQUALITY execution detail keys (first 10): {equality_exec_keys_all[:10]}")
        equality_merged_count = sum(1 for r in merged_records if r.policy_type == "EQUALITY")
        log_info(f"DEBUG Merge: EQUALITY merged {equality_merged_count} records from {len(equality_exec_keys_all)} execution details")

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
                f"✅ Using backload datetime (OVERRIDING tracking file): {start_datetime} "
                f"(timestamp: {start_timestamp})"
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

            loaded_timestamp = data.get("last_run_timestamp")
            loaded_datetime = None
            if data.get("last_run_datetime"):
                try:
                    loaded_datetime = datetime.fromisoformat(data.get("last_run_datetime"))
                except (ValueError, TypeError):
                    pass
            
            # Validate timestamp is not in the future (more than 1 hour ahead)
            current_ts = int(datetime.now().timestamp() * 1000)
            if loaded_timestamp and loaded_timestamp > current_ts + 3600000:  # 1 hour in ms
                log_info(
                    f"Tracking file has future timestamp ({loaded_timestamp}), "
                    f"resetting to 30 days ago"
                )
                # Reset to 30 days ago
                start_datetime = datetime.now() - timedelta(days=30)
                start_timestamp = int(start_datetime.timestamp() * 1000)
                return LastRunInfo(
                    last_run_timestamp=start_timestamp,
                    last_run_datetime=start_datetime,
                    total_records_processed=0,
                )

            # Log loaded timestamp for debugging
            if loaded_timestamp:
                current_ts = int(datetime.now().timestamp() * 1000)
                hours_diff = (loaded_timestamp - current_ts) / (1000 * 3600)
                log_info(
                    f"Loaded tracking file: timestamp={loaded_timestamp}, "
                    f"datetime={loaded_datetime}, "
                    f"hours_from_now={hours_diff:.2f}"
                )
            
            return LastRunInfo(
                last_run_timestamp=loaded_timestamp,
                last_run_datetime=loaded_datetime,
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
            execution_details, reconciliation_records = self._fetch_execution_details_parallel(
                policy_executions, progress, task2
            )
            # Remove the task after completion
            progress.remove_task(task2)
            
            # Log reconciliation records count
            if reconciliation_records:
                log_info(f"Fetched {len(reconciliation_records)} reconciliation records")

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
                reconciliation_records_count=len(reconciliation_records),
            )

            # Return both merged records and reconciliation records
            # Store reconciliation records in a custom attribute for access in export command
            self._reconciliation_records = reconciliation_records
            
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

        # Limit concurrent workers to avoid overwhelming the API
        # Start with a smaller batch to check if there's data
        max_workers = min(3, 10)  # Limit to 3 concurrent workers initially

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
        page_0_processed = False  # Track if Page 0 has been processed

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            while not stop_fetching and page < 50:  # Safety limit
                # Submit tasks for parallel execution
                futures = []
                pages_to_submit = max_workers

                for _ in range(pages_to_submit):
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
                
                # If no futures were submitted, break
                if not futures:
                    break

                # If no futures to process, break
                if not futures:
                    break

                # Wait for all submitted tasks to complete
                # Sort futures by page number to process Page 0 first
                futures_sorted = sorted(futures, key=lambda x: x[2])  # Sort by page_num (index 2)
                
                for future, worker_id, page_num in futures_sorted:
                    try:
                        # Use longer timeout for Page 0 when page_size is large (1000 items can take 2+ minutes to process)
                        # Also use longer timeout for larger page sizes
                        if page_num == 0 and page_size >= 1000:
                            timeout_seconds = 180  # 3 minutes for Page 0 with 1000 items
                        elif page_num == 0 and page_size >= 500:
                            timeout_seconds = 120  # 2 minutes for Page 0 with 500 items
                        elif page_size >= 1000:
                            timeout_seconds = 90  # 1.5 minutes for other pages with 1000 items
                        elif page_size >= 500:
                            timeout_seconds = 60  # 1 minute for other pages with 500 items
                        else:
                            timeout_seconds = 30  # 30 seconds for smaller page sizes
                        result_page, page_executions, should_stop = future.result(
                            timeout=timeout_seconds
                        )

                        if should_stop:
                            stop_fetching = True
                            log_info(f"Page {page_num}: API returned no executions (empty page), stopping pagination")
                            release_worker(worker_id)
                            pages_fetched += 1
                            progress.update(
                                task_id,
                                description=f"📥 Fetching executions (Pages: {pages_fetched}, Total: {len(data_collector)})"
                            )
                            # Cancel remaining futures in this batch and release workers
                            for remaining_future, remaining_worker_id, remaining_page_num in futures_sorted:
                                if remaining_future != future:
                                    try:
                                        remaining_future.cancel()
                                        log_info(f"Cancelled page {remaining_page_num} fetch (no more data available)")
                                    except Exception:
                                        pass
                                    release_worker(remaining_worker_id)
                            break  # Break out of the futures loop immediately

                        # Track when Page 0 is processed
                        if page_num == 0:
                            page_0_processed = True
                            log_info(f"Page 0 processed: {len(page_executions)} executions from API")
                            # Debug: Log first few execution timestamps from Page 0
                            if page_executions:
                                for i, exec in enumerate(page_executions[:5]):
                                    log_info(f"Page 0 execution {i}: id={exec.execution_id}, start_ts={exec.start_ts}, policy_type={exec.policy_type}")

                        # Initialize filtered_executions for the stop check later
                        filtered_executions = []
                        filtered_out_ids = []
                        
                        # If page_executions is empty, we've reached the end
                        if not page_executions:
                            # No executions on this page - this means we've reached the end
                            # (API returned empty page)
                            log_info(f"Page {page_num}: No executions returned from API (end of data)")
                            # Don't set stop_fetching here - let should_stop handle it
                        
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
                            for exec in page_executions:
                                if exec.start_ts is None or exec.start_ts > start_ts_marker:
                                    filtered_executions.append(exec)
                                else:
                                    filtered_out_ids.append(exec.execution_id)
                            
                            # Log timestamp filtering results with execution IDs
                            if len(filtered_executions) != len(page_executions):
                                filtered_out_count = len(page_executions) - len(filtered_executions)
                                log_info(
                                    f"Page {page_num}: Timestamp filter removed {filtered_out_count} "
                                    f"executions (kept {len(filtered_executions)} of {len(page_executions)})"
                                )
                                if filtered_out_ids:
                                    log_info(f"Page {page_num}: Filtered out execution IDs: {filtered_out_ids[:10]}")
                            else:
                                log_info(f"Page {page_num}: All {len(page_executions)} executions passed timestamp filter")
                            
                            # Log execution IDs that passed the filter for debugging
                            if filtered_executions and page_num <= 2:  # Only log first few pages to avoid spam
                                passed_ids = [exec.execution_id for exec in filtered_executions[:10]]
                                log_info(f"Page {page_num}: Execution IDs that passed filter: {passed_ids}")
                            
                            # Special logging for Page 0 to debug issues
                            if page_num == 0:
                                log_info(
                                    f"Page 0: Processed {len(page_executions)} executions, "
                                    f"{len(filtered_executions)} passed timestamp filter, "
                                    f"{len(filtered_out_ids)} filtered out"
                                )
                                if filtered_executions:
                                    log_info(f"Page 0: First 10 execution IDs that passed: {[e.execution_id for e in filtered_executions[:10]]}")
                                if filtered_out_ids:
                                    log_info(f"Page 0: First 10 execution IDs filtered out: {filtered_out_ids[:10]}")

                            if filtered_executions:
                                data_collector.extend(filtered_executions)

                            # Check if we've reached the timestamp marker
                            # IMPORTANT: Since results are sorted DESC (newest first), we should only stop
                            # if we've processed Page 0 (the newest page) and it has executions before the marker.
                            # Don't stop based on later pages (Page 1, 2, etc.) until we've checked Page 0.
                            
                            # Count executions before marker (filtered out)
                            executions_before_marker = [
                                exec for exec in page_executions
                                if exec.start_ts is not None and exec.start_ts <= start_ts_marker
                            ]
                            
                            # Stop pagination if ALL executions on a page are before the marker
                            # Since results are sorted DESC (newest first):
                            # - Page 0 has the newest executions
                            # - If Page 0 has all executions before marker, we can stop immediately
                            # - If a later page (Page 1+) has all executions before marker AND Page 0 is processed, we can stop
                            #   (because DESC sort means all subsequent pages will be older)
                            if len(executions_before_marker) == len(page_executions) and len(page_executions) > 0:
                                # All executions on this page are before the marker
                                if page_num == 0:
                                    # Page 0 is the newest page - if all are before marker, we can stop
                                    stop_fetching = True
                                    log_info(
                                        f"Page 0: All {len(executions_before_marker)} executions are before marker "
                                        f"({start_ts_marker}), stopping pagination"
                                    )
                                elif page_0_processed:
                                    # For later pages, only stop if Page 0 has been processed
                                    # (since DESC sort means Page 1, 2, etc. are older)
                                    stop_fetching = True
                                    log_info(
                                        f"Page {page_num}: All {len(executions_before_marker)} executions are before marker "
                                        f"(Page 0 already processed), stopping pagination"
                                    )
                                else:
                                    # Don't stop yet - wait for Page 0 to be processed first
                                    log_info(
                                        f"Page {page_num}: All executions before marker, but waiting for Page 0 to complete"
                                    )
                            
                            # Also stop if Page 0 has been processed and we got no filtered executions from it
                            # This handles the case where all executions are filtered out
                            if (page_num == 0 and page_0_processed and 
                                len(filtered_executions) == 0 and len(page_executions) > 0):
                                stop_fetching = True
                                log_info(
                                    f"Page 0: All {len(page_executions)} executions filtered out (all before marker), "
                                    f"stopping pagination"
                                )

                        # Update main progress
                        pages_fetched += 1
                        progress.update(
                            task_id,
                            description=f"📥 Fetching executions (Pages: {pages_fetched}, Total: {len(data_collector)})"
                        )

                    except Exception as e:
                        import traceback
                        error_details = traceback.format_exc()
                        log_error(f"Error processing page {page_num}: {e}")
                        log_error(f"Error details for page {page_num}: {error_details}")
                        pages_fetched += 1
                        progress.update(
                            task_id,
                            description=f"📥 Fetching executions (Pages: {pages_fetched}, Total: {len(data_collector)})"
                        )
                    finally:
                        # Release worker (unless already released in should_stop block)
                        if not (stop_fetching and page_num == 0):
                            release_worker(worker_id)
                    
                    # If should_stop was set, break immediately to stop submitting more pages
                    if stop_fetching:
                        # Cancel any remaining futures in this batch
                        for remaining_future, remaining_worker_id, _ in futures_sorted:
                            if remaining_future != future:
                                try:
                                    remaining_future.cancel()
                                except Exception:
                                    pass
                                release_worker(remaining_worker_id)
                        break
                    
                    # Also stop if Page 0 has been processed and we got no filtered executions from it
                    # AND we have no executions collected so far (meaning all were filtered out)
                    if (page_0_processed and page_num == 0 and 
                        not filtered_executions and len(data_collector) == 0):
                        # Page 0 had executions but all were filtered out, and we have nothing collected
                        # This means all executions are before the marker - we can stop
                        stop_fetching = True
                        log_info(
                            f"Page 0 processed: {len(page_executions)} executions found but all filtered out "
                            f"(all before timestamp marker). Stopping pagination."
                        )
                        # Cancel remaining futures
                        for remaining_future, remaining_worker_id, _ in futures_sorted:
                            if remaining_future != future:
                                try:
                                    remaining_future.cancel()
                                except Exception:
                                    pass
                                release_worker(remaining_worker_id)
                        break
                
                # If we didn't get any data or should_stop was set, break the outer loop
                if stop_fetching:
                    log_info("Stopping pagination - no more executions to fetch")
                    break

        policy_executions = data_collector.get_all()
        
        # Log final count by policy type after pagination
        final_exec_type_counts = {}
        for exec in policy_executions:
            final_exec_type_counts[exec.policy_type] = final_exec_type_counts.get(exec.policy_type, 0) + 1
        
        log_info(f"Total executions after pagination: {len(policy_executions)}, breakdown: {final_exec_type_counts}")
        
        # Log all execution IDs for debugging (limit to first 50 to avoid spam)
        if policy_executions:
            all_exec_ids = [exec.execution_id for exec in policy_executions[:50]]
            log_info(f"Execution IDs found (first 50): {all_exec_ids}")
            
            # Check for specific execution ID if provided (for debugging)
            # Check both string and integer formats since API might return either
            target_id_str = "10410555"
            target_id_int = 10410555
            found = False
            for exec in policy_executions:
                if (exec.execution_id == target_id_str or 
                    exec.execution_id == str(target_id_int) or
                    str(exec.execution_id) == target_id_str):
                    found = True
                    log_info(
                        f"✅ Found target execution ID {target_id_str} in fetched executions "
                        f"(stored as: {exec.execution_id}, type: {type(exec.execution_id).__name__})"
                    )
                    break
            
            if not found:
                log_info(f"❌ Target execution ID {target_id_str} NOT found in fetched executions")
                # Log all EQUALITY execution IDs to help debug
                equality_ids = [
                    exec.execution_id for exec in policy_executions 
                    if exec.policy_type == "EQUALITY"
                ]
                log_info(f"All EQUALITY execution IDs found: {equality_ids[:100]}")

        self.trace(
            "fetched_executions_parallel",
            total_executions=len(policy_executions),
            pages_processed=page,
        )

        return policy_executions

    @trace_method("fetch_execution_details_parallel", "execution_metrics_service")
    def _fetch_execution_details_parallel(
        self, policy_executions: list[PolicyExecution], progress: Progress, task_id
    ) -> tuple[list[ExecutionDetail], list[ReconciliationRecord]]:
        """Fetch execution details in parallel.

        Args:
            policy_executions: List of policy executions
            progress: Progress tracker
            task_id: Progress task ID

        Returns:
            Tuple of (list of ExecutionDetail models, list of ReconciliationRecord models)
        """
        if not policy_executions:
            return [], []

        # Create thread-safe data collectors
        data_collector = ThreadSafeDataCollector()
        reconciliation_collector = ThreadSafeDataCollector()

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
        page_0_processed = False  # Track if Page 0 has been processed

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
                    self.timezone,  # Pass timezone
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
                            execution_details, recon_records = future.result(timeout=30)
                            data_collector.extend(execution_details)
                            if recon_records:
                                reconciliation_collector.extend(recon_records)

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
                        self.timezone,  # Pass timezone
                    )
                    futures.append((future, worker_id, execution_index))
                    execution_index += 1

        execution_details = data_collector.get_all()
        reconciliation_records = reconciliation_collector.get_all()

        # Log summary if some executions didn't return details
        if len(execution_details) < len(policy_executions):
            missing_count = len(policy_executions) - len(execution_details)
            # Find which execution IDs are missing
            detail_execution_ids = set()
            for detail in execution_details:
                detail_execution_ids.add(detail.exec_id)
            missing_execution_ids = [
                exec.execution_id for exec in policy_executions 
                if exec.execution_id not in detail_execution_ids
            ]
            log_info(
                f"⚠️  {missing_count} out of {len(policy_executions)} executions "
                f"did not return execution details (may be due to failed API calls, "
                f"incomplete executions, or missing data)"
            )
            if missing_execution_ids:
                log_info(f"Missing execution IDs (first 20): {missing_execution_ids[:20]}")

        self.trace(
            "execution_details_parallel_completed",
            total_details=len(execution_details),
            reconciliation_records=len(reconciliation_records),
            executions_processed=len(policy_executions),
        )

        return execution_details, reconciliation_records

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
