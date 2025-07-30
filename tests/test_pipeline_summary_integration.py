"""Integration tests for pipeline-summary functionality."""

import pytest
from unittest.mock import Mock, patch
from datetime import datetime

from adoc_toolkit.cli.commands.show_command import ShowCommand
from adoc_toolkit.models.pipeline_models import PipelineSummary, PipelineSummaryData, PipelineSummaryMeta


class TestPipelineSummaryIntegration:
    """Test pipeline-summary integration with show command."""

    def test_show_command_recognizes_pipeline_summary(self):
        """Test that show command recognizes pipeline-summary resource type."""
        cmd = ShowCommand()
        
        # Test that pipeline-summary is available in completions
        completions = cmd.get_completions("show", 4)
        assert "pipeline-summary" in completions
        
        # Test that pipeline-summary is in resource registry
        from adoc_toolkit.models.registry import RESOURCE_REGISTRY
        assert "pipeline-summary" in RESOURCE_REGISTRY

    @patch('adoc_toolkit.cli.commands.show.pipeline_summary.PipelineSummaryResponse')
    def test_show_pipeline_summary_execution(self, mock_response_class):
        """Test executing 'show pipeline-summary' command."""
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
        
        # Create command with mocked HTTP client
        cmd = ShowCommand(mock_http_client)
        
        # Mock environment info
        with patch.object(mock_http_client, '_get_environment_info') as mock_env:
            mock_env.return_value = {"base_url": "http://test.com"}
            
            # Execute command
            result = cmd.execute(["pipeline-summary"])
            
            # Verify command executed successfully
            assert result is True
            
            # Verify API call was made
            mock_http_client.get.assert_called_once_with(
                "/torch-pipeline/api/pipelines/summary",
                params={
                    "page": 0,
                    "size": 20
                }
            )

    def test_pipeline_summary_help_integration(self):
        """Test that pipeline-summary appears in help output."""
        cmd = ShowCommand()
        help_text = cmd.get_help()
        
        # Check that pipeline-summary is mentioned in help
        assert "pipeline-summary" in help_text
        assert "show pipeline-summary" in help_text

    def test_pipeline_summary_filtering_and_sorting(self):
        """Test that pipeline-summary supports filtering and sorting."""
        from adoc_toolkit.models.registry import RESOURCE_REGISTRY
        
        # Get pipeline-summary column set
        column_set = RESOURCE_REGISTRY["pipeline-summary"]
        
        # Test filterable columns
        filterable = column_set.get_filterable_columns()
        assert "id" in filterable
        assert "name" in filterable
        assert "owner" in filterable
        assert "source_type" in filterable
        assert "total_runs_count" in filterable
        assert "latest_run_result" in filterable
        assert "latest_run_finished_at" in filterable
        
        # Test sortable columns
        sortable = column_set.get_sortable_columns()
        assert "id" in sortable
        assert "name" in sortable
        assert "owner" in sortable
        assert "source_type" in sortable
        assert "total_runs_count" in sortable
        assert "latest_run_result" in sortable
        assert "latest_run_finished_at" in sortable

    def test_pipeline_summary_model_validation(self):
        """Test pipeline summary model validation with nested structure."""
        # Test valid pipeline summary with nested structure
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

    def test_pipeline_summary_table_creation(self):
        """Test pipeline summary table creation."""
        from adoc_toolkit.cli.commands.show.pipeline_summary import PipelineSummaryHandler
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
        
        # Verify table structure
        assert table.title == "Pipeline Summaries"
        assert len(table.columns) == 7  # 7 columns as defined
        
        # Check column headers
        column_headers = [col.header for col in table.columns]
        expected_headers = ["Id", "Name", "Owner", "Source", "# Runs", "Last Run Status", "Finished Time in UTC"]
        assert column_headers == expected_headers 