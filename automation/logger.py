"""
Centralized logging configuration.

Provides structured logging with console and file outputs.
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

from automation.constants import (
    JSON_DATEFMT,
    RESERVED_ATTRS,
    STRUCT_CONSOLE_FMT,
    STRUCT_DATEFMT,
    STRUCT_FILE_FMT,
    TEXT_CONSOLE_FMT,
    TEXT_DATEFMT,
    TEXT_FILE_FMT,
)
from automation.context import get_operation_id


class BaseFormatter(logging.Formatter):
    """
    Base formatter that handles operation_id injection and extra field extraction.

    All other formatters inherit from this to get consistent behaviour.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Inject operation_id and extract extra fields before formatting.

        Args:
            record: LogRecord to format

        Returns:
            Formatted log string
        """
        operation_id = get_operation_id()
        record.operation_id = operation_id if operation_id else "--------"

        # Extract extra fields (anything not in RESERVED_ATTRS)
        record.extra_fields = self._extract_extra_fields(record)

        return super().format(record)

    def _extract_extra_fields(self, record: logging.LogRecord) -> dict[str, Any]:
        """
        Extract custom fields from LogRecord that were passed via extra={}.

        Args:
            record: LogRecord to extract from

        Returns:
            Dictionary of extra fields
        """
        extra_fields = {}
        for key, value in record.__dict__.items():
            if key not in RESERVED_ATTRS and not key.startswith("_"):
                extra_fields[key] = value
        return extra_fields


class TextFormatter(BaseFormatter):
    """
    Simple text formatter.
    Does not show extra fields.
    """

    pass


class StructuredFormatter(BaseFormatter):
    """
    Human-readable formatter that appends extra fields as key=value pairs.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format with extra fields appended as key=value pairs."""
        base_message = super().format(record)

        # Append extra fields (excluding operation_id)
        extra_fields = {
            key: value for key, value in record.extra_fields.items() if key != "operation_id"
        }

        if extra_fields:
            extra_str = " | " + " ".join(f"{key}={value}" for key, value in extra_fields.items())
            return base_message + extra_str

        return base_message


class JSONFormatter(BaseFormatter):
    """
    JSON formatter for structured logging.
    """

    def format(self, record: logging.LogRecord) -> str:
        """Format as JSON with all fields."""
        # Inject operation_id and extract extra fields
        super().format(record)

        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "operation_id": record.operation_id,
            "level": record.levelname,
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
            "message": record.getMessage(),
        }

        # Add all extra fields
        log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
    log_format: str = "text",
) -> None:
    """
    Configure application-wide logging.

    Should be called once at application startup (in main.py).
    Configures the root logger, which all module loggers inherit from.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
        log_format: Format type (text, structured, or json)
    """
    log_level = getattr(logging, level.upper())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Choose formatter based on format type
    if log_format == "json":
        console_formatter = JSONFormatter(datefmt=JSON_DATEFMT)
        file_formatter = JSONFormatter(datefmt=JSON_DATEFMT)
    elif log_format == "structured":
        console_formatter = StructuredFormatter(fmt=STRUCT_CONSOLE_FMT, datefmt=STRUCT_DATEFMT)
        file_formatter = StructuredFormatter(fmt=STRUCT_FILE_FMT, datefmt=STRUCT_DATEFMT)
    else:
        console_formatter = TextFormatter(fmt=TEXT_CONSOLE_FMT)
        file_formatter = TextFormatter(fmt=TEXT_FILE_FMT, datefmt=TEXT_DATEFMT)

    # Set up console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(console_formatter)
    root_logger.addHandler(console_handler)

    # Set up file handler (if specified)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(logging.DEBUG)  # Always DEBUG for files
        file_handler.setFormatter(file_formatter)
        root_logger.addHandler(file_handler)

    logging.getLogger("kubernetes").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger for a module.

    Call this at module level: logger = get_logger(__name__)
    The logger inherits configuration from the root logger.

    Args:
        name: Logger name (use __name__)

    Returns:
        Logger instance
    """
    return logging.getLogger(name)
