"""FastMCP server setup for Lodestar."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.loader import load_spec
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

logger = logging.getLogger("lodestar.mcp")


class LodestarContext:
    """Runtime context for the Lodestar MCP server.

    Holds the repository root, runtime database, and spec
    for use by tools and resources.
    """

    def __init__(self, repo_root: Path):
        """Initialize the Lodestar context.

        Args:
            repo_root: Path to the repository root.
        """
        self.repo_root = repo_root
        self.db_path = get_runtime_db_path(repo_root)
        self.db = RuntimeDatabase(self.db_path)
        self.spec = load_spec(repo_root)
        logger.info(f"Initialized context for repository: {repo_root}")

    def reload_spec(self) -> None:
        """Reload the spec from disk."""
        self.spec = load_spec(self.repo_root)
        logger.debug("Reloaded spec from disk")


def create_server(repo_root: Path | None = None) -> FastMCP:
    """
    Create and configure the FastMCP server for Lodestar.

    Args:
        repo_root: Path to the repository root. If None, will be discovered.

    Returns:
        Configured FastMCP server instance.

    Raises:
        FileNotFoundError: If repo_root is None and no Lodestar repository is found.
        ValueError: If the provided repo_root is not a valid Lodestar repository.
    """
    from mcp.server.fastmcp import FastMCP

    # Resolve repository root
    if repo_root is None:
        repo_root = find_lodestar_root()
        if repo_root is None:
            raise FileNotFoundError(
                "Could not find Lodestar repository. "
                "Run from within a repository or use --repo to specify path."
            )
    else:
        # Verify the provided path is a valid Lodestar repository
        if not (repo_root / ".lodestar" / "spec.yaml").exists():
            raise ValueError(f"Not a valid Lodestar repository: {repo_root}")

    # Initialize context
    context = LodestarContext(repo_root)

    # Create FastMCP server
    mcp = FastMCP("lodestar")

    # Store context in server dependencies for tools/resources to access
    # FastMCP uses dependency injection, so we can add the context as a dependency
    mcp.dependencies = {"context": context}

    logger.info(f"Created FastMCP server for repository: {repo_root}")
    logger.info(f"Runtime database: {context.db_path}")
    logger.info(f"Project: {context.spec.project.name}")

    # TODO: Register tools
    # TODO: Register resources

    return mcp
