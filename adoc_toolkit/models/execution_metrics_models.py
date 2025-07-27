"""Pydantic models for execution metrics data."""

from datetime import datetime
from decimal import Decimal
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class PolicyExecution(BaseModel):
    """Model for policy execution data."""

    policy_name: str = Field(description="Name of the policy")
    policy_version: int = Field(description="Version of the policy")
    policy_id: str = Field(description="Unique identifier for the policy")
    policy_type: str = Field(description="Type of policy (DATA_QUALITY, EQUALITY)")
    execution_id: str = Field(description="Unique identifier for the execution")
    execution_status: str = Field(description="Status of the execution")
    result_status: Optional[str] = Field(default=None, description="Result status")
    score: Optional[dict[str, Any]] = Field(
        default=None, description="Quality score data"
    )
    rows: Optional[dict[str, Any]] = Field(default=None, description="Row count data")
    failed_rows: Optional[dict[str, Any]] = Field(
        default=None, description="Failed row data"
    )
    success_rules: Optional[dict[str, Any]] = Field(
        default=None, description="Successful rule counts"
    )
    failure_rules: Optional[dict[str, Any]] = Field(
        default=None, description="Failed rule counts"
    )
    start_timestamp: Optional[datetime] = Field(
        default=None, description="Execution start time"
    )
    start_ts: Optional[int] = Field(
        default=None, description="Start timestamp (milliseconds)"
    )
    end_timestamp: Optional[datetime] = Field(
        default=None, description="Execution end time"
    )
    end_ts: Optional[int] = Field(
        default=None, description="End timestamp (milliseconds)"
    )

    @field_validator("policy_id", "execution_id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator("score", "rows", "failed_rows", "success_rules", "failure_rules", mode="before")
    @classmethod
    def validate_optional_dict_fields(cls, v: Any) -> Optional[dict[str, Any]]:
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
        }
        if v not in valid_types:
            raise ValueError(f"Policy type must be one of {valid_types}")
        return v


class ExecutionDetail(BaseModel):
    """Model for detailed execution result data."""

    item_id: str = Field(description="Item identifier")
    item_column_name: Optional[str] = Field(default=None, description="Column name")
    item_ver: int = Field(description="Item version")
    pde_name: Optional[str] = Field(default=None, description="PDE name")
    pde: Optional[str] = Field(default=None, description="PDE label")
    item_measurement_type: Optional[str] = Field(
        default=None, description="Measurement type"
    )
    rule_item_id: Optional[str] = Field(
        default=None, description="Rule item identifier"
    )
    rule_strategy: Optional[str] = Field(
        default=None, description="Rule threshold strategy"
    )
    rule_lower_threshold: Optional[float] = Field(
        default=None, description="Rule lower threshold"
    )
    rule_upper_threshold: Optional[float] = Field(
        default=None, description="Rule upper threshold"
    )
    result: Optional[str] = Field(default=None, description="Execution result")
    rows_scanned: Optional[int] = Field(
        default=None, description="Number of rows scanned"
    )
    rows_failed: Optional[int] = Field(
        default=None, description="Number of failed rows"
    )
    exec_id: str = Field(description="Execution identifier")
    end_ts: Optional[int] = Field(default=None, description="End timestamp")

    @field_validator("item_id", "exec_id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator("rule_item_id", mode="before")
    @classmethod
    def validate_optional_id_fields(cls, v: Any) -> Optional[str]:
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
    column_name: Optional[str] = Field(default=None, description="Column name")
    pde_value: Optional[str] = Field(default=None, description="PDE value")
    table_asset_id: Optional[str] = Field(
        default=None, description="Table asset identifier"
    )
    table_asset_name: Optional[str] = Field(
        default=None, description="Table asset name"
    )

    @field_validator("policy_id", "id", mode="before")
    @classmethod
    def validate_id_fields(cls, v: Any) -> str:
        """Convert integer IDs to strings."""
        return str(v)

    @field_validator("table_asset_id", mode="before")
    @classmethod
    def validate_optional_id_fields(cls, v: Any) -> Optional[str]:
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
    table_asset_name: Optional[str] = Field(
        default=None, description="Table asset name"
    )
    item_column_name: Optional[str] = Field(default=None, description="Column name")
    pde: Optional[str] = Field(default=None, description="PDE value")
    item_measurement_type: Optional[str] = Field(
        default=None, description="Measurement type"
    )
    rule_strategy: Optional[str] = Field(default=None, description="Rule strategy")
    rule_lower_threshold: Optional[float] = Field(
        default=None, description="Lower threshold"
    )
    rule_upper_threshold: Optional[float] = Field(
        default=None, description="Upper threshold"
    )
    item_id: str = Field(description="Item identifier")
    result: Optional[str] = Field(default=None, description="Result value")
    rows_scanned: Optional[int] = Field(default=None, description="Rows scanned")
    rows_failed: Optional[int] = Field(default=None, description="Rows failed")
    end_ts: Optional[int] = Field(default=None, description="End timestamp")
    execution_date: Optional[datetime] = Field(
        default=None, description="Execution date"
    )
    execution_status: str = Field(description="Execution status")
    policy_type: str = Field(description="Policy type")


class LastRunInfo(BaseModel):
    """Model for tracking last run information."""

    last_run_timestamp: Optional[int] = Field(
        default=None, description="Last run timestamp in milliseconds"
    )
    last_run_datetime: Optional[datetime] = Field(
        default=None, description="Last run datetime"
    )
    total_records_processed: int = Field(
        default=0, description="Total records processed in last run"
    )

    @field_validator("last_run_timestamp")
    @classmethod
    def validate_timestamp(cls, v: Optional[int]) -> Optional[int]:
        """Validate timestamp is positive."""
        if v is not None and v < 0:
            raise ValueError("Timestamp must be non-negative")
        return v


class ExecutionMetricsArgs(BaseModel):
    """Model for export-execution-metrics command arguments."""

    output_type: str = Field(default="csv", description="Output format")
    output_dir: Optional[str] = Field(default=None, description="Output directory")
    output_filename: Optional[str] = Field(
        default=None, description="Output filename template"
    )
    backload: Optional[str] = Field(
        default=None, description="Backload option for first run (e.g., -30d, 2024-01-15)"
    )
    policy_types: list[str] = Field(
        default=["DATA_QUALITY", "EQUALITY"], 
        description="Policy types to export (default: DATA_QUALITY, EQUALITY)"
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
            "SCHEMA_DRIFT"
        }
        if not v:
            raise ValueError("At least one policy type must be specified")
        
        invalid_types = [pt for pt in v if pt.upper() not in valid_types]
        if invalid_types:
            raise ValueError(f"Invalid policy types: {invalid_types}. Valid types: {sorted(valid_types)}")
        
        # Convert to uppercase for consistency
        return [pt.upper() for pt in v]
