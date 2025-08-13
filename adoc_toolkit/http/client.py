"""HTTP client for ADOC API interactions."""

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import aiohttp
from pydantic import ValidationError
from rich.console import Console

from .exceptions import HTTPError
from .http_request_data import HTTPRequestData
from .response import HTTPResponse


# Lazy imports to avoid circular dependencies
def _get_config_manager() -> Any:
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
        environment_info_callback: Callable[[], dict[str, Any]] | None = None,
        response_handler: Callable[[HTTPResponse], Any] | None = None,
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
        self._session: aiohttp.ClientSession | None = None

    async def __aenter__(self):
        """Async context manager entry."""
        await self._ensure_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def _ensure_session(self) -> None:
        """Ensure aiohttp session is available."""
        if self._session is None or self._session.closed:
            timeout = aiohttp.ClientTimeout(
                total=_get_config_manager().get("http.timeout") or 120,
                connect=_get_config_manager().get("http.connect_timeout") or 30
            )
            connector = aiohttp.TCPConnector(
                limit=_get_config_manager().get("http.connection_pool_size") or 100,
                limit_per_host=_get_config_manager().get("http.max_connections_per_host") or 10,
                ttl_dns_cache=_get_config_manager().get("http.dns_cache_ttl") or 300,
            )
            self._session = aiohttp.ClientSession(
                timeout=timeout,
                connector=connector,
                headers={
                    "User-Agent": "ADOC-Toolkit/1.0",
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }
            )

    async def close(self) -> None:
        """Close the HTTP client session."""
        if self._session and not self._session.closed:
            await self._session.close()

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
        self, additional_headers: dict[str, str] | None = None
    ) -> dict[str, str]:
        """Build headers for the request.

        Args:
            additional_headers: Additional headers to include

        Returns:
            Complete headers dictionary
        """
        headers = {
            "User-Agent": "ADOC-Toolkit/1.0",
            "Accept": "application/json",
        }

        # Add authentication headers if available
        env_info = self._get_environment_info()
        if env_info.get("access_key"):
            headers["X-API-Key"] = env_info["access_key"]
        if env_info.get("secret_key"):
            headers["X-API-Secret"] = env_info["secret_key"]

        # Add additional headers
        if additional_headers:
            headers.update(additional_headers)

        return headers

    def _build_url(self, endpoint: str) -> str:
        """Build full URL from endpoint.

        Args:
            endpoint: API endpoint path

        Returns:
            Complete URL with base URL

        Raises:
            HTTPError: If no environment is selected
        """
        env_info = self._get_environment_info()
        base_url = env_info.get("base_url")
        if not base_url:
            raise HTTPError("No environment selected. Use 'use <environment>' first.")

        # Ensure endpoint starts with /
        if not endpoint.startswith("/"):
            endpoint = "/" + endpoint

        # Combine base URL and endpoint
        return base_url.rstrip("/") + endpoint

    def _get_client_config(self) -> dict[str, Any]:
        """Get aiohttp client configuration.

        Returns:
            Client configuration dictionary
        """
        config_manager = _get_config_manager()
        return {
            "timeout": aiohttp.ClientTimeout(
                total=config_manager.get("http.timeout") or 120,
                connect=config_manager.get("http.connect_timeout") or 30
            ),
            "connector": aiohttp.TCPConnector(
                limit=config_manager.get("http.connection_pool_size") or 100,
                limit_per_host=config_manager.get("http.max_connections_per_host") or 10,
                ttl_dns_cache=config_manager.get("http.dns_cache_ttl") or 300,
            )
        }

    def _load_file_content(self, file_path: str) -> bytes:
        """Load file content for upload.

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
        except Exception as e:
            raise HTTPError(f"Error reading file {file_path}: {e}") from e

    def _prepare_data(
        self,
        data: dict[str, Any] | str | bytes | None = None,
        file_path: str | None = None,
    ) -> bytes | None:
        """Prepare request data.

        Args:
            data: Request data
            file_path: Path to file for request body

        Returns:
            Prepared request data as bytes

        Raises:
            HTTPError: If data cannot be prepared
        """
        if file_path:
            return self._load_file_content(file_path)
        elif data is None:
            return None
        elif isinstance(data, bytes):
            return data
        elif isinstance(data, str):
            return data.encode("utf-8")
        elif isinstance(data, dict):
            return json.dumps(data).encode("utf-8")
        else:
            raise HTTPError(f"Unsupported data type: {type(data)}")

    async def _make_request(
        self,
        method: str,
        endpoint: str,
        data: dict[str, Any] | str | bytes | None = None,
        headers: dict[str, str] | None = None,
        file_path: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """Make HTTP request.

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

        retryable_exceptions = (aiohttp.ClientError, aiohttp.ServerTimeoutError)

        await self._ensure_session()
        last_exception: HTTPError | None = None
        
        for attempt in range(retries + 1):
            request_info["retries_attempted"] = attempt
            try:
                async with self._session.request(
                    method=request_data.method,
                    url=url,
                    data=prepared_data,
                    headers=request_headers,
                    params=request_data.params,
                ) as response:
                    http_response = HTTPResponse(response, request_info)
                    self.audit_http_request(
                        method=request_data.method, url=url, headers=request_headers
                    )
                    trace_http_request(
                        method=request_data.method,
                        url=url,
                        status_code=response.status,
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
                last_exception = HTTPError(f"Request failed: {e}")
                if attempt < retries:
                    continue
                else:
                    raise last_exception
            except Exception as e:
                raise HTTPError(f"Unexpected error: {e}") from e

        raise last_exception or HTTPError("Request failed after all retries")

    async def get(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """Make GET request.

        Args:
            endpoint: API endpoint
            headers: Additional headers
            params: Query parameters

        Returns:
            HTTP response
        """
        return await self._make_request("GET", endpoint, headers=headers, params=params)

    async def post(
        self,
        endpoint: str,
        data: dict[str, Any] | str | bytes | None = None,
        headers: dict[str, str] | None = None,
        file_path: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """Make POST request.

        Args:
            endpoint: API endpoint
            data: Request data
            headers: Additional headers
            file_path: Path to file for request body
            params: Query parameters

        Returns:
            HTTP response
        """
        return await self._make_request(
            "POST", endpoint, data=data, headers=headers, file_path=file_path, params=params
        )

    async def put(
        self,
        endpoint: str,
        data: dict[str, Any] | str | bytes | None = None,
        headers: dict[str, str] | None = None,
        file_path: str | None = None,
        params: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """Make PUT request.

        Args:
            endpoint: API endpoint
            data: Request data
            headers: Additional headers
            file_path: Path to file for request body
            params: Query parameters

        Returns:
            HTTP response
        """
        return await self._make_request(
            "PUT", endpoint, data=data, headers=headers, file_path=file_path, params=params
        )

    async def delete(
        self,
        endpoint: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
    ) -> HTTPResponse:
        """Make DELETE request.

        Args:
            endpoint: API endpoint
            headers: Additional headers
            params: Query parameters

        Returns:
            HTTP response
        """
        return await self._make_request("DELETE", endpoint, headers=headers, params=params)

    async def health_check(self) -> bool:
        """Perform health check.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.get("/health")
            return response.is_success
        except Exception:
            return False
