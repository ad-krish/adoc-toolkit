"""Auditable mixin and decorators for easy audit logging integration."""

import functools
from collections.abc import Callable
from typing import Any, TypeVar

from .service import get_audit_logger

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
        audit_logger = get_audit_logger()
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
        audit_logger = get_audit_logger()
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
    """Decorator to automatically audit operations.

    Args:
        command_object: Command or object being accessed
        operation_type: Type of operation
        details: Additional operation details
        extract_args: Whether to extract method arguments into details

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            audit_logger = get_audit_logger()

            if audit_logger.is_enabled():
                audit_details = details.copy() if details else {}

                # Extract arguments if requested
                if extract_args:
                    # Get function argument names
                    import inspect

                    sig = inspect.signature(func)
                    bound_args = sig.bind(*args, **kwargs)
                    bound_args.apply_defaults()

                    # Add non-sensitive arguments to details
                    for param_name, param_value in bound_args.arguments.items():
                        if param_name not in (
                            "self",
                            "cls",
                            "password",
                            "secret",
                            "token",
                        ):
                            # Convert to string and limit length to avoid huge logs
                            str_value = str(param_value)
                            if len(str_value) > 100:
                                str_value = str_value[:97] + "..."
                            audit_details[param_name] = str_value

                # Check if first argument has audit context (AuditableMixin)
                user_id = None
                ip_address = None
                if args and hasattr(args[0], "_audit_user_id"):
                    user_id = args[0]._audit_user_id
                    ip_address = args[0]._audit_ip_address

                audit_logger.log_operation(
                    command_object=command_object,
                    operation_type=operation_type,
                    details=audit_details if audit_details else None,
                    user_id=user_id,
                    ip_address=ip_address,
                )

            return func(*args, **kwargs)

        return wrapper

    return decorator


def audit_http_request(extract_args: bool = True) -> Callable[[F], F]:
    """Decorator to automatically audit HTTP requests.

    Args:
        extract_args: Whether to extract method arguments for URL and headers

    Returns:
        Decorated function
    """

    def decorator(func: F) -> F:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            audit_logger = get_audit_logger()

            if audit_logger.is_enabled() and extract_args:
                # Extract HTTP request details from arguments
                import inspect

                sig = inspect.signature(func)
                bound_args = sig.bind(*args, **kwargs)
                bound_args.apply_defaults()

                # Look for HTTP-related arguments
                method = None
                url = None
                headers = None

                # Try to extract from common argument names
                for param_name, param_value in bound_args.arguments.items():
                    if param_name == "method":
                        method = param_value
                    elif param_name in ("url", "endpoint"):
                        url = param_value
                    elif param_name == "headers":
                        headers = param_value

                # If we have at least method info, log it
                if method:
                    # Check if first argument has audit context (AuditableMixin)
                    user_id = None
                    ip_address = None
                    if args and hasattr(args[0], "_audit_user_id"):
                        user_id = args[0]._audit_user_id
                        ip_address = args[0]._audit_ip_address

                    audit_logger.log_http_request(
                        method=method,
                        url=url or "unknown",
                        headers=headers,
                        user_id=user_id,
                        ip_address=ip_address,
                    )

            return func(*args, **kwargs)

        return wrapper

    return decorator
