"""Path utilities for finding Lodestar directories."""

from __future__ import annotations

from pathlib import Path

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
