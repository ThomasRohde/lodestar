"""MCP resources for read-only state access."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from lodestar.util.paths import get_spec_path


def register_resources(mcp: FastMCP, repo_root: Path) -> None:
    """
    Register MCP resources with the server.

    Args:
        mcp: FastMCP server instance.
        repo_root: Path to the repository root.
    """

    @mcp.resource(
        uri="lodestar://spec",
        mime_type="text/yaml",
        description="Lodestar specification file (.lodestar/spec.yaml)",
    )
    def get_spec() -> str:
        """
        Provides read-only access to the spec.yaml file.

        Returns:
            The content of .lodestar/spec.yaml as a string.
        """
        spec_path = get_spec_path(repo_root)
        return spec_path.read_text(encoding="utf-8")

    # TODO: Implement lodestar://status resource
    # TODO: Implement lodestar://task/{taskId} resource
