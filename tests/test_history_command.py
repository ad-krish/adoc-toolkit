"""Tests for history command."""

import json
import tempfile
from pathlib import Path
from typing import Any
from unittest.mock import patch

from adoc_toolkit.cli.commands.history_command import HistoryCommand
from adoc_toolkit.cli.interactive import InteractiveProcessor


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
    assert completions == []


def test_completions_with_empty_history() -> None:
    """Test completions with empty history."""

    def get_empty_history() -> list[str]:
        return []

    cmd = HistoryCommand(get_history_callback=get_empty_history)
    completions = cmd.get_completions("history ", 8)
    assert completions == []


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

    # Test partial matching for "1" should include "1", "10", "11"
    completions = cmd.get_completions("history 1", 9)
    matching_1 = [c for c in completions if c.startswith("1")]
    assert "1" in matching_1
    assert "10" in matching_1
    assert "11" in matching_1


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

    def _wait_for_keypress(self) -> None:
        """Override to avoid actual keypress waiting."""
        self.keypress_calls += 1


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

            assert data["version"] == "1.0"
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
