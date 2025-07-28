"""Tests for get command path parameter functionality."""

from unittest.mock import Mock, patch

from rich.console import Console

from adoc_toolkit.cli.commands.get_command import GetCommand
from adoc_toolkit.models import APIEndpoint, APIReference


class TestGetCommandPathParams:
    """Test path parameter functionality in get command."""

    def setup_method(self):
        """Set up test fixtures."""
        self.http_client = Mock()
        self.command = GetCommand(http_client=self.http_client)
        self.console = Console()

    def test_extract_path_parameters(self):
        """Test extracting path parameters from URLs."""
        # Test with asset-id parameter
        url = "/catalog-server/api/assets/:asset-id/metadata"
        params = self.command._extract_path_parameters(url)
        assert params == ["asset-id"]

        # Test with user-id parameter
        url = "/catalog-server/api/users/:user-id/info"
        params = self.command._extract_path_parameters(url)
        assert params == ["user-id"]

        # Test with multiple parameters
        url = "/catalog-server/api/assets/:asset-id/:user-id/info"
        params = self.command._extract_path_parameters(url)
        assert params == ["asset-id", "user-id"]

        # Test with no parameters
        url = "/catalog-server/api/assets/search"
        params = self.command._extract_path_parameters(url)
        assert params == []

    def test_replace_path_parameters(self):
        """Test replacing path parameters in URLs."""
        # Test single parameter replacement
        url = "/catalog-server/api/assets/:asset-id/metadata"
        path_params = {"asset-id": "123"}
        result = self.command._replace_path_parameters(url, path_params)
        assert result == "/catalog-server/api/assets/123/metadata"

        # Test multiple parameter replacement
        url = "/catalog-server/api/users/:user-id/info"
        path_params = {"user-id": "456"}
        result = self.command._replace_path_parameters(url, path_params)
        assert result == "/catalog-server/api/users/456/info"

        # Test with no parameters
        url = "/catalog-server/api/assets/search"
        path_params = {}
        result = self.command._replace_path_parameters(url, path_params)
        assert result == url

    def test_parse_path_params(self):
        """Test parsing path parameters from command arguments."""
        args = ["asset-id=123", "user-id=456", "?name=test"]
        path_params = self.command._parse_path_params(args)
        assert path_params == {"asset-id": "123", "user-id": "456"}

        # Test with query parameters (should be ignored)
        args = ["asset-id=123", "?name=test", "?page=1"]
        path_params = self.command._parse_path_params(args)
        assert path_params == {"asset-id": "123"}

        # Test with no path parameters
        args = ["?name=test", "?page=1"]
        path_params = self.command._parse_path_params(args)
        assert path_params == {}

    @patch("builtins.input")
    def test_prompt_for_missing_path_params(self, mock_input):
        """Test prompting for missing path parameters."""
        url = "/catalog-server/api/assets/:asset-id/metadata"
        provided_params = {}
        mock_input.return_value = "123"

        result = self.command._prompt_for_missing_path_params(url, provided_params)
        assert result == {"asset-id": "123"}

    @patch("builtins.input")
    def test_prompt_for_missing_path_params_cancel(self, mock_input):
        """Test canceling path parameter prompt."""
        url = "/catalog-server/api/assets/:asset-id/metadata"
        provided_params = {}
        mock_input.return_value = ""  # User cancels

        result = self.command._prompt_for_missing_path_params(url, provided_params)
        assert result == {}

    def test_execute_with_path_params(self):
        """Test executing get command with path parameters."""
        # Mock successful API response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/catalog-server/api/assets/123/metadata"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"data": "test"}
        mock_response.text = '{"data": "test"}'
        self.http_client.get.return_value = mock_response

        # Mock API reference
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={},
                    response_type="json",
                )
            },
        )

        with patch.object(self.command, "_load_api_reference", return_value=api_ref):
            with patch.object(
                self.command,
                "_prompt_for_missing_path_params",
                return_value={"asset-id": "123"},
            ):
                with patch.object(self.command.console, "print"):
                    with patch(
                        "adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config"
                    ):
                        result = self.command.execute(
                            [
                                "/catalog-server/api/assets/:asset-id/metadata",
                                "asset-id=123",
                            ]
                        )
                        assert result is True

                        # Verify the correct URL was called
                        self.http_client.get.assert_called_once_with(
                            "/catalog-server/api/assets/123/metadata", params={}
                        )

    def test_execute_with_missing_path_params(self):
        """Test executing get command with missing path parameters."""
        # Mock API reference
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={},
                    response_type="json",
                )
            },
        )

        with patch.object(self.command, "_load_api_reference", return_value=api_ref):
            with patch.object(
                self.command, "_prompt_for_missing_path_params", return_value={}
            ):
                with patch.object(self.command.console, "print") as mock_print:
                    result = self.command.execute(
                        ["/catalog-server/api/assets/:asset-id/metadata"]
                    )
                    assert result is True
                    mock_print.assert_called_with(
                        "Request cancelled by user", style="yellow"
                    )

    def test_show_endpoint_help_with_path_params(self):
        """Test showing help for endpoint with path parameters."""
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={},
                    response_type="json",
                )
            },
        )

        with patch.object(self.command, "_load_api_reference", return_value=api_ref):
            with patch.object(self.command.console, "print") as mock_print:
                self.command._show_endpoint_help(
                    "/catalog-server/api/assets/:asset-id/metadata"
                )
                # Verify that path parameters were shown in help
                mock_print.assert_called()

    def test_get_completions_with_path_params(self):
        """Test auto-completion with path parameters."""
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={},
                    response_type="json",
                ),
                "/catalog-server/api/assets/:asset-id/users/:user-id/permissions": (
                    APIEndpoint(
                        url="/catalog-server/api/assets/:asset-id/users/:user-id/permissions",
                        description="Get user permissions for asset",
                        query_params={},
                        response_type="json",
                    )
                ),
            },
        )

        with patch.object(self.command, "_load_api_reference", return_value=api_ref):
            # Test completion for complete URL - should show path parameters
            completions = self.command.get_completions(
                "get /catalog-server/api/assets/:asset-id/metadata ", 50
            )
            assert len(completions) > 0
            assert "asset-id" in completions

            # Test completion for complete URL with multiple parameters
            completions = self.command.get_completions(
                "get /catalog-server/api/assets/:asset-id/users/:user-id/permissions ",
                70,
            )
            assert len(completions) > 0
            assert "asset-id" in completions
            assert "user-id" in completions

    def test_get_completions_path_parameter_suggestions(self):
        """Test that path parameter suggestions work correctly."""
        api_ref = APIReference(
            version="1.0",
            description="Test API",
            endpoints={
                "/catalog-server/api/users/:user-id/info": APIEndpoint(
                    url="/catalog-server/api/users/:user-id/info",
                    description="Get user info",
                    query_params={},
                    response_type="json",
                ),
                "/catalog-server/api/assets/:asset-id/:uid/info": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/:uid/info",
                    description="Get asset info",
                    query_params={},
                    response_type="json",
                ),
            },
        )

        with patch.object(self.command, "_load_api_reference", return_value=api_ref):
            # Test completion for complete URL - should show path parameters
            completions = self.command.get_completions(
                "get /catalog-server/api/users/:user-id/info ", 44
            )
            assert "user-id" in completions

            # Test completion for complete URL with multiple parameters
            completions = self.command.get_completions(
                "get /catalog-server/api/assets/:asset-id/:uid/info ", 54
            )
            assert "asset-id" in completions
            assert "uid" in completions
