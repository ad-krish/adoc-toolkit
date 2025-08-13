"""Auditable mixin and decorators for easy audit logging integration."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from .audit_service import get_immutable_audit_logger

F = TypeVar("F", bound=Callable[..., Any])


class AuditableMixin:
    """Mixin class to add audit logging capabilities to any class."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        """Initialize auditable mixin."""
        super().__init__(*args, **kwargs)
        self._audit_user_id: str | None = None
        self._audit_ip_address: str | None = None

    def set_audit_context(
        self, user_id: str | None = None, ip_address: str | None = None
    ) -> None:
        """Set audit context for this instance.

        Args:
            user_id: User ID to use for audit logging
            ip_address: IP address to use for audit logging
        """
        self._audit_user_id = user_id
        self._audit_ip_address = ip_address

    def audit_operation(
        self,
        command_object: str,
        operation_type: str,
        details: dict[str, Any] | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an audit operation for this instance.

        Args:
            command_object: Command or object being accessed
            operation_type: Type of operation
            details: Additional operation details
            user_id: User ID (uses instance context if not provided)
            ip_address: IP address (uses instance context if not provided)
        """
        audit_logger = get_immutable_audit_logger()
        if not audit_logger.is_enabled():
            return

        # Use instance context if not explicitly provided
        effective_user_id = user_id or self._audit_user_id
        effective_ip_address = ip_address or self._audit_ip_address

        audit_logger.log_operation(
            command_object=command_object,
            operation_type=operation_type,
            details=details,
            user_id=effective_user_id,
            ip_address=effective_ip_address,
        )

    def audit_http_request(
        self,
        method: str,
        url: str,
        headers: dict[str, str] | None = None,
        user_id: str | None = None,
        ip_address: str | None = None,
    ) -> None:
        """Log an HTTP request audit entry for this instance.

        Args:
            method: HTTP method
            url: Request URL
            headers: Request headers
            user_id: User ID (uses instance context if not provided)
            ip_address: IP address (uses instance context if not provided)
        """
        audit_logger = get_immutable_audit_logger()
        if not audit_logger.is_enabled():
            return

        # Use instance context if not explicitly provided
        effective_user_id = user_id or self._audit_user_id
        effective_ip_address = ip_address or self._audit_ip_address

        audit_logger.log_http_request(
            method=method,
            url=url,
            headers=headers,
            user_id=effective_user_id,
            ip_address=effective_ip_address,
        )


def audit_operation(
    command_object: str,
    operation_type: str,
    details: dict[str, Any] | None = None,
    extract_args: bool = False,
) -> Callable[[F], F]:
    """Decorator to audit operations.

    Args:
        command_object: Command or object being accessed
        operation_type: Type of operation
        details: Additional operation details
        extract_args: Whether to extract function arguments as details

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            audit_logger = get_immutable_audit_logger()
            if not audit_logger.is_enabled():
                return func(*args, **kwargs)

            # Extract audit context from first argument if it's an AuditableMixin
            user_id = None
            ip_address = None
            if args and hasattr(args[0], '_audit_user_id'):
                user_id = args[0]._audit_user_id
                ip_address = args[0]._audit_ip_address

            # Extract additional details if requested
            audit_details = details or {}
            if extract_args:
                # Add function arguments to details
                audit_details["function_name"] = func.__name__
                audit_details["args"] = str(args)
                audit_details["kwargs"] = str(kwargs)

            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log successful operation
                audit_logger.log_operation(
                    command_object=command_object,
                    operation_type=operation_type,
                    details=audit_details,
                    user_id=user_id,
                    ip_address=ip_address,
                )
                
                return result
            except Exception as e:
                # Log failed operation
                audit_details["error"] = str(e)
                audit_logger.log_operation(
                    command_object=command_object,
                    operation_type=f"{operation_type}_failed",
                    details=audit_details,
                    user_id=user_id,
                    ip_address=ip_address,
                )
                raise

        return wrapper

    return decorator


def audit_http_request(extract_args: bool = True) -> Callable[[F], F]:
    """Decorator to audit HTTP requests.

    Args:
        extract_args: Whether to extract function arguments as details

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            audit_logger = get_immutable_audit_logger()
            if not audit_logger.is_enabled():
                return func(*args, **kwargs)

            # Extract audit context from first argument if it's an AuditableMixin
            user_id = None
            ip_address = None
            if args and hasattr(args[0], '_audit_user_id'):
                user_id = args[0]._audit_user_id
                ip_address = args[0]._audit_ip_address

            # Extract HTTP request details from arguments
            method = kwargs.get("method", "GET")
            url = kwargs.get("url", "")
            headers = kwargs.get("headers")

            # If not found in kwargs, try positional arguments
            if len(args) >= 1 and not args[0] is None and hasattr(args[0], '_audit_user_id'):
                # Skip self argument for mixin classes
                if len(args) >= 2:
                    method = str(args[1]) if args[1] is not None else method
                if len(args) >= 3:
                    url = str(args[2]) if args[2] is not None else url
                if len(args) >= 4:
                    headers = args[3] if args[3] is not None else headers
            else:
                # Regular function, first argument is method
                if len(args) >= 1:
                    method = str(args[0]) if args[0] is not None else method
                if len(args) >= 2:
                    url = str(args[1]) if args[1] is not None else url
                if len(args) >= 3:
                    headers = args[2] if args[2] is not None else headers

            # Extract additional details if requested
            audit_details = {}
            if extract_args:
                audit_details["function_name"] = func.__name__
                audit_details["args"] = str(args)
                audit_details["kwargs"] = str(kwargs)

            try:
                # Execute the function
                result = func(*args, **kwargs)
                
                # Log successful request
                audit_logger.log_http_request(
                    method=method,
                    url=url,
                    headers=headers,
                    details=audit_details,
                    user_id=user_id,
                    ip_address=ip_address,
                )
                
                return result
            except Exception as e:
                # Log failed request
                audit_details["error"] = str(e)
                audit_logger.log_http_request(
                    method=method,
                    url=url,
                    headers=headers,
                    details=audit_details,
                    user_id=user_id,
                    ip_address=ip_address,
                )
                raise

        return wrapper

    return decorator
