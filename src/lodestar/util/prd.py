"""PRD utilities for context extraction and drift detection."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path


def compute_prd_hash(path: Path) -> str:
    """Compute SHA256 hash of a PRD file's content.

    Args:
        path: Path to the PRD file.

    Returns:
        SHA256 hex digest of the file content.

    Raises:
        FileNotFoundError: If the PRD file doesn't exist.
    """
    content = path.read_text(encoding="utf-8")
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def extract_prd_section(
    path: Path,
    anchor: str | None = None,
    lines: tuple[int, int] | None = None,
) -> str:
    """Extract a section from a PRD file.

    Args:
        path: Path to the PRD file.
        anchor: Section anchor (e.g., "#task-claiming"). Supports both:
            - Explicit anchors: `## Heading {#anchor-id}`
            - Implicit anchors: heading text with dashes/spaces matching
        lines: Optional (start, end) line range (1-indexed, inclusive).

    Returns:
        The extracted section content.

    Raises:
        FileNotFoundError: If the PRD file doesn't exist.
        ValueError: If neither anchor nor lines are provided, or anchor not found.
    """
    content = path.read_text(encoding="utf-8")
    all_lines = content.splitlines()

    if lines:
        start, end = lines
        # Convert to 0-indexed and extract
        return "\n".join(all_lines[max(0, start - 1) : end])

    if anchor:
        anchor_text = anchor.lstrip("#")

        # First, try explicit anchor syntax: `## Heading {#anchor-id}`
        explicit_pattern = re.compile(
            rf"^(#{{1,6}})\s+.+\{{#{re.escape(anchor_text)}\}}", re.IGNORECASE
        )

        # Second, try implicit anchor (heading text matches anchor)
        # Replace dashes with pattern that matches either space or dash
        implicit_pattern_text = anchor_text.replace("-", "[ -]")
        implicit_pattern = re.compile(
            rf"^(#{{1,6}})\s+{implicit_pattern_text}", re.IGNORECASE
        )

        start_line = None
        heading_level = None

        for i, line in enumerate(all_lines):
            # Try explicit anchor first
            match = explicit_pattern.match(line)
            if match:
                start_line = i
                heading_level = len(match.group(1))
                break
            # Try implicit anchor
            match = implicit_pattern.match(line)
            if match:
                start_line = i
                heading_level = len(match.group(1))
                break

        if start_line is None:
            import os

            raise ValueError(f"Anchor '{anchor}' not found in {os.path.normpath(path)}")

        # Find next heading at same or higher level
        end_line = len(all_lines)
        for i in range(start_line + 1, len(all_lines)):
            line = all_lines[i]
            next_heading = re.match(r"^(#{1,6})\s+", line)
            if (
                next_heading
                and heading_level is not None
                and len(next_heading.group(1)) <= heading_level
            ):
                end_line = i
                break

        return "\n".join(all_lines[start_line:end_line])

    raise ValueError("Either anchor or lines must be provided")


def check_prd_drift(stored_hash: str, path: Path) -> bool:
    """Check if a PRD file has changed since the hash was computed.

    Args:
        stored_hash: Previously computed SHA256 hash.
        path: Path to the PRD file.

    Returns:
        True if the file has changed (drift detected), False otherwise.

    Raises:
        FileNotFoundError: If the PRD file doesn't exist.
    """
    current_hash = compute_prd_hash(path)
    return current_hash != stored_hash


def truncate_to_budget(content: str, max_chars: int = 1000) -> str:
    """Truncate content to fit within a character budget.

    Attempts to truncate at paragraph boundaries for cleaner output.

    Args:
        content: The content to truncate.
        max_chars: Maximum characters allowed.

    Returns:
        Truncated content, possibly with "..." suffix if truncated.
    """
    if len(content) <= max_chars:
        return content

    # Try to truncate at paragraph boundary
    truncated = content[: max_chars - 3]
    last_para = truncated.rfind("\n\n")
    if last_para > max_chars // 2:
        return truncated[:last_para] + "\n..."

    # Fall back to word boundary
    last_space = truncated.rfind(" ")
    if last_space > max_chars // 2:
        return truncated[:last_space] + "..."

    return truncated + "..."
