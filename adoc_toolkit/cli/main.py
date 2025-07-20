"""Main CLI entry point using Click."""

from typing import Optional

import click
from rich.console import Console

from .interactive import InteractiveProcessor


@click.group(invoke_without_command=True)
@click.option("--interactive", "-i", is_flag=True, help="Start interactive mode")
@click.option("--version", is_flag=True, help="Show version information")
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
@click.pass_context
def cli(
    ctx: click.Context, interactive: bool, version: bool, config: Optional[str]
) -> None:
    """ADOC Toolkit - AccelData Observability Cloud toolkit.

    A command-line toolkit for working with AccelData Observability Cloud.
    """
    console = Console()

    if version:
        from adoc_toolkit import __version__

        console.print(f"ADOC Toolkit version {__version__}")
        return

    if ctx.invoked_subcommand is None:
        if interactive:
            processor = InteractiveProcessor(config_file=config)
            processor.run()
        else:
            # Default behavior - show help and enter interactive mode
            console.print("ADOC Toolkit - AccelData Observability Cloud toolkit")
            console.print(
                "Starting interactive mode... (use --help for more options)\n"
            )
            processor = InteractiveProcessor(config_file=config)
            processor.run()


@cli.command()
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def interactive(config: Optional[str]) -> None:
    """Start interactive mode."""
    processor = InteractiveProcessor(config_file=config)
    processor.run()


@cli.command()
@click.argument("command", required=False)
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def help(command: Optional[str] = None, config: Optional[str] = None) -> None:
    """Show help for commands."""
    if command:
        # Show help for specific command
        processor = InteractiveProcessor(config_file=config)
        processor.execute_command("help", [command] if command else [])
    else:
        # Show general help
        ctx = click.get_current_context()
        click.echo(ctx.get_help())


def main() -> None:
    """Main entry point for the CLI."""
    cli()
