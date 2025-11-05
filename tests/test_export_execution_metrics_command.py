"""Tests for export-execution-metrics command."""

import json
import tempfile
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest
from pydantic import ValidationError

from adoc_toolkit.cli.commands.execution_metrics_service import (
    ExecutionMetricsService,
    ThreadSafeDataCollector,
    calculate_failed_rows,
    convert_timestamp_to_datetime,
    fetch_execution_page,
    merge_execution_data,
    process_execution_details_parallel,
    process_policy_details_parallel,
    process_policy_executions,
    safe_get,
)
from adoc_toolkit.cli.commands.export_execution_metrics_command import (
    ExportExecutionMetricsCommand,
    check_execution_metrics_dependencies,
    export_execution_metrics_to_format,
    generate_execution_metrics_filename,
    get_execution_metrics_completion_suggestions,
    parse_backload_option,
    parse_execution_metrics_args,
    preprocess_execution_metrics_dataframe,
)
from adoc_toolkit.models import (
    ExecutionDetail,
    ExecutionMetricsArgs,
    ExecutionMetricsRecord,
    LastRunInfo,
    PolicyDetail,
    PolicyExecution,
)


class TestPureFunctions:
    """Test pure functions used in export-execution-metrics command."""

    def test_parse_execution_metrics_args_valid(self):
        """Test parsing valid arguments."""
        args = ["--output-type", "parquet", "--output-dir", "/tmp", "--help"]
        result = parse_execution_metrics_args(args)

        expected = {"output_type": "parquet", "output_dir": "/tmp", "help": True}
        assert result == expected

    def test_parse_execution_metrics_args_empty(self):
        """Test parsing empty arguments."""
        result = parse_execution_metrics_args([])
        assert result == {}

    def test_parse_execution_metrics_args_invalid(self):
        """Test parsing invalid arguments raises error."""
        with pytest.raises(ValueError, match="Unknown argument"):
            parse_execution_metrics_args(["--invalid-arg"])

    def test_parse_execution_metrics_args_missing_value(self):
        """Test parsing arguments with missing values raises error."""
        with pytest.raises(ValueError, match="requires a value"):
            parse_execution_metrics_args(["--output-type"])

    def test_generate_execution_metrics_filename_basic(self):
        """Test filename generation with basic template."""
        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2023, 12, 25, 14, 30)

            result = generate_execution_metrics_filename(
                "execution-metrics-%y-%m-%d", "csv"
            )
            assert result == "execution-metrics-2023-12-25.csv"

    def test_generate_execution_metrics_filename_with_env(self):
        """Test filename generation with environment name."""
        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.datetime"
        ) as mock_dt:
            mock_dt.now.return_value = datetime(2023, 12, 25, 14, 30)

            result = generate_execution_metrics_filename(
                "exec-%y%m%d", "parquet", "prod"
            )
            assert result == "exec-20231225_prod.parquet"

    def test_check_execution_metrics_dependencies_csv(self):
        """Test dependency check for CSV format."""
        is_available, error = check_execution_metrics_dependencies("csv")
        assert is_available is True
        assert error is None

    def test_check_execution_metrics_dependencies_parquet_available(self):
        """Test dependency check for Parquet when pyarrow is available."""
        with patch.dict("sys.modules", {"pyarrow": Mock()}):
            is_available, error = check_execution_metrics_dependencies("parquet")
            assert is_available is True
            assert error is None

    def test_check_execution_metrics_dependencies_parquet_missing(self):
        """Test dependency check for Parquet when pyarrow is missing."""
        with patch.dict("sys.modules", {"pyarrow": None}):
            is_available, error = check_execution_metrics_dependencies("parquet")
            assert is_available is False
            assert "pyarrow is required" in error

    def test_preprocess_execution_metrics_dataframe_csv(self):
        """Test DataFrame preprocessing for CSV format."""
        df = pd.DataFrame(
            {
                "rule_version": ["1", "2"],
                "rows_scanned": ["100", "200"],
                "execution_date": ["2023-12-25T10:00:00", "2023-12-25T11:00:00"],
                "policy_name": ["Policy1", "Policy2"],
            }
        )

        result = preprocess_execution_metrics_dataframe(df, "csv")

        assert result["rule_version"].dtype in [pd.Int64Dtype(), "int64"]
        assert result["rows_scanned"].dtype in [pd.Int64Dtype(), "int64"]
        # After our change, execution_date becomes object type due to "null" strings
        assert result["policy_name"].dtype == object

    def test_preprocess_execution_metrics_dataframe_with_null_dates(self):
        """Test DataFrame preprocessing with None/NaT datetime values."""
        df = pd.DataFrame(
            {
                "rule_version": ["1", "2", "3"],
                "rows_scanned": ["100", "200", "300"],
                "execution_date (UTC)": ["2023-12-25T10:00:00", None, "invalid"],
                "policy_name": ["Policy1", "Policy2", "Policy3"],
            }
        )

        result = preprocess_execution_metrics_dataframe(df, "csv")

        # Check that None and invalid dates become "null"
        assert result["execution_date (UTC)"].iloc[1] == "null"
        assert result["execution_date (UTC)"].iloc[2] == "null"
        # Valid date should remain
        assert result["execution_date (UTC)"].iloc[0] != "null"

    def test_export_execution_metrics_to_format_csv(self):
        """Test exporting DataFrame to CSV format."""
        df = pd.DataFrame(
            {
                "policy_name": ["Policy1", "Policy2"],
                "rule_version": [1, 2],
                "rows_scanned": [100, 200],
            }
        )

        with tempfile.NamedTemporaryFile(suffix=".csv", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            export_execution_metrics_to_format(df, tmp_path, "csv")
            assert tmp_path.exists()

            # Verify content
            exported_df = pd.read_csv(tmp_path)
            assert len(exported_df) == 2
            assert "policy_name" in exported_df.columns
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_get_execution_metrics_completion_suggestions_command_options(self):
        """Test completion suggestions for command options."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics ", 25
        )

        expected_options = [
            "--help",
            "--output-type",
            "--output-dir",
            "--output-filename",
        ]
        assert all(opt in suggestions for opt in expected_options)

    def test_get_execution_metrics_completion_suggestions_output_type(self):
        """Test completion suggestions for output type values."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --output-type c", 35
        )

        assert "csv" in suggestions
        assert len([s for s in suggestions if s.startswith("c")]) >= 1

    def test_get_execution_metrics_completion_suggestions_filename_templates(self):
        """Test completion suggestions for filename templates."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --output-filename exec", 45
        )

        assert any("execution-metrics" in s for s in suggestions)

    def test_get_execution_metrics_completion_suggestions_backload_options(self):
        """Test completion suggestions for backload options."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --backload -", 33
        )

        assert "-10d" in suggestions
        assert "-30d" in suggestions
        assert "-60d" in suggestions

    def test_get_execution_metrics_completion_suggestions_policy_types_single(self):
        """Test completion suggestions for policy types."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --policy-types D", 37
        )

        assert "DATA_QUALITY" in suggestions
        assert "DATA_DRIFT" in suggestions
        # Should not include types that don't start with D
        assert "EQUALITY" not in suggestions

    def test_get_execution_metrics_completion_suggestions_policy_types_comma_separated(
        self,
    ):
        """Test completion suggestions for comma-separated policy types."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --policy-types DATA_QUALITY,E", 50
        )

        # Should complete with prefix for comma-separated values
        assert "DATA_QUALITY,EQUALITY" in suggestions
        # Should not include types that don't start with E after comma
        assert "DATA_QUALITY,DATA_DRIFT" not in suggestions

    def test_get_execution_metrics_completion_suggestions_policy_types_all_options(
        self,
    ):
        """Test completion suggestions include all policy types."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --policy-types ", 38
        )

        expected_types = [
            "DATA_QUALITY",
            "EQUALITY",
            "DATA_DRIFT",
            "PROFILE_ANOMALY",
            "SCHEMA_DRIFT",
        ]
        for policy_type in expected_types:
            assert policy_type in suggestions

    def test_get_execution_metrics_completion_suggestions_includes_policy_types_option(
        self,
    ):
        """Test completion suggestions include --policy-types option."""
        suggestions = get_execution_metrics_completion_suggestions(
            "export-execution-metrics --policy", 30
        )

        assert "--policy-types" in suggestions

    def test_parse_backload_option_relative_hours_valid(self):
        """Test parsing relative hour format."""
        from zoneinfo import ZoneInfo
        
        result = parse_backload_option("-12h", "UTC")
        expected = datetime.now(ZoneInfo("UTC")) - timedelta(hours=12)

        # Allow small time difference due to execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_backload_option_relative_hours_invalid_too_many(self):
        """Test parsing relative hour format with too many hours."""
        with pytest.raises(ValueError, match="cannot be more than 1440 hours"):
            parse_backload_option("-1441h")

    def test_parse_backload_option_relative_hours_zero(self):
        """Test parsing relative hour format with zero hours."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_backload_option("-0h")

    def test_parse_backload_option_relative_days_valid(self):
        """Test parsing relative day format."""
        from zoneinfo import ZoneInfo
        
        result = parse_backload_option("-30d", "UTC")
        expected = datetime.now(ZoneInfo("UTC")) - timedelta(days=30)

        # Allow small time difference due to execution time
        assert abs((result - expected).total_seconds()) < 1

    def test_parse_backload_option_relative_days_invalid_too_many(self):
        """Test parsing relative day format with too many days."""
        with pytest.raises(ValueError, match="cannot be more than 60 days"):
            parse_backload_option("-61d")

    def test_parse_backload_option_relative_days_zero(self):
        """Test parsing relative day format with zero days."""
        with pytest.raises(ValueError, match="must be positive"):
            parse_backload_option("-0d")

    def test_parse_backload_option_iso_date_valid(self):
        """Test parsing ISO date format."""
        from zoneinfo import ZoneInfo
        
        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.get_current_datetime"
        ) as mock_get_current:
            mock_get_current.return_value = datetime(2024, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

            result = parse_backload_option("2024-01-15", "UTC")
            expected = datetime(2024, 1, 15, 0, 0, 0, tzinfo=ZoneInfo("UTC"))
            assert result == expected

    def test_parse_backload_option_iso_datetime_valid(self):
        """Test parsing ISO datetime format."""
        from zoneinfo import ZoneInfo
        
        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.get_current_datetime"
        ) as mock_get_current:
            mock_get_current.return_value = datetime(2024, 2, 15, 10, 0, 0, tzinfo=ZoneInfo("UTC"))

            result = parse_backload_option("2024-01-15T10:30:00", "UTC")
            expected = datetime(2024, 1, 15, 10, 30, 0, tzinfo=ZoneInfo("UTC"))
            assert result == expected

    def test_parse_backload_option_date_too_old(self):
        """Test parsing date that's too old."""
        # Use a date that's clearly more than 60 days ago
        very_old_date = "2020-01-01"
        with pytest.raises(ValueError, match="more than 60 days ago"):
            parse_backload_option(very_old_date)

    def test_parse_backload_option_future_date(self):
        """Test parsing future date."""
        # Use a date that's clearly in the future
        future_date = "2030-12-31"
        with pytest.raises(ValueError, match="cannot be in the future"):
            parse_backload_option(future_date)

    def test_parse_backload_option_invalid_format(self):
        """Test parsing invalid format."""
        with pytest.raises(ValueError, match="Invalid backload format"):
            parse_backload_option("invalid-format")

    def test_parse_backload_option_empty_string(self):
        """Test parsing empty string."""
        with pytest.raises(ValueError, match="cannot be empty"):
            parse_backload_option("")

    def test_parse_execution_metrics_args_with_backload(self):
        """Test parsing arguments with backload option."""
        args = ["--backload", "-30d", "--output-type", "csv"]
        result = parse_execution_metrics_args(args)

        expected = {"backload": "-30d", "output_type": "csv"}
        assert result == expected

    def test_parse_execution_metrics_args_with_policy_types_single(self):
        """Test parsing arguments with single policy type."""
        args = ["--policy-types", "DATA_QUALITY"]
        result = parse_execution_metrics_args(args)

        expected = {"policy_types": ["DATA_QUALITY"]}
        assert result == expected

    def test_parse_execution_metrics_args_with_policy_types_multiple(self):
        """Test parsing arguments with multiple policy types."""
        args = ["--policy-types", "DATA_QUALITY,EQUALITY,DATA_DRIFT"]
        result = parse_execution_metrics_args(args)

        expected = {"policy_types": ["DATA_QUALITY", "EQUALITY", "DATA_DRIFT"]}
        assert result == expected

    def test_parse_execution_metrics_args_with_policy_types_whitespace(self):
        """Test parsing arguments with policy types containing whitespace."""
        args = ["--policy-types", " DATA_QUALITY , EQUALITY , DATA_DRIFT "]
        result = parse_execution_metrics_args(args)

        expected = {"policy_types": ["DATA_QUALITY", "EQUALITY", "DATA_DRIFT"]}
        assert result == expected

    def test_parse_execution_metrics_args_policy_types_empty_value(self):
        """Test parsing arguments with empty policy types value."""
        with pytest.raises(ValueError, match="requires at least one policy type"):
            parse_execution_metrics_args(["--policy-types", ""])

    def test_parse_execution_metrics_args_policy_types_empty_after_split(self):
        """
        Test parsing arguments with policy types that become empty after
        splitting.
        """
        with pytest.raises(ValueError, match="requires at least one policy type"):
            parse_execution_metrics_args(["--policy-types", " , , "])

    def test_parse_execution_metrics_args_policy_types_missing_value(self):
        """Test parsing arguments with policy types missing value."""
        with pytest.raises(ValueError, match="--policy-types requires a value"):
            parse_execution_metrics_args(["--policy-types"])

    def test_parse_execution_metrics_args_combined_with_policy_types(self):
        """Test parsing arguments with policy types combined with other options."""
        args = [
            "--policy-types",
            "DATA_QUALITY,DATA_DRIFT",
            "--output-type",
            "parquet",
            "--backload",
            "-7d",
        ]
        result = parse_execution_metrics_args(args)

        expected = {
            "policy_types": ["DATA_QUALITY", "DATA_DRIFT"],
            "output_type": "parquet",
            "backload": "-7d",
        }
        assert result == expected


class TestServiceUtilities:
    """Test service utility functions."""

    def test_safe_get_existing_key(self):
        """Test safe_get with existing key."""
        data = {"key": "value", "nested": {"inner": "data"}}
        assert safe_get(data, "key") == "value"
        assert safe_get(data, "nested") == {"inner": "data"}

    def test_safe_get_missing_key(self):
        """Test safe_get with missing key."""
        data = {"key": "value"}
        assert safe_get(data, "missing") is None
        assert safe_get(data, "missing", "default") == "default"

    def test_safe_get_none_data(self):
        """Test safe_get with None data."""
        assert safe_get(None, "key") is None
        assert safe_get(None, "key", "default") == "default"

    def test_convert_timestamp_to_datetime_valid(self):
        """Test timestamp conversion with valid timestamp."""
        timestamp = 1703505600000  # 2023-12-25 10:00:00 UTC in milliseconds
        result = convert_timestamp_to_datetime(timestamp)

        assert isinstance(result, datetime)
        assert result.year == 2023
        assert result.month == 12
        assert result.day == 25

    def test_convert_timestamp_to_datetime_none(self):
        """Test timestamp conversion with None."""
        result = convert_timestamp_to_datetime(None)
        assert result is None

    def test_convert_timestamp_to_datetime_zero(self):
        """Test timestamp conversion with zero (Unix epoch)."""
        # Zero should return None, not 1970-01-01
        result = convert_timestamp_to_datetime(0)
        assert result is None

    def test_convert_timestamp_to_datetime_negative(self):
        """Test timestamp conversion with negative timestamp."""
        result = convert_timestamp_to_datetime(-1000)
        assert result is None

    def test_convert_timestamp_to_datetime_string_iso(self):
        """Test that ISO string timestamps are converted correctly."""
        # Test ISO format with Z suffix
        result = convert_timestamp_to_datetime("2024-01-01T12:00:00Z", "UTC")
        assert result is not None
        assert result.year == 2024
        assert result.month == 1
        assert result.day == 1
        assert result.hour == 12
        
        # Test ISO format with timezone
        result2 = convert_timestamp_to_datetime("2024-01-01T12:00:00+00:00", "UTC")
        assert result2 is not None
        assert result2.year == 2024

    def test_convert_timestamp_to_datetime_string_invalid(self):
        """Test that invalid string timestamps return None."""
        result = convert_timestamp_to_datetime("invalid-date", "UTC")
        assert result is None
        
        result2 = convert_timestamp_to_datetime("", "UTC")
        assert result2 is None

    def test_convert_timestamp_to_datetime_invalid(self):
        """Test timestamp conversion with invalid timestamp."""
        # Use a very large timestamp that would cause overflow
        result = convert_timestamp_to_datetime(9999999999999999)
        assert result is None

    def test_calculate_failed_rows_valid(self):
        """Test failed rows calculation with valid inputs."""
        result = calculate_failed_rows(1000, "0.85")
        assert result == 150  # (1 - 0.85) * 1000

    def test_calculate_failed_rows_none_inputs(self):
        """Test failed rows calculation with None inputs."""
        assert calculate_failed_rows(None, "0.85") == 0
        assert calculate_failed_rows(1000, None) == 0
        assert calculate_failed_rows(None, None) == 0

    def test_calculate_failed_rows_invalid_inputs(self):
        """Test failed rows calculation with invalid inputs."""
        assert calculate_failed_rows(1000, "invalid") == 0
        assert calculate_failed_rows("invalid", "0.85") == 0

    def test_process_policy_executions_valid_data(self):
        """Test processing policy executions with valid data."""
        executions_data = {
            "executions": [
                {
                    "execution": {
                        "ruleName": "Test Policy",
                        "ruleVersion": 1,
                        "ruleId": "policy-123",
                        "ruleType": "DATA_QUALITY",
                        "id": "exec-456",
                        "executionStatus": "SUCCESSFUL",
                        "startedAt": 1703505600000,
                        "finishedAt": 1703505700000,
                    },
                    "result": {"qualityScore": {"value": 85.5}},
                }
            ]
        }

        result = process_policy_executions(executions_data, 0)

        assert len(result) == 1
        assert isinstance(result[0], PolicyExecution)
        assert result[0].policy_name == "Test Policy"
        assert result[0].policy_type == "DATA_QUALITY"
        assert result[0].execution_status == "SUCCESSFUL"

    def test_process_policy_executions_filtered_by_timestamp(self):
        """Test processing policy executions filtered by timestamp."""
        executions_data = {
            "executions": [
                {
                    "execution": {
                        "ruleName": "Old Policy",
                        "ruleType": "DATA_QUALITY",
                        "startedAt": 1000000000000,  # Old timestamp
                    }
                },
                {
                    "execution": {
                        "ruleName": "New Policy",
                        "ruleType": "DATA_QUALITY",
                        "startedAt": 2000000000000,  # New timestamp
                    }
                },
            ]
        }

        # Filter out executions before timestamp 1500000000000
        result = process_policy_executions(executions_data, 1500000000000)

        assert len(result) == 1
        assert result[0].policy_name == "New Policy"

    def test_process_policy_executions_filtered_by_type(self):
        """Test processing policy executions filtered by type."""
        executions_data = {
            "executions": [
                {
                    "execution": {
                        "ruleName": "DQ Policy",
                        "ruleType": "DATA_QUALITY",
                        "startedAt": 1703505600000,
                    }
                },
                {
                    "execution": {
                        "ruleName": "Other Policy",
                        "ruleType": "SCHEMA_DRIFT",  # Not included in default types
                        "startedAt": 1703505600000,
                    }
                },
            ]
        }

        # Test with default policy types (all supported types) - both should be included
        result = process_policy_executions(executions_data, 0)
        assert len(result) == 2
        policy_names = [exec.policy_name for exec in result]
        assert "DQ Policy" in policy_names
        assert "Other Policy" in policy_names

        # Test with specific policy types including SCHEMA_DRIFT
        result = process_policy_executions(
            executions_data, 0, ["DATA_QUALITY", "SCHEMA_DRIFT"]
        )
        assert len(result) == 2
        policy_names = [exec.policy_name for exec in result]
        assert "DQ Policy" in policy_names
        assert "Other Policy" in policy_names

    def test_process_policy_executions_with_policy_types_parameter(self):
        """Test processing policy executions with policy types parameter."""
        executions_data = {
            "executions": [
                {
                    "execution": {
                        "ruleName": "DQ Policy",
                        "ruleType": "DATA_QUALITY",
                        "startedAt": 1703505600000,
                    }
                },
                {
                    "execution": {
                        "ruleName": "Equality Policy",
                        "ruleType": "EQUALITY",
                        "startedAt": 1703505600000,
                    }
                },
                {
                    "execution": {
                        "ruleName": "Drift Policy",
                        "ruleType": "DATA_DRIFT",
                        "startedAt": 1703505600000,
                    }
                },
            ]
        }

        # Test with only DATA_QUALITY
        result = process_policy_executions(executions_data, 0, ["DATA_QUALITY"])
        assert len(result) == 1
        assert result[0].policy_name == "DQ Policy"

        # Test with DATA_QUALITY and EQUALITY
        result = process_policy_executions(
            executions_data, 0, ["DATA_QUALITY", "EQUALITY"]
        )
        assert len(result) == 2
        policy_names = [exec.policy_name for exec in result]
        assert "DQ Policy" in policy_names
        assert "Equality Policy" in policy_names

        # Test with all supported types
        result = process_policy_executions(
            executions_data, 0, ["DATA_QUALITY", "EQUALITY", "DATA_DRIFT"]
        )
        assert len(result) == 3
        policy_names = [exec.policy_name for exec in result]
        assert "DQ Policy" in policy_names
        assert "Equality Policy" in policy_names
        assert "Drift Policy" in policy_names


class TestPydanticModels:
    """Test Pydantic models for execution metrics."""

    def test_execution_metrics_args_valid(self):
        """Test ExecutionMetricsArgs with valid data."""
        args = ExecutionMetricsArgs(
            output_type="csv",
            output_dir="/tmp/test",
            output_filename="test-metrics",
            help=False,
        )

        assert args.output_type == "csv"
        assert args.output_dir == "/tmp/test"
        assert args.output_filename == "test-metrics"
        assert args.help is False

    def test_execution_metrics_args_defaults(self):
        """Test ExecutionMetricsArgs with default values."""
        args = ExecutionMetricsArgs()

        assert args.output_type == "csv"
        assert args.output_dir is None
        assert args.output_filename is None
        assert args.help is False

    def test_execution_metrics_args_invalid_output_type(self):
        """Test ExecutionMetricsArgs with invalid output type."""
        with pytest.raises(ValidationError):
            ExecutionMetricsArgs(output_type="invalid")

    def test_execution_metrics_args_valid_policy_types(self):
        """Test ExecutionMetricsArgs with valid policy types."""
        args = ExecutionMetricsArgs(
            policy_types=["DATA_QUALITY", "EQUALITY", "DATA_DRIFT"]
        )

        assert args.policy_types == ["DATA_QUALITY", "EQUALITY", "DATA_DRIFT"]

    def test_execution_metrics_args_policy_types_case_insensitive(self):
        """Test ExecutionMetricsArgs with case insensitive policy types."""
        args = ExecutionMetricsArgs(policy_types=["data_quality", "equality"])

        # Should be converted to uppercase
        assert args.policy_types == ["DATA_QUALITY", "EQUALITY"]

    def test_execution_metrics_args_policy_types_default(self):
        """Test ExecutionMetricsArgs with default policy types."""
        args = ExecutionMetricsArgs()

        assert args.policy_types == ["DATA_QUALITY", "EQUALITY"]

    def test_execution_metrics_args_invalid_policy_type(self):
        """Test ExecutionMetricsArgs with invalid policy type."""
        with pytest.raises(ValidationError, match="Invalid policy types"):
            ExecutionMetricsArgs(policy_types=["INVALID_TYPE"])

    def test_execution_metrics_args_empty_policy_types(self):
        """Test ExecutionMetricsArgs with empty policy types list."""
        with pytest.raises(
            ValidationError, match="At least one policy type must be specified"
        ):
            ExecutionMetricsArgs(policy_types=[])

    def test_execution_metrics_args_mixed_valid_invalid_policy_types(self):
        """Test ExecutionMetricsArgs with mix of valid and invalid policy types."""
        with pytest.raises(ValidationError, match="Invalid policy types"):
            ExecutionMetricsArgs(policy_types=["DATA_QUALITY", "INVALID", "EQUALITY"])

    def test_last_run_info_valid(self):
        """Test LastRunInfo with valid data."""
        info = LastRunInfo(
            last_run_timestamp=1703505600000,
            last_run_datetime=datetime(2023, 12, 25, 10, 0, 0),
            total_records_processed=150,
        )

        assert info.last_run_timestamp == 1703505600000
        assert info.last_run_datetime.year == 2023
        assert info.total_records_processed == 150

    def test_last_run_info_defaults(self):
        """Test LastRunInfo with default values."""
        info = LastRunInfo()

        assert info.last_run_timestamp is None
        assert info.last_run_datetime is None
        assert info.total_records_processed == 0

    def test_last_run_info_invalid_timestamp(self):
        """Test LastRunInfo with invalid timestamp."""
        with pytest.raises(ValidationError):
            LastRunInfo(last_run_timestamp=-1)

    def test_policy_execution_valid(self):
        """Test PolicyExecution with valid data."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            execution_id="exec-456",
            execution_status="SUCCESSFUL",
        )

        assert execution.policy_name == "Test Policy"
        assert execution.policy_type == "DATA_QUALITY"
        assert execution.execution_status == "SUCCESSFUL"

    def test_policy_execution_integer_ids(self):
        """Test PolicyExecution with integer IDs (should be converted to strings)."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id=70381,  # Integer ID
            policy_type="DATA_QUALITY",
            execution_id=5805918,  # Integer ID
            execution_status="SUCCESSFUL",
        )

        assert execution.policy_id == "70381"
        assert execution.execution_id == "5805918"

    def test_policy_execution_simple_values_as_dicts(self):
        """Test PolicyExecution with simple values for dict fields."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            execution_id="exec-456",
            execution_status="SUCCESSFUL",
            score=100.0,  # Simple float value
            rows=6890,  # Simple int value
            failed_rows=0,  # Simple int value
            success_rules=4,  # Simple int value
            failure_rules=0,  # Simple int value
        )

        assert execution.score == {"value": 100.0}
        assert execution.rows == {"value": 6890}
        assert execution.failed_rows == {"value": 0}
        assert execution.success_rules == {"value": 4}
        assert execution.failure_rules == {"value": 0}

    def test_policy_execution_invalid_type(self):
        """Test PolicyExecution with invalid policy type."""
        with pytest.raises(ValidationError):
            PolicyExecution(
                policy_name="Test Policy",
                policy_version=1,
                policy_id="policy-123",
                policy_type="INVALID_TYPE",
                execution_id="exec-456",
                execution_status="SUCCESSFUL",
            )

    def test_execution_metrics_record_valid(self):
        """Test ExecutionMetricsRecord with valid data."""
        record = ExecutionMetricsRecord(
            policy_name="Test Policy",
            policy_id="policy-123",
            rule_version=1,
            exec_id="exec-456",
            item_id="item-789",
            execution_status="SUCCESSFUL",
            policy_type="DATA_QUALITY",
        )

        assert record.policy_name == "Test Policy"
        assert record.policy_id == "policy-123"
        assert record.execution_status == "SUCCESSFUL"
        assert record.policy_type == "DATA_QUALITY"

    def test_execution_detail_integer_ids(self):
        """Test ExecutionDetail with integer IDs (should be converted to strings)."""
        detail = ExecutionDetail(
            item_id=238228,  # Integer ID
            exec_id=5805917,  # Integer ID
            rule_item_id=238228,  # Integer ID (optional)
            item_ver=1,
            execution_status="SUCCESSFUL",
        )

        assert detail.item_id == "238228"
        assert detail.exec_id == "5805917"
        assert detail.rule_item_id == "238228"

    def test_execution_detail_none_optional_id(self):
        """Test ExecutionDetail with None for optional ID field."""
        detail = ExecutionDetail(
            item_id="item-123",
            exec_id="exec-456",
            rule_item_id=None,  # None value for optional field
            item_ver=1,
            execution_status="SUCCESSFUL",
        )

        assert detail.item_id == "item-123"
        assert detail.exec_id == "exec-456"
        assert detail.rule_item_id is None

    def test_policy_detail_integer_ids(self):
        """Test PolicyDetail with integer IDs (should be converted to strings)."""
        detail = PolicyDetail(
            policy_name="Test Policy",
            policy_id=70381,  # Integer ID
            policy_type="DATA_QUALITY",
            id=238228,  # Integer ID
            rule_version=1,
            table_asset_id=12345,  # Integer ID (optional)
        )

        assert detail.policy_id == "70381"
        assert detail.policy_type == "DATA_QUALITY"
        assert detail.id == "238228"
        assert detail.table_asset_id == "12345"

    def test_policy_detail_none_optional_id(self):
        """Test PolicyDetail with None for optional ID field."""
        detail = PolicyDetail(
            policy_name="Test Policy",
            policy_id="policy-123",
            policy_type="EQUALITY",
            id="item-456",
            rule_version=1,
            table_asset_id=None,  # None value for optional field
        )

        assert detail.policy_id == "policy-123"
        assert detail.policy_type == "EQUALITY"
        assert detail.id == "item-456"
        assert detail.table_asset_id is None

    def test_policy_detail_different_policy_types(self):
        """Test PolicyDetail with different policy types."""
        # Test DATA_QUALITY
        detail_dq = PolicyDetail(
            policy_name="DQ Policy",
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            id="item-456",
            rule_version=1,
        )
        assert detail_dq.policy_type == "DATA_QUALITY"

        # Test EQUALITY
        detail_eq = PolicyDetail(
            policy_name="Equality Policy",
            policy_id="policy-456",
            policy_type="EQUALITY",
            id="item-789",
            rule_version=1,
        )
        assert detail_eq.policy_type == "EQUALITY"

        # Test DATA_DRIFT
        detail_drift = PolicyDetail(
            policy_name="Drift Policy",
            policy_id="policy-789",
            policy_type="DATA_DRIFT",
            id="item-012",
            rule_version=1,
        )
        assert detail_drift.policy_type == "DATA_DRIFT"


class TestThreadSafeDataCollector:
    """Test ThreadSafeDataCollector class."""

    def test_thread_safe_data_collector_init(self):
        """Test ThreadSafeDataCollector initialization."""
        collector = ThreadSafeDataCollector()
        assert collector.get_all() == []

    def test_thread_safe_data_collector_add(self):
        """Test adding items to ThreadSafeDataCollector."""
        collector = ThreadSafeDataCollector()
        collector.add("item1")
        collector.add("item2")

        result = collector.get_all()
        assert len(result) == 2
        assert "item1" in result
        assert "item2" in result

    def test_thread_safe_data_collector_extend(self):
        """Test extending ThreadSafeDataCollector with multiple items."""
        collector = ThreadSafeDataCollector()
        collector.extend(["item1", "item2", "item3"])

        result = collector.get_all()
        assert len(result) == 3
        assert "item1" in result
        assert "item2" in result
        assert "item3" in result

    def test_thread_safe_data_collector_clear(self):
        """Test clearing ThreadSafeDataCollector."""
        collector = ThreadSafeDataCollector()
        collector.add("item1")
        collector.add("item2")

        assert len(collector.get_all()) == 2

        collector.clear()
        assert len(collector.get_all()) == 0

    def test_thread_safe_data_collector_get_all_returns_copy(self):
        """Test that get_all returns a copy of the data."""
        collector = ThreadSafeDataCollector()
        collector.add("item1")

        result1 = collector.get_all()
        result2 = collector.get_all()

        # Modifying one result shouldn't affect the other
        result1.append("item2")
        assert len(result1) == 2
        assert len(result2) == 1
        assert len(collector.get_all()) == 1


class TestParallelProcessingFunctions:
    """Test parallel processing functions."""

    def test_fetch_execution_page_success(self):
        """Test successful execution page fetching."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "executions": [
                {
                    "execution": {
                        "ruleName": "Test Policy",
                        "ruleVersion": 1,
                        "ruleId": "policy-123",
                        "ruleType": "DATA_QUALITY",
                        "id": "exec-456",
                        "executionStatus": "SUCCESSFUL",
                        "startedAt": 1703505600000,
                    },
                    "result": {"qualityScore": {"value": 85.5}},
                }
            ]
        }
        mock_client.get.return_value = mock_response

        mock_progress = Mock()
        mock_task_id = "test_task"

        page, executions, should_stop = fetch_execution_page(
            0, 100, ["DATA_QUALITY"], mock_client, mock_progress, mock_task_id
        )

        assert page == 0
        assert len(executions) == 1
        assert should_stop is False
        assert executions[0].policy_name == "Test Policy"

    def test_fetch_execution_page_no_data(self):
        """Test execution page fetching with no data."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {"executions": []}
        mock_client.get.return_value = mock_response

        mock_progress = Mock()
        mock_task_id = "test_task"

        page, executions, should_stop = fetch_execution_page(
            0, 100, ["DATA_QUALITY"], mock_client, mock_progress, mock_task_id
        )

        assert page == 0
        assert len(executions) == 0
        assert should_stop is True

    def test_fetch_execution_page_http_error(self):
        """Test execution page fetching with HTTP error."""
        mock_client = Mock()
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 500
        mock_client.get.return_value = mock_response

        mock_progress = Mock()
        mock_task_id = "test_task"

        page, executions, should_stop = fetch_execution_page(
            0, 100, ["DATA_QUALITY"], mock_client, mock_progress, mock_task_id
        )

        assert page == 0
        assert len(executions) == 0
        assert should_stop is False

    def test_process_execution_details_parallel_success(self):
        """Test successful parallel execution details processing."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            execution_id="exec-456",
            execution_status="SUCCESSFUL",
            end_ts=1703505700000,
        )

        mock_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "items": [
                {
                    "item": {
                        "id": "item-123",
                        "columnName": "test_column",
                        "ruleVersion": 1,
                    },
                    "rowsScanned": 1000,
                    "result": "0.95",
                    "thresholdConfig": {
                        "strategy": "ABSOLUTE",
                        "lower": 0.8,
                        "upper": 1.0,
                    },
                }
            ]
        }
        mock_client.get.return_value = mock_response

        mock_progress = Mock()
        mock_task_id = "test_task"

        result = process_execution_details_parallel(
            execution, mock_client, mock_progress, mock_task_id
        )

        assert len(result) == 1
        assert result[0].item_id == "item-123"
        assert result[0].item_column_name == "test_column"

    def test_process_execution_details_parallel_unsuccessful_execution(self):
        """Test parallel execution details processing for unsuccessful execution."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            execution_id="exec-456",
            execution_status="ERRORED",  # Not successful
            end_ts=1703505700000,
        )

        mock_client = Mock()
        mock_progress = Mock()
        mock_task_id = "test_task"

        result = process_execution_details_parallel(
            execution, mock_client, mock_progress, mock_task_id
        )

        assert len(result) == 0  # Should return empty list for unsuccessful execution

    def test_process_policy_details_parallel_success(self):
        """Test successful parallel policy details processing."""
        execution = PolicyExecution(
            policy_name="Test Policy",
            policy_version=1,
            policy_id="policy-123",
            policy_type="DATA_QUALITY",
            execution_id="exec-456",
            execution_status="SUCCESSFUL",
        )

        mock_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "rule": {"backingAsset": {"tableAssetId": "asset-123"}},
            "details": {
                "items": [
                    {
                        "id": "item-123",
                        "ruleVersion": 1,
                        "columnName": "test_column",
                        "labels": [{"key": "PDE", "value": "test_pde"}],
                    }
                ]
            },
        }
        mock_client.get.return_value = mock_response

        mock_progress = Mock()
        mock_task_id = "test_task"

        result = process_policy_details_parallel(
            execution, mock_client, mock_progress, mock_task_id
        )

        assert len(result) == 1
        assert result[0].id == "item-123"
        assert result[0].policy_type == "DATA_QUALITY"
        assert result[0].column_name == "test_column"


class TestMergeExecutionData:
    """Test merge_execution_data function."""

    def test_merge_execution_data_basic(self):
        """Test basic merging of execution details with policy details."""
        execution_details = [
            ExecutionDetail(
                item_id="item-123",
                exec_id="exec-456",
                item_ver=1,
                result="0.95",
                rows_scanned=1000,
                rows_failed=50,
                end_ts=1703505600000,
                execution_status="SUCCESSFUL",
            )
        ]

        policy_details = [
            PolicyDetail(
                policy_name="Test Policy",
                policy_id="policy-123",
                policy_type="DATA_QUALITY",
                id="item-123",
                rule_version=1,
                table_asset_name="test_table",
            )
        ]

        result = merge_execution_data(execution_details, policy_details)

        assert len(result) == 1
        record = result[0]
        assert record.policy_name == "Test Policy"
        assert record.policy_id == "policy-123"
        assert (
            record.policy_type == "DATA_QUALITY"
        )  # Should use policy_type from PolicyDetail
        assert record.exec_id == "exec-456"
        assert record.table_asset_name == "test_table"
        assert record.execution_status == "SUCCESSFUL"

    def test_merge_execution_data_different_policy_types(self):
        """Test merging with different policy types."""
        execution_details = [
            ExecutionDetail(
                item_id="item-123",
                exec_id="exec-456",
                item_ver=1,
                result="0.95",
                rows_scanned=1000,
                rows_failed=50,
                end_ts=1703505600000,
                execution_status="SUCCESSFUL",
            ),
            ExecutionDetail(
                item_id="item-456",
                exec_id="exec-789",
                item_ver=1,
                result="0.98",
                rows_scanned=500,
                rows_failed=10,
                end_ts=1703505700000,
                execution_status="SUCCESSFUL",
            ),
        ]

        policy_details = [
            PolicyDetail(
                policy_name="DQ Policy",
                policy_id="policy-123",
                policy_type="DATA_QUALITY",
                id="item-123",
                rule_version=1,
                table_asset_name="dq_table",
            ),
            PolicyDetail(
                policy_name="Equality Policy",
                policy_id="policy-456",
                policy_type="EQUALITY",
                id="item-456",
                rule_version=1,
                table_asset_name="equality_table",
            ),
        ]

        result = merge_execution_data(execution_details, policy_details)

        assert len(result) == 2

        # Check first record (DATA_QUALITY)
        record1 = result[0]
        assert record1.policy_type == "DATA_QUALITY"
        assert record1.policy_name == "DQ Policy"

        # Check second record (EQUALITY)
        record2 = result[1]
        assert record2.policy_type == "EQUALITY"
        assert record2.policy_name == "Equality Policy"

    def test_merge_execution_data_no_matching_policy_detail(self):
        """Test merging when no matching policy detail is found."""
        execution_details = [
            ExecutionDetail(
                item_id="item-123",
                exec_id="exec-456",
                item_ver=1,
                result="0.95",
                rows_scanned=1000,
                rows_failed=50,
                end_ts=1703505600000,
                execution_status="SUCCESSFUL",
            )
        ]

        policy_details = [
            PolicyDetail(
                policy_name="Different Policy",
                policy_id="policy-456",
                policy_type="DATA_QUALITY",
                id="item-456",  # Different ID
                rule_version=1,
                table_asset_name="different_table",
            )
        ]

        result = merge_execution_data(execution_details, policy_details)

        # Should not create any records when no matching policy detail is found
        assert len(result) == 0

    def test_merge_execution_data_all_policy_types(self):
        """Test merging with all supported policy types."""
        execution_details = [
            ExecutionDetail(
                item_id=f"item-{i}",
                exec_id=f"exec-{i}",
                item_ver=1,
                result="0.95",
                rows_scanned=1000,
                rows_failed=50,
                end_ts=1703505600000,
                execution_status="SUCCESSFUL",
            )
            for i in range(1, 6)
        ]

        policy_types = [
            "DATA_QUALITY",
            "EQUALITY",
            "DATA_DRIFT",
            "PROFILE_ANOMALY",
            "SCHEMA_DRIFT",
        ]
        policy_details = [
            PolicyDetail(
                policy_name=f"Policy {i}",
                policy_id=f"policy-{i}",
                policy_type=policy_types[i - 1],
                id=f"item-{i}",
                rule_version=1,
                table_asset_name=f"table_{i}",
            )
            for i in range(1, 6)
        ]

        result = merge_execution_data(execution_details, policy_details)

        assert len(result) == 5

        # Check that all policy types are correctly set
        result_policy_types = [record.policy_type for record in result]
        assert set(result_policy_types) == set(policy_types)


class TestExecutionMetricsService:
    """Test ExecutionMetricsService class."""

    def test_init(self):
        """Test ExecutionMetricsService initialization."""
        mock_client = Mock()
        service = ExecutionMetricsService(mock_client)

        assert service.http_client == mock_client
        assert service.trace_prefix == "execution_metrics_service"

    def test_load_last_run_info_file_not_exists(self):
        """Test loading last run info when file doesn't exist."""
        service = ExecutionMetricsService(Mock())

        with tempfile.TemporaryDirectory() as tmpdir:
            tracking_file = Path(tmpdir) / "nonexistent.json"
            result = service.load_last_run_info(tracking_file)

            assert isinstance(result, LastRunInfo)
            assert (
                result.last_run_timestamp is not None
            )  # Should be 30 days ago timestamp
            assert (
                result.last_run_datetime is not None
            )  # Should be 30 days ago datetime
            assert result.total_records_processed == 0

    def test_load_last_run_info_valid_file(self):
        """Test loading last run info from valid file."""
        service = ExecutionMetricsService(Mock())

        test_data = {
            "last_run_timestamp": 1703505600000,
            "last_run_datetime": "2023-12-25T10:00:00",
            "total_records_processed": 150,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            result = service.load_last_run_info(tmp_path)

            assert result.last_run_timestamp == 1703505600000
            assert result.last_run_datetime.year == 2023
            assert result.total_records_processed == 150
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_load_last_run_info_invalid_file(self):
        """Test loading last run info from invalid file."""
        service = ExecutionMetricsService(Mock())

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            tmp.write("invalid json")
            tmp_path = Path(tmp.name)

        try:
            result = service.load_last_run_info(tmp_path)

            # Should return 30 days ago timestamp on error
            assert isinstance(result, LastRunInfo)
            assert (
                result.last_run_timestamp is not None
            )  # Should be 30 days ago timestamp
            assert (
                result.last_run_datetime is not None
            )  # Should be 30 days ago datetime
            assert result.total_records_processed == 0
        finally:
            tmp_path.unlink(missing_ok=True)

    def test_save_last_run_info(self):
        """Test saving last run info to file."""
        service = ExecutionMetricsService(Mock())

        last_run_info = LastRunInfo(
            last_run_timestamp=1703505600000,
            last_run_datetime=datetime(2023, 12, 25, 10, 0, 0),
            total_records_processed=150,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            tracking_file = Path(tmpdir) / "tracking.json"
            service.save_last_run_info(tracking_file, last_run_info)

            assert tracking_file.exists()

            # Verify content
            with open(tracking_file) as f:
                data = json.load(f)

            assert data["last_run_timestamp"] == 1703505600000
            assert data["last_run_datetime"] == "2023-12-25T10:00:00"
            assert data["total_records_processed"] == 150

    def test_load_last_run_info_with_backload_datetime(self):
        """Test loading last run info with backload datetime for first run."""
        service = ExecutionMetricsService(Mock())

        backload_datetime = datetime(2024, 1, 1, 12, 0, 0)

        with tempfile.TemporaryDirectory() as tmpdir:
            tracking_file = Path(tmpdir) / "nonexistent.json"
            result = service.load_last_run_info(tracking_file, backload_datetime)

            assert isinstance(result, LastRunInfo)
            assert result.last_run_datetime == backload_datetime
            assert result.last_run_timestamp == int(
                backload_datetime.timestamp() * 1000
            )
            assert result.total_records_processed == 0

    def test_load_last_run_info_backload_overrides_existing_file(self):
        """Test that backload always overrides tracking file when provided."""
        service = ExecutionMetricsService(Mock())

        backload_datetime = datetime(2024, 1, 1, 12, 0, 0)

        test_data = {
            "last_run_timestamp": 1703505600000,
            "last_run_datetime": "2023-12-25T10:00:00",
            "total_records_processed": 150,
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as tmp:
            json.dump(test_data, tmp)
            tmp_path = Path(tmp.name)

        try:
            # backload_datetime should always override tracking file
            result = service.load_last_run_info(tmp_path, backload_datetime)

            # Should use backload datetime, not data from file
            assert result.last_run_datetime == backload_datetime
            assert result.last_run_timestamp == int(
                backload_datetime.timestamp() * 1000
            )
            assert result.total_records_processed == 0  # Reset to 0 for backload
        finally:
            tmp_path.unlink(missing_ok=True)

    @patch(
        "adoc_toolkit.cli.commands.execution_metrics_service.process_execution_details"
    )
    @patch("adoc_toolkit.cli.commands.execution_metrics_service.process_policy_details")
    @patch("adoc_toolkit.cli.commands.execution_metrics_service.merge_execution_data")
    def test_fetch_execution_metrics_with_policy_types(
        self, mock_merge, mock_policy_details, mock_exec_details
    ):
        """Test fetch_execution_metrics with different policy types."""
        # Mock the service methods
        mock_exec_details.return_value = [
            ExecutionDetail(
                item_id="item-123",
                exec_id="exec-456",
                item_ver=1,
                result="0.95",
                rows_scanned=1000,
                rows_failed=50,
                end_ts=1703505600000,
                execution_status="SUCCESSFUL",
            )
        ]
        mock_policy_details.return_value = [
            PolicyDetail(
                policy_name="Test Policy",
                policy_id="policy-123",
                policy_type="DATA_QUALITY",
                id="item-123",
                rule_version=1,
                table_asset_name="test_table",
            )
        ]
        mock_merge.return_value = [
            ExecutionMetricsRecord(
                policy_name="Test Policy",
                policy_id="policy-123",
                rule_version=1,
                exec_id="exec-456",
                item_id="item-123",
                execution_status="SUCCESSFUL",
                policy_type="DATA_QUALITY",
            )
        ]

        # Mock HTTP client
        mock_client = Mock()
        service = ExecutionMetricsService(mock_client)

        # Mock progress
        mock_progress = Mock()
        mock_task = Mock()
        mock_progress.add_task.return_value = mock_task

        # Mock the _fetch_policy_executions method to return test data
        with patch.object(service, "_fetch_policy_executions") as mock_fetch:
            mock_fetch.return_value = [
                PolicyExecution(
                    policy_name="Test Policy",
                    policy_version=1,
                    policy_id="policy-123",
                    policy_type="DATA_QUALITY",
                    execution_id="exec-456",
                    execution_status="SUCCESSFUL",
                )
            ]

            # Test with specific policy types
            result = service.fetch_execution_metrics(
                start_ts_marker=0,
                progress=mock_progress,
                policy_types=["DATA_QUALITY", "EQUALITY"],
            )

            # Verify that _fetch_policy_executions was called with the correct
            # policy types
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            assert call_args[0][3] == [
                "DATA_QUALITY",
                "EQUALITY",
            ]  # policy_types

            assert len(result) == 1
            assert result[0].policy_type == "DATA_QUALITY"

    def test_fetch_execution_metrics_default_policy_types(self):
        """Test fetch_execution_metrics with default policy types."""
        # Mock HTTP client
        mock_client = Mock()
        service = ExecutionMetricsService(mock_client)

        # Mock progress
        mock_progress = Mock()
        mock_task = Mock()
        mock_progress.add_task.return_value = mock_task

        # Mock the _fetch_policy_executions method
        with patch.object(service, "_fetch_policy_executions") as mock_fetch:
            mock_fetch.return_value = []

            # Test without specifying policy types (should use defaults)
            result = service.fetch_execution_metrics(
                start_ts_marker=0, progress=mock_progress
            )

            # Verify that _fetch_policy_executions was called with default policy types
            mock_fetch.assert_called_once()
            call_args = mock_fetch.call_args
            assert call_args[0][3] == [
                "DATA_QUALITY",
                "EQUALITY",
            ]  # default policy types

            assert result == []


class TestExportExecutionMetricsCommand:
    """Test ExportExecutionMetricsCommand class."""

    def test_init(self):
        """Test command initialization."""
        callback = Mock()
        command = ExportExecutionMetricsCommand(callback)

        assert command.environment_info_callback == callback
        assert command.trace_prefix == "export_execution_metrics"

    def test_properties(self):
        """Test command properties."""
        command = ExportExecutionMetricsCommand()

        assert command.name == "export-execution-metrics"
        assert "execution metrics" in command.description.lower()
        assert "exec-metrics" in command.aliases
        assert "execution-metrics" in command.aliases

    def test_get_help(self):
        """Test help text generation."""
        command = ExportExecutionMetricsCommand()
        help_text = command.get_help()

        assert "export-execution-metrics" in help_text
        assert "--output-type" in help_text
        assert "--output-dir" in help_text
        assert "--output-filename" in help_text
        assert "CSV" in help_text
        assert "Parquet" in help_text

    def test_get_completions(self):
        """Test completion suggestions."""
        command = ExportExecutionMetricsCommand()
        completions = command.get_completions("export-execution-metrics ", 25)

        assert "--help" in completions
        assert "--output-type" in completions

    def test_execute_help(self):
        """Test command execution with --help."""
        command = ExportExecutionMetricsCommand()

        with patch("builtins.print"):
            result = command.execute(["--help"])

            assert result is True  # Should continue
            # Help should be printed (captured by Console, but we can verify
            # execute completes)

    def test_execute_invalid_args(self):
        """Test command execution with invalid arguments."""
        command = ExportExecutionMetricsCommand()

        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.Console"
        ) as mock_console:
            result = command.execute(["--invalid-arg"])

            assert result is True  # Should continue
            mock_console.return_value.print.assert_called()

    def test_execute_invalid_output_type(self):
        """Test command execution with invalid output type."""
        command = ExportExecutionMetricsCommand()

        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.Console"
        ) as mock_console:
            result = command.execute(["--output-type", "invalid"])

            assert result is True  # Should continue
            mock_console.return_value.print.assert_called()

    @patch(
        "adoc_toolkit.cli.commands.export_execution_metrics_command.check_execution_metrics_dependencies"
    )
    def test_execute_missing_dependencies(self, mock_check_deps):
        """Test command execution with missing dependencies."""
        mock_check_deps.return_value = (False, "Missing dependency error")
        command = ExportExecutionMetricsCommand()

        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.Console"
        ) as mock_console:
            result = command.execute(["--output-type", "parquet"])

            assert result is True  # Should continue
            mock_console.return_value.print.assert_called()

    def test_get_environment_info_with_callback(self):
        """Test getting environment info with callback."""
        callback = Mock(
            return_value={"name": "test-env", "base_url": "https://test.com"}
        )
        command = ExportExecutionMetricsCommand(callback)

        result = command._get_environment_info()

        assert result == {"name": "test-env", "base_url": "https://test.com"}
        callback.assert_called_once()

    def test_get_environment_info_without_callback(self):
        """Test getting environment info without callback."""
        command = ExportExecutionMetricsCommand()

        result = command._get_environment_info()

        assert result == {}

    def test_execute_no_environment_set(self):
        """Test command execution when no environment is set."""
        # Mock environment callback to return empty environment
        callback = Mock(return_value={})  # No environment set
        command = ExportExecutionMetricsCommand(callback)

        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.Console"
        ) as mock_console:
            result = command.execute([])

            assert result is True  # Should return True to continue interactive session

            # Should print error message about no environment
            mock_console.return_value.print.assert_called()
            call_args = mock_console.return_value.print.call_args_list
            error_printed = any(
                "No environment selected" in str(call[0][0]) for call in call_args
            )
            assert error_printed, f"Expected environment error message in: {call_args}"

    def test_execute_environment_without_name(self):
        """Test command execution when environment info has no environment name."""
        # Mock environment callback to return info without environment name
        callback = Mock(
            return_value={"base_url": "https://test.com"}
        )  # Missing environment
        command = ExportExecutionMetricsCommand(callback)

        with patch(
            "adoc_toolkit.cli.commands.export_execution_metrics_command.Console"
        ) as mock_console:
            result = command.execute([])

            assert result is True  # Should return True to continue interactive session

            # Should print error message about no environment
            mock_console.return_value.print.assert_called()
            call_args = mock_console.return_value.print.call_args_list
            error_printed = any(
                "No environment selected" in str(call[0][0]) for call in call_args
            )
            assert error_printed, f"Expected environment error message in: {call_args}"


if __name__ == "__main__":
    pytest.main([__file__])
