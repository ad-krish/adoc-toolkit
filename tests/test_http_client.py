"""Tests for HTTP client."""

import json
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
import pytest

from adoc_toolkit.http import ADOCHTTPClient, HTTPError, HTTPResponse


def test_http_response_properties():
    """Test HTTP response wrapper properties."""
    # Create a mock httpx response
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {"Content-Type": "application/json"}
    mock_response.text = "test response"
    mock_response.content = b"test response"
    mock_response.json.return_value = {"key": "value"}

    request_info = {"method": "GET", "url": "https://test.com/api"}

    response = HTTPResponse(mock_response, request_info)

    assert response.status_code == 200
    assert response.headers == {"Content-Type": "application/json"}
    assert response.text == "test response"
    assert response.content == b"test response"
    assert response.json() == {"key": "value"}
    assert response.is_success is True
    assert response.is_client_error is False
    assert response.is_server_error is False


def test_http_response_error_status_codes():
    """Test HTTP response status code classification."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.headers = {}
    request_info = {"method": "GET", "url": "http://test.com", "endpoint": "/test"}

    # Test client error (4xx)
    mock_response.status_code = 404
    response = HTTPResponse(mock_response, request_info)
    assert response.is_success is False
    assert response.is_client_error is True
    assert response.is_server_error is False

    # Test server error (5xx)
    mock_response.status_code = 500
    response = HTTPResponse(mock_response, request_info)
    assert response.is_success is False
    assert response.is_client_error is False
    assert response.is_server_error is True


def test_http_response_json_error():
    """Test HTTP response JSON parsing error."""
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.json.side_effect = json.JSONDecodeError("Invalid JSON", "", 0)

    response = HTTPResponse(
        mock_response, {"method": "GET", "url": "http://test.com", "endpoint": "/test"}
    )

    with pytest.raises(ValueError, match="Invalid JSON"):
        response.json()


def test_http_client_initialization():
    """Test HTTP client initialization."""
    env_callback = Mock()
    response_handler = Mock()

    client = ADOCHTTPClient(env_callback, response_handler)

    assert client.environment_info_callback == env_callback
    assert client.response_handler == response_handler


def test_build_headers_basic():
    """Test basic header building."""
    client = ADOCHTTPClient()
    headers = client._build_headers()

    assert headers["Content-Type"] == "application/json"
    assert headers["Accept"] == "application/json"
    assert "User-Agent" in headers


def test_build_headers_with_environment():
    """Test header building with environment authentication."""

    def mock_env_callback():
        return {"access_key": "test-access-key", "secret_key": "test-secret-key"}

    client = ADOCHTTPClient(environment_info_callback=mock_env_callback)
    headers = client._build_headers()

    assert headers["accessKey"] == "test-access-key"
    assert headers["secretKey"] == "test-secret-key"


def test_build_headers_with_additional():
    """Test header building with additional headers."""
    client = ADOCHTTPClient()
    additional = {"Custom-Header": "custom-value"}
    headers = client._build_headers(additional)

    assert headers["Custom-Header"] == "custom-value"
    assert headers["Content-Type"] == "application/json"


def test_build_url_success():
    """Test URL building with environment."""

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    client = ADOCHTTPClient(environment_info_callback=mock_env_callback)

    # Test with leading slash
    url = client._build_url("/test/endpoint")
    assert url == "https://api.example.com/test/endpoint"

    # Test without leading slash
    url = client._build_url("test/endpoint")
    assert url == "https://api.example.com/test/endpoint"

    # Test with trailing slash in base_url
    def mock_env_callback_trailing():
        return {"base_url": "https://api.example.com/"}

    client = ADOCHTTPClient(environment_info_callback=mock_env_callback_trailing)
    url = client._build_url("/test/endpoint")
    assert url == "https://api.example.com/test/endpoint"


def test_build_url_no_environment():
    """Test URL building without environment."""
    client = ADOCHTTPClient()

    with pytest.raises(HTTPError, match="No environment selected"):
        client._build_url("/test/endpoint")


def test_get_client_config():
    """Test getting HTTP client configuration."""
    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)
        config_manager = get_config_manager()
        config_manager.set("http.timeout", 90)
        config_manager.set("http.proxy", "https://proxy.example.com")

        client = ADOCHTTPClient()
        config = client._get_client_config()

        assert config["timeout"] == 90
        assert config["proxies"] == "https://proxy.example.com"


def test_prepare_data_dict():
    """Test data preparation with dictionary."""
    client = ADOCHTTPClient()

    data = {"key": "value", "number": 42}
    prepared = client._prepare_data(data)

    expected = json.dumps(data).encode("utf-8")
    assert prepared == expected


def test_prepare_data_string():
    """Test data preparation with string."""
    client = ADOCHTTPClient()

    data = "test string"
    prepared = client._prepare_data(data)

    assert prepared == b"test string"


def test_prepare_data_bytes():
    """Test data preparation with bytes."""
    client = ADOCHTTPClient()

    data = b"test bytes"
    prepared = client._prepare_data(data)

    assert prepared == b"test bytes"


def test_prepare_data_none():
    """Test data preparation with None."""
    client = ADOCHTTPClient()

    prepared = client._prepare_data(None)

    assert prepared is None


def test_prepare_data_file():
    """Test data preparation with file."""
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as temp_file:
        temp_file.write("test file content")
        temp_file.flush()

        client = ADOCHTTPClient()
        prepared = client._prepare_data(file_path=temp_file.name)

        assert prepared == b"test file content"

        # Clean up
        Path(temp_file.name).unlink()


def test_prepare_data_file_not_found():
    """Test data preparation with non-existent file."""
    client = ADOCHTTPClient()

    with pytest.raises(HTTPError, match="File not found"):
        client._prepare_data(file_path="/nonexistent/file.txt")


def test_prepare_data_both_data_and_file():
    """Test data preparation with both data and file specified."""
    client = ADOCHTTPClient()

    with pytest.raises(HTTPError, match="Cannot specify both data and file_path"):
        client._prepare_data(data="test", file_path="test.txt")


def test_prepare_data_unsupported_type():
    """Test data preparation with unsupported data type."""
    client = ADOCHTTPClient()

    with pytest.raises(HTTPError, match="Unsupported data type"):
        client._prepare_data(data=object())


@patch("adoc_toolkit.http.client.httpx.Client")
def test_make_request_success(mock_client_class):
    """Test successful HTTP request."""
    # Mock the httpx client and response
    mock_client = Mock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_response.text = "success"
    mock_client.request.return_value = mock_response

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    response_handler = Mock()
    client = ADOCHTTPClient(mock_env_callback, response_handler)

    response = client._make_request("GET", "/test")

    assert response.status_code == 200
    assert response.text == "success"
    assert response_handler.called


@patch("adoc_toolkit.http.client.httpx.Client")
def test_make_request_with_retries(mock_client_class):
    """Test HTTP request with retries on timeout."""
    # Mock the httpx client
    mock_client = Mock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # First two calls timeout, third succeeds
    mock_response = Mock(spec=httpx.Response)
    mock_response.status_code = 200
    mock_response.headers = {}
    mock_client.request.side_effect = [
        httpx.TimeoutException("Timeout 1"),
        httpx.TimeoutException("Timeout 2"),
        mock_response,
    ]

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)
        get_config_manager().set("http.retries", 3)

        client = ADOCHTTPClient(mock_env_callback)
        response = client._make_request("GET", "/test")

        assert response.status_code == 200
        assert mock_client.request.call_count == 3


@patch("adoc_toolkit.http.client.httpx.Client")
def test_make_request_all_retries_fail(mock_client_class):
    """Test HTTP request when all retries fail."""
    # Mock the httpx client
    mock_client = Mock()
    mock_client_class.return_value.__enter__.return_value = mock_client

    # All calls timeout
    mock_client.request.side_effect = httpx.TimeoutException("Timeout")

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    with tempfile.TemporaryDirectory() as temp_dir:
        config_file = Path(temp_dir) / "test-config.json"

        from adoc_toolkit.config import get_config_manager, reset_config_manager

        reset_config_manager(config_file)
        get_config_manager().set("http.retries", 2)

        client = ADOCHTTPClient(mock_env_callback)

        with pytest.raises(HTTPError, match="Request timeout"):
            client._make_request("GET", "/test")


def test_http_client_methods():
    """Test HTTP client method delegates."""

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    client = ADOCHTTPClient(mock_env_callback)

    with patch.object(client, "_make_request") as mock_make_request:
        mock_response = Mock()
        mock_make_request.return_value = mock_response

        # Test GET
        result = client.get("/test", headers={"X-Test": "test"}, params={"q": "query"})
        mock_make_request.assert_called_with(
            "GET", "/test", headers={"X-Test": "test"}, params={"q": "query"}
        )
        assert result == mock_response

        # Test POST
        result = client.post("/test", data={"key": "value"}, file_path="test.txt")
        mock_make_request.assert_called_with(
            "POST",
            "/test",
            data={"key": "value"},
            headers=None,
            file_path="test.txt",
            params=None,
        )
        assert result == mock_response

        # Test PUT
        result = client.put("/test", data="test data")
        mock_make_request.assert_called_with(
            "PUT", "/test", data="test data", headers=None, file_path=None, params=None
        )
        assert result == mock_response

        # Test DELETE
        result = client.delete("/test")
        mock_make_request.assert_called_with(
            "DELETE", "/test", headers=None, params=None
        )
        assert result == mock_response


def test_health_check_success():
    """Test successful health check."""

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    client = ADOCHTTPClient(mock_env_callback)

    with patch.object(client, "get") as mock_get:
        mock_response = Mock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        result = client.health_check()

        assert result is True
        mock_get.assert_called_with("/")


def test_health_check_failure():
    """Test failed health check."""

    def mock_env_callback():
        return {"base_url": "https://api.example.com"}

    client = ADOCHTTPClient(mock_env_callback)

    with patch.object(client, "get") as mock_get:
        mock_get.side_effect = HTTPError("Connection failed")

        result = client.health_check()

        assert result is False
