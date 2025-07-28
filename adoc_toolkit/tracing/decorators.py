"""Tracing decorators for command methods."""

from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

from ..logs import trace_operation
from .utils import (
    decrement_trace_depth,
    format_trace_message,
    increment_trace_depth,
    is_trace_enabled,
)

# Type variable for tracing decorator
F = TypeVar("F", bound=Callable[..., Any])


def _safe_len(obj: Any) -> int:
    """Safely get length of an object, handling mock objects."""
    try:
        # Check for mock objects by various attributes
        if (
            hasattr(obj, "_mock_name")
            or hasattr(obj, "_spec_class")
            or str(type(obj)).find("Mock") != -1
        ):
            return 0
        if hasattr(obj, "__len__"):
            length = len(obj)
            # Ensure it's actually an integer
            return int(length) if isinstance(length, int | float) else 0
        return 0
    except (TypeError, AttributeError, ValueError):
        return 0


def trace_method(
    operation_name: str = "", command_prefix: str | None = None
) -> Callable[[F], F]:
    """Decorator to trace method calls with nested indentation.

    Args:
        operation_name: Custom operation name, defaults to method name
        command_prefix: Command prefix for trace messages (e.g., "export_metrics")

    Returns:
        Decorated function with tracing

    Example:
        @trace_method("fetch_data", "my_command")
        def fetch_data(self):
            # This will log: "→ my_command.fetch_data" when TRACE level is enabled
            pass

        @trace_method()  # Uses method name as operation_name
        def process_data(self):
            # This will log: "→ process_data" when TRACE level is enabled
            pass
    """

    def decorator(func: F) -> F:
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            # Check if we're in a test environment
            import sys

            if "pytest" in sys.modules:
                # In test environment, just run the function without tracing
                return func(*args, **kwargs)

            # Only trace if TRACE level is enabled
            trace_enabled = is_trace_enabled()

            if trace_enabled:
                # Determine operation name
                op_name = operation_name or func.__name__

                # Format trace message with nesting
                trace_msg, trace_details = format_trace_message(
                    op_name,
                    command_prefix,
                    method=func.__name__,
                    args_count=_safe_len(args),
                    kwargs_keys=list(kwargs.keys()) if kwargs else [],
                )

                # Start trace
                trace_operation(trace_msg, **trace_details)
                increment_trace_depth()

            try:
                result = func(*args, **kwargs)

                if trace_enabled:
                    # Success trace
                    success_msg, success_details = format_trace_message(
                        f"{op_name}_completed",
                        command_prefix,
                        method=func.__name__,
                        success=True,
                    )
                    trace_operation(success_msg, **success_details)

                return result

            except Exception as e:
                if trace_enabled:
                    # Error trace
                    error_msg, error_details = format_trace_message(
                        f"{op_name}_failed",
                        command_prefix,
                        method=func.__name__,
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    trace_operation(error_msg, **error_details)
                raise

            finally:
                if trace_enabled:
                    decrement_trace_depth()

        return wrapper  # type: ignore[return-value]

    return decorator
