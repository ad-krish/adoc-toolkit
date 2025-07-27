"""Tests for export-metrics command."""

import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pandas as pd
import pytest

from adoc_toolkit.cli.commands.export_metrics_command import (
    ExportMetricsCommand,
    parse_command_args,
    check_output_dependencies,
    generate_filename_from_template,
    preprocess_dataframe_for_format,
    process_metrics_data,
    export_dataframe_to_format,
    get_completion_suggestions,
)
from adoc_toolkit.http import HTTPError, HTTPResponse


class TestExportMetricsCommand:
    """Test cases for ExportMetricsCommand."""

    def setup_method(self):
        """Set up test fixtures."""

        # Mock environment callback for testing
        def mock_env_callback():
            return {
                "name": "test-env",
                "base_url": "https://test.example.com",
                "access_key": "test_access_key",
                "secret_key": "test_secret_key",
            }

        self.command = ExportMetricsCommand(environment_info_callback=mock_env_callback)

    def test_command_properties(self):
        """Test command basic properties."""
        assert self.command.name == "export-metrics"
        assert (
            self.command.description
            == "Export metrics data to CSV, Parquet, or Avro format"
        )
        assert self.command.aliases == ["export", "metrics"]

    def test_help_output(self):
        """Test help output contains expected information."""
        help_text = self.command.get_help()

        assert "export-metrics" in help_text
        assert "--output-type" in help_text
        assert "--output-dir" in help_text
        assert "--output-filename" in help_text
        assert "csv, parquet, avro" in help_text
        assert "%y=year" in help_text

    def test_parse_args_help(self):
        """Test parsing help flag."""
        result = parse_command_args(["--help"])
        assert result["help"] is True

    def test_parse_args_output_type(self):
        """Test parsing output type argument."""
        result = parse_command_args(["--output-type", "parquet"])
        assert result["output_type"] == "parquet"

    def test_parse_args_output_dir(self):
        """Test parsing output directory argument."""
        result = parse_command_args(["--output-dir", "/tmp/reports"])
        assert result["output_dir"] == "/tmp/reports"

    def test_parse_args_output_filename(self):
        """Test parsing output filename argument."""
        result = parse_command_args(["--output-filename", "custom-%y-%m-%d"])
        assert result["output_filename"] == "custom-%y-%m-%d"

    def test_parse_args_multiple(self):
        """Test parsing multiple arguments."""
        result = parse_command_args(
            [
                "--output-type",
                "csv",
                "--output-dir",
                "./data",
                "--output-filename",
                "metrics-%d%m%y",
            ]
        )
        assert result["output_type"] == "csv"
        assert result["output_dir"] == "./data"
        assert result["output_filename"] == "metrics-%d%m%y"

    def test_parse_args_missing_value(self):
        """Test error when argument value is missing."""
        with pytest.raises(ValueError, match="--output-type requires a value"):
            parse_command_args(["--output-type"])

    def test_parse_args_unknown_argument(self):
        """Test error for unknown arguments."""
        with pytest.raises(ValueError, match="Unknown argument"):
            parse_command_args(["--unknown-arg"])

    def test_check_dependencies_csv(self):
        """Test dependency check for CSV format."""
        is_available, error_message = check_output_dependencies("csv")
        assert is_available is True
        assert error_message is None

    def test_check_dependencies_parquet_missing(self):
        """Test dependency check for Parquet when pyarrow is missing."""
        # Skip if pyarrow is actually available
        try:
            import pyarrow  # noqa: F401

            pytest.skip("pyarrow is available, cannot test missing dependency")
        except ImportError:
            pass

        is_available, error_message = check_output_dependencies("parquet")
        assert is_available is False
        assert "pyarrow is required" in error_message

    def test_check_dependencies_avro_missing(self):
        """Test dependency check for Avro when fastavro is missing."""
        # Skip if fastavro is actually available
        try:
            import fastavro  # noqa: F401

            pytest.skip("fastavro is available, cannot test missing dependency")
        except ImportError:
            pass

        is_available, error_message = check_output_dependencies("avro")
        assert is_available is False
        assert "fastavro is required" in error_message

    def test_generate_filename_default(self):
        """Test filename generation with default template."""
        filename = generate_filename_from_template("ad-metrics-%d-%m-%y-%h-%M", "csv")

        assert filename.endswith(".csv")
        assert "ad-metrics-" in filename
        # Should contain numbers for date/time
        assert any(char.isdigit() for char in filename)

    def test_generate_filename_custom(self):
        """Test filename generation with custom template."""
        filename = generate_filename_from_template("data-%y%m%d", "parquet")

        assert filename.endswith(".parquet")
        assert "data-" in filename
        assert any(char.isdigit() for char in filename)

    def test_generate_filename_extensions(self):
        """Test correct extensions for different output types."""
        csv_file = generate_filename_from_template("test", "csv")
        parquet_file = generate_filename_from_template("test", "parquet")
        avro_file = generate_filename_from_template("test", "avro")

        assert csv_file.endswith(".csv")
        assert parquet_file.endswith(".parquet")
        assert avro_file.endswith(".avro")

    def test_generate_filename_with_environment(self):
        """Test filename generation includes environment name suffix."""
        filename = generate_filename_from_template("metrics-%y%m%d", "csv", "production")

        assert filename.endswith("_production.csv")
        assert "metrics-" in filename

    def test_generate_filename_no_environment(self):
        """Test filename generation without environment name."""
        filename = generate_filename_from_template("metrics-%y%m%d", "csv")

        assert filename.endswith(".csv")
        assert "_" not in filename.split(".")[0]  # No environment suffix

    def test_preprocess_for_parquet(self):
        """Test DataFrame preprocessing for Parquet export."""
        # Create test data with problematic values
        test_data = {
            "Rule Name": ["Test Rule 1", "Test Rule 2"],
            "Quality Score": ["95", "N/A"],  # Mix of numeric and N/A
            "Records Processed": ["1000", "N/A"],
            "Execution Date": ["2024-01-01T12:00:00Z", "N/A"],
            "Tags": [{"critical"}, "N/A"],  # Set and string
            "Asset Name": ["Asset 1", "Asset 2"],  # Regular strings
        }
        df = pd.DataFrame(test_data)

        # Preprocess the DataFrame
        processed_df = preprocess_dataframe_for_format(df, "parquet")

        # Check that N/A values are converted to proper nulls
        assert pd.isna(processed_df.loc[1, "Quality Score"])
        assert pd.isna(processed_df.loc[1, "Records Processed"])
        assert pd.isna(processed_df.loc[1, "Execution Date"])

        # Check that numeric columns are properly converted
        assert processed_df["Quality Score"].dtype in ["float64", "Int64"]
        assert processed_df["Records Processed"].dtype in ["float64", "Int64"]

        # Check that datetime columns are properly converted
        assert pd.api.types.is_datetime64_any_dtype(processed_df["Execution Date"])

        # Check that string columns remain strings
        assert processed_df["Asset Name"].dtype == "object"
        assert processed_df["Tags"].dtype == "object"

    def test_preprocess_for_avro(self):
        """Test DataFrame preprocessing for Avro export."""
        # Create test data with problematic values
        test_data = {
            "Rule Name": ["Test Rule 1", "Test Rule 2"],
            "Quality Score": ["95", "N/A"],  # Mix of numeric and N/A
            "Records Processed": ["1000", "N/A"],
            "Execution Date": ["2024-01-01T12:00:00Z", "N/A"],
            "Tags": [{"critical"}, "N/A"],  # Set and string
            "Asset Name": ["Asset 1", "Asset 2"],  # Regular strings
        }
        df = pd.DataFrame(test_data)

        # Preprocess the DataFrame
        processed_df = preprocess_dataframe_for_format(df, "avro")

        # Check that N/A values are converted to None or NaN
        qs_val = processed_df.loc[1, "Quality Score"]
        rp_val = processed_df.loc[1, "Records Processed"]
        assert pd.isna(qs_val) or qs_val is None
        assert pd.isna(rp_val) or rp_val is None
        assert processed_df.loc[1, "Execution Date"] is None

        # Check that numeric columns are properly converted
        assert processed_df.loc[0, "Quality Score"] == 95.0
        assert processed_df.loc[0, "Records Processed"] == 1000.0

        # Check that datetime columns are converted to strings
        assert isinstance(processed_df.loc[0, "Execution Date"], str)
        assert "2024-01-01T" in str(processed_df.loc[0, "Execution Date"])

        # Check that string columns remain strings
        assert processed_df["Asset Name"].dtype == "object"

    def test_display_statistics(self):
        """Test the statistics display functionality."""
        from io import StringIO

        from rich.console import Console

        # Create test data with various metrics
        test_data = [
            {
                "Rule Name": "Test Rule 1",
                "Rule Type": "COMPLETENESS",
                "Execution Status": "SUCCESS",
                "Quality Score": "95",
                "Open Alerts": "2",
                "Asset Type": "TABLE",
                "Source Type": "POSTGRES",
            },
            {
                "Rule Name": "Test Rule 2",
                "Rule Type": "VALIDITY",
                "Execution Status": "FAILED",
                "Quality Score": "75",
                "Open Alerts": "8",
                "Asset Type": "TABLE",
                "Source Type": "MYSQL",
            },
            {
                "Rule Name": "Test Rule 3",
                "Rule Type": "COMPLETENESS",
                "Execution Status": "SUCCESS",
                "Quality Score": "88",
                "Open Alerts": "0",
                "Asset Type": "VIEW",
                "Source Type": "POSTGRES",
            },
        ]
        df = pd.DataFrame(test_data)

        # Capture console output
        string_io = StringIO()
        console = Console(file=string_io, width=80)

        # Call the statistics display method
        self.command._display_statistics(df, console)

        # Get the output
        output = string_io.getvalue()

        # Check that key statistics are included
        assert "Export Summary" in output
        assert "Total Records" in output
        assert "Rule Type Distribution" in output
        assert "Execution Status" in output  # Account for Rich table wrapping
        assert "Quality Score" in output  # Account for Rich table wrapping
        assert "Data Quality Insights" in output

        # Check specific values
        assert "3" in output  # Total records
        assert "COMPLETENESS" in output
        assert "SUCCESS" in output
        assert "FAILED" in output

    def test_get_completions_options(self):
        """Test auto-completion for command options."""
        # Test completion for partial option
        completions = get_completion_suggestions("export-metrics --out", 0)
        assert "--output-type" in completions
        assert "--output-dir" in completions
        assert "--output-filename" in completions

        # Test completion for specific option prefix
        completions = get_completion_suggestions("export-metrics --output-t", 0)
        assert completions == ["--output-type"]

        # Test completion after space
        completions = get_completion_suggestions("export-metrics ", 0)
        expected_options = [
            "--help",
            "--output-type",
            "--output-dir",
            "--output-filename",
        ]
        assert all(opt in completions for opt in expected_options)

    def test_get_completions_output_types(self):
        """Test auto-completion for output type values."""
        # Test completion for output types
        completions = get_completion_suggestions("export-metrics --output-type ", 0)
        assert "csv" in completions
        assert "parquet" in completions
        assert "avro" in completions

        # Test partial completion
        completions = get_completion_suggestions("export-metrics --output-type p", 0)
        assert completions == ["parquet"]

    def test_get_completions_templates(self):
        """Test auto-completion for filename templates."""
        # Test completion for filename templates
        completions = get_completion_suggestions(
            "export-metrics --output-filename ", 0
        )
        assert "ad-metrics-%d-%m-%y-%h-%M" in completions
        assert "metrics-%y%m%d" in completions

        # Test partial completion
        completions = get_completion_suggestions(
            "export-metrics --output-filename me", 0
        )
        assert "metrics-%y%m%d" in completions

    def test_get_completions_used_options(self):
        """Test that used options are not suggested again."""
        completions = get_completion_suggestions(
            "export-metrics --output-type csv --out", 0
        )
        assert "--output-type" not in completions  # Already used
        assert "--output-dir" in completions
        assert "--output-filename" in completions

    def test_process_data_empty(self):
        """Test data processing with empty data."""
        data = {"catalog": {}, "dq_policies": {}, "alerts": {}}
        result = process_metrics_data(data)
        assert result == []

    def test_process_data_basic(self):
        """Test data processing with basic data."""
        data = {
            "catalog": {
                "assets": [
                    {"assetId": "asset1", "name": "Test Asset", "qualityScore": 85}
                ]
            },
            "dq_policies": {
                "rules": [
                    {
                        "rule": {
                            "name": "Test Rule",
                            "id": "rule1",
                            "type": "COMPLETENESS",
                            "backingAssets": [{"tableAssetId": "asset1"}],
                            "tags": [{"name": "critical"}],
                        },
                        "execution": {
                            "executionStatus": "SUCCESS",
                            "finishedAt": "2024-01-01T12:00:00Z",
                        },
                        "executionMetrics": {
                            "qualityScore": 90,
                            "totalRecordsProcessed": 1000,
                        },
                    }
                ]
            },
            "alerts": {"incidents": []},
        }

        result = process_metrics_data(data)

        assert len(result) == 1
        record = result[0]
        assert record["Rule Name"] == "Test Rule"
        assert record["Asset ID"] == "asset1"
        assert record["Asset Name"] == "Test Asset"
        assert record["Quality Score"] == 90

    def test_export_data_csv(self):
        """Test CSV export functionality."""
        with tempfile.TemporaryDirectory() as temp_dir:
            df = pd.DataFrame(
                [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456},
                ]
            )
            output_path = Path(temp_dir) / "test.csv"

            export_dataframe_to_format(df, output_path, "csv")

            assert output_path.exists()

            # Read back and verify
            read_df = pd.read_csv(output_path)
            assert len(read_df) == 2
            assert "column1" in read_df.columns
            assert "column2" in read_df.columns

    def test_export_data_parquet(self):
        """Test Parquet export functionality."""
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            pytest.skip("pyarrow not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            df = pd.DataFrame(
                [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456},
                ]
            )
            output_path = Path(temp_dir) / "test.parquet"

            export_dataframe_to_format(df, output_path, "parquet")

            assert output_path.exists()

            # Read back and verify
            read_df = pd.read_parquet(output_path)
            assert len(read_df) == 2

    def test_export_data_parquet_with_na_values(self):
        """Test Parquet export with N/A values and mixed data types."""
        try:
            import pyarrow  # noqa: F401
        except ImportError:
            pytest.skip("pyarrow not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data with N/A values and mixed types
            df = pd.DataFrame(
                [
                    {
                        "Rule Name": "Test Rule 1",
                        "Quality Score": "95",
                        "Records Processed": "1000",
                        "Execution Date": "2024-01-01T12:00:00Z",
                        "Asset Name": "Asset 1",
                    },
                    {
                        "Rule Name": "Test Rule 2",
                        "Quality Score": "N/A",
                        "Records Processed": "N/A",
                        "Execution Date": "N/A",
                        "Asset Name": "Asset 2",
                    },
                ]
            )
            output_path = Path(temp_dir) / "test_na.parquet"

            # This should not raise an error with the preprocessing
            export_dataframe_to_format(df, output_path, "parquet")

            assert output_path.exists()

            # Read back and verify
            read_df = pd.read_parquet(output_path)

            assert len(read_df) == 2
            assert "Rule Name" in read_df.columns
            assert "Quality Score" in read_df.columns

            # Check that N/A values are properly handled as nulls
            assert pd.isna(read_df.loc[1, "Quality Score"])
            assert pd.isna(read_df.loc[1, "Records Processed"])
            assert pd.isna(read_df.loc[1, "Execution Date"])

    def test_export_data_avro_with_na_values(self):
        """Test Avro export with N/A values and mixed data types."""
        try:
            import fastavro  # noqa: F401
        except ImportError:
            pytest.skip("fastavro not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            # Create test data with N/A values and mixed types
            df = pd.DataFrame(
                [
                    {
                        "Rule Name": "Test Rule 1",
                        "Quality Score": "95",
                        "Records Processed": "1000",
                        "Execution Date": "2024-01-01T12:00:00Z",
                        "Asset Name": "Asset 1",
                    },
                    {
                        "Rule Name": "Test Rule 2",
                        "Quality Score": "N/A",
                        "Records Processed": "N/A",
                        "Execution Date": "N/A",
                        "Asset Name": "Asset 2",
                    },
                ]
            )
            output_path = Path(temp_dir) / "test_na.avro"

            # This should not raise an error with the preprocessing
            export_dataframe_to_format(df, output_path, "avro")

            assert output_path.exists()

            # Read back and verify
            import fastavro

            with open(output_path, "rb") as f:
                reader = fastavro.reader(f)
                records = list(reader)

            assert len(records) == 2
            # Type ignore for avro record access which mypy doesn't understand well
            assert "rule_name" in records[0]  # type: ignore[operator]
            assert "quality_score" in records[0]  # type: ignore[operator]

            # Check that N/A values are properly handled as nulls
            assert records[1]["quality_score"] is None  # type: ignore[call-overload]
            assert records[1]["records_processed"] is None  # type: ignore[call-overload]
            assert records[1]["execution_date"] is None  # type: ignore[call-overload]

    def test_export_data_avro(self):
        """Test Avro export functionality."""
        try:
            import fastavro  # noqa: F401
        except ImportError:
            pytest.skip("fastavro not available")

        with tempfile.TemporaryDirectory() as temp_dir:
            df = pd.DataFrame(
                [
                    {"column1": "value1", "column2": 123},
                    {"column1": "value2", "column2": 456},
                ]
            )
            output_path = Path(temp_dir) / "test.avro"

            export_dataframe_to_format(df, output_path, "avro")

            assert output_path.exists()
            # Note: We don't verify reading back Avro as it requires more complex setup

    @patch("adoc_toolkit.cli.commands.export_metrics_command.ThreadPoolExecutor")
    def test_fetch_all_data_success(self, mock_executor):
        """Test successful data fetching."""
        # Mock HTTP client and responses
        mock_http_client = Mock()

        # Create mock responses
        mock_catalog_response = Mock(spec=HTTPResponse)
        mock_catalog_response.is_success = True
        mock_catalog_response.json.return_value = {"assets": []}

        mock_dq_response = Mock(spec=HTTPResponse)
        mock_dq_response.is_success = True
        mock_dq_response.json.return_value = {"rules": []}

        mock_alerts_response = Mock(spec=HTTPResponse)
        mock_alerts_response.is_success = True
        mock_alerts_response.json.return_value = {"incidents": []}

        # Configure mock client
        mock_http_client.get.side_effect = [
            mock_catalog_response,
            mock_dq_response,
            mock_alerts_response,
        ]

        # Mock ThreadPoolExecutor
        mock_executor_instance = Mock()
        mock_executor.return_value.__enter__ = Mock(return_value=mock_executor_instance)
        mock_executor.return_value.__exit__ = Mock(return_value=None)

        def mock_map(func, items):
            results = []
            for item in items:
                results.append(func(item))
            return results

        mock_executor_instance.map = mock_map

        # Mock progress
        mock_progress = Mock()
        mock_task = Mock()

        result = self.command._fetch_all_data(
            mock_http_client, mock_progress, mock_task
        )

        assert "catalog" in result
        assert "dq_policies" in result
        assert "alerts" in result

    @patch("adoc_toolkit.cli.commands.export_metrics_command.ThreadPoolExecutor")
    def test_fetch_all_data_http_error(self, mock_executor):
        """Test data fetching with HTTP error."""
        # Mock HTTP client
        mock_http_client = Mock()

        # Create mock error response
        mock_response = Mock(spec=HTTPResponse)
        mock_response.is_success = False
        mock_response.status_code = 404

        mock_http_client.get.return_value = mock_response

        # Mock ThreadPoolExecutor
        mock_executor_instance = Mock()
        mock_executor.return_value.__enter__ = Mock(return_value=mock_executor_instance)
        mock_executor.return_value.__exit__ = Mock(return_value=None)

        def mock_map_error(func, items):
            # Call the function which should raise HTTPError
            for item in items:
                func(item)

        mock_executor_instance.map = mock_map_error

        # Mock progress
        mock_progress = Mock()
        mock_task = Mock()

        with pytest.raises(HTTPError):
            self.command._fetch_all_data(mock_http_client, mock_progress, mock_task)

    def test_execute_help_flag(self):
        """Test executing command with help flag."""
        with patch("builtins.print"):
            result = self.command.execute(["--help"])
            assert result is True

    def test_execute_invalid_output_type(self):
        """Test executing command with invalid output type."""
        with patch("rich.console.Console.print") as mock_print:
            result = self.command.execute(["--output-type", "invalid"])
            assert result is True
            mock_print.assert_called_with(
                "Error: output-type must be csv, parquet, or avro", style="red"
            )

    @patch("adoc_toolkit.cli.commands.export_metrics_command.pd.DataFrame")
    @patch("adoc_toolkit.cli.commands.export_metrics_command.ADOCHTTPClient")
    def test_execute_success_csv(self, mock_http_client_class, mock_dataframe):
        """Test successful execution with CSV output."""
        with tempfile.TemporaryDirectory() as temp_dir:
            # Mock HTTP client
            mock_client = Mock()
            mock_http_client_class.return_value = mock_client

            # Mock command methods
            with patch.object(self.command, "_fetch_all_data") as mock_fetch:
                with patch("adoc_toolkit.cli.commands.export_metrics_command.process_metrics_data") as mock_process:
                    with patch("adoc_toolkit.cli.commands.export_metrics_command.export_dataframe_to_format") as mock_export:
                        with patch("adoc_toolkit.cli.commands.export_metrics_command.generate_filename_from_template") as mock_generate_filename:
                            with patch("pathlib.Path.stat") as mock_stat:
                                with patch("pathlib.Path.exists") as mock_exists:
                                    with patch("pathlib.Path.mkdir") as mock_mkdir:
                                        # Configure mocks
                                        mock_fetch.return_value = {
                                            "data": "test",
                                            "_debug_files": [],
                                        }
                                        mock_process.return_value = [{"test": "data"}]

                                        # Mock DataFrame properly
                                        mock_df = Mock()
                                        mock_df.empty = False
                                        mock_df.__len__ = Mock(return_value=1)
                                        mock_df.columns = ["test_column_1", "test_column_2"]
                                        mock_df.head.return_value.to_string.return_value = "test data"
                                        # Ensure the DataFrame constructor returns our mock
                                        mock_dataframe.return_value = mock_df

                                        # Mock filename generation
                                        mock_generate_filename.return_value = "test-metrics.csv"

                                        # Mock file stats for tracing
                                        mock_stat.return_value.st_size = 1024
                                        mock_exists.return_value = True

                                        # Mock Progress to avoid console issues
                                        with patch("adoc_toolkit.cli.commands.export_metrics_command.Progress") as mock_progress:
                                            mock_progress_instance = Mock()
                                            mock_progress.return_value.__enter__.return_value = mock_progress_instance
                                            mock_progress_instance.add_task.return_value = "task_id"
                                            mock_progress_instance.update = Mock()

                                            # Execute command
                                            result = self.command.execute(
                                                [
                                                    "--output-type",
                                                    "csv",
                                                    "--output-dir",
                                                    temp_dir,
                                                    "--output-filename",
                                                    "test-metrics",
                                                ]
                                            )

                                            assert result is True
                                            mock_fetch.assert_called_once()
                                            mock_process.assert_called_once()
                                            mock_export.assert_called_once()

    @patch("adoc_toolkit.cli.commands.export_metrics_command.ADOCHTTPClient")
    def test_execute_http_error(self, mock_http_client_class):
        """Test execution with HTTP error."""
        # Mock HTTP client to raise error
        mock_client = Mock()
        mock_http_client_class.return_value = mock_client

        with patch.object(self.command, "_fetch_all_data") as mock_fetch:
            mock_fetch.side_effect = HTTPError("Test error")

            with patch("rich.console.Console.print") as mock_print:
                result = self.command.execute(["--output-type", "csv"])

                assert result is True
                mock_print.assert_called_with(
                    "Error: HTTP error during data fetch: Test error", style="red"
                )

    def test_execute_empty_data(self):
        """Test execution when no data is retrieved."""
        with patch("adoc_toolkit.cli.commands.export_metrics_command.ADOCHTTPClient"):
            with patch.object(self.command, "_fetch_all_data") as mock_fetch:
                with patch("adoc_toolkit.cli.commands.export_metrics_command.process_metrics_data") as mock_process:
                    with patch(
                        "adoc_toolkit.cli.commands.export_metrics_command.pd.DataFrame"
                    ) as mock_df_class:
                        with patch(
                            "adoc_toolkit.cli.commands.export_metrics_command.Progress"
                        ):
                            # Configure mocks
                            mock_fetch.return_value = {"data": "test"}
                            mock_process.return_value = []

                            mock_df = Mock()
                            mock_df.empty = True
                            mock_df_class.return_value = mock_df

                            # Capture the output - the warning message should be printed
                            result = self.command.execute(["--output-type", "csv"])

                            assert result is True
                            # The warning should be printed to stdout
                            # (captured in pytest output)
