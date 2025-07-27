"""Command execution tracking models."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class CommandExecution(BaseModel):
    """Model for tracking command execution details."""

    command: str = Field(description="The command that was executed")
    status: str = Field(description="Execution status: 'success' or 'failure'")
    start_time: datetime = Field(description="When the command started")
    end_time: datetime = Field(description="When the command finished")
    duration_seconds: float = Field(description="Duration in seconds")
    error_message: Optional[str] = Field(
        default=None, description="Error message if command failed"
    )

    @property
    def formatted_start_time(self) -> str:
        """Get formatted start time for display."""
        return self.start_time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def formatted_end_time(self) -> str:
        """Get formatted end time for display."""
        return self.end_time.strftime("%Y-%m-%d %H:%M:%S")

    @property
    def formatted_duration(self) -> str:
        """Get formatted duration for display."""
        if self.duration_seconds < 1:
            return f"{self.duration_seconds:.3f}s"
        elif self.duration_seconds < 60:
            return f"{self.duration_seconds:.2f}s"
        else:
            minutes = int(self.duration_seconds // 60)
            seconds = self.duration_seconds % 60
            return f"{minutes}m {seconds:.1f}s"


class ExecutionHistory(BaseModel):
    """Model for execution history data structure."""

    version: str = Field(default="1.0", description="History format version")
    command_history: list[str] = Field(
        default_factory=list, description="Command text history"
    )
    execution_history: list[CommandExecution] = Field(
        default_factory=list, description="Command execution tracking"
    )

    def add_execution(
        self,
        command: str,
        status: str,
        start_time: datetime,
        end_time: datetime,
        error_message: Optional[str] = None,
        max_executions: int = 500,
    ) -> None:
        """Add a new command execution record.

        Args:
            command: The command that was executed
            status: 'success' or 'failure'
            start_time: When the command started
            end_time: When the command finished
            error_message: Error message if command failed
            max_executions: Maximum number of executions to keep
        """
        duration = (end_time - start_time).total_seconds()

        execution = CommandExecution(
            command=command,
            status=status,
            start_time=start_time,
            end_time=end_time,
            duration_seconds=duration,
            error_message=error_message,
        )

        # Add to front of list (most recent first)
        self.execution_history.insert(0, execution)

        # Maintain max limit
        if len(self.execution_history) > max_executions:
            self.execution_history = self.execution_history[:max_executions]

    def get_recent_executions(self, limit: int = 10) -> list[CommandExecution]:
        """Get recent command executions.

        Args:
            limit: Maximum number of executions to return

        Returns:
            List of recent executions (most recent first)
        """
        return self.execution_history[:limit]