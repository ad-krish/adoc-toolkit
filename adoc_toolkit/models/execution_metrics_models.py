"""Pydantic models for execution metrics data."""

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, field_validator


class PolicyExecution(BaseModel):
    """Model for policy execution data."""

    policy_name: str = Field(description="Name of the policy")
    policy_version: int = Field(description="Version of the policy")
    policy_id: str = Field(description="Unique identifier for the policy")
    policy_type: str = Field(description="Type of policy (DATA_QUALITY, EQUALITY)")
    execution_id: str = Field(description="Unique identifier for the execution")
    execution_status: str = Field(description="Status of the execution")
    result_status: str | None = Field(default=None, description="Result status")
    score: dict[str, Any] | None = Field(
        default=None, description="Quality score data"
    )
    rows: dict[str, Any] | None = Field(default=None, description="Row count data")
    failed_rows: dict[str, Any] | None = Field(
        default=None, description="Failed row data"
    )
    success_rules: dict[str, Any] | None = Field(
        default=None, description="Successful rule counts"
    )
    failure_rules: dict[str, Any] | None = Field(
        default=None, description="Failed rule counts"
    )
    start_timestamp: datetime | None = Field(
        default=None, description="Execution start time"
    )
    start_ts: int | None = Field(
        default=None, description="Start timestamp (milliseconds)"
    )
    end_timestamp: datetime | None = Field(
        default=None, description="Execution end time"
    )
    end_ts: int | None = Field(
        default=None, description="End timestamp (milliseconds)"
    )

    @field_validator("policy_id", "execution_id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator(
        "score", "rows", "failed_rows", "success_rules", "failure_rules", mode="before"
    )
    @classmethod
    def validate_optional_dict_fields(cls, v: Any) -> dict[str, Any] | None:
        """Handle fields that can be either dict or simple values."""
        if v is None:
            return None
        if isinstance(v, dict):
            return v
        # Convert simple values to dict format
        return {"value": v}

    @field_validator("policy_type")
    @classmethod
    def validate_policy_type(cls, v: str) -> str:
        """Validate policy type."""
        valid_types = {
            "DATA_QUALITY",
            "EQUALITY",
            "DATA_DRIFT",
            "PROFILE_ANOMALY",
            "SCHEMA_DRIFT",
            "FRESHNESS",
        }
        if v not in valid_types:
            raise ValueError(f"Policy type must be one of {valid_types}")
        return v


class ExecutionDetail(BaseModel):
    """Model for detailed execution result data."""

    item_id: str = Field(description="Item identifier")
    item_column_name: str | None = Field(default=None, description="Column name")
    left_column: str | None = Field(default=None, description="Left column name (for EQUALITY policies)")
    right_column: str | None = Field(default=None, description="Right column name (for EQUALITY policies)")
    item_ver: int = Field(description="Item version")
    pde_name: str | None = Field(default=None, description="PDE name")
    pde: str | None = Field(default=None, description="PDE label")
    item_measurement_type: str | None = Field(
        default=None, description="Measurement type"
    )
    rule_item_id: str | None = Field(
        default=None, description="Rule item identifier"
    )
    rule_strategy: str | None = Field(
        default=None, description="Rule threshold strategy"
    )
    rule_lower_threshold: float | None = Field(
        default=None, description="Rule lower threshold"
    )
    rule_upper_threshold: float | None = Field(
        default=None, description="Rule upper threshold"
    )
    result: str | None = Field(default=None, description="Execution result")
    result_status: str | None = Field(
        default=None, description="Rule result status (SUCCESSFUL if items.success is true, FAILED otherwise)"
    )
    overall_policy_status: str | None = Field(
        default=None, description="Overall policy status from result.status"
    )
    overall_policy_quality_score: float | None = Field(
        default=None, description="Overall policy quality score from result.qualityScore"
    )
    rows_scanned: int | None = Field(
        default=None, description="Number of rows scanned"
    )
    rows_failed: int | None = Field(
        default=None, description="Number of failed rows"
    )
    exec_id: str = Field(description="Execution identifier")
    start_ts: int | None = Field(default=None, description="Start timestamp")
    end_ts: int | None = Field(default=None, description="End timestamp")
    execution_status: str = Field(description="Execution status")
    anomaly_detected: bool | None = Field(
        default=None, description="Anomaly detected flag from items.anomalyDetected (for FRESHNESS only)"
    )
    threshold_breached: bool | None = Field(
        default=None, description="Threshold breached flag from items.thresholdBreached (for FRESHNESS only)"
    )

    @field_validator("item_id", "exec_id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator("rule_item_id", mode="before")
    @classmethod
    def validate_optional_id_fields(cls, v: Any) -> str | None:
        """Convert integer IDs to strings, handling None values."""
        if v is None:
            return None
        return str(v)


class PolicyDetail(BaseModel):
    """Model for policy detail information."""

    policy_name: str = Field(description="Name of the policy")
    policy_id: str = Field(description="Policy identifier")
    policy_type: str = Field(description="Type of policy")
    id: str = Field(description="Item identifier")
    rule_version: int = Field(description="Rule version")
    column_name: str | None = Field(default=None, description="Column name")
    pde_value: str | None = Field(default=None, description="PDE value")
    table_asset_id: str | None = Field(
        default=None, description="Table asset identifier"
    )
    table_asset_name: str | None = Field(
        default=None, description="Table asset name"
    )
    policy_enabled: bool | None = Field(
        default=None, description="Whether the policy is enabled (from rule.enabled)"
    )
    label_key: str | None = Field(
        default=None, description="Label key from details.items.labels.key"
    )
    label_value: str | None = Field(
        default=None, description="Label value from details.items.labels.value"
    )
    policy_description: str | None = Field(
        default=None, description="Policy description from rule.description"
    )
    rule_description: str | None = Field(
        default=None, description="Rule description from details.items.businessExplanation (for DATA_QUALITY)"
    )
    item_measurement_type: str | None = Field(
        default=None, description="Item measurement type from details.items.metricType (for DATA_DRIFT) or details.items.measurementType (for FRESHNESS)"
    )
    drift_threshold: float | None = Field(
        default=None, description="Drift threshold from details.items.driftThreshold (for DATA_DRIFT)"
    )
    rule_strategy: str | None = Field(
        default=None, description="Rule strategy from details.items.thresholdConfig.strategy (for FRESHNESS)"
    )
    rule_lower_threshold: float | None = Field(
        default=None, description="Lower threshold from details.items.thresholdConfig.lower (for FRESHNESS)"
    )
    rule_upper_threshold: float | None = Field(
        default=None, description="Upper threshold from details.items.thresholdConfig.upper (for FRESHNESS)"
    )

    @field_validator("policy_id", "id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator("table_asset_id", mode="before")
    @classmethod
    def validate_optional_id_fields(cls, v: Any) -> str | None:
        """Convert integer IDs to strings, handling None values."""
        if v is None:
            return None
        return str(v)


class ExecutionMetricsRecord(BaseModel):
    """Model for combined execution metrics record."""

    policy_name: str = Field(description="Policy name")
    policy_id: str = Field(description="Policy identifier")
    rule_version: int = Field(description="Rule version")
    exec_id: str = Field(description="Execution identifier")
    table_asset_name: str | None = Field(
        default=None, description="Table asset name"
    )
    item_column_name: str | None = Field(default=None, description="Column name")
    left_column: str | None = Field(default=None, description="Left column name (for EQUALITY policies)")
    right_column: str | None = Field(default=None, description="Right column name (for EQUALITY policies)")
    pde: str | None = Field(default=None, description="PDE value")
    item_measurement_type: str | None = Field(
        default=None, description="Measurement type"
    )
    rule_strategy: str | None = Field(default=None, description="Rule strategy")
    rule_lower_threshold: float | None = Field(
        default=None, description="Lower threshold"
    )
    rule_upper_threshold: float | None = Field(
        default=None, description="Upper threshold"
    )
    item_id: str = Field(description="Item identifier")
    result: str | None = Field(default=None, description="Result value")
    result_status: str | None = Field(
        default=None, description="Rule result status (SUCCESSFUL if items.success is true, FAILED otherwise)"
    )
    overall_policy_status: str | None = Field(
        default=None, description="Overall policy status from result.status"
    )
    overall_policy_quality_score: float | None = Field(
        default=None, description="Overall policy quality score from result.qualityScore"
    )
    rows_scanned: int | None = Field(default=None, description="Rows scanned")
    rows_failed: int | None = Field(default=None, description="Rows failed")
    startedAt: int | None = Field(default=None, description="Start timestamp (milliseconds)")
    started_at: datetime | None = Field(
        default=None, description="Start date (human-readable)"
    )
    finishedAt: int | None = Field(default=None, description="Finish timestamp (milliseconds)")
    finished_at: datetime | None = Field(
        default=None, description="Finish date (human-readable)"
    )
    execution_date: datetime | None = Field(
        default=None, description="Execution date (deprecated, use finished_at)"
    )
    execution_status: str = Field(description="Execution status")
    policy_type: str = Field(description="Policy type")
    policy_enabled: bool | None = Field(
        default=None, description="Whether the policy is enabled"
    )
    anomaly_detected: bool | None = Field(
        default=None, description="Anomaly detected flag from items.anomalyDetected (for FRESHNESS only)"
    )
    threshold_breached: bool | None = Field(
        default=None, description="Threshold breached flag from items.thresholdBreached (for FRESHNESS only)"
    )
    label_key: str | None = Field(
        default=None, description="Label key from policy details"
    )
    label_value: str | None = Field(
        default=None, description="Label value from policy details"
    )
    policy_description: str | None = Field(
        default=None, description="Policy description from rule.description"
    )
    rule_description: str | None = Field(
        default=None, description="Rule description from details.items.businessExplanation (for DATA_QUALITY)"
    )
    drift_threshold: float | None = Field(
        default=None, description="Drift threshold from details.items.driftThreshold (for DATA_DRIFT)"
    )


class ReconciliationRecord(BaseModel):
    """Model for reconciliation (EQUALITY) specific export record."""

    Policy_Name: str = Field(description="Policy name from execution.ruleName")
    Policy_ID: str = Field(description="Policy ID from execution.ruleId")
    Rule_Version: int = Field(description="Rule version from execution.ruleVersion")
    Execution_ID: str = Field(description="Execution ID from execution.id")
    Left_Column: str | None = Field(default=None, description="Left column name from items.columnMapping.leftColumnName")
    Right_Column: str | None = Field(default=None, description="Right column name from items.columnMapping.rightColumnName")
    Rule_ID: str = Field(description="Rule item ID from items.ruleItemId")
    Recon_Type: str | None = Field(default=None, description="Reconciliation type based on dimension (Equality_Match or Row_Count_Match)")
    Result_Percentage: float | None = Field(default=None, description="Result percentage from items.resultPercent")
    Rows_Scanned: int | None = Field(default=None, description="Rows scanned from result.rows")
    Rows_Failed: int | None = Field(default=None, description="Failed rows from result.failedRows or drift for Row_Count_Match")
    Left_Rows_Scanned: int | str | None = Field(default=None, description="Left rows scanned from result.leftRowsScanned (only for Row_Count_Match)")
    Right_Rows_Scanned: int | str | None = Field(default=None, description="Right rows scanned from result.rightRowsScanned (only for Row_Count_Match)")
    Use_For_Joining: str | None = Field(default=None, description="Use for joining from details.columnMappings.useForJoining")
    Policy_Description: str | None = Field(default=None, description="Policy description from rule.description")
    Rule_Description: str | None = Field(default=None, description="Rule description from details.columnMappings.businessExplanation")
    Left_ASSET_UID: str | None = Field(default=None, description="Left asset UID from rule.leftBackingAsset.tableAssetId")
    Right_ASSET_UID: str | None = Field(default=None, description="Right asset UID from rule.rightBackingAsset.tableAssetId")
    Join_Type: str | None = Field(default=None, description="Join type from details.joinType")
    Started_At_UTC: datetime | None = Field(default=None, description="Start time from execution.startedAt")
    Finished_At_UTC: datetime | None = Field(default=None, description="Finish time from execution.finishedAt")
    Execution_Date_UTC: datetime | None = Field(default=None, description="Execution date from execution.finishedAt")
    Execution_Status: str = Field(description="Execution status from execution.executionStatus")
    Rule_Result_Status: str | None = Field(default=None, description="Rule result status from items[].success")
    Overall_Policy_Status: str | None = Field(default=None, description="Overall policy status from result.status")
    Overall_Policy_Quality_Score: float | None = Field(default=None, description="Overall policy quality score from result.qualityScore")
    Policy_Type: str = Field(description="Policy type from execution.ruleType")
    Policy_Enabled: bool | None = Field(
        default=None, description="Whether the policy is enabled (from rule.enabled)"
    )
    Operation: str | None = Field(
        default=None, description="Operation from details.columnMappings.operation"
    )
    Label_Key: str | None = Field(
        default=None, description="Label key from details.columnMappings.labels.key"
    )
    Label_Value: str | None = Field(
        default=None, description="Label value from details.columnMappings.labels.value"
    )

    @field_validator("Policy_ID", "Execution_ID", "Rule_ID", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)


class LastRunInfo(BaseModel):
    """Model for tracking last run information."""

    last_run_timestamp: int | None = Field(
        default=None, description="Last run timestamp in milliseconds"
    )
    last_run_datetime: datetime | None = Field(
        default=None, description="Last run datetime"
    )
    timezone: str = Field(
        default="UTC", description="Timezone used for last run datetime"
    )
    total_records_processed: int = Field(
        default=0, description="Total records processed in last run"
    )

    @field_validator("last_run_timestamp")
    @classmethod
    def validate_timestamp(cls, v: int | None) -> int | None:
        """Validate timestamp is positive."""
        if v is not None and v < 0:
            raise ValueError("Timestamp must be non-negative")
        return v


class ExecutionMetricsArgs(BaseModel):
    """Model for export-execution-metrics command arguments."""

    output_type: str = Field(default="csv", description="Output format")
    output_dir: str | None = Field(default=None, description="Output directory")
    output_filename: str | None = Field(
        default=None, description="Output filename template"
    )
    backload: str | None = Field(
        default=None,
        description="Backload option for first run (e.g., -30d, 2024-01-15)",
    )
    policy_types: list[str] = Field(
        default=["DATA_QUALITY", "EQUALITY"],
        description="Policy types to export (default: DATA_QUALITY, EQUALITY)",
    )
    page_size: int = Field(
        default=100,
        description="Number of items per page for API calls (default: 100, max: 1000)",
    )
    help: bool = Field(default=False, description="Show help")

    @field_validator("output_type")
    @classmethod
    def validate_output_type(cls, v: str) -> str:
        """Validate output type."""
        valid_types = {"csv", "parquet"}
        if v.lower() not in valid_types:
            raise ValueError(f"Output type must be one of {valid_types}")
        return v.lower()

    @field_validator("policy_types")
    @classmethod
    def validate_policy_types(cls, v: list[str]) -> list[str]:
        """Validate policy types."""
        valid_types = {
            "DATA_QUALITY",
            "EQUALITY",
            "DATA_DRIFT",
            "PROFILE_ANOMALY",
            "SCHEMA_DRIFT",
            "FRESHNESS",
        }
        if not v:
            raise ValueError("At least one policy type must be specified")

        invalid_types = [pt for pt in v if pt.upper() not in valid_types]
        if invalid_types:
            raise ValueError(
                f"Invalid policy types: {invalid_types}. "
                f"Valid types: {sorted(valid_types)}"
            )

        # Convert to uppercase for consistency
        return [pt.upper() for pt in v]

    @field_validator("page_size")
    @classmethod
    def validate_page_size(cls, v: int) -> int:
        """Validate page size."""
        if v <= 0:
            raise ValueError("page_size must be a positive integer")
        if v > 1000:
            raise ValueError("page_size cannot exceed 1000 (server limit)")
        return v
