"""Tests for get command."""

import pytest
from unittest.mock import Mock, patch, MagicMock
from rich.console import Console

from adoc_toolkit.cli.commands.get_command import GetCommand
from adoc_toolkit.models import APIReference, APIEndpoint, QueryParameter


class TestGetCommand:
    """Test get command functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.http_client = Mock()
        self.command = GetCommand(http_client=self.http_client)
        self.console = Console()

    def test_command_name(self):
        """Test command name property."""
        assert self.command.name == "get"

    def test_command_description(self):
        """Test command description."""
        assert self.command.description == "Make HTTP GET requests to ADOC API endpoints"

    def test_command_aliases(self):
        """Test command aliases."""
        assert "g" in self.command.aliases

    def test_help_functionality(self):
        """Test help system integration."""
        help_text = self.command.get_help()
        assert "Make HTTP GET requests" in help_text
        assert "Usage: get <url>" in help_text
        assert "Path Parameters:" in help_text

    @patch('builtins.open', create=True)
    @patch('json.load')
    def test_load_api_reference_success(self, mock_json_load, mock_open):
        """Test successful API reference loading."""
        mock_data = {
            "version": "1.0",
            "description": "Test API",
            "endpoints": {
                "/test": {
                    "url": "/test",
                    "description": "Test endpoint",
                    "query_params": {},
                    "response_type": "json"
                }
            }
        }
        mock_json_load.return_value = mock_data
        
        result = self.command._load_api_reference()
        
        assert result is not None
        assert result.version == "1.0"
        assert result.description == "Test API"

    @patch('builtins.open', side_effect=FileNotFoundError)
    def test_load_api_reference_file_not_found(self, mock_open):
        """Test API reference loading when file not found."""
        result = self.command._load_api_reference()
        assert result is None

    def test_parse_query_params(self):
        """Test query parameter parsing."""
        args = ["?environment=prod", "?limit=5"]
        params = self.command._parse_query_params(args)
        
        assert params["environment"] == "prod"
        assert params["limit"] == 5

    def test_parse_query_params_boolean(self):
        """Test boolean query parameter parsing."""
        args = ["?verbose=true", "?debug=false"]
        params = self.command._parse_query_params(args)
        
        assert params["verbose"] is True
        assert params["debug"] is False

    def test_parse_query_params_float(self):
        """Test float query parameter parsing."""
        args = ["?ratio=0.5"]
        params = self.command._parse_query_params(args)
        
        assert params["ratio"] == "0.5"  # Floats are kept as strings in simplified version

    def test_parse_query_params_boolean_flag(self):
        """Test boolean flag parameter parsing."""
        args = ["?verbose"]
        params = self.command._parse_query_params(args)
        
        assert params["verbose"] is True

    def test_execute_help_flag(self):
        """Test help flag execution."""
        with patch('builtins.print') as mock_print:
            result = self.command.execute(["--help"])
            assert result is True
            mock_print.assert_called()

    def test_execute_no_args(self):
        """Test execution with no arguments."""
        with patch.object(self.command.console, 'print') as mock_print:
            result = self.command.execute([])
            assert result is True
            # Check that the first call contains the usage message
            mock_print.assert_any_call("Usage: get <url> [path-params] [query-params]", style="red")

    @patch.object(GetCommand, '_load_api_reference')
    def test_execute_unknown_endpoint(self, mock_load_api):
        """Test execution with unknown endpoint."""
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {"/known": Mock()}
        mock_load_api.return_value = mock_api_ref
        
        with patch.object(self.command.console, 'print') as mock_print:
            result = self.command.execute(["/unknown"])
            assert result is True
            mock_print.assert_any_call("Unknown URL: /unknown", style="red")

    @patch.object(GetCommand, '_load_api_reference')
    @patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config')
    def test_execute_successful_request(self, mock_print_response, mock_load_api):
        """Test successful request execution."""
        # Mock API reference
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/test": APIEndpoint(
                url="/test",
                description="Test endpoint",
                query_params={},
                response_type="json"
            )
        }
        mock_load_api.return_value = mock_api_ref
        
        # Mock successful response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/test"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'
        self.http_client.get.return_value = mock_response
        
        with patch.object(self.command.console, 'print'):
            result = self.command.execute(["/test"])
            assert result is True
            self.http_client.get.assert_called_once_with("/test", params={})

    @patch.object(GetCommand, '_load_api_reference')
    @patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config')
    def test_execute_with_query_params(self, mock_print_response, mock_load_api):
        """Test execution with query parameters."""
        # Mock API reference
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/test": APIEndpoint(
                url="/test",
                description="Test endpoint",
                query_params={},
                response_type="json"
            )
        }
        mock_load_api.return_value = mock_api_ref
        
        # Mock successful response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/test"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'
        self.http_client.get.return_value = mock_response
        
        with patch.object(self.command.console, 'print'):
            result = self.command.execute(["/test", "?param1=value1", "?param2=value2"])
            assert result is True
            self.http_client.get.assert_called_once_with("/test", params={"param1": "value1", "param2": "value2"})

    @patch.object(GetCommand, '_load_api_reference')
    def test_execute_failed_request(self, mock_load_api):
        """Test failed request execution."""
        # Mock API reference
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/test": APIEndpoint(
                url="/test",
                description="Test endpoint",
                query_params={},
                response_type="json"
            )
        }
        mock_load_api.return_value = mock_api_ref
        
        # Mock failed response
        mock_response = Mock()
        mock_response.is_success = False
        mock_response.status_code = 404
        mock_response.url = "/test"
        mock_response.text = "Not found"
        self.http_client.get.return_value = mock_response
        
        with patch.object(self.command.console, 'print'):
            result = self.command.execute(["/test"])
            assert result is True
            self.http_client.get.assert_called_once_with("/test", params={})

    @patch.object(GetCommand, '_load_api_reference')
    def test_execute_no_environment(self, mock_load_api):
        """Test execution when API reference cannot be loaded."""
        mock_load_api.return_value = None
        
        result = self.command.execute(["/test"])
        assert result is False

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_endpoints(self, mock_load_api):
        """Test completion for endpoints."""
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/test1": Mock(),
            "/test2": Mock()
        }
        mock_load_api.return_value = mock_api_ref
        
        completions = self.command.get_completions("get ", 5)
        assert len(completions) == 2
        assert "/test1" in completions
        assert "/test2" in completions

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_parameters(self, mock_load_api):
        """Test completion for query parameters."""
        mock_api_ref = Mock()
        mock_endpoint = APIEndpoint(
            url="/test",
            description="Test endpoint",
            query_params={
                "param1": QueryParameter(type="string", description="Param 1"),
                "param2": QueryParameter(type="string", description="Param 2")
            },
            response_type="json"
        )
        mock_api_ref.endpoints = {"/test": mock_endpoint}
        mock_load_api.return_value = mock_api_ref
        
        # The simplified implementation doesn't support query parameter completion
        # So we expect no completions for query parameter input
        completions = self.command.get_completions("get /test ?", 12)
        assert len(completions) == 0

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_parameter_values(self, mock_load_api):
        """Test completion for parameter values."""
        mock_api_ref = Mock()
        mock_endpoint = APIEndpoint(
            url="/test",
            description="Test endpoint",
            query_params={
                "format": QueryParameter(
                    type="string", 
                    description="Format",
                    options=["json", "xml"]
                )
            },
            response_type="json"
        )
        mock_api_ref.endpoints = {"/test": mock_endpoint}
        mock_load_api.return_value = mock_api_ref
        
        # The simplified implementation doesn't support parameter value completion
        # So we expect no completions for parameter value input
        completions = self.command.get_completions("get /test ?format=", 20)
        assert len(completions) == 0

    def test_get_command_args_validation(self):
        """Test GetCommandArgs validation."""
        from adoc_toolkit.models import GetCommandArgs
        
        # Test valid args
        args = GetCommandArgs(
            endpoint="/test",
            query_params={"param": "value"},
            path_params={"id": "123"}
        )
        assert args.endpoint == "/test"
        assert args.query_params["param"] == "value"
        assert args.path_params["id"] == "123"

    def test_api_reference_model(self):
        """Test APIReference model."""
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/test": APIEndpoint(
                    url="/test",
                    description="Test endpoint",
                    query_params={},
                    response_type="json"
                )
            }
        )
        assert api_ref.version == "1.0"
        assert api_ref.description == "Test API"
        assert len(api_ref.endpoints) == 1

    def test_query_parameter_model(self):
        """Test QueryParameter model."""
        param = QueryParameter(
            type="string",
            description="Test parameter",
            default="default",
            options=["option1", "option2"]
        )
        assert param.type == "string"
        assert param.description == "Test parameter"
        assert param.default == "default"
        assert param.options == ["option1", "option2"]

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_path_parameters(self, mock_load_api):
        """Test completion for path parameters when URL is complete."""
        mock_api_ref = Mock()
        mock_endpoint = APIEndpoint(
            url="/catalog-server/api/assets/:asset-id/metadata",
            description="Get asset metadata",
            query_params={},
            response_type="json"
        )
        mock_api_ref.endpoints = {"/catalog-server/api/assets/:asset-id/metadata": mock_endpoint}
        mock_load_api.return_value = mock_api_ref
        
        # Test path parameter completion when URL is complete
        completions = self.command.get_completions("get /catalog-server/api/assets/:asset-id/metadata ", 50)
        assert len(completions) == 1
        assert "asset-id" in completions

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_path_parameters_multiple(self, mock_load_api):
        """Test completion for multiple path parameters."""
        mock_api_ref = Mock()
        mock_endpoint = APIEndpoint(
            url="/catalog-server/api/assets/:asset-id/users/:user-id/permissions",
            description="Get user permissions for asset",
            query_params={},
            response_type="json"
        )
        mock_api_ref.endpoints = {"/catalog-server/api/assets/:asset-id/users/:user-id/permissions": mock_endpoint}
        mock_load_api.return_value = mock_api_ref
        
        # Test path parameter completion for URL with multiple parameters
        completions = self.command.get_completions("get /catalog-server/api/assets/:asset-id/users/:user-id/permissions ", 70)
        assert len(completions) == 2
        assert "asset-id" in completions
        assert "user-id" in completions

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_path_parameters_with_provided(self, mock_load_api):
        """Test completion for path parameters when some are already provided."""
        mock_api_ref = Mock()
        mock_endpoint = APIEndpoint(
            url="/catalog-server/api/assets/:asset-id/users/:user-id/permissions",
            description="Get user permissions for asset",
            query_params={},
            response_type="json"
        )
        mock_api_ref.endpoints = {"/catalog-server/api/assets/:asset-id/users/:user-id/permissions": mock_endpoint}
        mock_load_api.return_value = mock_api_ref
        
        # Test path parameter completion when one parameter is already provided
        completions = self.command.get_completions("get /catalog-server/api/assets/:asset-id/users/:user-id/permissions asset-id=123 ", 85)
        assert len(completions) == 1
        assert "user-id" in completions
        assert "asset-id" not in completions  # Already provided

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_url_partial(self, mock_load_api):
        """Test completion for partial URL paths."""
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/catalog-server/api/assets/search": Mock(),
            "/catalog-server/api/assets/discover": Mock(),
            "/catalog-server/api/users/info": Mock()
        }
        mock_load_api.return_value = mock_api_ref
        
        # Test partial URL completion
        completions = self.command.get_completions("get /catalog-server/api/assets/", 30)
        assert len(completions) == 2
        assert "/catalog-server/api/assets/search" in completions
        assert "/catalog-server/api/assets/discover" in completions
        assert "/catalog-server/api/users/info" not in completions

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_empty_input(self, mock_load_api):
        """Test completion for empty input."""
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {"/test": Mock()}
        mock_load_api.return_value = mock_api_ref
        
        # Test empty input
        completions = self.command.get_completions("", 0)
        assert len(completions) == 0

    @patch.object(GetCommand, '_load_api_reference')
    def test_get_completions_only_get_command(self, mock_load_api):
        """Test completion when only 'get' command is entered."""
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {"/test1": Mock(), "/test2": Mock()}
        mock_load_api.return_value = mock_api_ref
        
        # Test when only 'get' is entered
        completions = self.command.get_completions("get", 4)
        assert len(completions) == 2
        assert "/test1" in completions
        assert "/test2" in completions

    @patch.object(GetCommand, '_load_api_reference')
    @patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config')
    def test_execute_honors_response_type_config(self, mock_print_response, mock_load_api):
        """Test that get command honors http.response.type configuration."""
        # Mock API reference
        mock_api_ref = Mock()
        mock_api_ref.endpoints = {
            "/test": APIEndpoint(
                url="/test",
                description="Test endpoint",
                query_params={},
                response_type="json"
            )
        }
        mock_load_api.return_value = mock_api_ref
        
        # Mock successful response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/test"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": {"test": "value", "nested": {"key": "value"}}}
        mock_response.text = '{"data": {"test": "value", "nested": {"key": "value"}}}'
        self.http_client.get.return_value = mock_response
        
        result = self.command.execute(["/test"])
        assert result is True
        
        # Verify that the response formatter was called
        assert mock_print_response.called
