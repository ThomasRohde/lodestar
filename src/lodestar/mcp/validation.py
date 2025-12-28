"""Input validation and safety guards for MCP tools.

This module provides validators to enforce safety constraints on MCP tool inputs:
- Maximum message lengths
- List size limits
- TTL (time-to-live) range constraints
- Required fields for mutating operations

All tool inputs should be validated before processing to prevent abuse
and ensure data integrity.
"""

from __future__ import annotations

from typing import Any

# Constants for validation limits
MAX_MESSAGE_LENGTH = 16 * 1024  # 16 KB
MAX_LIST_SIZE = 100  # Maximum items in a list response
MIN_TTL_SECONDS = 60  # 1 minute
MAX_TTL_SECONDS = 2 * 60 * 60  # 2 hours
DEFAULT_TTL_SECONDS = 15 * 60  # 15 minutes


class ValidationError(ValueError):
    """Raised when input validation fails."""

    def __init__(self, message: str, field: str | None = None):
        """Initialize validation error.

        Args:
            message: Human-readable error message
            field: Optional field name that failed validation
        """
        self.field = field
        super().__init__(message)


def validate_message(message: str, field_name: str = "message") -> str:
    """
    Validate message length is within allowed limit.

    Args:
        message: The message text to validate
        field_name: Name of the field for error reporting

    Returns:
        The validated message

    Raises:
        ValidationError: If message exceeds MAX_MESSAGE_LENGTH
    """
    if len(message.encode("utf-8")) > MAX_MESSAGE_LENGTH:
        raise ValidationError(
            f"{field_name} exceeds maximum length of {MAX_MESSAGE_LENGTH} bytes",
            field=field_name,
        )
    return message


def validate_list_size(items: list[Any], field_name: str = "items") -> list[Any]:
    """
    Validate list size is within allowed limit.

    Args:
        items: The list to validate
        field_name: Name of the field for error reporting

    Returns:
        The validated list

    Raises:
        ValidationError: If list exceeds MAX_LIST_SIZE
    """
    if len(items) > MAX_LIST_SIZE:
        raise ValidationError(
            f"{field_name} exceeds maximum size of {MAX_LIST_SIZE} items",
            field=field_name,
        )
    return items


def validate_ttl(ttl_seconds: int | None) -> int:
    """
    Validate and clamp TTL (time-to-live) to allowed range.

    Args:
        ttl_seconds: Requested TTL in seconds (None uses default)

    Returns:
        Clamped TTL value within [MIN_TTL_SECONDS, MAX_TTL_SECONDS]

    Note:
        This function clamps rather than raises errors to be user-friendly.
        Values outside the range are adjusted to the nearest valid value.
    """
    if ttl_seconds is None:
        return DEFAULT_TTL_SECONDS

    # Clamp to valid range
    if ttl_seconds < MIN_TTL_SECONDS:
        return MIN_TTL_SECONDS
    if ttl_seconds > MAX_TTL_SECONDS:
        return MAX_TTL_SECONDS

    return ttl_seconds


def validate_agent_id(agent_id: str | None, field_name: str = "agent_id") -> str:
    """
    Validate that agent_id is provided and non-empty.

    Args:
        agent_id: The agent ID to validate
        field_name: Name of the field for error reporting

    Returns:
        The validated agent ID

    Raises:
        ValidationError: If agent_id is None or empty
    """
    if not agent_id:
        raise ValidationError(
            f"{field_name} is required for this operation",
            field=field_name,
        )
    return agent_id.strip()


def validate_required_field(
    value: Any,
    field_name: str,
    expected_type: type | None = None,
) -> Any:
    """
    Validate that a required field is present and optionally of the correct type.

    Args:
        value: The value to validate
        field_name: Name of the field for error reporting
        expected_type: Optional type to check against

    Returns:
        The validated value

    Raises:
        ValidationError: If field is None or of wrong type
    """
    if value is None:
        raise ValidationError(
            f"{field_name} is required",
            field=field_name,
        )

    if expected_type is not None and not isinstance(value, expected_type):
        raise ValidationError(
            f"{field_name} must be of type {expected_type.__name__}",
            field=field_name,
        )

    # For strings, also check they're not empty
    if isinstance(value, str) and not value.strip():
        raise ValidationError(
            f"{field_name} cannot be empty",
            field=field_name,
        )

    return value


def validate_task_id(task_id: str | None) -> str:
    """
    Validate task ID format and presence.

    Args:
        task_id: The task ID to validate

    Returns:
        The validated task ID

    Raises:
        ValidationError: If task_id is invalid
    """
    if not task_id:
        raise ValidationError("task_id is required", field="task_id")

    task_id = task_id.strip()

    if not task_id:
        raise ValidationError("task_id cannot be empty", field="task_id")

    # Task IDs should be reasonable length (not too long)
    if len(task_id) > 100:
        raise ValidationError(
            "task_id exceeds maximum length of 100 characters",
            field="task_id",
        )

    return task_id


def validate_priority(priority: int | None) -> int | None:
    """
    Validate priority value is within reasonable range.

    Args:
        priority: Priority value (lower is higher priority)

    Returns:
        The validated priority

    Raises:
        ValidationError: If priority is negative or unreasonably high
    """
    if priority is None:
        return None

    if priority < 0:
        raise ValidationError(
            "priority cannot be negative",
            field="priority",
        )

    if priority > 1000:
        raise ValidationError(
            "priority exceeds maximum value of 1000",
            field="priority",
        )

    return priority


def clamp_limit(limit: int | None, default: int = 50) -> int:
    """
    Clamp list limit to reasonable range.

    Args:
        limit: Requested limit (None uses default)
        default: Default limit if not specified

    Returns:
        Clamped limit value within [1, MAX_LIST_SIZE]
    """
    if limit is None:
        return min(default, MAX_LIST_SIZE)

    if limit < 1:
        return 1

    if limit > MAX_LIST_SIZE:
        return MAX_LIST_SIZE

    return limit
