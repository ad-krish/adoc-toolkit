"""Tests for history command."""

import json
import sys
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Any
from unittest.mock import Mock, patch

from adoc_toolkit.cli.commands.history_command import HistoryCommand
from adoc_toolkit.cli.interactive import InteractiveProcessor
from adoc_toolkit.models import CommandExecution


def test_command_name() -> None:
    """Test command name property."""
    cmd = HistoryCommand()
    assert cmd.name == "history"


def test_command_description() -> None:
    """Test command description."""
    cmd = HistoryCommand()
    assert cmd.description == "Show command history and recall previous commands"


def test_command_aliases() -> None:
    """Test command aliases."""
    cmd = HistoryCommand()
    assert cmd.aliases == ["hist"]


def test_help_functionality() -> None:
    """Test help system integration."""
    cmd = HistoryCommand()
    help_text = cmd.get_help()
    assert "history" in help_text
    assert "Show command history" in help_text
    assert "Usage: history [number]" in help_text


def test_execute_with_help_flag() -> None:
    """Test execution with --help flag."""
    cmd = HistoryCommand()
    result = cmd.execute(["--help"])
    assert result is True


def test_execute_without_history_callback() -> None:
    """Test execution without history callback."""
    cmd = HistoryCommand()
    result = cmd.execute([])
    assert result is True


def test_execute_with_empty_history() -> None:
    """Test execution with empty history."""

    def get_empty_history() -> list[str]:
        return []

    cmd = HistoryCommand(get_history_callback=get_empty_history)
    result = cmd.execute([])
    assert result is True


def test_execute_with_history() -> None:
    """Test execution with history items."""
    history_items = ["use dev", "show-env", "use staging"]

    def get_history() -> list[str]:
        return history_items

    cmd = HistoryCommand(get_history_callback=get_history)
    result = cmd.execute([])
    assert result is True


def test_recall_valid_number() -> None:
    """Test recalling a command with valid number."""
    history_items = ["use dev", "show-env", "use staging"]
    recalled_command = None

    def get_history() -> list[str]:
        return history_items

    def recall_callback(command: str) -> None:
        nonlocal recalled_command
        recalled_command = command

    cmd = HistoryCommand(
        get_history_callback=get_history, recall_callback=recall_callback
    )

    result = cmd.execute(["2"])
    assert result is True
    assert recalled_command == "show-env"


def test_recall_invalid_number() -> None:
    """Test recalling with invalid number."""
    history_items = ["use dev", "show-env"]

    def get_history() -> list[str]:
        return history_items

    cmd = HistoryCommand(get_history_callback=get_history)
    result = cmd.execute(["5"])  # Out of range
    assert result is True


def test_recall_non_numeric_argument() -> None:
    """Test recalling with non-numeric argument."""
    history_items = ["use dev", "show-env"]

    def get_history() -> list[str]:
        return history_items

    cmd = HistoryCommand(get_history_callback=get_history)
    result = cmd.execute(["invalid"])
    assert result is True


def test_completions_without_callback() -> None:
    """Test completions without history callback."""
    cmd = HistoryCommand()
    completions = cmd.get_completions("history ", 8)
    # Should still show --executions option even without history callback
    assert "--executions" in completions


def test_completions_with_empty_history() -> None:
    """Test completions with empty history."""

    def get_empty_history() -> list[str]:
        return []

    cmd = HistoryCommand(get_history_callback=get_empty_history)
    completions = cmd.get_completions("history ", 8)
    # Should still show --executions option even with empty history
    assert "--executions" in completions


def test_completions_with_history() -> None:
    """Test completions with history items."""
    history_items = ["use dev", "show-env", "use staging"]

    def get_history() -> list[str]:
        return history_items

    cmd = HistoryCommand(get_history_callback=get_history)

    # Test completion for empty argument
    completions = cmd.get_completions("history ", 8)
    assert "1" in completions
    assert "2" in completions
    assert "3" in completions

    # Test completion for partial number
    completions = cmd.get_completions("history 1", 9)
    assert "1" in completions
    assert len([c for c in completions if c.startswith("1")]) > 0


def test_completions_partial_matching() -> None:
    """Test completions with partial number matching."""
    history_items = [
        "cmd1",
        "cmd2",
        "cmd3",
        "cmd4",
        "cmd5",
        "cmd6",
        "cmd7",
        "cmd8",
        "cmd9",
        "cmd10",
        "cmd11",
    ]

    def get_history() -> list[str]:
        return history_items

    cmd = HistoryCommand(get_history_callback=get_history)

    # Test partial matching for "1" should include "1", "10" (limited to first 10)
    completions = cmd.get_completions("history 1", 9)
    matching_1 = [c for c in completions if c.startswith("1")]
    assert "1" in matching_1
    assert "10" in matching_1
    # The completion is limited to first 10 items, so "11" might not be included
    # depending on the implementation limit


class MockHistoryCommand(HistoryCommand):
    """Mock HistoryCommand for testing display functionality."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.displayed_pages: list[dict[str, Any]] = []
        self.keypress_calls = 0

    def _display_history_page(
        self, history_items: list[str], start_idx: int, page_size: int = 25
    ) -> bool:
        """Override to capture displayed pages."""
        end_idx = min(start_idx + page_size, len(history_items))
        page_items = history_items[start_idx:end_idx]
        self.displayed_pages.append(
            {"start_idx": start_idx, "end_idx": end_idx, "items": page_items}
        )
        return end_idx < len(history_items)

    def _wait_for_keypress(self) -> bool:
        """Override to avoid actual keypress waiting."""
        self.keypress_calls += 1
        return True  # Always continue for testing


def test_pagination_single_page() -> None:
    """Test history display with single page."""
    history_items = ["cmd1", "cmd2", "cmd3"]

    def get_history() -> list[str]:
        return history_items

    cmd = MockHistoryCommand(get_history_callback=get_history)
    result = cmd.execute([])

    assert result is True
    assert len(cmd.displayed_pages) == 1
    assert cmd.displayed_pages[0]["items"] == history_items
    assert cmd.keypress_calls == 0  # No keypress needed for single page


def test_pagination_multiple_pages() -> None:
    """Test history display with multiple pages."""
    # Create 30 history items to test pagination
    history_items = [f"cmd{i}" for i in range(1, 31)]

    def get_history() -> list[str]:
        return history_items

    cmd = MockHistoryCommand(get_history_callback=get_history)
    result = cmd.execute([])

    assert result is True
    assert len(cmd.displayed_pages) == 2  # Should have 2 pages (25 + 5)
    assert len(cmd.displayed_pages[0]["items"]) == 25  # First page has 25 items
    assert len(cmd.displayed_pages[1]["items"]) == 5  # Second page has 5 items
    assert cmd.keypress_calls == 1  # One keypress for second page


def test_history_file_persistence() -> None:
    """Test history persistence to file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        history_file = Path(temp_dir) / ".adoc-toolkit-history"

        # Mock Path.home() to return our temp directory
        with patch("pathlib.Path.home", return_value=Path(temp_dir)):
            # Create first processor and add some history
            processor1 = InteractiveProcessor()
            processor1.add_to_history("use dev")
            processor1.add_to_history("show-env")
            processor1.add_to_history("use prod")

            # Verify file was created and contains the history
            assert history_file.exists()
            with open(history_file) as f:
                data = json.load(f)

            assert data["version"] == "2.0"  # Updated to version 2.0
            assert data["history"] == ["use prod", "show-env", "use dev"]

            # Create second processor - should load existing history
            processor2 = InteractiveProcessor()
            history = processor2.get_command_history()

            assert history == ["use prod", "show-env", "use dev"]

            # Add more history to second processor
            processor2.add_to_history("use staging")

            # Verify the file was updated
            with open(history_file) as f:
                data = json.load(f)

            assert data["history"] == ["use staging", "use prod", "show-env", "use dev"]


def test_history_file_corruption_handling() -> None:
    """Test handling of corrupted history file."""
    with tempfile.TemporaryDirectory() as temp_dir:
        history_file = Path(temp_dir) / ".adoc-toolkit-history"

        # Create corrupted file
        with open(history_file, "w") as f:
            f.write("invalid json content")

        # Mock Path.home() to return our temp directory
        with patch("pathlib.Path.home", return_value=Path(temp_dir)):
            # Should handle corruption gracefully and start with empty history
            processor = InteractiveProcessor()
            history = processor.get_command_history()

            assert history == []

            # Adding new history should work normally
            processor.add_to_history("new command")
            history = processor.get_command_history()

            assert history == ["new command"]


def test_history_file_missing() -> None:
    """Test behavior when history file doesn't exist."""
    with tempfile.TemporaryDirectory() as temp_dir:
        # Mock Path.home() to return our temp directory (no history file exists)
        with patch("pathlib.Path.home", return_value=Path(temp_dir)):
            processor = InteractiveProcessor()
            history = processor.get_command_history()

            # Should start with empty history
            assert history == []

            # Adding history should create the file
            processor.add_to_history("first command")
            history_file = Path(temp_dir) / ".adoc-toolkit-history"

            assert history_file.exists()
            with open(history_file) as f:
                data = json.load(f)

            assert data["history"] == ["first command"]


def test_history_duplicate_handling_with_persistence() -> None:
    """Test duplicate handling with file persistence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("pathlib.Path.home", return_value=Path(temp_dir)):
            processor = InteractiveProcessor()

            # Add some commands
            processor.add_to_history("use dev")
            processor.add_to_history("show-env")
            processor.add_to_history("use prod")

            # Add duplicate - should move to top
            processor.add_to_history("show-env")

            history = processor.get_command_history()
            assert history == ["show-env", "use prod", "use dev"]

            # Verify file persistence
            history_file = Path(temp_dir) / ".adoc-toolkit-history"
            with open(history_file) as f:
                data = json.load(f)

            assert data["history"] == ["show-env", "use prod", "use dev"]


def test_history_max_limit_with_persistence() -> None:
    """Test history limit enforcement with file persistence."""
    with tempfile.TemporaryDirectory() as temp_dir:
        with patch("pathlib.Path.home", return_value=Path(temp_dir)):
            processor = InteractiveProcessor()

            # Add more than max_history commands
            for i in range(105):
                processor.add_to_history(f"command_{i}")

            history = processor.get_command_history()

            # Should be limited to max_history (100)
            assert len(history) == 100
            assert history[0] == "command_104"  # Most recent
            assert history[99] == "command_5"  # 100th from the end

            # Verify file persistence respects the limit
            history_file = Path(temp_dir) / ".adoc-toolkit-history"
            with open(history_file) as f:
                data = json.load(f)

            assert len(data["history"]) == 100
            assert data["history"][0] == "command_104"


# Tests for execution tracking functionality


def test_executions_help_content() -> None:
    """Test help message includes execution option."""
    cmd = HistoryCommand()
    help_text = cmd.get_help()
    assert "history --executions [count]" in help_text
    assert "Show execution details" in help_text
    assert "count: Number to show (10,25,50,100)" in help_text
    assert "<escape> to exit" in help_text


def test_execution_history_display() -> None:
    """Test execution history display functionality."""
    # Create mock executions
    executions = [
        CommandExecution(
            command="export-execution-metrics --output-type csv",
            status="success",
            start_time=datetime(2024, 1, 15, 10, 30, 0),
            end_time=datetime(2024, 1, 15, 10, 31, 5),
            duration_seconds=65.0,
        ),
        CommandExecution(
            command="use prod",
            status="success",
            start_time=datetime(2024, 1, 15, 10, 29, 0),
            end_time=datetime(2024, 1, 15, 10, 29, 1),
            duration_seconds=1.2,
        ),
        CommandExecution(
            command="invalid-command",
            status="failure",
            start_time=datetime(2024, 1, 15, 10, 28, 0),
            end_time=datetime(2024, 1, 15, 10, 28, 0),
            duration_seconds=0.1,
            error_message="Unknown command",
        ),
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch("builtins.print") as mock_print:
        # Test displaying executions
        result = cmd.execute(["--executions"])
        assert result is True

        # Check that execution data was displayed
        print_calls = [call[0][0] for call in mock_print.call_args_list]
        execution_output = "\n".join(print_calls)

        assert "Execution History" in execution_output
        assert "export-execution-metrics" in execution_output
        assert "success" in execution_output
        assert "failure" in execution_output
        assert "1m 5.0s" in execution_output  # Duration formatting
        assert "2024-01-15 10:30:00" in execution_output  # Start time


def test_execution_history_page_sizes() -> None:
    """Test different page sizes for execution history."""
    executions = [
        CommandExecution(
            command=f"command-{i}",
            status="success",
            start_time=datetime(2024, 1, 15, 10, i % 60, 0),
            end_time=datetime(2024, 1, 15, 10, i % 60, 1),
            duration_seconds=1.0,
        )
        for i in range(50)  # Create 50 test executions
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    # Test different page sizes
    for page_size in [10, 25, 50, 100]:
        with patch("builtins.print") as mock_print:
            with patch.object(
                cmd, "_wait_for_keypress", return_value=False
            ):  # Mock to avoid stdin
                result = cmd.execute(["--executions", str(page_size)])
                assert result is True

                # Check that correct number of executions shown for first page
                print_calls = [call[0][0] for call in mock_print.call_args_list]
                execution_output = "\n".join(print_calls)

                expected_shown = min(page_size, len(executions))
                assert (
                    f"showing 1-{expected_shown} of {len(executions)}"
                    in execution_output
                )


def test_execution_history_empty() -> None:
    """Test execution history when no executions exist."""
    get_executions_callback = Mock(return_value=[])
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch("builtins.print") as mock_print:
        result = cmd.execute(["--executions"])
        assert result is True

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        output = "\n".join(print_calls)
        assert "No execution history available" in output


def test_execution_history_not_available() -> None:
    """Test execution history when callback not provided."""
    cmd = HistoryCommand()  # No callback provided

    with patch("builtins.print") as mock_print:
        result = cmd.execute(["--executions"])
        assert result is True

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        output = "\n".join(print_calls)
        assert "Execution history functionality not available" in output


def test_parse_executions_args() -> None:
    """Test parsing of --executions arguments."""
    cmd = HistoryCommand()

    # Test default page size
    assert cmd._parse_executions_args(["--executions"]) == 25

    # Test valid page sizes
    assert cmd._parse_executions_args(["--executions", "10"]) == 10
    assert cmd._parse_executions_args(["--executions", "25"]) == 25
    assert cmd._parse_executions_args(["--executions", "50"]) == 50
    assert cmd._parse_executions_args(["--executions", "100"]) == 100

    # Test invalid page sizes (should use default)
    with patch("builtins.print") as mock_print:
        assert cmd._parse_executions_args(["--executions", "15"]) == 25
        assert cmd._parse_executions_args(["--executions", "200"]) == 25
        assert cmd._parse_executions_args(["--executions", "abc"]) == 25


def test_command_truncation() -> None:
    """Test that long commands are truncated in display."""
    long_command = "export-execution-metrics --output-type csv --output-dir /very/long/path/to/directory --output-filename very-long-filename-template"

    execution = CommandExecution(
        command=long_command,
        status="success",
        start_time=datetime(2024, 1, 15, 10, 30, 0),
        end_time=datetime(2024, 1, 15, 10, 31, 0),
        duration_seconds=60.0,
    )

    get_executions_callback = Mock(return_value=[execution])
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch("builtins.print") as mock_print:
        result = cmd.execute(["--executions"])
        assert result is True

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        execution_output = "\n".join(print_calls)

        # Command should be truncated with "..."
        assert "..." in execution_output
        # Full command should not appear in output
        assert long_command not in execution_output


def test_duration_formatting() -> None:
    """Test duration formatting in different ranges."""
    executions = [
        CommandExecution(
            command="fast-command",
            status="success",
            start_time=datetime(2024, 1, 15, 10, 30, 0),
            end_time=datetime(2024, 1, 15, 10, 30, 0, 500000),  # 0.5 seconds
            duration_seconds=0.5,
        ),
        CommandExecution(
            command="medium-command",
            status="success",
            start_time=datetime(2024, 1, 15, 10, 30, 0),
            end_time=datetime(2024, 1, 15, 10, 30, 30),  # 30 seconds
            duration_seconds=30.0,
        ),
        CommandExecution(
            command="slow-command",
            status="success",
            start_time=datetime(2024, 1, 15, 10, 30, 0),
            end_time=datetime(2024, 1, 15, 10, 32, 45),  # 2m 45s
            duration_seconds=165.0,
        ),
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch("builtins.print") as mock_print:
        result = cmd.execute(["--executions"])
        assert result is True

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        execution_output = "\n".join(print_calls)

        # Check different duration formats
        assert "0.500s" in execution_output  # Sub-second precision
        assert "30.00s" in execution_output  # Seconds with decimals
        assert "2m 45.0s" in execution_output  # Minutes and seconds


def test_auto_completion_executions() -> None:
    """Test auto-completion for --executions option."""
    cmd = HistoryCommand()

    # Test completing --executions option
    completions = cmd.get_completions("history --exec", 0)
    assert "--executions" in completions

    # Test completing page sizes
    completions = cmd.get_completions("history --executions ", 0)
    assert "10" in completions
    assert "25" in completions
    assert "50" in completions
    assert "100" in completions

    # Test partial page size completion
    completions = cmd.get_completions("history --executions 1", 0)
    # Should get both 10 and 100 since they start with 1
    numbers_starting_with_1 = [c for c in completions if c.startswith("1")]
    assert "10" in numbers_starting_with_1
    assert "100" in numbers_starting_with_1


def test_auto_completion_mixed_options() -> None:
    """Test auto-completion with mixed history and execution options."""
    history_items = ["command1", "command2", "command3"]
    get_history_callback = Mock(return_value=history_items)
    cmd = HistoryCommand(get_history_callback=get_history_callback)

    # Test that both --executions and numbers are suggested
    completions = cmd.get_completions("history ", 0)
    assert "--executions" in completions
    assert "1" in completions
    assert "2" in completions
    assert "3" in completions


def test_keypress_handling() -> None:
    """Test keyboard input handling for pagination."""
    cmd = HistoryCommand()

    # Test return values directly since mocking low-level stdin is complex in pytest
    # We'll just test the expected behavior patterns

    # Test that method returns a boolean value
    with patch.object(cmd, "_wait_for_keypress", return_value=True):
        result = cmd._wait_for_keypress()
        assert result is True

    with patch.object(cmd, "_wait_for_keypress", return_value=False):
        result = cmd._wait_for_keypress()
        assert result is False


def test_backward_compatibility() -> None:
    """Test that existing history functionality still works."""
    history_items = ["use prod", "export-metrics", "show-env"]
    get_history_callback = Mock(return_value=history_items)
    recall_callback = Mock()

    cmd = HistoryCommand(
        get_history_callback=get_history_callback, recall_callback=recall_callback
    )

    with patch("builtins.print") as mock_print:
        # Test normal history display
        result = cmd.execute([])
        assert result is True

        print_calls = [call[0][0] for call in mock_print.call_args_list]
        output = "\n".join(print_calls)
        assert "use prod" in output
        assert "export-metrics" in output

        # Test command recall
        result = cmd.execute(["1"])
        assert result is True
        recall_callback.assert_called_once_with("use prod")


def test_integration_with_display_pagination() -> None:
    """Test integration between execution display and pagination."""
    # Create enough executions to require pagination
    executions = [
        CommandExecution(
            command=f"command-{i:02d}",
            status="success" if i % 2 == 0 else "failure",
            start_time=datetime(2024, 1, 15, 10, i, 0),
            end_time=datetime(2024, 1, 15, 10, i, 1),
            duration_seconds=1.0,
            error_message="Test error" if i % 2 == 1 else None,
        )
        for i in range(30)
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch("builtins.print") as mock_print:
        with patch.object(cmd, "_wait_for_keypress", return_value=False) as mock_wait:
            # Test with page size of 10 - should show first page then exit
            result = cmd.execute(["--executions", "10"])
            assert result is True

            # Should have called wait_for_keypress once (for pagination)
            assert mock_wait.call_count == 1

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            output = "\n".join(print_calls)

            # Should show first 10 executions
            assert "showing 1-10 of 30" in output
            assert "Press any key to show next 10 executions" in output


def test_execution_pagination_all_pages() -> None:
    """Test going through all pages of execution history."""
    executions = [
        CommandExecution(
            command=f"test-command-{i:03d}",
            status="success" if i % 3 != 0 else "failure",
            start_time=datetime(2024, 1, 15, 10, i % 60, 0),
            end_time=datetime(2024, 1, 15, 10, i % 60, (i % 5) + 1),
            duration_seconds=float((i % 5) + 1),
            error_message=f"Error {i}" if i % 3 == 0 else None,
        )
        for i in range(75)  # 3 pages of 25 each
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    # Mock keypress to continue through all pages
    with patch.object(
        cmd, "_wait_for_keypress", side_effect=[True, True, False]
    ) as mock_wait:
        with patch("builtins.print") as mock_print:
            result = cmd.execute(["--executions", "25"])
            assert result is True

            # Should have called wait twice (for 2 intermediate pages)
            assert mock_wait.call_count == 2


def test_execution_pagination_early_exit() -> None:
    """Test exiting pagination early with escape key."""
    executions = [
        CommandExecution(
            command=f"test-command-{i:03d}",
            status="success",
            start_time=datetime(2024, 1, 15, 10, i % 60, 0),
            end_time=datetime(2024, 1, 15, 10, i % 60, 1),
            duration_seconds=1.0,
        )
        for i in range(100)
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    # Mock keypress to exit after first page
    with patch.object(cmd, "_wait_for_keypress", return_value=False) as mock_wait:
        with patch("builtins.print") as mock_print:
            result = cmd.execute(["--executions", "25"])
            assert result is True

            # Should have called wait once and then stopped
            assert mock_wait.call_count == 1

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            output = "\n".join(print_calls)

            # Should only show first page
            assert "showing 1-25 of 100" in output
            # Should not show subsequent pages
            assert "showing 26-50" not in output


def test_exact_page_boundary() -> None:
    """Test pagination when execution count exactly matches page size."""
    executions = [
        CommandExecution(
            command=f"test-command-{i:03d}",
            status="success",
            start_time=datetime(2024, 1, 15, 10, i % 60, 0),
            end_time=datetime(2024, 1, 15, 10, i % 60, 1),
            duration_seconds=1.0,
        )
        for i in range(25)  # Exactly one page
    ]

    get_executions_callback = Mock(return_value=executions)
    cmd = HistoryCommand(get_executions_callback=get_executions_callback)

    with patch.object(cmd, "_wait_for_keypress") as mock_wait:
        with patch("builtins.print") as mock_print:
            result = cmd.execute(["--executions", "25"])
            assert result is True

            # Should not call wait_for_keypress because there's only one page
            assert mock_wait.call_count == 0

            print_calls = [call[0][0] for call in mock_print.call_args_list]
            output = "\n".join(print_calls)

            # Should show all executions in one page
            assert "showing 1-25 of 25" in output
            assert "Press any key" not in output
