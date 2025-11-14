"""
Centralized logging configuration.

Provides structured logging with console and file outputs.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any

from automation.constants import RESERVED_ATTRS
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


def setup_logging(
    level: str = "INFO",
    log_file: str | None = None,
) -> None:
    """
    Configure application-wide logging.

    Should be called once at application startup (in main.py).
    Configures the root logger, which all module loggers inherit from.

    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Optional file path for log output
    """
    log_level = getattr(logging, level.upper())

    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # Remove existing handlers
    root_logger.handlers.clear()

    # Create formatters
    detailed_formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s:%(funcName)s:%(lineno)d | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter(fmt="%(levelname)-8s | %(message)s")

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
        file_handler.setFormatter(detailed_formatter)
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
