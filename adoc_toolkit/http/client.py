"""HTTP client for ADOC API interactions."""

import json
from pathlib import Path
from typing import Any, Callable, Optional, Union

import httpx
from pydantic import ValidationError
from rich.console import Console

from .exceptions import HTTPError
from .http_request_data import HTTPRequestData
from .response import HTTPResponse


# Lazy imports to avoid circular dependencies
def _get_config_manager():
    from ..config import get_config_manager

    return get_config_manager()


# Optional tracing functions with fallbacks
try:
    from ..logs import trace_error, trace_http_request
except ImportError:

    def trace_error(*args: Any, **kwargs: Any) -> None:
        pass

    def trace_http_request(*args: Any, **kwargs: Any) -> None:
        pass


# Optional audit mixin with fallback
try:
    from ..audit import AuditableMixin

    _AuditMixin = AuditableMixin
except ImportError:

    class _AuditMixin:
        def audit_http_request(self, *args: Any, **kwargs: Any) -> None:
            pass


class ADOCHTTPClient(_AuditMixin):
    """HTTP client for ADOC API interactions with environment integration.

    Includes audit logging capabilities.
    """

    def __init__(
        self,
        environment_info_callback: Optional[Callable[[], dict[str, Any]]] = None,
        response_handler: Optional[Callable[[HTTPResponse], Any]] = None,
    ):
        """Initialize ADOC HTTP client.

        Args:
            environment_info_callback: Callback to get current environment info
            response_handler: Optional callback to handle responses
        """
        super().__init__()
        self.environment_info_callback = environment_info_callback
        self.response_handler = response_handler
        self.console = Console()

    def _get_environment_info(self) -> dict[str, Any]:
        """Get current environment information.

        Returns:
            Environment info including base_url, access_key, secret_key
        """
        if self.environment_info_callback:
            env_data = self.environment_info_callback()
            if "name" in env_data and "base_url" in env_data:
                try:
                    from ..models import EnvironmentInfo

                    env_info = EnvironmentInfo(
                        name=env_data["name"],
                        base_url=env_data["base_url"],
                        access_key=env_data.get("access_key"),
                        secret_key=env_data.get("secret_key"),
                    )
                    return env_info.model_dump()
                except ValidationError as e:
                    raise HTTPError(f"Invalid environment configuration: {e}") from e
            return env_data
        return {}

    def _build_headers(
        self, additional_headers: Optional[dict[str, str]] = None
    ) -> dict[str, str]:
        """Build headers for the request.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Complete headers dictionary
        """
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "ADOC-Toolkit/1.0.0",
        }
        env_info = self._get_environment_info()
        access_key = env_info.get("access_key")
        secret_key = env_info.get("secret_key")
        if access_key:
            headers["accessKey"] = access_key
        if secret_key:
            headers["secretKey"] = secret_key
        if additional_headers:
            headers.update(additional_headers)
        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build complete URL from endpoint.

        Args:
            endpoint: API endpoint (with or without leading slash)

        Returns:
            Complete URL

        Raises:
            HTTPError: If no environment is set or base_url is missing
        """
        env_info = self._get_environment_info()
        base_url = env_info.get("base_url")
        if not base_url:
            raise HTTPError(
                "No environment selected. Use 'use <environment>' to set an "
                "environment."
            )
        if not endpoint.startswith("/"):
            endpoint = f"/{endpoint}"
        return f"{base_url.rstrip('/')}{endpoint}"

    def _get_client_config(self) -> dict[str, Any]:
        """Get HTTP client configuration.

        Returns:
            Configuration dictionary for httpx client
        """
        config_manager = _get_config_manager()
        config = {"timeout": config_manager.get("http.timeout") or 120}
        proxy = config_manager.get("http.proxy")
        if proxy:
            config["proxies"] = proxy
        return config

    def _load_file_content(self, file_path: str) -> bytes:
        """Load content from file.

        Args:
            file_path: Path to file to load

        Returns:
            File content as bytes

        Raises:
            HTTPError: If file cannot be read
        """
        try:
            path = Path(file_path)
            if not path.exists():
                raise HTTPError(f"File not found: {file_path}")
            return path.read_bytes()
        except OSError as e:
            raise HTTPError(f"Error reading file {file_path}: {e}") from e

    def _prepare_data(
        self,
        data: Optional[Union[dict[str, Any], str, bytes]] = None,
        file_path: Optional[str] = None,
    ) -> Optional[bytes]:
        """Prepare request data.

        Args:
            data: Request data (dict, str, or bytes)
            file_path: Path to file to use as request body

        Returns:
            Prepared request data as bytes

        Raises:
            HTTPError: If both data and file_path are provided or other data errors
        """
        if data is not None and file_path is not None:
            raise HTTPError("Cannot specify both data and file_path")
        if file_path:
            return self._load_file_content(file_path)
        if data is None:
            return None
        if isinstance(data, bytes):
            return data
        if isinstance(data, str):
            return data.encode("utf-8")
        if isinstance(data, dict):
            try:
                return json.dumps(data).encode("utf-8")
            except (TypeError, ValueError) as e:
                raise HTTPError(f"Error serializing JSON data: {e}") from e
        raise HTTPError(f"Unsupported data type: {type(data)}")

    def _make_request(
        self,
        method: str,
        endpoint: str,
        data: Optional[Union[dict[str, Any], str, bytes]] = None,
        headers: Optional[dict[str, str]] = None,
        file_path: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HTTPResponse:
        """Make HTTP request with retry logic.

        Args:
            method: HTTP method (GET, POST, PUT, DELETE)
            endpoint: API endpoint
            data: Request data
            headers: Additional headers
            file_path: Path to file for request body
            params: Query parameters

        Returns:
            HTTP response wrapper

        Raises:
            HTTPError: For various HTTP-related errors
        """
        try:
            request_data = HTTPRequestData(
                method=method,
                endpoint=endpoint,
                headers=headers,
                params=params,
                data=data,
                file_path=file_path,
            )
        except ValidationError as e:
            raise HTTPError(f"Invalid request data: {e}") from e

        url = self._build_url(request_data.endpoint)
        request_headers = self._build_headers(request_data.headers)
        prepared_data = self._prepare_data(request_data.data, request_data.file_path)
        client_config = self._get_client_config()
        retries = _get_config_manager().get("http.retries") or 3

        if request_data.file_path and prepared_data:
            path = Path(request_data.file_path)
            suffix = path.suffix.lower()
            if suffix == ".json":
                request_headers["Content-Type"] = "application/json"
            elif suffix in [".txt", ".log"]:
                request_headers["Content-Type"] = "text/plain"
            else:
                request_headers["Content-Type"] = "application/octet-stream"

        request_info = {
            "method": request_data.method,
            "url": url,
            "endpoint": request_data.endpoint,
            "retries_attempted": 0,
        }

        retryable_exceptions = (httpx.TimeoutException, httpx.ConnectError)

        with httpx.Client(**client_config) as client:
            last_exception: Optional[HTTPError] = None
            for attempt in range(retries + 1):
                request_info["retries_attempted"] = attempt
                try:
                    response = client.request(
                        method=request_data.method,
                        url=url,
                        content=prepared_data,
                        headers=request_headers,
                        params=request_data.params,
                    )
                    http_response = HTTPResponse(response, request_info)
                    self.audit_http_request(
                        method=request_data.method, url=url, headers=request_headers
                    )
                    trace_http_request(
                        method=request_data.method,
                        url=url,
                        status_code=response.status_code,
                        retries=attempt,
                    )
                    if self.response_handler:
                        try:
                            self.response_handler(http_response)
                        except Exception as e:
                            self.console.print(
                                f"Response handler error: {e}", style="yellow"
                            )
                    return http_response
                except retryable_exceptions as e:
                    error_type = (
                        "Timeout"
                        if isinstance(e, httpx.TimeoutException)
                        else "Connection"
                    )
                    last_exception = HTTPError(
                        f"Request {error_type.lower()} after "
                        f"{client_config['timeout']}s: {e}"
                        if error_type == "Timeout"
                        else f"Connection error: {e}"
                    )
                    trace_error(
                        f"HTTP {request_data.method} {url}",
                        f"{error_type}: {e}",
                        attempt=attempt,
                    )
                    if attempt < retries:
                        self.console.print(
                            f"{error_type} error, retrying... (attempt "
                            f"{attempt + 1}/{retries})",
                            style="yellow",
                        )
                        continue
                    raise last_exception from None
                except httpx.HTTPError as e:
                    last_exception = HTTPError(f"HTTP error: {e}")
                    trace_error(
                        f"HTTP {request_data.method} {url}",
                        f"HTTP error: {e}",
                        attempt=attempt,
                    )
                    raise last_exception from None
                except Exception as e:
                    last_exception = HTTPError(f"Unexpected error: {e}")
                    trace_error(
                        f"HTTP {request_data.method} {url}",
                        f"Unexpected: {e}",
                        attempt=attempt,
                    )
                    raise last_exception from None
            raise last_exception or HTTPError("Request failed after all retries")

    def get(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HTTPResponse:
        """Make GET request.

        Args:
            endpoint: API endpoint
            headers: Additional headers
            params: Query parameters

        Returns:
            HTTP response wrapper
        """
        return self._make_request("GET", endpoint, headers=headers, params=params)

    def post(
        self,
        endpoint: str,
        data: Optional[Union[dict[str, Any], str, bytes]] = None,
        headers: Optional[dict[str, str]] = None,
        file_path: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HTTPResponse:
        """Make POST request.

        Args:
            endpoint: API endpoint
            data: Request data
            headers: Additional headers
            file_path: Path to file for request body
            params: Query parameters

        Returns:
            HTTP response wrapper
        """
        return self._make_request(
            "POST",
            endpoint,
            data=data,
            headers=headers,
            file_path=file_path,
            params=params,
        )

    def put(
        self,
        endpoint: str,
        data: Optional[Union[dict[str, Any], str, bytes]] = None,
        headers: Optional[dict[str, str]] = None,
        file_path: Optional[str] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HTTPResponse:
        """Make PUT request.

        Args:
            endpoint: API endpoint
            data: Request data
            headers: Additional headers
            file_path: Path to file for request body
            params: Query parameters

        Returns:
            HTTP response wrapper
        """
        return self._make_request(
            "PUT",
            endpoint,
            data=data,
            headers=headers,
            file_path=file_path,
            params=params,
        )

    def delete(
        self,
        endpoint: str,
        headers: Optional[dict[str, str]] = None,
        params: Optional[dict[str, Any]] = None,
    ) -> HTTPResponse:
        """Make DELETE request.

        Args:
            endpoint: API endpoint
            headers: Additional headers
            params: Query parameters

        Returns:
            HTTP response wrapper
        """
        return self._make_request("DELETE", endpoint, headers=headers, params=params)

    def health_check(self) -> bool:
        """Perform basic health check against current environment.

        Returns:
            True if environment is reachable, False otherwise
        """
        try:
            response = self.get("/")
            return response.status_code < 500
        except HTTPError:
            return False
