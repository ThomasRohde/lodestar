"""Retry logic for transient Windows file system errors."""

from __future__ import annotations

import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T", default=None)

# Windows error codes that indicate transient file system locks
WINDOWS_TRANSIENT_ERRORS = {
    5,  # ERROR_ACCESS_DENIED - File is locked by another process
    32,  # ERROR_SHARING_VIOLATION - File is being used by another process
    33,  # ERROR_LOCK_VIOLATION - File region is locked
}


def is_windows_transient_error(error: Exception) -> bool:
    """Check if an exception is a transient Windows file system error.

    Args:
        error: The exception to check

    Returns:
        True if this is a retriable Windows file system error
    """
    if not isinstance(error, OSError):
        return False

    # Check if this is a Windows error we should retry
    return hasattr(error, "winerror") and error.winerror in WINDOWS_TRANSIENT_ERRORS


def retry_on_windows_error(
    func: Callable[[], T],
    max_attempts: int = 3,
    base_delay_ms: int = 50,
) -> T:
    """Retry a function on transient Windows file system errors.

    Uses exponential backoff: base_delay_ms, base_delay_ms*2, base_delay_ms*4, ...

    Args:
        func: The function to retry (should take no arguments)
        max_attempts: Maximum number of attempts (default: 3)
        base_delay_ms: Base delay in milliseconds (default: 50ms)

    Returns:
        The result of the function

    Raises:
        The last exception if all retries fail, or immediately if error is not retriable
    """
    last_error: Exception | None = None

    for attempt in range(max_attempts):
        try:
            return func()
        except Exception as e:
            # If not a transient Windows error, fail immediately
            if not is_windows_transient_error(e):
                raise

            last_error = e

            # If this was the last attempt, raise the error
            if attempt == max_attempts - 1:
                raise

            # Calculate delay with exponential backoff
            delay_ms = base_delay_ms * (2**attempt)
            time.sleep(delay_ms / 1000.0)

    # Should never reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected retry loop exit")
