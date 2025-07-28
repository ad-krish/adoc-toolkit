"""Tracing mixins for command classes."""

from typing import Any

from .utils import reset_trace_depth, trace_if_enabled


class TraceableMixin:
    """Mixin class that provides tracing capabilities to commands.

    Commands can inherit from this mixin to get easy access to tracing
    functionality without having to import and use tracing utilities directly.

    Example:
        class MyCommand(Command, TraceableMixin):
            @property
            def trace_prefix(self) -> str:
                return "my_command"

            def execute(self, args: list[str]) -> bool:
                self.trace("execution_started", args_count=len(args))
                # ... command logic ...
                self.trace("execution_completed", success=True)
                return True
    """

    @property
    def trace_prefix(self) -> str | None:
        """Get the trace prefix for this command.

        Commands should override this to provide a meaningful prefix
        for their trace messages (e.g., "export_metrics", "import_data").

        Returns:
            Command-specific prefix for trace messages, or None for no prefix
        """
        return None

    def trace(self, operation: str, **details: Any) -> None:
        """Trace an operation with optional details.

        Args:
            operation: The operation name to trace
            **details: Additional details to include in the trace

        Example:
            self.trace("data_processing_started", records_count=100)
            self.trace("validation_completed", errors_found=0)
        """
        # Check if we're in a test environment
        import sys

        if "pytest" in sys.modules:
            return  # Skip tracing in tests

        try:
            trace_if_enabled(operation, self.trace_prefix, **details)
        except Exception:
            pass  # Ignore tracing errors

    def trace_start(self, operation: str, **details: Any) -> None:
        """Trace the start of an operation.

        Convenience method that adds "_started" suffix to operation name.

        Args:
            operation: Base operation name
            **details: Additional details to include in the trace
        """
        self.trace(f"{operation}_started", **details)

    def trace_complete(self, operation: str, **details: Any) -> None:
        """Trace the completion of an operation.

        Convenience method that adds "_completed" suffix to operation name.

        Args:
            operation: Base operation name
            **details: Additional details to include in the trace
        """
        self.trace(f"{operation}_completed", success=True, **details)

    def trace_error(self, operation: str, error: Exception, **details: Any) -> None:
        """Trace an operation error.

        Convenience method that adds "_failed" suffix and error details.

        Args:
            operation: Base operation name
            error: The exception that occurred
            **details: Additional details to include in the trace
        """
        self.trace(
            f"{operation}_failed",
            error=str(error),
            error_type=type(error).__name__,
            **details,
        )

    def reset_trace(self) -> None:
        """Reset trace nesting depth to zero.

        Useful for commands that might want to reset tracing state
        between major operations or in error recovery scenarios.
        """
        reset_trace_depth()
