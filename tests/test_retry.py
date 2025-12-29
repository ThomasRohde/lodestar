"""Tests for retry utility for Windows file system operations."""

from __future__ import annotations

import pytest

from lodestar.util.retry import (
    is_windows_transient_error,
    retry_on_windows_error,
)


def test_is_windows_transient_error_detects_winerror_5():
    """Test detection of WinError 5 (Access Denied)."""
    # Create a mock OSError with winerror attribute
    error = OSError()
    error.winerror = 5
    assert is_windows_transient_error(error)


def test_is_windows_transient_error_detects_winerror_32():
    """Test detection of WinError 32 (Sharing Violation)."""
    error = OSError()
    error.winerror = 32
    assert is_windows_transient_error(error)


def test_is_windows_transient_error_detects_winerror_33():
    """Test detection of WinError 33 (Lock Violation)."""
    error = OSError()
    error.winerror = 33
    assert is_windows_transient_error(error)


def test_is_windows_transient_error_rejects_other_winerrors():
    """Test that other WinErrors are not considered transient."""
    error = OSError()
    error.winerror = 2  # File not found - not transient
    assert not is_windows_transient_error(error)


def test_is_windows_transient_error_rejects_non_oserror():
    """Test that non-OSError exceptions are not considered transient."""
    assert not is_windows_transient_error(ValueError("test"))
    assert not is_windows_transient_error(RuntimeError("test"))


def test_retry_succeeds_on_first_attempt():
    """Test that retry returns immediately if function succeeds."""
    call_count = 0

    def success_func():
        nonlocal call_count
        call_count += 1
        return "success"

    result = retry_on_windows_error(success_func)
    assert result == "success"
    assert call_count == 1


def test_retry_succeeds_after_transient_errors():
    """Test that retry succeeds after transient Windows errors."""
    call_count = 0

    def eventually_succeeds():
        nonlocal call_count
        call_count += 1
        if call_count < 3:
            error = OSError()
            error.winerror = 5  # WinError 5
            raise error
        return "success"

    result = retry_on_windows_error(eventually_succeeds, max_attempts=3, base_delay_ms=1)
    assert result == "success"
    assert call_count == 3


def test_retry_fails_after_max_attempts():
    """Test that retry raises error after max attempts."""
    call_count = 0

    def always_fails():
        nonlocal call_count
        call_count += 1
        error = OSError()
        error.winerror = 5
        raise error

    with pytest.raises(OSError) as exc_info:
        retry_on_windows_error(always_fails, max_attempts=3, base_delay_ms=1)

    assert exc_info.value.winerror == 5
    assert call_count == 3


def test_retry_fails_immediately_on_non_transient_error():
    """Test that non-transient errors are not retried."""
    call_count = 0

    def raises_non_transient():
        nonlocal call_count
        call_count += 1
        raise ValueError("Not a transient error")

    with pytest.raises(ValueError, match="Not a transient error"):
        retry_on_windows_error(raises_non_transient, max_attempts=3, base_delay_ms=1)

    # Should fail immediately, not retry
    assert call_count == 1


def test_retry_fails_immediately_on_non_retriable_oserror():
    """Test that non-retriable OSErrors are not retried."""
    call_count = 0

    def raises_non_retriable():
        nonlocal call_count
        call_count += 1
        error = OSError()
        error.winerror = 2  # File not found - not transient
        raise error

    with pytest.raises(OSError) as exc_info:
        retry_on_windows_error(raises_non_retriable, max_attempts=3, base_delay_ms=1)

    assert exc_info.value.winerror == 2
    # Should fail immediately, not retry
    assert call_count == 1


def test_retry_exponential_backoff():
    """Test that retry uses exponential backoff."""
    import time

    call_times = []

    def track_timing():
        call_times.append(time.time())
        if len(call_times) < 3:
            error = OSError()
            error.winerror = 5
            raise error
        return "success"

    retry_on_windows_error(track_timing, max_attempts=3, base_delay_ms=10)

    # Check that delays are roughly exponential (10ms, 20ms)
    # Allow some tolerance for timing variations
    assert len(call_times) == 3
    delay1 = (call_times[1] - call_times[0]) * 1000  # Convert to ms
    delay2 = (call_times[2] - call_times[1]) * 1000

    # First delay should be ~10ms
    assert 5 < delay1 < 50, f"First delay was {delay1}ms, expected ~10ms"
    # Second delay should be ~20ms (roughly 2x first delay)
    assert 10 < delay2 < 100, f"Second delay was {delay2}ms, expected ~20ms"
    # Second delay should be roughly double the first
    assert delay2 > delay1, f"Expected exponential backoff, got {delay1}ms then {delay2}ms"
