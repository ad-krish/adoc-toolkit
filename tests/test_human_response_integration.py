"""Integration tests for human-readable response formatting."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from pathlib import Path

from adoc_toolkit.http.formatter import ResponseFormatter
from adoc_toolkit.http.http_config import ResponseType


class TestHumanResponseIntegration:
    """Test integration of human response type with real scenarios."""

    def setup_method(self):
        """Set up test fixtures."""
        self.console = Mock()
        self.formatter = ResponseFormatter(self.console)

    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    @patch('adoc_toolkit.config.get_config_manager')
    @patch('adoc_toolkit.llm.client.get_llm_client')
    def test_human_response_with_real_data(self, mock_get_client, mock_get_config, mock_open, mock_exists):
        """Test human formatting with realistic API response data."""
        # Mock prompt file
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"
        
        # Mock config manager with realistic values
        mock_config = Mock()
        mock_config.get.side_effect = lambda key: {
            "llm.vendor": "gemini",
            "llm.apikey": "test-api-key-123",
            "llm.model": "gemini-1.5-pro"
        }.get(key)
        mock_get_config.return_value = mock_config
        
        # Mock LLM client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.content = """**API Response Summary**

*Status*: Success (200 OK)
*Timestamp*: January 15, 2024 at 2:30:45 PM

**Data Overview**
- Total records found: 2
- Search criteria: name contains "snowflake"

**Results:**
1. **Snowflake Data Warehouse**
   - ID: sf-001
   - Name: Production Snowflake
   - Status: Active
   - Type: Data Warehouse
   - Location: US East

2. **Snowflake Analytics**
   - ID: sf-002
   - Name: Analytics Snowflake
   - Status: Active
   - Type: Analytics Platform
   - Location: US West

**Additional Information**
- Response time: 245ms
- Cache status: Hit"""
        # Mock the tuple return from with_error_handling decorator
        mock_client.generate_response.return_value = (mock_response, None)
        mock_get_client.return_value = mock_client
        
        # Realistic API response data (similar to what the user was testing)
        test_data = {
            "status": "success",
            "data": [
                {
                    "id": "sf-001",
                    "name": "Production Snowflake",
                    "type": "data_warehouse",
                    "status": "active",
                    "location": "us-east-1",
                    "created_at": "2024-01-01T00:00:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                },
                {
                    "id": "sf-002",
                    "name": "Analytics Snowflake",
                    "type": "analytics_platform",
                    "status": "active",
                    "location": "us-west-1",
                    "created_at": "2024-01-05T00:00:00Z",
                    "updated_at": "2024-01-15T10:30:00Z"
                }
            ],
            "metadata": {
                "count": 2,
                "response_time": 245,
                "cache_status": "hit",
                "timestamp": "2024-01-15T14:30:45Z"
            }
        }
        
        result = self.formatter._format_human(test_data)
        
        # Verify LLM was called with correct data
        mock_client.generate_response.assert_called_once()
        call_args = mock_client.generate_response.call_args[0][0]
        
        # Check that the JSON data was passed correctly
        assert "status" in call_args.user_prompt
        assert "success" in call_args.user_prompt
        assert "sf-001" in call_args.user_prompt
        assert "Production Snowflake" in call_args.user_prompt
        assert call_args.api_key == "test-api-key-123"
        assert call_args.model == "gemini-1.5-pro"
        
        # Check that the response contains expected human-readable content
        assert "**API Response Summary**" in result
        assert "Snowflake Data Warehouse" in result
        assert "Snowflake Analytics" in result
        assert "Total records found: 2" in result

    @patch('pathlib.Path.exists')
    @patch('builtins.open')
    @patch('adoc_toolkit.config.get_config_manager')
    def test_human_response_with_none_values(self, mock_get_config, mock_open, mock_exists):
        """Test human formatting when config values are None."""
        # Mock prompt file
        mock_exists.return_value = True
        mock_open.return_value.__enter__.return_value.read.return_value = "System prompt"
        
        # Mock config manager with None values
        mock_config = Mock()
        mock_config.get.side_effect = lambda key: {
            "llm.vendor": None,
            "llm.apikey": "test-api-key-123",
            "llm.model": None
        }.get(key)
        mock_get_config.return_value = mock_config
        
        # Mock LLM client
        with patch('adoc_toolkit.llm.client.get_llm_client') as mock_get_client:
            mock_client = Mock()
            mock_response = Mock()
            mock_response.content = "Human readable response"
            # Mock the tuple return from with_error_handling decorator
            mock_client.generate_response.return_value = (mock_response, None)
            mock_get_client.return_value = mock_client
            
            test_data = {"status": "success", "data": []}
            result = self.formatter._format_human(test_data)
            
            # Verify that default values were used
            mock_get_client.assert_called_once_with("gemini", self.console)
            call_args = mock_client.generate_response.call_args[0][0]
            assert call_args.model == "gemini-1.5-pro"

    def test_format_response_with_human_type(self):
        """Test that format_response correctly routes to human formatting."""
        test_data = {"test": "data"}
        
        with patch.object(self.formatter, '_format_human') as mock_human:
            mock_human.return_value = "Human readable text"
            
            result = self.formatter.format_response(test_data, ResponseType.HUMAN)
            
            mock_human.assert_called_once_with(test_data)
            assert result == "Human readable text"

    def test_response_type_enum_includes_human(self):
        """Test that ResponseType enum includes HUMAN."""
        assert ResponseType.HUMAN == "human"
        assert "human" in [rt.value for rt in ResponseType]
        assert len(ResponseType) == 4  # json, table, csv, human 