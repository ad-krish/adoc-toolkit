"""Command system for ADOC toolkit interactive shell."""

# Import base Command class
from .base import Command

# Import all commands to make them available
from .example_command import ExampleCommand
from .exit_command import ExitCommand
from .export_execution_metrics_command import ExportExecutionMetricsCommand
from .export_metrics_command import ExportMetricsCommand
from .find_asset_command import FindAssetCommand
from .get_command import GetCommand
from .help_command import HelpCommand
from .history_command import HistoryCommand
from .set_config_command import SetConfigCommand
from .show_env_command import ShowEnvCommand
from .use_command import UseCommand

__all__ = [
    "Command",
    "ExampleCommand",
    "ExitCommand",
    "ExportExecutionMetricsCommand",
    "ExportMetricsCommand",
    "FindAssetCommand",
    "GetCommand",
    "HelpCommand",
    "HistoryCommand",
    "SetConfigCommand",
    "ShowEnvCommand",
    "UseCommand",
]
