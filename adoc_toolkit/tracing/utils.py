"""Tracing utilities for command operations."""

import threading
from typing import Any

from ..logs import LogLevel, get_logger, trace_operation

# Thread-local storage for trace nesting
try:
    _trace_local = threading.local()
except Exception:
    # Fallback for test environments or other issues
    class MockLocal:
        def __init__(self):
            self.depth = 0

    _trace_local = MockLocal()


def get_trace_depth() -> int:
    """Get current trace nesting depth."""
    try:
        if not hasattr(_trace_local, "depth"):
            _trace_local.depth = 0
        return int(_trace_local.depth)
    except (AttributeError, TypeError, ValueError):
        return 0


def increment_trace_depth() -> None:
    """Increment trace nesting depth."""
    try:
        if not hasattr(_trace_local, "depth"):
            _trace_local.depth = 0
        _trace_local.depth = int(_trace_local.depth) + 1
    except (AttributeError, TypeError, ValueError):
        pass


def decrement_trace_depth() -> None:
    """Decrement trace nesting depth."""
    try:
        if not hasattr(_trace_local, "depth"):
            _trace_local.depth = 0
        elif int(_trace_local.depth) > 0:
            _trace_local.depth = int(_trace_local.depth) - 1
    except (AttributeError, TypeError, ValueError):
        pass


def reset_trace_depth() -> None:
    """Reset trace nesting depth to zero."""
    try:
        if hasattr(_trace_local, "depth"):
            _trace_local.depth = 0
    except (AttributeError, TypeError, ValueError):
        pass


def format_trace_message(
    operation: str, command_prefix: str | None = None, **details: Any
) -> tuple[str, dict[str, Any]]:
    """Format trace message with nesting indicators.

    Args:
        operation: The operation name to trace
        command_prefix: Optional command prefix (e.g., "export_metrics")
        **details: Additional details to include in trace

    Returns:
        Tuple of (formatted_message, trace_details)
    """
    depth = get_trace_depth()
    indent = "  " * depth

    # Add command prefix if provided
    if command_prefix:
        nested_operation = f"{indent}-> {command_prefix}.{operation}"
    else:
        nested_operation = f"{indent}-> {operation}"

    # Add trace depth to details
    trace_details = {"trace_depth": depth, **details}

    return nested_operation, trace_details


def trace_if_enabled(
    operation: str, command_prefix: str | None = None, **details: Any
) -> None:
    """Trace operation only if TRACE level is enabled.

    Args:
        operation: The operation name to trace
        command_prefix: Optional command prefix (e.g., "export_metrics")
        **details: Additional details to include in trace
    """
    logger = get_logger()
    if logger.is_level_enabled(LogLevel.TRACE):
        trace_msg, trace_details = format_trace_message(
            operation, command_prefix, **details
        )
        trace_operation(trace_msg, **trace_details)


def is_trace_enabled() -> bool:
    """Check if TRACE level is enabled.

    Returns:
        True if TRACE level is enabled, False otherwise
    """
    try:
        logger = get_logger()
        return logger.is_level_enabled(LogLevel.TRACE)
    except Exception:
        # If there's any issue with logging, disable tracing
        return False
