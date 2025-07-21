"""Tests for get command."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import pytest

from adoc_toolkit.cli.commands.get_command import GetCommand
from adoc_toolkit.models import (
    APIReference,
    CompletionItem,
    GetCommandArgs,
    QueryParameter,
)


class TestGetCommand:
    """Test cases for GetCommand."""

    def setup_method(self):
        """Set up test fixtures."""
        self.http_client = Mock()
        self.command = GetCommand(http_client=self.http_client)

        # Create temporary API reference file
        self.temp_dir = tempfile.mkdtemp()
        self.api_ref_file = Path(self.temp_dir) / "adoc-toolkit-api-reference.json"

        # Sample API reference data
        self.api_ref_data = {
            "version": "1.0",
            "description": "Test API Reference",
            "endpoints": {
                "health": {
                    "url": "/health",
                    "description": "Health check endpoint",
                    "query_params": {},
                    "response_type": "json",
                },
                "datasets": {
                    "url": "/api/v1/datasets",
                    "description": "Dataset management endpoint",
                    "query_params": {
                        "environment": {
                            "type": "string",
                            "description": "Environment name",
                        },
                        "limit": {
                            "type": "integer",
                            "description": "Maximum number of results",
                            "default": 100,
                        },
                        "status": {
                            "type": "string",
                            "description": "Value for status parameter",
                            "options": ["active", "inactive"],
                        },
                    },
                    "response_type": "json",
                },
            },
        }

        with open(self.api_ref_file, "w") as f:
            json.dump(self.api_ref_data, f)

    def teardown_method(self):
        """Clean up test fixtures."""
        import shutil

        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def test_command_name(self):
        """Test command name property."""
        assert self.command.name == "get"

    def test_command_description(self):
        """Test command description."""
        assert (
            self.command.description == "Make GET HTTP requests to ADOC API endpoints"
        )

    def test_command_aliases(self):
        """Test command aliases."""
        assert "fetch" in self.command.aliases
        assert "request" in self.command.aliases

    def test_help_functionality(self):
        """Test help system integration."""
        help_text = self.command.get_help()
        assert "get:" in help_text
        assert "Make GET HTTP requests" in help_text
        assert "Usage: get <url>" in help_text

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_load_api_reference_success(self, mock_path):
        """Test successful API reference loading."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            api_ref = self.command._load_api_reference()
            assert api_ref is not None
            assert api_ref.version == "1.0"
            assert "health" in api_ref.endpoints
            assert "datasets" in api_ref.endpoints

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_load_api_reference_file_not_found(self, mock_path):
        """Test API reference loading when file doesn't exist."""
        mock_path.return_value.exists.return_value = False

        api_ref = self.command._load_api_reference()
        assert api_ref is None

    def test_parse_query_params(self):
        """Test query parameter parsing."""
        args = ["environment=prod", "limit=10", "status=active"]
        params = self.command._parse_query_params(args)

        assert params["environment"] == "prod"
        assert params["limit"] == 10
        assert params["status"] == "active"

    def test_parse_query_params_boolean(self):
        """Test boolean parameter parsing."""
        args = ["verbose=true", "debug=false"]
        params = self.command._parse_query_params(args)

        assert params["verbose"] is True
        assert params["debug"] is False

    def test_parse_query_params_float(self):
        """Test float parameter parsing."""
        args = ["ratio=0.5"]
        params = self.command._parse_query_params(args)

        assert params["ratio"] == 0.5

    def test_parse_query_params_boolean_flag(self):
        """Test boolean flag parsing."""
        args = ["verbose", "debug"]
        params = self.command._parse_query_params(args)

        assert params["verbose"] is True
        assert params["debug"] is True

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_help_flag(self, mock_path):
        """Test execute with --help flag."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            result = self.command.execute(["--help"])
            assert result is True

    def test_execute_no_args(self):
        """Test execute with no arguments."""
        result = self.command.execute([])
        assert result is True

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_unknown_endpoint(self, mock_path):
        """Test execute with unknown endpoint."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            result = self.command.execute(["unknown"])
            assert result is True

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_successful_request(self, mock_path):
        """Test successful HTTP request execution."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Mock successful HTTP response
            mock_response = Mock()
            mock_response.is_success = True
            mock_response.json.return_value = {"status": "ok"}
            mock_response.text = '{"status": "ok"}'

            self.http_client.get.return_value = mock_response

            result = self.command.execute(["health"])
            assert result is True
            self.http_client.get.assert_called_once_with("/health", params={})

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_with_query_params(self, mock_path):
        """Test execute with query parameters."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Mock successful HTTP response
            mock_response = Mock()
            mock_response.is_success = True
            mock_response.json.return_value = {"datasets": []}
            mock_response.text = '{"datasets": []}'

            self.http_client.get.return_value = mock_response

            result = self.command.execute(["datasets", "environment=prod", "limit=5"])
            assert result is True
            self.http_client.get.assert_called_once_with(
                "/api/v1/datasets", params={"environment": "prod", "limit": 5}
            )

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_failed_request(self, mock_path):
        """Test failed HTTP request execution."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Mock failed HTTP response
            mock_response = Mock()
            mock_response.is_success = False
            mock_response.status_code = 404
            mock_response.text = "Not found"

            self.http_client.get.return_value = mock_response

            result = self.command.execute(["health"])
            assert result is True

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_execute_no_environment(self, mock_path):
        """Test execute when no environment is set."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Mock HTTP client to raise environment error
            from adoc_toolkit.http.exceptions import HTTPError

            self.http_client.get.side_effect = HTTPError(
                "No environment selected. Use 'use <environment>' to set an "
                "environment."
            )

            result = self.command.execute(["health"])
            assert result is True

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_get_completions_endpoints(self, mock_path):
        """Test endpoint name completions."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Test completion for "get h"
            completions = self.command.get_completions("get h", 6)
            # Check that we get CompletionItem objects with descriptions
            assert any(
                isinstance(c, CompletionItem) and c.text == "health"
                for c in completions
            )
            assert any(
                c.text == "health" and c.description == "Health check endpoint"
                for c in completions
            )

            # Test completion for "get d"
            completions = self.command.get_completions("get d", 6)
            assert any(
                c.text == "datasets" and c.description == "Dataset management endpoint"
                for c in completions
            )

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_get_completions_parameters(self, mock_path):
        """Test parameter name completions."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Test completion for "get datasets e"
            completions = self.command.get_completions("get datasets e", 15)
            assert any(
                c.text == "environment" and c.description == "Environment name"
                for c in completions
            )

            # Test completion for "get datasets l"
            completions = self.command.get_completions("get datasets l", 15)
            assert any(
                c.text == "limit" and c.description == "Maximum number of results"
                for c in completions
            )

    @patch("adoc_toolkit.cli.commands.get_command.Path")
    def test_get_completions_parameter_values(self, mock_path):
        """Test parameter value completions."""
        mock_path.return_value.exists.return_value = True

        with patch("builtins.open", create=True) as mock_open:
            mock_open.return_value.__enter__.return_value.read.return_value = (
                json.dumps(self.api_ref_data)
            )

            # Test completion for "get datasets status=a"
            completions = self.command.get_completions("get datasets status=a", 20)
            assert any(
                c.text == "active" and c.description == "Value for status parameter"
                for c in completions
            )

    def test_get_command_args_validation(self):
        """Test GetCommandArgs validation."""
        # Valid args
        args = GetCommandArgs(endpoint="health", query_params={"limit": 10})
        assert args.endpoint == "health"
        assert args.query_params["limit"] == 10

        # Test endpoint validation
        with pytest.raises(ValueError, match="Endpoint name cannot be empty"):
            GetCommandArgs(endpoint="", query_params={})

        # Test query params validation
        with pytest.raises(ValueError, match="Query parameter.*must be string"):
            GetCommandArgs(endpoint="health", query_params={"invalid": []})

    def test_api_reference_model(self):
        """Test APIReference model validation."""
        api_ref = APIReference.model_validate(self.api_ref_data)
        assert api_ref.version == "1.0"
        assert "health" in api_ref.endpoints
        assert "datasets" in api_ref.endpoints

        health_endpoint = api_ref.endpoints["health"]
        assert health_endpoint.url == "/health"
        assert health_endpoint.description == "Health check endpoint"

        datasets_endpoint = api_ref.endpoints["datasets"]
        assert datasets_endpoint.url == "/api/v1/datasets"
        assert "environment" in datasets_endpoint.query_params
        assert "limit" in datasets_endpoint.query_params
        assert "status" in datasets_endpoint.query_params

    def test_query_parameter_model(self):
        """Test QueryParameter model validation."""
        param_data = {
            "type": "string",
            "description": "Test parameter",
            "default": "test",
            "options": ["option1", "option2"],
        }

        param = QueryParameter.model_validate(param_data)
        assert param.type == "string"
        assert param.description == "Test parameter"
        assert param.default == "test"
        assert param.options == ["option1", "option2"]
