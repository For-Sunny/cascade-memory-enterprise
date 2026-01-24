"""Logging configuration for RAM Disk Manager.

Provides consistent logging across all modules with:
- JSON or text output formats
- Timestamps in ISO format
- Configurable log levels
- File and console handlers
"""

import json
import logging
import sys
from datetime import datetime
from pathlib import Path
from typing import Optional, Union


# Default format for text output
TEXT_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class JsonFormatter(logging.Formatter):
    """Format log records as JSON lines for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format a log record as JSON.

        Args:
            record: The log record to format

        Returns:
            JSON string representation of the log record
        """
        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        # Include any extra fields
        for key, value in record.__dict__.items():
            if key not in (
                "name", "msg", "args", "created", "filename", "funcName",
                "levelname", "levelno", "lineno", "module", "msecs",
                "pathname", "process", "processName", "relativeCreated",
                "stack_info", "exc_info", "exc_text", "thread", "threadName",
                "message", "taskName"
            ):
                try:
                    # Ensure value is JSON serializable
                    json.dumps(value)
                    log_data[key] = value
                except (TypeError, ValueError):
                    log_data[key] = str(value)

        return json.dumps(log_data)


def get_logger(
    name: str,
    level: Union[int, str] = logging.INFO,
    json_output: bool = False,
    log_file: Optional[Path] = None,
    console: bool = True
) -> logging.Logger:
    """Get a configured logger instance.

    Args:
        name: Logger name (usually __name__ or module name)
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        json_output: If True, use JSON format. If False, use text format.
        log_file: Optional path to log file
        console: If True, also log to console (stderr)

    Returns:
        Configured logger instance

    Example:
        >>> logger = get_logger("ram_disk_manager.sync")
        >>> logger.info("Syncing files", extra={"count": 42})

        >>> json_logger = get_logger("ram_disk_manager", json_output=True)
        >>> json_logger.info("Started")  # {"timestamp": "...", "level": "INFO", ...}
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers
    if logger.handlers:
        return logger

    # Convert string level to int if needed
    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    logger.setLevel(level)

    # Create formatter
    if json_output:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(TEXT_FORMAT, DATE_FORMAT)

    # Console handler
    if console:
        console_handler = logging.StreamHandler(sys.stderr)
        console_handler.setLevel(level)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def configure_root_logger(
    level: Union[int, str] = logging.INFO,
    json_output: bool = False,
    log_file: Optional[Path] = None
) -> None:
    """Configure the root logger for the entire application.

    Call this once at application startup to set defaults for all loggers.

    Args:
        level: Default logging level
        json_output: If True, use JSON format globally
        log_file: Optional path to log file
    """
    # Configure root logger
    root_logger = logging.getLogger()

    if isinstance(level, str):
        level = getattr(logging, level.upper(), logging.INFO)
    root_logger.setLevel(level)

    # Clear existing handlers
    root_logger.handlers.clear()

    # Create formatter
    if json_output:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(TEXT_FORMAT, DATE_FORMAT)

    # Console handler
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setLevel(level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # File handler
    if log_file:
        log_file = Path(log_file)
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setLevel(level)
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
