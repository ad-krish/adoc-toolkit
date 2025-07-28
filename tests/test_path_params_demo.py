"""Demonstration of path parameter functionality."""

import pytest
from unittest.mock import Mock, patch
from rich.console import Console

from adoc_toolkit.cli.commands.get_command import GetCommand
from adoc_toolkit.models import APIReference, APIEndpoint


class TestPathParamsDemo:
    """Demonstration of path parameter functionality."""

    def setup_method(self):
        """Set up test fixtures."""
        self.http_client = Mock()
        self.command = GetCommand(http_client=self.http_client)

    def test_path_parameter_demo(self):
        """Demonstrate path parameter functionality."""
        # Mock API reference with path parameter configuration
        api_ref = APIReference(
            version="1.0",
            description="Demo API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={},
                    response_type="json"
                )
            }
        )

        # Mock successful API response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/catalog-server/api/assets/123/metadata"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"metadata": "test data"}
        mock_response.text = '{"metadata": "test data"}'
        self.http_client.get.return_value = mock_response

        with patch.object(self.command, '_load_api_reference', return_value=api_ref):
            with patch.object(self.command, '_prompt_for_missing_path_params', return_value={"asset-id": "123"}):
                with patch.object(self.command.console, 'print'):
                    with patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config'):
                        # Test 1: Direct path parameter specification
                        result = self.command.execute([
                            "/catalog-server/api/assets/:asset-id/metadata",
                            "asset-id=123"
                        ])
                        assert result is True
                        self.http_client.get.assert_called_with(
                            "/catalog-server/api/assets/123/metadata",
                            params={}
                        )

                        # Reset mock
                        self.http_client.get.reset_mock()

                        # Test 2: Interactive path parameter (simulated)
                        result = self.command.execute([
                            "/catalog-server/api/assets/:asset-id/metadata"
                        ])
                        assert result is True
                        self.http_client.get.assert_called_with(
                            "/catalog-server/api/assets/123/metadata",
                            params={}
                        )

    def test_multiple_path_parameters(self):
        """Demonstrate multiple path parameters."""
        # Mock API reference with multiple path parameters
        api_ref = APIReference(
            version="1.0",
            description="Demo API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/users/:user-id/permissions": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/users/:user-id/permissions",
                    description="Get user permissions for asset",
                    query_params={},
                    response_type="json"
                )
            }
        )

        # Mock successful API response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/catalog-server/api/assets/123/users/456/permissions"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"permissions": ["read", "write"]}
        mock_response.text = '{"permissions": ["read", "write"]}'
        self.http_client.get.return_value = mock_response

        with patch.object(self.command, '_load_api_reference', return_value=api_ref):
            with patch.object(self.command, '_prompt_for_missing_path_params', return_value={"asset-id": "123", "user-id": "456"}):
                with patch.object(self.command.console, 'print'):
                    with patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config'):
                        # Test with multiple path parameters
                        result = self.command.execute([
                            "/catalog-server/api/assets/:asset-id/users/:user-id/permissions",
                            "asset-id=123",
                            "user-id=456"
                        ])
                        assert result is True
                        self.http_client.get.assert_called_with(
                            "/catalog-server/api/assets/123/users/456/permissions",
                            params={}
                        )

    def test_path_parameters_with_query_parameters(self):
        """Demonstrate path parameters with query parameters."""
        # Mock API reference
        api_ref = APIReference(
            version="1.0",
            description="Demo API",
            endpoints={
                "/catalog-server/api/assets/:asset-id/metadata": APIEndpoint(
                    url="/catalog-server/api/assets/:asset-id/metadata",
                    description="Get metadata for a specific asset",
                    query_params={
                        "include_history": {
                            "type": "boolean",
                            "description": "Include history in response"
                        },
                        "format": {
                            "type": "string",
                            "description": "Response format",
                            "options": ["json", "xml"]
                        }
                    },
                    response_type="json"
                )
            }
        )

        # Mock successful API response
        mock_response = Mock()
        mock_response.is_success = True
        mock_response.status_code = 200
        mock_response.url = "/catalog-server/api/assets/123/metadata"
        mock_response.headers = {"content-type": "application/json"}
        mock_response.json.return_value = {"metadata": "test data"}
        mock_response.text = '{"metadata": "test data"}'
        self.http_client.get.return_value = mock_response

        with patch.object(self.command, '_load_api_reference', return_value=api_ref):
            with patch.object(self.command, '_prompt_for_missing_path_params', return_value={"asset-id": "123"}):
                with patch.object(self.command.console, 'print'):
                    with patch('adoc_toolkit.http.formatter.ResponseFormatter.print_response_with_config'):
                        # Test with both path and query parameters
                        result = self.command.execute([
                            "/catalog-server/api/assets/:asset-id/metadata",
                            "asset-id=123",
                            "include_history=true",
                            "format=json"
                        ])
                        assert result is True
                        self.http_client.get.assert_called_with(
                            "/catalog-server/api/assets/123/metadata",
                            params={"include_history": True, "format": "json"}
                        ) 