"""Tests for utility functions."""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import timedelta
from pathlib import Path

import pytest

from lodestar.mcp.utils import validate_repo_root
from lodestar.util.paths import cleanup_stale_temp_files
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


class TestTempFileCleanup:
    """Test stale temp file cleanup utilities."""

    def test_cleanup_removes_old_tmp_files(self):
        """Test that cleanup removes .tmp files older than max_age."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()

            # Create some temp files
            old_tmp = lodestar_dir / "spec.tmp"
            old_tmp.write_text("old content")

            new_tmp = lodestar_dir / "recent.tmp"
            new_tmp.write_text("new content")

            # Set old file's mtime to 10 minutes ago
            old_time = time.time() - 600
            os.utime(old_tmp, (old_time, old_time))

            # Cleanup with 5 minute threshold
            cleaned = cleanup_stale_temp_files(root, max_age_seconds=300)

            # Old file should be cleaned
            assert cleaned == 1
            assert not old_tmp.exists()

            # New file should remain
            assert new_tmp.exists()

    def test_cleanup_handles_missing_lodestar_dir(self):
        """Test that cleanup handles missing .lodestar directory gracefully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            # No .lodestar directory

            # Should return 0, not raise
            cleaned = cleanup_stale_temp_files(root)
            assert cleaned == 0

    def test_cleanup_ignores_locked_files(self):
        """Test that cleanup ignores files that can't be deleted."""
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()

            # Create a temp file
            tmp_file = lodestar_dir / "locked.tmp"
            tmp_file.write_text("content")

            # Set old mtime
            import time

            old_time = time.time() - 600
            os.utime(tmp_file, (old_time, old_time))

            # Open file to simulate lock (on Windows this would prevent deletion)
            # On Unix, this doesn't actually prevent deletion, but we're testing
            # that the cleanup doesn't raise if it can't delete
            with open(tmp_file):
                # Cleanup should still work (may or may not delete depending on OS)
                cleanup_stale_temp_files(root, max_age_seconds=300)

            # No assertion on result - just verify no exception

    def test_cleanup_removes_atomicwrites_temp_files(self):
        """Test that cleanup also removes tmp* pattern files from atomicwrites."""
        import time

        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()

            # Create atomicwrites-style temp file
            atomic_tmp = lodestar_dir / "tmpabcd1234"
            atomic_tmp.write_text("atomic content")

            # Set old mtime
            old_time = time.time() - 600
            os.utime(atomic_tmp, (old_time, old_time))

            # Cleanup
            cleaned = cleanup_stale_temp_files(root, max_age_seconds=300)

            assert cleaned == 1
            assert not atomic_tmp.exists()
