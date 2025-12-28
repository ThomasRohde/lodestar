"""Time parsing and formatting utilities."""

from __future__ import annotations

import re
from datetime import datetime, timedelta
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass


class TimestampParseError(ValueError):
    """Error parsing a timestamp string."""

    pass


# Pattern for duration strings like "15m", "1h30m", "2h", "30s"
DURATION_PATTERN = re.compile(
    r"^(?:(\d+)h)?(?:(\d+)m)?(?:(\d+)s)?$",
    re.IGNORECASE,
)


def parse_duration(value: str) -> timedelta:
    """Parse a duration string into a timedelta.

    Supports formats like:
    - "15m" -> 15 minutes
    - "1h" -> 1 hour
    - "1h30m" -> 1 hour 30 minutes
    - "30s" -> 30 seconds
    - "2h15m30s" -> 2 hours 15 minutes 30 seconds

    Raises:
        ValueError: If the format is invalid.
    """
    value = value.strip().lower()
    if not value:
        raise ValueError("Duration cannot be empty")

    match = DURATION_PATTERN.match(value)
    if not match:
        raise ValueError(
            f"Invalid duration format: '{value}'. Use format like '15m', '1h', '1h30m', '30s'."
        )

    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)

    if hours == 0 and minutes == 0 and seconds == 0:
        raise ValueError("Duration must be greater than zero")

    return timedelta(hours=hours, minutes=minutes, seconds=seconds)


def format_duration(td: timedelta) -> str:
    """Format a timedelta as a human-readable duration string."""
    total_seconds = int(td.total_seconds())

    if total_seconds < 0:
        return "expired"

    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    parts = []
    if hours:
        parts.append(f"{hours}h")
    if minutes:
        parts.append(f"{minutes}m")
    if seconds or not parts:
        parts.append(f"{seconds}s")

    return "".join(parts)


def parse_iso_timestamp(value: str) -> datetime:
    """Parse an ISO 8601 timestamp string.

    Supports standard ISO 8601 formats including timezone offsets.

    Args:
        value: ISO timestamp string (e.g., "2024-01-15T10:30:00Z")

    Returns:
        Parsed datetime object.

    Raises:
        TimestampParseError: If the format is invalid.
    """
    try:
        return datetime.fromisoformat(value)
    except ValueError as e:
        raise TimestampParseError(f"Invalid timestamp format: '{value}'") from e


def format_relative_time(dt: datetime, now: datetime | None = None) -> str:
    """Format a datetime as relative time (e.g., "5 minutes ago").

    Args:
        dt: The datetime to format.
        now: Reference time (defaults to current time).

    Returns:
        Human-readable relative time string.
    """
    from datetime import UTC

    if now is None:
        now = datetime.now(UTC)

    # Ensure both datetimes are timezone-aware for comparison
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    diff = now - dt
    seconds = int(diff.total_seconds())

    if seconds < 0:
        return "in the future"
    if seconds < 60:
        return "just now"
    if seconds < 3600:
        minutes = seconds // 60
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    if seconds < 86400:
        hours = seconds // 3600
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = seconds // 86400
    return f"{days} day{'s' if days != 1 else ''} ago"
