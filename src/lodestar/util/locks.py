"""Glob pattern overlap detection for file lock conflicts.

Used to detect when multiple agents might be working on the same files
based on task lock patterns.
"""

from __future__ import annotations

import fnmatch
from pathlib import PurePosixPath


def normalize_glob_pattern(pattern: str) -> str:
    """Normalize glob pattern for cross-platform comparison.

    - Convert backslashes to forward slashes (Windows paths)
    - Remove leading ./ if present
    - Strip trailing slashes

    Args:
        pattern: A glob pattern string

    Returns:
        Normalized pattern with forward slashes
    """
    if not pattern:
        return ""

    # Convert Windows backslashes to forward slashes
    normalized = pattern.replace("\\", "/")

    # Remove leading ./
    if normalized.startswith("./"):
        normalized = normalized[2:]

    # Strip trailing slashes
    normalized = normalized.rstrip("/")

    return normalized


def globs_overlap(pattern1: str, pattern2: str) -> bool:
    """Check if two glob patterns potentially overlap.

    Two patterns overlap if:
    - They are identical
    - One pattern matches the other (parent/child relationship)
    - They could match the same files

    Args:
        pattern1: First glob pattern
        pattern2: Second glob pattern

    Returns:
        True if patterns could match overlapping files
    """
    # Normalize both patterns
    p1 = normalize_glob_pattern(pattern1)
    p2 = normalize_glob_pattern(pattern2)

    # Empty patterns don't overlap with anything
    if not p1 or not p2:
        return False

    # Exact match
    if p1 == p2:
        return True

    # Check if one is a parent/prefix of the other
    # For glob patterns, we need to check both directions

    # Check if p1 matches p2 (p1 is parent glob, p2 is child path)
    if _pattern_contains(p1, p2):
        return True

    # Check if p2 matches p1 (p2 is parent glob, p1 is child path)
    if _pattern_contains(p2, p1):
        return True

    # Check for common prefix overlap (both are globs that could match same files)
    return _patterns_could_overlap(p1, p2)


def _pattern_contains(parent: str, child: str) -> bool:
    """Check if a parent glob pattern contains/matches a child path.

    Args:
        parent: A glob pattern that might contain the child
        child: A path or pattern to check

    Returns:
        True if parent pattern would match the child
    """
    # Handle ** (recursive) patterns
    if "**" in parent:
        # For patterns like "src/**", check if child is under "src/"
        prefix = parent.split("**")[0].rstrip("/")
        if prefix:
            # Use path prefix check, not string prefix
            # Extract child's prefix up to first wildcard for comparison
            child_prefix = child.split("**")[0].rstrip("/") if "**" in child else child
            child_prefix = (
                child_prefix.split("*")[0].rstrip("/") if "*" in child_prefix else child_prefix
            )
            # Check if child starts with prefix as a path (not string)
            if child_prefix == prefix or child_prefix.startswith(prefix + "/"):
                return True
        # Also check full fnmatch
        if fnmatch.fnmatch(child, parent):
            return True
    else:
        # Use fnmatch for simple patterns
        if fnmatch.fnmatch(child, parent):
            return True

    return False


def _patterns_could_overlap(p1: str, p2: str) -> bool:
    """Check if two glob patterns could match the same files.

    This handles cases where both patterns have wildcards.

    Args:
        p1: First pattern
        p2: Second pattern

    Returns:
        True if patterns could match overlapping files
    """
    # Get the concrete (non-wildcard) prefix of each pattern
    prefix1 = _get_concrete_prefix(p1)
    prefix2 = _get_concrete_prefix(p2)

    if not prefix1 or not prefix2:
        # One or both patterns start with wildcard - could overlap
        return True

    # Check if prefixes are compatible (one is a path prefix of the other)
    # Must match complete path segments, not just string prefix
    return _is_path_prefix(prefix1, prefix2) or _is_path_prefix(prefix2, prefix1)


def _get_concrete_prefix(pattern: str) -> str:
    """Get the concrete (non-wildcard) prefix of a glob pattern.

    Args:
        pattern: A glob pattern

    Returns:
        The portion before any wildcards
    """
    parts = PurePosixPath(pattern).parts
    concrete_parts = []

    for part in parts:
        if "*" in part or "?" in part or "[" in part:
            break
        concrete_parts.append(part)

    return "/".join(concrete_parts)


def _is_path_prefix(path: str, potential_prefix: str) -> bool:
    """Check if potential_prefix is a path prefix of path.

    Unlike string prefix, this checks complete path segments.
    E.g., "src/auth" is a prefix of "src/auth/users" but NOT of "src/authorization".

    Args:
        path: The path to check
        potential_prefix: The potential prefix

    Returns:
        True if potential_prefix is a valid path prefix of path
    """
    if path == potential_prefix:
        return True

    # Must match complete path segments
    # Either path starts with prefix followed by /
    return path.startswith(potential_prefix + "/")


def find_overlapping_patterns(
    patterns: list[str], other_patterns: list[str]
) -> list[tuple[str, str]]:
    """Find all overlapping pattern pairs between two lists.

    Args:
        patterns: First list of glob patterns
        other_patterns: Second list of glob patterns

    Returns:
        List of (pattern1, pattern2) tuples that overlap
    """
    overlaps: list[tuple[str, str]] = []

    for p1 in patterns:
        for p2 in other_patterns:
            if globs_overlap(p1, p2):
                overlaps.append((p1, p2))

    return overlaps
