"""Time parsing and formatting utilities."""

from __future__ import annotations

import re
from datetime import timedelta

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
