"""Utility functions for MCP server operations."""

from __future__ import annotations

from pathlib import Path


def find_repo_root(start_path: Path | None = None) -> Path | None:
    """
    Find the repository root by walking upwards to find .lodestar/ directory.

    Args:
        start_path: Starting path for search. Defaults to current directory.

    Returns:
        Path to repository root, or None if not found.
    """
    current = start_path or Path.cwd()

    # Walk up the directory tree
    for parent in [current, *current.parents]:
        lodestar_dir = parent / ".lodestar"
        if lodestar_dir.is_dir():
            return parent

    return None


def validate_repo_root(repo_root: Path) -> tuple[bool, str]:
    """
    Validate that a path is a valid Lodestar repository root.

    Args:
        repo_root: Path to validate.

    Returns:
        Tuple of (is_valid, error_message). error_message is empty if valid.
    """
    import os
    if not repo_root.exists():
        return False, f"Repository root does not exist: {os.path.normpath(repo_root)}"

    lodestar_dir = repo_root / ".lodestar"
    if not lodestar_dir.is_dir():
        return False, f"No .lodestar directory found at: {os.path.normpath(repo_root)}"

    spec_file = lodestar_dir / "spec.yaml"
    if not spec_file.exists():
        return False, f"No spec.yaml found in: {os.path.normpath(lodestar_dir)}"

    return True, ""
