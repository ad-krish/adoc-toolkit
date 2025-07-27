"""Main CLI entry point using Click."""

from typing import Optional, Callable
from functools import partial

import click
from rich.console import Console

from .interactive import InteractiveProcessor


def display_version() -> None:
    """Display version information - pure function."""
    from adoc_toolkit import __version__
    console = Console()
    console.print(f"ADOC Toolkit version {__version__}")


def create_processor(config: Optional[str]) -> InteractiveProcessor:
    """Create an InteractiveProcessor instance - pure function."""
    return InteractiveProcessor(config_file=config)


def run_processor(config: Optional[str]) -> None:
    """Run the interactive processor - pure function."""
    create_processor(config).run()


def execute_help_command(command: str, config: Optional[str]) -> None:
    """Execute help command for specific command - pure function."""
    processor = create_processor(config)
    processor.execute_command("help", [command] if command else [])


def display_general_help() -> None:
    """Display general help - pure function."""
    ctx = click.get_current_context()
    click.echo(ctx.get_help())


def handle_help_command(command: Optional[str], config: Optional[str]) -> None:
    """Handle help command logic - pure function."""
    if command:
        execute_help_command(command, config)
    else:
        display_general_help()


@click.group(invoke_without_command=True)
@click.option("--interactive", "-i", is_flag=True, help="Start interactive mode")
@click.option("--version", is_flag=True, help="Show version information")
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
@click.pass_context
def cli(
    ctx: click.Context, interactive: bool, version: bool, config: Optional[str]
) -> None:
    """ADOC Toolkit - Acceldata Observability Cloud toolkit.

    A command-line toolkit for working with Acceldata Observability Cloud.
    """
    if version:
        display_version()
        return

    if ctx.invoked_subcommand is None:
        # Both interactive and default behavior are identical
        run_processor(config)


@cli.command()
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def interactive(config: Optional[str]) -> None:
    """Start interactive mode."""
    run_processor(config)


@cli.command()
@click.argument("command", required=False)
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def help(command: Optional[str] = None, config: Optional[str] = None) -> None:
    """Show help for commands."""
    handle_help_command(command, config)


def main() -> None:
    """Main entry point for the CLI."""
    cli()
