"""Retry logic for transient Windows file system errors."""

from __future__ import annotations

import random
import time
from collections.abc import Callable
from typing import TypeVar

T = TypeVar("T", default=None)

# Windows error codes that indicate transient file system locks
# These are typically caused by antivirus, Windows Search, or other processes
# that briefly hold file handles during rename/write operations
WINDOWS_TRANSIENT_ERRORS = {
    5,  # ERROR_ACCESS_DENIED - File is locked by another process
    32,  # ERROR_SHARING_VIOLATION - File is being used by another process
    33,  # ERROR_LOCK_VIOLATION - File region is locked
    110,  # ERROR_OPEN_FAILED - System cannot open the file
    158,  # ERROR_NOT_LOCKED - Segment already unlocked (race condition)
    183,  # ERROR_ALREADY_EXISTS - Can occur during atomic rename race
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

    # Try to extract winerror from the exception
    winerror = None

    # First check if winerror attribute exists (set by Python on Windows)
    if hasattr(error, "winerror") and error.winerror is not None:
        winerror = error.winerror
    # Otherwise check args tuple: OSError(errno, strerror, filename, winerror)
    elif len(error.args) >= 4 and error.args[3] is not None:
        winerror = error.args[3]

    return winerror in WINDOWS_TRANSIENT_ERRORS


def retry_on_windows_error(
    func: Callable[[], T],
    max_attempts: int = 5,
    base_delay_ms: int = 100,
    jitter_factor: float = 0.3,
) -> T:
    """Retry a function on transient Windows file system errors.

    Uses exponential backoff with jitter to handle Windows file locking issues
    caused by antivirus, Windows Search indexer, and other file system monitors.

    Delay calculation: base_delay_ms * (2^attempt) * (1 ± jitter_factor)
    With defaults: ~100ms, ~200ms, ~400ms, ~800ms, ~1600ms = ~3.1s total window

    Args:
        func: The function to retry (should take no arguments)
        max_attempts: Maximum number of attempts (default: 5)
        base_delay_ms: Base delay in milliseconds (default: 100ms)
        jitter_factor: Random jitter factor 0-1 to prevent synchronized retries (default: 0.3)

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

            # Calculate delay with exponential backoff and jitter
            delay_ms = base_delay_ms * (2**attempt)
            # Add random jitter to prevent synchronized retries from multiple processes
            jitter = delay_ms * jitter_factor * (2 * random.random() - 1)  # noqa: S311
            delay_ms = max(10, delay_ms + jitter)  # Ensure minimum 10ms delay
            time.sleep(delay_ms / 1000.0)

    # Should never reach here, but satisfy type checker
    if last_error:
        raise last_error
    raise RuntimeError("Unexpected retry loop exit")
