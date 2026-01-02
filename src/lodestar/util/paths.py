"""Path utilities for finding Lodestar directories."""

from __future__ import annotations

import logging
import time
from pathlib import Path

logger = logging.getLogger(__name__)

LODESTAR_DIR = ".lodestar"
SPEC_FILE = "spec.yaml"
RUNTIME_DB = "runtime.sqlite"


def find_lodestar_root(start: Path | None = None) -> Path | None:
    """Find the root directory containing .lodestar.

    Searches from the start directory upward until a .lodestar directory
    is found or the filesystem root is reached.

    Args:
        start: Starting directory. Defaults to current working directory.

    Returns:
        Path to the repository root containing .lodestar, or None if not found.
    """
    if start is None:
        start = Path.cwd()

    current = start.resolve()

    while current != current.parent:
        if (current / LODESTAR_DIR).is_dir():
            return current
        current = current.parent

    # Check root as well
    if (current / LODESTAR_DIR).is_dir():
        return current

    return None


def get_lodestar_dir(root: Path | None = None) -> Path:
    """Get the .lodestar directory path.

    Args:
        root: Repository root. If None, searches for it.

    Returns:
        Path to the .lodestar directory.

    Raises:
        FileNotFoundError: If no .lodestar directory is found.
    """
    if root is None:
        root = find_lodestar_root()
        if root is None:
            raise FileNotFoundError("Not a lodestar repository. Run 'lodestar init' first.")

    return root / LODESTAR_DIR


def get_spec_path(root: Path | None = None) -> Path:
    """Get the path to spec.yaml."""
    return get_lodestar_dir(root) / SPEC_FILE


def get_runtime_db_path(root: Path | None = None) -> Path:
    """Get the path to runtime.sqlite."""
    return get_lodestar_dir(root) / RUNTIME_DB


def cleanup_stale_temp_files(root: Path | None = None, max_age_seconds: float = 300) -> int:
    """Remove orphaned temp files from failed spec writes.

    Cleans up any .tmp files in the .lodestar directory that are older
    than max_age_seconds. These can accumulate from crashed processes
    or interrupted writes.

    Args:
        root: Repository root. If None, searches for it.
        max_age_seconds: Maximum age in seconds before a temp file is considered stale.
                        Defaults to 300 (5 minutes).

    Returns:
        Number of temp files cleaned up.
    """
    try:
        lodestar_dir = get_lodestar_dir(root)
    except FileNotFoundError:
        return 0

    cleaned = 0
    cutoff_time = time.time() - max_age_seconds

    # Clean up .tmp files (from our atomic writes)
    # and any temp files from atomicwrites library (random names with .tmp suffix)
    for tmp_file in lodestar_dir.glob("*.tmp"):
        try:
            if tmp_file.stat().st_mtime < cutoff_time:
                tmp_file.unlink()
                cleaned += 1
                logger.debug(f"Cleaned up stale temp file: {tmp_file}")
        except OSError:
            # File might be locked or already deleted - ignore
            pass

    # Also clean up any temp files that atomicwrites might create
    # (they follow pattern: tmp* in the same directory)
    for tmp_file in lodestar_dir.glob("tmp*"):
        try:
            if tmp_file.is_file() and tmp_file.stat().st_mtime < cutoff_time:
                tmp_file.unlink()
                cleaned += 1
                logger.debug(f"Cleaned up stale temp file: {tmp_file}")
        except OSError:
            pass

    if cleaned > 0:
        logger.info(f"Cleaned up {cleaned} stale temp file(s) from {lodestar_dir}")

    return cleaned
