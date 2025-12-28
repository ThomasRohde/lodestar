"""MCP resources for read-only state access."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def register_resources(mcp: FastMCP, repo_root: Path) -> None:
    """
    Register MCP resources with the server.

    Args:
        mcp: FastMCP server instance.
        repo_root: Path to the repository root.
    """
    # TODO: Implement lodestar://spec resource
    # TODO: Implement lodestar://status resource
    # TODO: Implement lodestar://task/{taskId} resource
    pass
