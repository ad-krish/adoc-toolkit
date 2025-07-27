"""Tests for find-asset command."""

import pytest
from unittest.mock import Mock, patch
from adoc_toolkit.cli.commands.find_asset_command import FindAssetCommand


class TestFindAssetCommand:
    """Test cases for find-asset command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.http_client = Mock()
        self.command = FindAssetCommand(self.http_client)

    def test_command_name(self):
        """Test command name property."""
        assert self.command.name == "find-asset"

    def test_command_description(self):
        """Test command description."""
        assert self.command.description == "Find assets by name"

    def test_command_aliases(self):
        """Test command aliases."""
        expected_aliases = ["search", "search-asset", "asset-search"]
        assert self.command.aliases == expected_aliases

    def test_help_functionality(self):
        """Test help system integration."""
        help_text = self.command.get_help()
        assert "find-asset" in help_text
        assert "Find assets by name" in help_text
        assert "Usage: find-asset <asset-name>" in help_text

    def test_execute_with_help_flag(self):
        """Test command execution with --help flag."""
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["--help"])
            assert result is True
            mock_print.assert_called()

    def test_execute_without_args(self):
        """Test command execution without arguments."""
        with patch('builtins.print') as mock_print:
            result = self.command.execute([])
            assert result is True
            # Should print error message about missing asset name
            mock_print.assert_called()

    def test_execute_with_asset_name(self):
        """Test command execution with asset name."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {
            "assets": [
                {
                    "id": 123,
                    "name": "test_database",
                    "assetType": {"name": "Database", "id": 1},
                    "uid": "db_123"
                }
            ]
        }
        
        self.http_client.get.return_value = mock_response
        
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["test_database"])
            assert result is True
            
            # Verify API call was made correctly
            self.http_client.get.assert_called_once_with(
                "/catalog-server/api/assets/search",
                params={"name": "test_database"}
            )

    def test_execute_with_no_results(self):
        """Test command execution when no assets are found."""
        # Mock successful API response with no assets
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.json.return_value = {"assets": []}
        
        self.http_client.get.return_value = mock_response
        
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["nonexistent"])
            assert result is True
            
            # Should print no results message
            mock_print.assert_called()

    def test_execute_with_api_error(self):
        """Test command execution when API returns error."""
        # Mock failed API response
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 404
        
        self.http_client.get.return_value = mock_response
        
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["test"])
            assert result is True
            
            # Should print error message
            mock_print.assert_called_with("Error searching for assets: HTTP 404")

    def test_execute_with_exception(self):
        """Test command execution when exception occurs."""
        self.http_client.get.side_effect = Exception("Network error")
        
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["test"])
            assert result is True
            
            # Should print exception message
            mock_print.assert_called_with("Error executing search: Network error")

    def test_display_results_with_multiple_assets(self):
        """Test displaying multiple search results."""
        from adoc_toolkit.models import AssetSearchResponse, Asset, AssetType
        
        response_data = AssetSearchResponse(
            assets=[
                Asset(
                    id=123,
                    name="database_1",
                    asset_type=AssetType(name="Database", id=1),
                    uid="db_123"
                ),
                Asset(
                    id=456,
                    name="table_1",
                    asset_type=AssetType(name="Table", id=2),
                    uid="tbl_456"
                )
            ]
        )
        
        with patch('builtins.print') as mock_print:
            self.command._display_results(response_data, "test")
            
            # Should print table with results
            assert mock_print.call_count > 0

    def test_display_results_with_long_values(self):
        """Test displaying results with long values that need truncation."""
        from adoc_toolkit.models import AssetSearchResponse, Asset, AssetType
        
        response_data = AssetSearchResponse(
            assets=[
                Asset(
                    id=123456789012345,
                    name="very_long_asset_name_that_exceeds_fifty_characters_and_should_be_displayed_fully",
                    asset_type=AssetType(name="VeryLongAssetTypeName", id=999),
                    uid="very_long_uid_that_exceeds_fifty_characters_and_should_be_displayed_fully"
                )
            ]
        )
        
        with patch('builtins.print') as mock_print:
            self.command._display_results(response_data, "test")
            
            # Should print full name and UID values
            assert mock_print.call_count > 0

    def test_get_completions(self):
        """Test auto-completion functionality."""
        completions = self.command.get_completions("search-asset ", 12)
        # Currently returns empty list, but method exists for future enhancement
        assert isinstance(completions, list) 