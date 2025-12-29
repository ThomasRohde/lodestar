"""Tests for utility functions."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from lodestar.mcp.utils import validate_repo_root
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


class TestPathNormalization:
    """Test that paths in error messages use platform-native separators."""

    def test_validate_repo_root_normalizes_paths(self):
        """Test that validate_repo_root() normalizes paths in error messages."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)

            # Test with non-existent directory
            fake_path = root / "nonexistent"
            is_valid, error_msg = validate_repo_root(fake_path)
            assert not is_valid

            # Check that path uses platform-appropriate separators
            if sys.platform == "win32":
                # On Windows, normalized path should contain backslashes
                normalized = os.path.normpath(fake_path)
                assert normalized in error_msg
                # Should not have mixed separators
                assert error_msg.count("\\") > 0 or "/" not in error_msg
            else:
                # On Unix, should have forward slashes
                normalized = os.path.normpath(fake_path)
                assert normalized in error_msg

            # Test with missing .lodestar directory
            root.mkdir(exist_ok=True)
            is_valid, error_msg = validate_repo_root(root)
            assert not is_valid
            assert ".lodestar" in error_msg

            # Verify path normalization
            if sys.platform == "win32":
                normalized = os.path.normpath(root)
                assert normalized in error_msg

            # Test with missing spec.yaml
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()
            is_valid, error_msg = validate_repo_root(root)
            assert not is_valid
            assert "spec.yaml" in error_msg

            # Verify path normalization for lodestar_dir
            if sys.platform == "win32":
                normalized = os.path.normpath(lodestar_dir)
                assert normalized in error_msg
