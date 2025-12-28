"""FastMCP server setup for Lodestar."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP


def create_server(repo_root: Path | None = None) -> FastMCP:
    """
    Create and configure the FastMCP server for Lodestar.

    Args:
        repo_root: Path to the repository root. If None, will be discovered.

    Returns:
        Configured FastMCP server instance.
    """
    from mcp.server.fastmcp import FastMCP

    mcp = FastMCP("lodestar")

    # TODO: Add repo root resolution logic
    # TODO: Register tools
    # TODO: Register resources

    return mcp
