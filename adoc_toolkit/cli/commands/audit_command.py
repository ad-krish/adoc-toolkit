"""Audit command implementation for managing immutable blockchain audit logging."""

from typing import Any
from rich.console import Console
from rich.table import Table
from rich.panel import Panel

from ...config import get_config_manager
from ...audit.audit_service import get_immutable_audit_logger
from ...models import CompletionItem
from .base import Command


class AuditCommand(Command):
    """Command to manage and query immutable blockchain audit logging."""

    def __init__(self) -> None:
        """Initialize audit command."""
        super().__init__()
        self.console = Console()

    @property
    def name(self) -> str:
        """Get command name."""
        return "audit"

    @property
    def description(self) -> str:
        """Get command description."""
        return "Manage and query secure audit logging"

    @property
    def aliases(self) -> list[str]:
        """Get command aliases."""
        return ["audit-log", "secure-audit"]

    def get_help(self) -> str:
        """Get detailed help for audit command."""
        help_text = f"{self.name}: {self.description}\n"
        help_text += "Usage: audit <subcommand> [options]\n\n"
        
        help_text += "Subcommands:\n"
        help_text += "  status          - Show audit system status\n"
        help_text += "  info            - Show audit log information\n"
        help_text += "  verify          - Verify audit log integrity\n"
        help_text += "  logs            - Query audit logs (use --help for options)\n"
        help_text += "  enable          - Enable secure audit logging\n"
        help_text += "  disable         - Disable secure audit logging\n"
        help_text += "  reconfigure     - Reconfigure audit system\n\n"
        
        help_text += "Log Query Options (for 'audit logs'):\n"
        help_text += "  --user <user_id>     - Filter by user ID\n"
        help_text += "  --operation <op>     - Filter by operation type\n"
        help_text += "  --resource <res>     - Filter by resource\n"
        help_text += "  --limit <number>     - Limit number of results (default: 100)\n\n"
        
        help_text += "Examples:\n"
        help_text += "  audit status\n"
        help_text += "  audit info\n"
        help_text += "  audit verify\n"
        help_text += "  audit logs\n"
        help_text += "  audit logs --user john.doe --limit 10\n"
        help_text += "  audit logs --operation authentication\n"
        help_text += "  audit enable\n"
        help_text += "  audit disable\n"
        help_text += "  audit reconfigure\n"
        
        return help_text

    def execute(self, args: list[str]) -> bool:
        """Execute the audit command.

        Args:
            args: Command arguments

        Returns:
            True to continue interactive mode
        """
        if not args:
            self.console.print("Usage: audit <subcommand> [options]", style="yellow")
            self.console.print("Use 'audit --help' for more information.", style="yellow")
            return True

        subcommand = args[0].lower()

        if subcommand == "status":
            return self._show_status()
        elif subcommand == "info":
            return self._show_info()
        elif subcommand == "verify":
            return self._verify_integrity()
        elif subcommand == "logs":
            return self._query_logs(args[1:])
        elif subcommand == "enable":
            return self._enable_audit()
        elif subcommand == "disable":
            return self._disable_audit()
        elif subcommand == "reconfigure":
            return self._reconfigure_audit()
        elif subcommand in ["--help", "-h", "help"]:
            self.console.print(self.get_help())
            return True
        else:
            self.console.print(f"Unknown subcommand: {subcommand}", style="red")
            self.console.print("Use 'audit --help' for available subcommands.", style="yellow")
            return True

    def _show_status(self) -> bool:
        """Show audit system status."""
        audit_logger = get_immutable_audit_logger()
        config_manager = get_config_manager()

        # Create status table
        table = Table(title="[bold cyan]Audit System Status[/bold cyan]")
        table.add_column("Component", style="cyan", width=25)
        table.add_column("Status", style="white", width=15)
        table.add_column("Details", style="green", width=40)

        # Blockchain logging status
        blockchain_enabled = config_manager.get("audit.log.enabled")
        blockchain_status = "Enabled" if blockchain_enabled else "Disabled"
        blockchain_details = "Immutable blockchain audit log"
        table.add_row("Blockchain Log", blockchain_status, blockchain_details)

        # Audit Log status
        log_enabled = config_manager.get("audit.log.enabled")
        log_status = "Enabled" if log_enabled else "Disabled"
        log_details = "Secure audit log (tamper-proof)"
        table.add_row("Audit Log", log_status, log_details)

        # Overall status
        overall_enabled = audit_logger.is_enabled()
        overall_status = "Active" if overall_enabled else "Inactive"
        overall_details = "Audit system is operational" if overall_enabled else "No audit logging configured"
        table.add_row("Overall System", overall_status, overall_details)

        self.console.print(table)
        return True

    def _show_info(self) -> bool:
        """Show blockchain information."""
        audit_logger = get_immutable_audit_logger()
        info = audit_logger.get_blockchain_info()

        if not info.get("enabled"):
            self.console.print("Audit logging is not enabled.", style="yellow")
            self.console.print("Use 'set-config audit.log.enabled true' to enable it.", style="blue")
            return True

        # Create info table
        table = Table(title="[bold cyan]Blockchain Audit Information[/bold cyan]")
        table.add_column("Property", style="cyan", width=25)
        table.add_column("Value", style="white", width=40)

        if "error" in info:
            table.add_row("Status", "[red]Error[/red]")
            table.add_row("Error", info["error"])
        else:
            table.add_row("Status", "[green]Active[/green]")
            table.add_row("Total Blocks", str(info.get("total_blocks", 0)))
            table.add_row("Last Block Hash", info.get("last_block_hash", "N/A")[:16] + "...")
            table.add_row("Integrity Verified", "Yes" if info.get("integrity_verified") else "No")
            table.add_row("Difficulty", str(info.get("difficulty", "N/A")))
            table.add_row("Database Path", info.get("database_path", "N/A"))

        self.console.print(table)
        return True

    def _verify_integrity(self) -> bool:
        """Verify blockchain integrity."""
        audit_logger = get_immutable_audit_logger()
        result = audit_logger.verify_blockchain_integrity()

        if not result.get("enabled"):
            self.console.print("Audit logging is not enabled.", style="yellow")
            return True

        if "error" in result:
            self.console.print(f"[red]Error verifying integrity: {result['error']}[/red]")
            return True

        if result.get("integrity_verified"):
            self.console.print("[green]✅ Blockchain integrity verified[/green]")
            self.console.print(f"[green]{result['message']}[/green]")
        else:
            self.console.print("[red]❌ Blockchain integrity compromised[/red]")
            self.console.print(f"[red]{result['message']}[/red]")

        return True

    def _query_logs(self, args: list[str]) -> bool:
        """Query audit logs."""
        audit_logger = get_immutable_audit_logger()

        # Parse arguments
        user_id = None
        operation = None
        resource = None
        limit = 100

        i = 0
        while i < len(args):
            if args[i] == "--user" and i + 1 < len(args):
                user_id = args[i + 1]
                i += 2
            elif args[i] == "--operation" and i + 1 < len(args):
                operation = args[i + 1]
                i += 2
            elif args[i] == "--resource" and i + 1 < len(args):
                resource = args[i + 1]
                i += 2
            elif args[i] == "--limit" and i + 1 < len(args):
                try:
                    limit = int(args[i + 1])
                except ValueError:
                    self.console.print("Invalid limit value. Using default of 100.", style="yellow")
                i += 2
            else:
                i += 1

        # Get logs
        logs = audit_logger.get_blockchain_logs(
            user_id=user_id,
            operation=operation,
            resource=resource,
            limit=limit
        )

        if not logs:
            self.console.print("No audit logs found matching the criteria.", style="yellow")
            return True

        # Create logs table
        table = Table(title=f"[bold cyan]Audit Logs ({len(logs)} entries)[/bold cyan]")
        table.add_column("Timestamp", style="cyan", width=20)
        table.add_column("User", style="white", width=15)
        table.add_column("Operation", style="green", width=15)
        table.add_column("Resource", style="blue", width=20)
        table.add_column("Duration", style="magenta", width=10)
        table.add_column("Full Command", style="yellow", width=30)

        for log in logs:
            # Format timestamp
            timestamp = log.get("timestamp", 0)
            if timestamp:
                from datetime import datetime
                dt = datetime.fromtimestamp(timestamp)
                timestamp_str = dt.strftime("%Y-%m-%d %H:%M:%S")
            else:
                timestamp_str = "N/A"

            # Get user and other details
            user = log.get("user_id", "unknown")[:14]
            operation = log.get("operation", "unknown")[:14]
            resource = log.get("resource", "unknown")[:19]
            
            # Get duration and full command from details
            details = log.get("details", {})
            duration = details.get("duration", 0)
            duration_str = f"{duration:.3f}s" if duration > 0 else "0.000s"
            
            full_command = details.get("full_command", "unknown")
            full_command_short = full_command[:29] + "..." if len(full_command) > 30 else full_command

            table.add_row(timestamp_str, user, operation, resource, duration_str, full_command_short)

        self.console.print(table)
        return True

    def _enable_audit(self) -> bool:
        """Enable immutable audit logging."""
        config_manager = get_config_manager()
        
        try:
            config_manager.set("audit.log.enabled", True)
            self.console.print("[green]✅ Audit logging enabled[/green]")
            self.console.print("The audit system will be reconfigured automatically.", style="blue")
            
            # Reconfigure the audit logger
            audit_logger = get_immutable_audit_logger()
            audit_logger.reconfigure()
            
        except Exception as e:
            self.console.print(f"[red]Error enabling audit logging: {e}[/red]")
        
        return True

    def _disable_audit(self) -> bool:
        """Disable immutable audit logging."""
        config_manager = get_config_manager()
        
        try:
            config_manager.set("audit.log.enabled", False)
            self.console.print("[yellow]⚠️  Audit logging disabled[/yellow]")
            self.console.print("The audit system will be reconfigured automatically.", style="blue")
            
            # Reconfigure the audit logger
            audit_logger = get_immutable_audit_logger()
            audit_logger.reconfigure()
            
        except Exception as e:
            self.console.print(f"[red]Error disabling audit logging: {e}[/red]")
        
        return True

    def _reconfigure_audit(self) -> bool:
        """Reconfigure the audit system."""
        try:
            audit_logger = get_immutable_audit_logger()
            audit_logger.reconfigure()
            self.console.print("[green]✅ Audit system reconfigured[/green]")
        except Exception as e:
            self.console.print(f"[red]Error reconfiguring audit system: {e}[/red]")
        
        return True

    def get_completions(
        self, current_input: str, cursor_position: int
    ) -> list[str | CompletionItem]:
        """Get auto-completion suggestions for audit command.

        Args:
            current_input: Current input text
            cursor_position: Current cursor position

        Returns:
            List of completion suggestions with descriptions
        """
        words = current_input.split()

        # Subcommands
        subcommands = [
            CompletionItem(text="status", description="Show audit system status"),
            CompletionItem(text="info", description="Show audit log information"),
            CompletionItem(text="verify", description="Verify audit log integrity"),
            CompletionItem(text="logs", description="Query audit logs"),
            CompletionItem(text="enable", description="Enable secure audit logging"),
            CompletionItem(text="disable", description="Disable secure audit logging"),
            CompletionItem(text="reconfigure", description="Reconfigure audit system"),
            CompletionItem(text="--help", description="Show help information"),
        ]

        # If we're typing the first argument (subcommand)
        if len(words) <= 1:
            if len(words) == 0 or current_input.endswith(" "):
                return subcommands
            else:
                partial = words[0]
                return [
                    item for item in subcommands
                    if item.text.startswith(partial)
                ]
        elif len(words) == 2 and not current_input.endswith(" "):
            # Partial subcommand completion (e.g., "audit s")
            partial = words[1]
            return [
                item for item in subcommands
                if item.text.startswith(partial)
            ]

        # If we're typing after "logs" subcommand
        if len(words) >= 2 and words[1] == "logs":
            log_options = [
                CompletionItem(text="--user", description="Filter by user ID"),
                CompletionItem(text="--operation", description="Filter by operation type"),
                CompletionItem(text="--resource", description="Filter by resource"),
                CompletionItem(text="--limit", description="Limit number of results"),
            ]
            
            if len(words) == 2 or current_input.endswith(" "):
                return log_options
            else:
                partial = words[-1]
                return [
                    item for item in log_options
                    if item.text.startswith(partial)
                ]

        return [] 