"""Tests for utility functions."""

from __future__ import annotations

from datetime import timedelta

import pytest

from lodestar.util.time import format_duration, parse_duration


class TestTimeParsing:
    """Test time parsing utilities."""

    def test_parse_minutes(self):
        result = parse_duration("15m")
        assert result == timedelta(minutes=15)

    def test_parse_hours(self):
        result = parse_duration("2h")
        assert result == timedelta(hours=2)

    def test_parse_seconds(self):
        result = parse_duration("30s")
        assert result == timedelta(seconds=30)

    def test_parse_combined(self):
        result = parse_duration("1h30m")
        assert result == timedelta(hours=1, minutes=30)

    def test_parse_full(self):
        result = parse_duration("2h15m30s")
        assert result == timedelta(hours=2, minutes=15, seconds=30)

    def test_parse_case_insensitive(self):
        result = parse_duration("15M")
        assert result == timedelta(minutes=15)

    def test_parse_empty_fails(self):
        with pytest.raises(ValueError):
            parse_duration("")

    def test_parse_invalid_format_fails(self):
        with pytest.raises(ValueError):
            parse_duration("invalid")

    def test_parse_zero_fails(self):
        with pytest.raises(ValueError):
            parse_duration("0m")


class TestTimeFormatting:
    """Test time formatting utilities."""

    def test_format_minutes(self):
        result = format_duration(timedelta(minutes=15))
        assert result == "15m"

    def test_format_hours(self):
        result = format_duration(timedelta(hours=2))
        assert result == "2h"

    def test_format_seconds(self):
        result = format_duration(timedelta(seconds=45))
        assert result == "45s"

    def test_format_combined(self):
        result = format_duration(timedelta(hours=1, minutes=30, seconds=15))
        assert result == "1h30m15s"

    def test_format_zero(self):
        result = format_duration(timedelta(0))
        assert result == "0s"

    def test_format_expired(self):
        result = format_duration(timedelta(seconds=-10))
        assert result == "expired"
