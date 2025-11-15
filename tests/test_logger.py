"""
Tests for logger.py

These tests verify custom formatters, logging setup, and operation ID injection.
"""

import json
import logging
import shutil
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from automation.constants import (
    EXCLUDED_EXTRA_FIELDS,
    JSON_DATEFMT,
    LOG_BACKUP_COUNT,
    LOG_MAX_BYTES,
    RESERVED_ATTRS,
    STRUCT_CONSOLE_FMT,
    STRUCT_DATEFMT,
    TEXT_CONSOLE_FMT,
)
from automation.logger import (
    BaseFormatter,
    JSONFormatter,
    StructuredFormatter,
    TextFormatter,
    get_logger,
    setup_logging,
)


@pytest.fixture
def log_record():
    """Create a basic LogRecord for testing."""
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/path/to/file.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
    )
    return record


@pytest.fixture
def log_record_with_extra():
    """Create a LogRecord with extra fields."""
    record = logging.LogRecord(
        name="test.logger",
        level=logging.INFO,
        pathname="/path/to/file.py",
        lineno=42,
        msg="Test message",
        args=(),
        exc_info=None,
        func="test_function",
    )

    record.namespace = "pr-123"
    record.service = "frontend"
    record.duration_seconds = 1.234
    return record


@pytest.fixture
def log_record_with_exception():
    """Create a LogRecord with exception info."""
    try:
        raise ValueError("Test exception")
    except ValueError:
        import sys

        exc_info = sys.exc_info()

    return logging.LogRecord(
        name="test.logger",
        level=logging.ERROR,
        pathname="/path/to/file.py",
        lineno=42,
        msg="Error occurred",
        args=(),
        exc_info=exc_info,
    )


@pytest.fixture
def temp_log_dir():
    """Create a temporary directory for log files."""
    tmpdir = tempfile.mkdtemp()
    yield tmpdir

    # Cleanup after test
    try:
        # Close any open file handlers before cleanup
        logging.getLogger().handlers.clear()
        shutil.rmtree(tmpdir, ignore_errors=True)
    except Exception:
        pass


class TestBaseFormatter:
    """Tests for BaseFormatter class."""

    @patch("automation.logger.get_operation_id")
    def test_format_injects_operation_id(self, mock_get_op_id, log_record):
        """Test that operation_id is injected into log record."""
        mock_get_op_id.return_value = "abc12345"
        formatter = BaseFormatter()

        formatter.format(log_record)

        assert hasattr(log_record, "operation_id")
        assert log_record.operation_id == "abc12345"

    @patch("automation.logger.get_operation_id")
    def test_format_uses_dashes_when_no_operation_id(self, mock_get_op_id, log_record):
        """Test that dashes are used when operation_id is None."""
        mock_get_op_id.return_value = None
        formatter = BaseFormatter()

        formatter.format(log_record)

        assert log_record.operation_id == "--------"

    @patch("automation.logger.get_operation_id")
    def test_extract_extra_fields(self, mock_get_op_id, log_record_with_extra):
        """Test extraction of custom extra fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = BaseFormatter()

        formatter.format(log_record_with_extra)

        assert hasattr(log_record_with_extra, "extra_fields")
        assert "namespace" in log_record_with_extra.extra_fields
        assert "service" in log_record_with_extra.extra_fields
        assert "duration_seconds" in log_record_with_extra.extra_fields
        assert log_record_with_extra.extra_fields["namespace"] == "pr-123"
        assert log_record_with_extra.extra_fields["service"] == "frontend"
        assert log_record_with_extra.extra_fields["duration_seconds"] == 1.234

    @patch("automation.logger.get_operation_id")
    def test_extract_extra_fields_excludes_reserved_attrs(self, mock_get_op_id, log_record):
        """Test that reserved LogRecord attributes are not in extra_fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = BaseFormatter()

        formatter.format(log_record)

        # Reserved attrs should not be in extra_fields
        for attr in RESERVED_ATTRS:
            assert attr not in log_record.extra_fields

    @patch("automation.logger.get_operation_id")
    def test_extract_extra_fields_excludes_excluded_fields(self, mock_get_op_id, log_record):
        """Test that explicitly excluded fields are not in extra_fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = BaseFormatter()

        formatter.format(log_record)

        # Excluded fields should not be in extra_fields
        for field in EXCLUDED_EXTRA_FIELDS:
            assert field not in log_record.extra_fields

    @patch("automation.logger.get_operation_id")
    def test_extract_extra_fields_excludes_private_attrs(self, mock_get_op_id, log_record):
        """Test that private attributes (starting with _) are excluded."""
        mock_get_op_id.return_value = "abc12345"
        formatter = BaseFormatter()

        # Add a private attribute
        log_record._private_field = "should not appear"

        formatter.format(log_record)

        assert "_private_field" not in log_record.extra_fields


class TestTextFormatter:
    """Tests for TextFormatter class."""

    @patch("automation.logger.get_operation_id")
    def test_format_basic_message(self, mock_get_op_id, log_record):
        """Test basic text formatting."""
        mock_get_op_id.return_value = "abc12345"
        formatter = TextFormatter(fmt=TEXT_CONSOLE_FMT)

        output = formatter.format(log_record)

        assert "abc12345" in output
        assert "INFO" in output
        assert "Test message" in output

    @patch("automation.logger.get_operation_id")
    def test_format_does_not_show_extra_fields(self, mock_get_op_id, log_record_with_extra):
        """Test that TextFormatter does not display extra fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = TextFormatter(fmt=TEXT_CONSOLE_FMT)

        output = formatter.format(log_record_with_extra)

        # Extra fields should not appear in text format
        assert "namespace" not in output
        assert "pr-123" not in output
        assert "service" not in output


class TestStructuredFormatter:
    """Tests for StructuredFormatter class."""

    @patch("automation.logger.get_operation_id")
    def test_format_with_extra_fields(self, mock_get_op_id, log_record_with_extra):
        """Test structured formatting with extra fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = StructuredFormatter(fmt=STRUCT_CONSOLE_FMT, datefmt=STRUCT_DATEFMT)

        output = formatter.format(log_record_with_extra)

        # Should contain base message
        assert "abc12345" in output
        assert "INFO" in output
        assert "Test message" in output

        # Should contain extra fields as key=value pairs
        assert " | " in output
        assert "namespace=pr-123" in output
        assert "service=frontend" in output
        assert "duration_seconds=1.234" in output

    @patch("automation.logger.get_operation_id")
    def test_format_without_extra_fields(self, mock_get_op_id, log_record):
        """Test structured formatting without extra fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = StructuredFormatter(fmt=STRUCT_CONSOLE_FMT, datefmt=STRUCT_DATEFMT)

        output = formatter.format(log_record)

        # Should contain base message
        assert "abc12345" in output
        assert "INFO" in output
        assert "Test message" in output

        # Should not have extra separator if no extra fields
        assert not output.endswith(" | ")

    @patch("automation.logger.get_operation_id")
    def test_format_multiple_extra_fields(self, mock_get_op_id, log_record):
        """Test structured formatting with multiple extra fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = StructuredFormatter(fmt=STRUCT_CONSOLE_FMT, datefmt=STRUCT_DATEFMT)

        # Add multiple extra fields
        log_record.field1 = "value1"
        log_record.field2 = "value2"
        log_record.field3 = "value3"

        output = formatter.format(log_record)

        # All fields should be present separated by spaces
        assert "field1=value1" in output
        assert "field2=value2" in output
        assert "field3=value3" in output


class TestJSONFormatter:
    """Tests for JSONFormatter class."""

    @patch("automation.logger.get_operation_id")
    def test_format_produces_valid_json(self, mock_get_op_id, log_record):
        """Test that JSONFormatter produces valid JSON."""
        mock_get_op_id.return_value = "abc12345"
        formatter = JSONFormatter(datefmt=JSON_DATEFMT)

        output = formatter.format(log_record)

        # Should be valid JSON
        log_data = json.loads(output)
        assert isinstance(log_data, dict)

    @patch("automation.logger.get_operation_id")
    def test_format_contains_required_fields(self, mock_get_op_id, log_record):
        """Test that JSON output contains all required fields."""
        mock_get_op_id.return_value = "abc12345"
        formatter = JSONFormatter(datefmt=JSON_DATEFMT)

        output = formatter.format(log_record)
        log_data = json.loads(output)

        # Check required fields
        assert log_data["timestamp"] is not None
        assert log_data["operation_id"] == "abc12345"
        assert log_data["level"] == "INFO"
        assert log_data["logger"] == "test.logger"
        assert log_data["function"] == "test_function"
        assert log_data["line"] == 42
        assert log_data["message"] == "Test message"

    @patch("automation.logger.get_operation_id")
    def test_format_includes_extra_fields(self, mock_get_op_id, log_record_with_extra):
        """Test that extra fields are included in JSON output."""
        mock_get_op_id.return_value = "abc12345"
        formatter = JSONFormatter(datefmt=JSON_DATEFMT)

        output = formatter.format(log_record_with_extra)
        log_data = json.loads(output)

        # Extra fields should be at top level
        assert log_data["namespace"] == "pr-123"
        assert log_data["service"] == "frontend"
        assert log_data["duration_seconds"] == 1.234

    @patch("automation.logger.get_operation_id")
    def test_format_with_exception_info(self, mock_get_op_id, log_record_with_exception):
        """Test JSON formatting with exception information."""
        mock_get_op_id.return_value = "abc12345"
        formatter = JSONFormatter(datefmt=JSON_DATEFMT)

        output = formatter.format(log_record_with_exception)
        log_data = json.loads(output)

        # Should contain exception field
        assert "exception" in log_data
        assert "ValueError" in log_data["exception"]
        assert "Test exception" in log_data["exception"]
        assert "Traceback" in log_data["exception"]

    @patch("automation.logger.get_operation_id")
    def test_format_timestamp_format(self, mock_get_op_id, log_record):
        """Test that timestamp is formatted correctly."""
        mock_get_op_id.return_value = "abc12345"
        formatter = JSONFormatter(datefmt=JSON_DATEFMT)

        output = formatter.format(log_record)
        log_data = json.loads(output)

        # Timestamp should match the expected format
        timestamp = log_data["timestamp"]
        assert "T" in timestamp
        # Should be parseable as a datetime
        from datetime import datetime

        datetime.strptime(timestamp, JSON_DATEFMT)


class TestSetupLogging:
    """Tests for setup_logging function."""

    @pytest.fixture(autouse=True)
    def cleanup_logging(self):
        """Cleanup logging handlers after each test."""
        yield
        # Clear all handlers and reset to default state
        root_logger = logging.getLogger()
        for handler in root_logger.handlers[:]:
            handler.close()
            root_logger.removeHandler(handler)
        root_logger.setLevel(logging.WARNING)

    def test_setup_logging_default_text_format(self):
        """Test setup_logging with default text format."""
        setup_logging(level="INFO", log_format="text")

        root_logger = logging.getLogger()
        assert root_logger.level == logging.DEBUG
        assert len(root_logger.handlers) == 1  # Console handler only

        console_handler = root_logger.handlers[0]
        assert isinstance(console_handler, logging.StreamHandler)
        assert console_handler.level == logging.INFO
        assert isinstance(console_handler.formatter, TextFormatter)

    def test_setup_logging_structured_format(self):
        """Test setup_logging with structured format."""
        setup_logging(level="DEBUG", log_format="structured")

        root_logger = logging.getLogger()
        console_handler = root_logger.handlers[0]

        assert console_handler.level == logging.DEBUG
        assert isinstance(console_handler.formatter, StructuredFormatter)

    def test_setup_logging_json_format(self):
        """Test setup_logging with JSON format."""
        setup_logging(level="WARNING", log_format="json")

        root_logger = logging.getLogger()
        console_handler = root_logger.handlers[0]

        assert console_handler.level == logging.WARNING
        assert isinstance(console_handler.formatter, JSONFormatter)

    def test_setup_logging_with_log_file(self, temp_log_dir):
        """Test setup_logging with file handler."""
        log_file = str(Path(temp_log_dir) / "test.log")

        setup_logging(level="INFO", log_file=log_file, log_format="text")

        root_logger = logging.getLogger()
        assert len(root_logger.handlers) == 2  # Console + file

        file_handler = root_logger.handlers[1]
        assert isinstance(file_handler, logging.handlers.RotatingFileHandler)
        assert file_handler.level == logging.DEBUG
        assert isinstance(file_handler.formatter, TextFormatter)

        # Verify file was created
        assert Path(log_file).exists()

    def test_setup_logging_creates_log_directory(self, temp_log_dir):
        """Test that setup_logging creates log directory if it doesn't exist."""
        log_file = str(Path(temp_log_dir) / "subdir" / "nested" / "test.log")

        setup_logging(level="INFO", log_file=log_file, log_format="text")

        # Directory should be created
        assert Path(log_file).parent.exists()
        assert Path(log_file).exists()

    def test_setup_logging_rotating_file_handler_config(self, temp_log_dir):
        """Test that RotatingFileHandler is configured correctly."""
        log_file = str(Path(temp_log_dir) / "test.log")

        setup_logging(level="INFO", log_file=log_file, log_format="text")

        root_logger = logging.getLogger()
        file_handler = root_logger.handlers[1]

        assert isinstance(file_handler, logging.handlers.RotatingFileHandler)
        assert file_handler.maxBytes == LOG_MAX_BYTES
        assert file_handler.backupCount == LOG_BACKUP_COUNT

    def test_setup_logging_clears_existing_handlers(self):
        """Test that setup_logging removes existing handlers."""
        # Add a dummy handler
        dummy_handler = logging.StreamHandler()
        logging.getLogger().addHandler(dummy_handler)

        initial_handler_count = len(logging.getLogger().handlers)
        assert initial_handler_count > 0

        setup_logging(level="INFO", log_format="text")

        # Old handlers should be cleared, only new ones present
        assert len(logging.getLogger().handlers) == 1

    def test_setup_logging_silences_third_party_loggers(self):
        """Test that kubernetes and urllib3 loggers are set to WARNING."""
        setup_logging(level="DEBUG", log_format="text")

        k8s_logger = logging.getLogger("kubernetes")
        urllib3_logger = logging.getLogger("urllib3")

        assert k8s_logger.level == logging.WARNING
        assert urllib3_logger.level == logging.WARNING

    def test_setup_logging_different_levels(self):
        """Test setup_logging with different log levels."""
        levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]

        for level in levels:
            setup_logging(level=level, log_format="text")
            console_handler = logging.getLogger().handlers[0]
            assert console_handler.level == getattr(logging, level)

    def test_setup_logging_file_always_debug(self, temp_log_dir):
        """Test that file handler always uses DEBUG level."""
        log_file = str(Path(temp_log_dir) / "test.log")

        setup_logging(level="ERROR", log_file=log_file, log_format="text")

        root_logger = logging.getLogger()
        file_handler = root_logger.handlers[1]

        # File handler should always be DEBUG, regardless of console level
        assert file_handler.level == logging.DEBUG


class TestGetLogger:
    """Tests for get_logger function."""

    def test_get_logger_returns_logger(self):
        """Test that get_logger returns a Logger instance."""
        logger = get_logger("test.module")

        assert isinstance(logger, logging.Logger)
        assert logger.name == "test.module"

    def test_get_logger_returns_same_instance(self):
        """Test that get_logger returns the same instance for the same name."""
        logger1 = get_logger("test.module")
        logger2 = get_logger("test.module")

        assert logger1 is logger2

    def test_get_logger_inherits_from_root(self):
        """Test that module loggers inherit configuration from root logger."""
        setup_logging(level="INFO", log_format="text")

        logger = get_logger("test.module")

        # Should inherit from root logger
        root_logger = logging.getLogger()
        assert logger.parent is root_logger
