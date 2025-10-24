"""Application logging service with rotation and tracer functionality."""

import logging
import threading
from datetime import datetime, timedelta
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Optional

# get_config_manager imported locally to avoid circular import
from .log_config import LogConfig, LogLevel


class TimedRotatingHandler(logging.Handler):
    """Custom handler for time-based log rotation."""

    def __init__(self, filename: str, rotate_minutes: int = 120):
        """Initialize timed rotating handler.

        Args:
            filename: Log file path
            rotate_minutes: Minutes after which to rotate logs
        """
        super().__init__()
        self.filename = filename
        self.rotate_minutes = rotate_minutes
        self.base_filename = filename
        self.current_handler: logging.FileHandler | None = None
        self.last_rotation = datetime.now()
        self.lock: threading.Lock = threading.Lock()
        self._setup_handler()

    def _setup_handler(self) -> None:
        """Setup or recreate the file handler."""
        if self.current_handler:
            self.current_handler.close()

        # Ensure directory exists
        Path(self.filename).parent.mkdir(parents=True, exist_ok=True)

        self.current_handler = logging.FileHandler(
            self.filename, mode="a", encoding="utf-8"
        )
        self.current_handler.setFormatter(self.formatter)

    def _should_rotate(self) -> bool:
        """Check if log should be rotated based on time."""
        time_diff = datetime.now() - self.last_rotation
        return time_diff >= timedelta(minutes=self.rotate_minutes)

    def _rotate_log(self) -> None:
        """Rotate the log file."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        base_path = Path(self.base_filename)
        rotated_name = f"{base_path.stem}_{timestamp}{base_path.suffix}"
        rotated_path = base_path.parent / rotated_name

        # Close current handler
        if self.current_handler:
            self.current_handler.close()

        # Rename current log file if it exists
        if Path(self.filename).exists():
            try:
                Path(self.filename).rename(rotated_path)
            except OSError:
                # If rename fails, just continue with new file
                pass

        # Create new handler
        self._setup_handler()
        self.last_rotation = datetime.now()

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record."""
        with self.lock:
            if self._should_rotate():
                self._rotate_log()

            if self.current_handler:
                self.current_handler.emit(record)

    def close(self) -> None:
        """Close the handler."""
        if self.current_handler:
            self.current_handler.close()
        super().close()


class SizeAndTimeRotatingHandler(RotatingFileHandler):
    """Handler that rotates on both size and time."""

    def __init__(
        self,
        filename: str,
        maxBytes: int = 0,
        backupCount: int = 5,
        rotate_minutes: int = 120,
    ):
        """Initialize combined rotating handler.

        Args:
            filename: Log file path
            maxBytes: Maximum size before rotation
            backupCount: Number of backup files to keep
            rotate_minutes: Minutes after which to rotate logs
        """
        super().__init__(filename, maxBytes=maxBytes, backupCount=backupCount, encoding='utf-8')
        self.rotate_minutes = rotate_minutes
        self.last_rotation = datetime.now()

    def shouldRollover(self, record: logging.LogRecord) -> bool:
        """Check if rollover should occur."""
        # Check size-based rotation first
        if super().shouldRollover(record):
            return True

        # Check time-based rotation
        time_diff = datetime.now() - self.last_rotation
        if time_diff >= timedelta(minutes=self.rotate_minutes):
            self.last_rotation = datetime.now()
            return True

        return False


class TracerLogger:
    """Tracer-style logger for critical operations."""

    _instance: Optional["TracerLogger"] = None
    _lock = threading.Lock()

    def __init__(self) -> None:
        """Initialize tracer logger."""
        self._logger: logging.Logger | None = None
        self._current_config: LogConfig | None = None
        self._setup_logger()

    @classmethod
    def get_instance(cls) -> "TracerLogger":
        """Get singleton instance of tracer logger."""
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """Reset singleton instance (for testing)."""
        with cls._lock:
            if cls._instance is not None:
                if cls._instance._logger:
                    for handler in cls._instance._logger.handlers[:]:
                        handler.close()
                        cls._instance._logger.removeHandler(handler)
                cls._instance = None

    def _setup_logger(self) -> None:
        """Setup or reconfigure the logger based on current configuration."""
        from ..config import get_config_manager

        config_manager = get_config_manager()
        log_config = config_manager._config.log

        # Check if configuration changed
        if (
            self._current_config
            and self._current_config.level == log_config.level
            and self._current_config.get_effective_filepath()
            == log_config.get_effective_filepath()
            and self._current_config.rotate.onsize == log_config.rotate.onsize
            and self._current_config.rotate.ontime == log_config.rotate.ontime
        ):
            return  # No change needed

        self._current_config = log_config

        # Create or get logger
        if self._logger is None:
            self._logger = logging.getLogger("adoc_toolkit.tracer")
            self._logger.propagate = False

        # Clear existing handlers
        for handler in self._logger.handlers[:]:
            handler.close()
            self._logger.removeHandler(handler)

        # Set log level
        level_mapping = {
            LogLevel.TRACE: logging.DEBUG,  # Use DEBUG level for TRACE
            LogLevel.DEBUG: logging.DEBUG,
            LogLevel.INFO: logging.INFO,
            LogLevel.ERROR: logging.ERROR,
        }
        self._logger.setLevel(level_mapping[log_config.level])

        try:
            # Setup file handler with rotation
            log_path = log_config.get_effective_filepath()

            # Parse size configuration
            max_bytes = log_config.rotate.size_in_bytes()
            rotate_minutes = log_config.rotate.ontime

            # Create handler
            handler = SizeAndTimeRotatingHandler(
                filename=log_path,
                maxBytes=max_bytes,
                backupCount=5,
                rotate_minutes=rotate_minutes,
            )

            # Set formatter for tracer-style logging
            formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                datefmt="%Y-%m-%d %H:%M:%S",
            )
            handler.setFormatter(formatter)
            handler.setLevel(level_mapping[log_config.level])

            self._logger.addHandler(handler)

        except Exception:
            # Debug: print the actual error during development
            # print(f"Logger setup failed: {e}")
            # import traceback
            # traceback.print_exc()
            # If we can't create the log file, try to create the directory and retry
            try:
                log_path = log_config.get_effective_filepath()
                log_dir = Path(log_path).parent
                log_dir.mkdir(parents=True, exist_ok=True)

                # Retry creating the handler
                handler = SizeAndTimeRotatingHandler(
                    filename=log_path,
                    maxBytes=max_bytes,
                    backupCount=5,
                    rotate_minutes=rotate_minutes,
                )

                formatter = logging.Formatter(
                    "%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                    datefmt="%Y-%m-%d %H:%M:%S",
                )
                handler.setFormatter(formatter)
                handler.setLevel(level_mapping[log_config.level])

                self._logger.addHandler(handler)

            except Exception:
                # If still failing, disable logging
                self._logger = None

    def is_enabled(self) -> bool:
        """Check if logging is enabled."""
        self._setup_logger()  # Refresh configuration
        return self._logger is not None

    def is_level_enabled(self, level: LogLevel) -> bool:
        """Check if specific log level is enabled."""
        if not self.is_enabled():
            return False

        from ..config import get_config_manager

        config_manager = get_config_manager()
        current_level = config_manager._config.log.level

        # Log level hierarchy: TRACE includes all, DEBUG includes DEBUG+INFO+ERROR,
        # INFO includes INFO+ERROR, ERROR includes only ERROR
        level_order = {
            LogLevel.TRACE: 0,
            LogLevel.DEBUG: 1,
            LogLevel.INFO: 2,
            LogLevel.ERROR: 3,
        }
        return level_order.get(level, 2) >= level_order.get(current_level, 2)

    def trace(self, message: str, **kwargs: Any) -> None:
        """Log trace message."""
        if self.is_level_enabled(LogLevel.TRACE):
            self._log(logging.DEBUG, f"TRACE: {message}", **kwargs)

    def debug(self, message: str, **kwargs: Any) -> None:
        """Log debug message."""
        if self.is_level_enabled(LogLevel.DEBUG):
            self._log(logging.DEBUG, message, **kwargs)

    def info(self, message: str, **kwargs: Any) -> None:
        """Log info message."""
        if self.is_level_enabled(LogLevel.INFO):
            self._log(logging.INFO, message, **kwargs)

    def error(self, message: str, **kwargs: Any) -> None:
        """Log error message."""
        if self.is_level_enabled(LogLevel.ERROR):
            self._log(logging.ERROR, message, **kwargs)

    def _log(self, level: int, message: str, **kwargs: Any) -> None:
        """Internal logging method."""
        if not self.is_enabled():
            return

        try:
            # Format message with additional context
            if kwargs:
                context = " | ".join(f"{k}={v}" for k, v in kwargs.items())
                full_message = f"{message} | {context}"
            else:
                full_message = message

            # Ensure message is ASCII-safe for Windows compatibility
            # Replace any problematic Unicode characters if they slip through
            try:
                full_message.encode('ascii')
            except UnicodeEncodeError:
                # If message contains non-ASCII characters, encode safely
                full_message = full_message.encode('ascii', errors='replace').decode('ascii')

            if self._logger is not None:
                self._logger.log(level, full_message)
        except Exception:
            # Fail silently to avoid breaking application functionality
            pass

    def trace_operation(self, operation: str, **details: Any) -> None:
        """Trace a critical operation."""
        self.trace(operation, **details)

    def trace_http_request(
        self, method: str, url: str, status_code: int | None = None, **details: Any
    ) -> None:
        """Trace HTTP request."""
        status_info = f" -> {status_code}" if status_code else ""
        self.trace(f"HTTP: {method} {url}{status_info}", **details)

    def trace_config_change(
        self, key: str, old_value: Any, new_value: Any, **details: Any
    ) -> None:
        """Trace configuration changes."""
        self.info(
            f"CONFIG: {key} changed", old=str(old_value), new=str(new_value), **details
        )

    def trace_error(
        self, operation: str, error: str | Exception, **details: Any
    ) -> None:
        """Trace errors."""
        error_msg = str(error)
        self.error(f"ERROR: {operation} failed", error=error_msg, **details)


# Global logger instance
def get_logger() -> TracerLogger:
    """Get the global tracer logger instance."""
    return TracerLogger.get_instance()


def log_trace(message: str, **kwargs: Any) -> None:
    """Convenience function to log trace message."""
    get_logger().trace(message, **kwargs)


def log_debug(message: str, **kwargs: Any) -> None:
    """Convenience function to log debug message."""
    get_logger().debug(message, **kwargs)


def log_info(message: str, **kwargs: Any) -> None:
    """Convenience function to log info message."""
    get_logger().info(message, **kwargs)


def log_error(message: str, **kwargs: Any) -> None:
    """Convenience function to log error message."""
    get_logger().error(message, **kwargs)


def trace_operation(operation: str, **details: Any) -> None:
    """Convenience function to trace operation."""
    get_logger().trace_operation(operation, **details)


def trace_http_request(
    method: str, url: str, status_code: int | None = None, **details: Any
) -> None:
    """Convenience function to trace HTTP request."""
    get_logger().trace_http_request(method, url, status_code, **details)


def trace_config_change(
    key: str, old_value: Any, new_value: Any, **details: Any
) -> None:
    """Convenience function to trace config change."""
    get_logger().trace_config_change(key, old_value, new_value, **details)


def trace_error(operation: str, error: str | Exception, **details: Any) -> None:
    """Convenience function to trace error."""
    get_logger().trace_error(operation, error, **details)


def reset_logger() -> None:
    """Reset logger instance (for testing)."""
    TracerLogger.reset_instance()
