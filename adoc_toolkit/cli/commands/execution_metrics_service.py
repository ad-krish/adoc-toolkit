"""Service for handling execution metrics data fetching and processing."""

import json
import decimal
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Optional

import pandas as pd
from rich.progress import Progress

from ...http import ADOCHTTPClient, HTTPError
from ...logs import log_error, log_info
from ...models import (
    ExecutionDetail,
    ExecutionMetricsRecord,
    LastRunInfo,
    PolicyDetail,
    PolicyExecution,
)
from ...tracing import TraceableMixin, trace_method


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


def convert_timestamp_to_datetime(timestamp: Optional[int]) -> Optional[datetime]:
    """Convert millisecond timestamp to datetime.

    Args:
        timestamp: Timestamp in milliseconds

    Returns:
        Datetime object or None
    """
    if timestamp is None:
        return None
    try:
        return datetime.fromtimestamp(timestamp / 1000)
    except (ValueError, OSError):
        return None


def calculate_failed_rows(rows_scanned: Optional[int], result: Optional[str]) -> int:
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


def process_policy_executions(
    executions_data: dict[str, Any], start_ts_marker: int
) -> list[PolicyExecution]:
    """Process policy executions data into PolicyExecution models.

    Args:
        executions_data: Raw execution data from API
        start_ts_marker: Timestamp marker for incremental processing

    Returns:
        List of PolicyExecution models
    """
    policy_executions = []

    for execution in safe_get(executions_data, "executions", []):
        ex = safe_get(execution, "execution", {})
        start_ts = safe_get(ex, "startedAt")

        # Skip if timestamp is before marker (incremental processing)
        if start_ts is not None and start_ts <= start_ts_marker:
            continue

        policy_type = safe_get(ex, "ruleType")
        if policy_type in ("DATA_QUALITY", "EQUALITY"):
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
                start_timestamp=convert_timestamp_to_datetime(start_ts),
                start_ts=start_ts,
                end_timestamp=convert_timestamp_to_datetime(safe_get(ex, "finishedAt")),
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
    """Process execution details for DQ policies.

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
        if (
            execution.execution_status == "SUCCESSFUL"
            and execution.policy_type == "DATA_QUALITY"
        ):
            try:
                progress.update(
                    task_id,
                    description=f"Processing DQ execution {processed_count + 1}...",
                )

                endpoint = f"/catalog-server/api/rules/data-quality/executions/{execution.execution_id}"
                response = http_client.get(endpoint)

                if not response.is_success:
                    log_error(
                        f"Failed to fetch execution details for {execution.execution_id}"
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
                        end_ts=execution.end_ts,
                    )
                    execution_details.append(execution_detail)

            except Exception as e:
                log_error(f"Error processing execution {execution.execution_id}: {e}")
                continue

        processed_count += 1
        if processed_count % 25 == 0:
            progress.update(
                task_id, description=f"Processed {processed_count} DQ executions..."
            )

    return execution_details


def fetch_asset_name(asset_id: str, http_client: ADOCHTTPClient) -> Optional[str]:
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
    """Process policy details for DQ policies.

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
        if execution.policy_type == "DATA_QUALITY":
            try:
                progress.update(
                    task_id,
                    description=f"Processing policy details {processed_count + 1}...",
                )

                endpoint = f"/catalog-server/api/rules/data-quality/{execution.policy_id}?version={execution.policy_version}"
                response = http_client.get(endpoint)

                if not response.is_success:
                    log_error(
                        f"Failed to fetch policy details for {execution.policy_id}"
                    )
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
                        id=safe_get(item, "id", ""),
                        rule_version=safe_get(item, "ruleVersion", 1),
                        column_name=safe_get(item, "columnName"),
                        pde_value=pde_value,
                        table_asset_id=table_asset_id,
                        table_asset_name=table_asset_name,
                    )
                    policy_details.append(policy_detail)

            except Exception as e:
                log_error(
                    f"Error processing policy details for {execution.policy_id}: {e}"
                )
                continue

        processed_count += 1
        if processed_count % 10 == 0:
            progress.update(
                task_id, description=f"Processed {processed_count} policy details..."
            )

    return policy_details


def merge_execution_data(
    execution_details: list[ExecutionDetail], policy_details: list[PolicyDetail]
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
                end_ts=exec_detail.end_ts,
                execution_date=convert_timestamp_to_datetime(exec_detail.end_ts),
                execution_status="SUCCESSFUL",  # Only successful executions are processed
                policy_type="DATA_QUALITY",  # Only DQ policies are processed
            )
            merged_records.append(record)

    return merged_records


class ExecutionMetricsService(TraceableMixin):
    """Service for fetching and processing execution metrics data."""

    def __init__(self, http_client: ADOCHTTPClient):
        """Initialize ExecutionMetricsService.

        Args:
            http_client: HTTP client for API interactions
        """
        self.http_client = http_client

    @property
    def trace_prefix(self) -> str | None:
        """Get the trace prefix for this service."""
        return "execution_metrics_service"

    @trace_method("load_last_run_info", "execution_metrics_service")
    def load_last_run_info(
        self, tracking_file: Path, backload_datetime: Optional[datetime] = None
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
            log_info(
                f"First run detected. Defaulting to 30 days ago: {start_datetime}"
            )
            return LastRunInfo(
                last_run_timestamp=start_timestamp,
                last_run_datetime=start_datetime,
                total_records_processed=0,
            )

        # Load from tracking file
        try:
            with open(tracking_file, "r", encoding="utf-8") as f:
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

            data = {
                "last_run_timestamp": last_run_info.last_run_timestamp,
                "last_run_datetime": last_run_info.last_run_datetime.isoformat()
                if last_run_info.last_run_datetime
                else None,
                "total_records_processed": last_run_info.total_records_processed,
            }

            with open(tracking_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

            log_info(f"Saved last run info to {tracking_file}")
        except OSError as e:
            log_error(f"Error saving last run info: {e}")

    @trace_method("fetch_execution_metrics", "execution_metrics_service")
    def fetch_execution_metrics(
        self, start_ts_marker: int, progress: Progress
    ) -> list[ExecutionMetricsRecord]:
        """Fetch and process execution metrics data.

        Args:
            start_ts_marker: Timestamp marker for incremental processing
            progress: Progress tracker

        Returns:
            List of ExecutionMetricsRecord models
        """
        # Step 1: Fetch policy executions
        task1 = progress.add_task("Fetching policy executions...", total=None)
        self.trace("fetching_policy_executions", start_ts_marker=start_ts_marker)

        try:
            policy_executions = self._fetch_policy_executions(
                start_ts_marker, progress, task1
            )
            progress.update(
                task1,
                description=f"Found {len(policy_executions)} executions",
                completed=True,
            )

            if not policy_executions:
                log_info("No new policy executions found")
                return []

            # Step 2: Fetch execution details
            task2 = progress.add_task("Fetching execution details...", total=None)
            execution_details = process_execution_details(
                policy_executions, self.http_client, progress, task2
            )
            progress.update(
                task2,
                description=f"Processed {len(execution_details)} execution details",
                completed=True,
            )

            # Step 3: Fetch policy details
            task3 = progress.add_task("Fetching policy details...", total=None)
            policy_details = process_policy_details(
                policy_executions, self.http_client, progress, task3
            )
            progress.update(
                task3,
                description=f"Processed {len(policy_details)} policy details",
                completed=True,
            )

            # Step 4: Merge data
            task4 = progress.add_task("Merging execution data...", total=None)
            merged_records = merge_execution_data(execution_details, policy_details)
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
        self, start_ts_marker: int, progress: Progress, task_id
    ) -> list[PolicyExecution]:
        """Fetch policy executions from API with pagination.

        Args:
            start_ts_marker: Timestamp marker for incremental processing
            progress: Progress tracker
            task_id: Progress task ID

        Returns:
            List of PolicyExecution models
        """
        policy_executions = []
        page = 0
        exec_count = 100
        stop_loop = False

        while not stop_loop:
            progress.update(
                task_id, description=f"Fetching executions page {page + 1}..."
            )

            endpoint = (
                f"/catalog-server/api/rules/executions"
                f"?page={page}&size={exec_count}&sortBy=execution.startedAt:DESC"
                "&executionStatus=SUCCESSFUL,ERRORED,ABORTED,WARNING"
                "&ruleType=EQUALITY,DATA_QUALITY,DATA_DRIFT,PROFILE_ANOMALY,SCHEMA_DRIFT"
            )

            try:
                response = self.http_client.get(endpoint)
                if not response.is_success:
                    raise HTTPError(
                        f"Failed to fetch executions page {page}: HTTP {response.status_code}"
                    )

                exec_data = response.json()
                executions = safe_get(exec_data, "executions", [])

                if not executions:
                    break

                page_executions = process_policy_executions(exec_data, start_ts_marker)

                # Check if we've reached the timestamp marker
                for execution in executions:
                    ex = safe_get(execution, "execution", {})
                    start_ts = safe_get(ex, "startedAt")
                    if start_ts is not None and start_ts <= start_ts_marker:
                        stop_loop = True
                        break

                policy_executions.extend(page_executions)
                page += 1

                self.trace(
                    "fetched_executions_page",
                    page=page,
                    executions_on_page=len(executions),
                    processed_executions=len(page_executions),
                )

            except Exception as e:
                log_error(f"Error fetching executions page {page}: {e}")
                break

        return policy_executions
