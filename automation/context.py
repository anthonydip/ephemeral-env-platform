"""
Request context for distributed tracing.

Used to store a unique operation ID for the current context
allowing for injection into loggers to track operations.
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

# Context variable to store the current operation ID
_operation_id: ContextVar[str | None] = ContextVar("operation_id", default=None)


def set_operation_id(operation_id: str | None = None) -> str:
    """
    Set the operation ID for the current context.

    Args:
        operation_id: Optional operation ID. If None, generates a new one.

    Returns:
        The operation ID that was set
    """
    if operation_id is None:
        operation_id = str(uuid.uuid4())[:8]

    _operation_id.set(operation_id)
    return operation_id


def get_operation_id() -> str | None:
    """
    Get the current operation ID from context.

    Returns:
        The operation ID, or None if not set
    """
    return _operation_id.get()


def clear_operation_id() -> None:
    """Clear the operation ID from context."""
    _operation_id.set(None)
