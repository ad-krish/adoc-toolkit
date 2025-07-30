"""Tests for pipeline-summary command functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from adoc_toolkit.models.pipeline_models import (
    PipelineSummary,
    PipelineSummaryData,
    PipelineSummaryMeta,
    PipelineSummaryResponse,
    PipelineSummaryResponseMeta,
    PIPELINE_SUMMARY_COLUMNS,
)
from adoc_toolkit.cli.commands.show.pipeline_summary import PipelineSummaryHandler


class TestPipelineSummaryModels:
    """Test pipeline summary models."""

    def test_pipeline_summary_model(self):
        """Test PipelineSummary model creation with nested structure."""
        # Create the nested structure
        meta = PipelineSummaryMeta(owner="testuser")
        pipeline_data = PipelineSummaryData(
            id="pipeline-123",
            name="Test Pipeline",
            meta=meta,
            source_type="SNOWFLAKE",
            total_runs_count=42,
            latest_run_result="SUCCESS",
            latest_run_finished_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        pipeline = PipelineSummary(pipeline_summary=pipeline_data)
        
        assert pipeline.id == "pipeline-123"
        assert pipeline.name == "Test Pipeline"
        assert pipeline.owner == "testuser"
        assert pipeline.source_type == "SNOWFLAKE"
        assert pipeline.total_runs_count == 42
        assert pipeline.latest_run_result == "SUCCESS"
        assert pipeline.latest_run_finished_at == datetime(2024, 1, 1, 12, 0, 0)

    def test_pipeline_summary_response_from_api(self):
        """Test PipelineSummaryResponse creation from API response with nested structure."""
        api_response = {
            "meta": {
                "count": 2,
                "size": 20
            },
            "pipelines": [
                {
                    "pipelineSummary": {
                        "id": "pipeline-1",
                        "name": "Pipeline 1",
                        "meta": {
                            "owner": "user1"
                        },
                        "sourceType": "SNOWFLAKE",
                        "totalRunsCount": 10,
                        "latestRunResult": "SUCCESS",
                        "latestRunFinishedAt": "2024-01-01T12:00:00Z"
                    }
                },
                {
                    "pipelineSummary": {
                        "id": "pipeline-2", 
                        "name": "Pipeline 2",
                        "meta": {
                            "owner": "user2"
                        },
                        "sourceType": "ORACLE",
                        "totalRunsCount": 5,
                        "latestRunResult": "FAILED",
                        "latestRunFinishedAt": "2024-01-02T12:00:00Z"
                    }
                }
            ]
        }
        
        response = PipelineSummaryResponse.from_api_response(api_response)
        
        assert response.meta.count == 2
        assert response.meta.size == 20
        assert len(response.pipelines) == 2
        assert response.pipelines[0].id == "pipeline-1"
        assert response.pipelines[1].name == "Pipeline 2"
        assert response.pipelines[0].owner == "user1"
        assert response.pipelines[1].owner == "user2"

    def test_pipeline_summary_columns(self):
        """Test pipeline summary column definitions."""
        assert PIPELINE_SUMMARY_COLUMNS.resource_type == "pipeline-summary"
        assert "id" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "name" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "owner" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "source_type" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "total_runs_count" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "latest_run_result" in PIPELINE_SUMMARY_COLUMNS.columns
        assert "latest_run_finished_at" in PIPELINE_SUMMARY_COLUMNS.columns
        
        # Test filterable columns
        filterable = PIPELINE_SUMMARY_COLUMNS.get_filterable_columns()
        assert "id" in filterable
        assert "name" in filterable
        assert "owner" in filterable
        assert "source_type" in filterable
        assert "total_runs_count" in filterable
        assert "latest_run_result" in filterable
        assert "latest_run_finished_at" in filterable
        
        # Test sortable columns
        sortable = PIPELINE_SUMMARY_COLUMNS.get_sortable_columns()
        assert "id" in sortable
        assert "name" in sortable
        assert "owner" in sortable
        assert "source_type" in sortable
        assert "total_runs_count" in sortable
        assert "latest_run_result" in sortable
        assert "latest_run_finished_at" in sortable


class TestPipelineSummaryHandler:
    """Test PipelineSummaryHandler."""

    def test_handler_initialization(self):
        """Test handler initialization."""
        mock_http_client = Mock()
        handler = PipelineSummaryHandler(mock_http_client)
        
        assert handler.http_client == mock_http_client
        assert handler.console is not None

    @patch('adoc_toolkit.cli.commands.show.pipeline_summary.PipelineSummaryResponse')
    def test_fetch_resources(self, mock_response_class):
        """Test fetching resources from API with nested structure."""
        # Mock HTTP response
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "meta": {"count": 1, "size": 20},
            "pipelines": [
                {
                    "pipelineSummary": {
                        "id": "pipeline-1",
                        "name": "Test Pipeline",
                        "meta": {
                            "owner": "testuser"
                        },
                        "sourceType": "SNOWFLAKE",
                        "totalRunsCount": 10,
                        "latestRunResult": "SUCCESS",
                        "latestRunFinishedAt": "2024-01-01T12:00:00Z"
                    }
                }
            ]
        }
        mock_http_client.get.return_value = mock_response
        
        # Mock response model
        mock_response_instance = Mock()
        mock_response_instance.pipelines = [Mock()]
        mock_response_class.from_api_response.return_value = mock_response_instance
        
        handler = PipelineSummaryHandler(mock_http_client)
        resources = handler.fetch_resources()
        
        # Verify API call
        mock_http_client.get.assert_called_once_with(
            "/torch-pipeline/api/pipelines/summary",
            params={
                "page": 0,
                "size": 20
            }
        )
        
        # Verify response parsing
        mock_response_class.from_api_response.assert_called_once()
        assert resources == mock_response_instance.pipelines

    def test_fetch_resources_error(self):
        """Test error handling in fetch_resources."""
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 404
        mock_http_client.get.return_value = mock_response
        
        handler = PipelineSummaryHandler(mock_http_client)
        
        with pytest.raises(Exception, match="Failed to fetch pipeline-summary: 404"):
            handler.fetch_resources()

    def test_fetch_resources_json_error(self):
        """Test error handling for invalid JSON response."""
        mock_http_client = Mock()
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.text = "Invalid JSON content"
        mock_response.json.side_effect = ValueError("Expecting value: line 1 column 1 (char 0)")
        mock_http_client.get.return_value = mock_response
        
        handler = PipelineSummaryHandler(mock_http_client)
        
        with pytest.raises(Exception) as exc_info:
            handler.fetch_resources()
        
        assert "Invalid JSON response" in str(exc_info.value)
        assert "Invalid JSON content" in str(exc_info.value)

    def test_create_table(self):
        """Test table creation."""
        import pandas as pd
        
        mock_http_client = Mock()
        handler = PipelineSummaryHandler(mock_http_client)
        
        # Create test data
        data = [
            {
                "id": "pipeline-1",
                "name": "Test Pipeline 1",
                "owner": "user1",
                "source_type": "SNOWFLAKE",
                "total_runs_count": 10,
                "latest_run_result": "SUCCESS",
                "latest_run_finished_at": datetime(2024, 1, 1, 12, 0, 0)
            },
            {
                "id": "pipeline-2",
                "name": "Test Pipeline 2", 
                "owner": "user2",
                "source_type": "ORACLE",
                "total_runs_count": 5,
                "latest_run_result": "FAILED",
                "latest_run_finished_at": datetime(2024, 1, 2, 12, 0, 0)
            }
        ]
        
        df = pd.DataFrame(data)
        table = handler.create_table(df)
        
        assert table.title == "Pipeline Summaries"
        assert len(table.columns) == 7  # 7 columns as defined
        
        # Check column headers
        column_headers = [col.header for col in table.columns]
        expected_headers = ["Id", "Name", "Owner", "Source", "# Runs", "Last Run Status", "Finished Time in UTC"]
        assert column_headers == expected_headers

    def test_display_resources_empty(self):
        """Test displaying empty resources."""
        mock_http_client = Mock()
        handler = PipelineSummaryHandler(mock_http_client)
        
        # Mock console to capture output
        with patch.object(handler.console, 'print') as mock_print:
            handler.display_resources([])
            mock_print.assert_called_with("No pipeline-summary found.", style="yellow")

    def test_display_resources_with_data(self):
        """Test displaying resources with data."""
        import pandas as pd
        
        mock_http_client = Mock()
        handler = PipelineSummaryHandler(mock_http_client)
        
        # Create test resources with nested structure
        meta = PipelineSummaryMeta(owner="testuser")
        pipeline_data = PipelineSummaryData(
            id="pipeline-1",
            name="Test Pipeline",
            meta=meta,
            source_type="SNOWFLAKE",
            total_runs_count=10,
            latest_run_result="SUCCESS",
            latest_run_finished_at=datetime(2024, 1, 1, 12, 0, 0)
        )
        resources = [PipelineSummary(pipeline_summary=pipeline_data)]
        
        # Mock console to capture output
        with patch.object(handler.console, 'print') as mock_print:
            handler.display_resources(resources)
            
            # Should call print twice: once for table, once for summary
            assert mock_print.call_count == 2
            # Check summary call
            mock_print.assert_any_call("\nTotal pipeline-summary: 1", style="green") 