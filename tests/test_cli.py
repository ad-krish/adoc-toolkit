"""Tests for CLI functionality."""

from click.testing import CliRunner

from adoc_toolkit.cli.main import cli


def test_cli_version() -> None:
    """Test version flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--version"])
    assert result.exit_code == 0
    assert "ADOC Toolkit version" in result.output


def test_cli_help() -> None:
    """Test help flag."""
    runner = CliRunner()
    result = runner.invoke(cli, ["--help"])
    assert result.exit_code == 0
    assert "ADOC Toolkit" in result.output
