"""
Main CLI entry point using Click with functional programming principles.

This module provides the command-line interface for the ADOC Toolkit using Click.
The code is structured using functional programming principles:

- Pure functions with no side effects where possible
- Function composition to reduce code duplication
- Immutable data flow
- Single responsibility principle for each function

The CLI supports both interactive and non-interactive modes, with commands for:
- Version display
- Interactive shell
- Help system
- Configuration management

Example usage:
    $ adoc-toolkit --version
    $ adoc-toolkit --interactive
    $ adoc-toolkit help
    $ adoc-toolkit help <command>
"""

from typing import Optional, Callable
from functools import partial

import click
from rich.console import Console

from .interactive import InteractiveProcessor


def display_version() -> None:
    """
    Display version information - pure function.
    
    This is a pure function that imports the version and displays it
    using Rich console formatting. It has no side effects beyond
    the display operation.
    
    Example:
        >>> display_version()
        ADOC Toolkit version 0.1.0
    """
    from adoc_toolkit import __version__
    console = Console()
    console.print(f"ADOC Toolkit version {__version__}")


def create_processor(config: Optional[str]) -> InteractiveProcessor:
    """
    Create an InteractiveProcessor instance - pure function.
    
    This function creates and returns a new InteractiveProcessor instance
    with the specified configuration file. It's pure because it always
    returns the same result for the same input and has no side effects.
    
    Args:
        config: Optional path to configuration file
        
    Returns:
        InteractiveProcessor: A new processor instance
        
    Example:
        >>> processor = create_processor("/path/to/config.json")
        >>> isinstance(processor, InteractiveProcessor)
        True
    """
    return InteractiveProcessor(config_file=config)


def run_processor(config: Optional[str]) -> None:
    """
    Run the interactive processor - pure function.
    
    This function composes create_processor() with the run() method
    to create and immediately execute a processor. It demonstrates
    function composition in functional programming.
    
    Args:
        config: Optional path to configuration file
        
    Example:
        >>> run_processor("/path/to/config.json")
        # Starts interactive mode with specified config
    """
    create_processor(config).run()


def execute_help_command(command: str, config: Optional[str]) -> None:
    """
    Execute help command for specific command - pure function.
    
    Creates a processor and executes the help command for a specific
    command. The function handles the conditional list creation
    for the command arguments.
    
    Args:
        command: The command name to get help for
        config: Optional path to configuration file
        
    Example:
        >>> execute_help_command("get", "/path/to/config.json")
        # Shows help for the 'get' command
    """
    processor = create_processor(config)
    processor.execute_command("help", [command] if command else [])


def display_general_help() -> None:
    """
    Display general help - pure function.
    
    Uses Click's context to display the general help information
    for all available commands. This is a pure function that
    only performs the display operation.
    
    Example:
        >>> display_general_help()
        # Shows general CLI help
    """
    ctx = click.get_current_context()
    click.echo(ctx.get_help())


def handle_help_command(command: Optional[str], config: Optional[str]) -> None:
    """
    Handle help command logic - pure function.
    
    This function demonstrates conditional logic in functional programming.
    It routes to either specific command help or general help based on
    whether a command parameter is provided.
    
    Args:
        command: Optional command name for specific help
        config: Optional path to configuration file
        
    Example:
        >>> handle_help_command("get", None)
        # Shows help for 'get' command
        
        >>> handle_help_command(None, None)
        # Shows general help
    """
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
    """
    ADOC Toolkit - Acceldata Observability Cloud toolkit.

    A command-line toolkit for working with Acceldata Observability Cloud.
    
    This is the main CLI group that handles the root command and its options.
    The function demonstrates functional programming by:
    - Using pure functions for side effects (display_version, run_processor)
    - Eliminating code duplication between interactive and default modes
    - Maintaining immutable data flow
    
    Args:
        ctx: Click context for command execution
        interactive: Flag to explicitly start interactive mode
        version: Flag to display version information
        config: Optional path to configuration file
        
    Example:
        $ adoc-toolkit --version
        $ adoc-toolkit --interactive --config config.json
        $ adoc-toolkit  # Defaults to interactive mode
    """
    # Handle version display using pure function
    if version:
        display_version()
        return

    # Both interactive and default behavior are identical
    # This eliminates code duplication and simplifies logic
    if ctx.invoked_subcommand is None:
        run_processor(config)


@cli.command()
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def interactive(config: Optional[str]) -> None:
    """
    Start interactive mode.
    
    This command explicitly starts the interactive shell. It reuses
    the pure function run_processor() to maintain consistency and
    avoid code duplication.
    
    Args:
        config: Optional path to configuration file
        
    Example:
        $ adoc-toolkit interactive --config config.json
    """
    run_processor(config)


@cli.command()
@click.argument("command", required=False)
@click.option("--config", "-c", type=click.Path(), help="Path to configuration file")
def help(command: Optional[str] = None, config: Optional[str] = None) -> None:
    """
    Show help for commands.
    
    This command provides help functionality for the CLI. It can show
    either general help or help for a specific command. The function
    uses the pure function handle_help_command() to maintain separation
    of concerns.
    
    Args:
        command: Optional command name for specific help
        config: Optional path to configuration file
        
    Example:
        $ adoc-toolkit help
        $ adoc-toolkit help get
        $ adoc-toolkit help --config config.json
    """
    handle_help_command(command, config)


def main() -> None:
    """
    Main entry point for the CLI.
    
    This function serves as the entry point for the Click CLI application.
    It's kept simple and delegates all logic to the Click framework.
    
    Example:
        >>> main()
        # Starts the CLI application
    """
    cli()
