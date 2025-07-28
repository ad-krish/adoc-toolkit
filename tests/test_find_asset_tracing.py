"""Tests for find-asset command tracing functionality."""

from unittest.mock import Mock

from adoc_toolkit.cli.commands.find_asset_command import FindAssetCommand


class TestFindAssetTracing:
    """Test tracing functionality in FindAssetCommand."""

    def setup_method(self):
        """Set up test fixtures."""
        self.mock_http_client = Mock()
        self.command = FindAssetCommand(self.mock_http_client)

    def test_trace_prefix(self):
        """Test that the command has the correct trace prefix."""
        assert self.command.trace_prefix == "find_asset"

    def test_trace_methods_available(self):
        """Test that tracing methods are available."""
        assert hasattr(self.command, "trace")
        assert hasattr(self.command, "trace_start")
        assert hasattr(self.command, "trace_complete")
        assert hasattr(self.command, "trace_error")

    def test_trace_integration(self):
        """Test that tracing is properly integrated into the command."""
        # Verify that the command inherits from TraceableMixin
        from adoc_toolkit.tracing.mixins import TraceableMixin

        assert isinstance(self.command, TraceableMixin)

        # Verify that trace_prefix is properly set
        assert self.command.trace_prefix == "find_asset"

        # Verify that tracing methods are callable (they won't do anything in tests)
        self.command.trace("test_operation")
        self.command.trace_start("test_operation")
        self.command.trace_complete("test_operation")
        self.command.trace_error("test_operation", Exception("test error"))

        # If we get here without errors, the integration is working
        assert True

    def test_trace_method_signatures(self):
        """Test that tracing methods have the correct signatures."""
        import inspect

        # Check trace method signature
        trace_sig = inspect.signature(self.command.trace)
        assert "operation" in trace_sig.parameters
        assert (
            trace_sig.parameters["operation"].kind
            == inspect.Parameter.POSITIONAL_OR_KEYWORD
        )

        # Check trace_start method signature
        trace_start_sig = inspect.signature(self.command.trace_start)
        assert "operation" in trace_start_sig.parameters

        # Check trace_complete method signature
        trace_complete_sig = inspect.signature(self.command.trace_complete)
        assert "operation" in trace_complete_sig.parameters

        # Check trace_error method signature
        trace_error_sig = inspect.signature(self.command.trace_error)
        assert "operation" in trace_error_sig.parameters
        assert "error" in trace_error_sig.parameters
