"""MCP resources for read-only state access."""

from __future__ import annotations

import json
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from lodestar.mcp.server import LodestarContext
from lodestar.util.paths import get_spec_path


def register_resources(mcp: FastMCP, context: LodestarContext) -> None:
    """
    Register MCP resources with the server.

    Args:
        mcp: FastMCP server instance.
        context: Lodestar server context with DB and spec access.
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
        spec_path = get_spec_path(context.repo_root)
        return spec_path.read_text(encoding="utf-8")

    @mcp.resource(
        uri="lodestar://status",
        mime_type="application/json",
        description="Repository status and statistics (JSON)",
    )
    def get_status() -> str:
        """
        Provides read-only access to repository status.

        Returns comprehensive information about the Lodestar repository including:
        - Repository paths (root, spec, runtime DB)
        - Task counts by status
        - Active leases count
        - Registered agents count
        - Message statistics
        - Suggested next actions

        Returns:
            JSON string with repository status information.
        """
        from lodestar.mcp.tools.repo import repo_status

        # Get status using the existing repo_status function
        result = repo_status(context)

        # Extract the structured data from the CallToolResult
        if hasattr(result, "structuredContent") and result.structuredContent:
            return json.dumps(result.structuredContent, indent=2)

        # Fallback: return empty object if something went wrong
        return "{}"

    @mcp.resource(
        uri="lodestar://task/{taskId}",
        mime_type="application/json",
        description="Get a specific task by ID (JSON)",
    )
    def get_task(task_id: str) -> str:
        """
        Provides read-only access to a specific task.

        Returns comprehensive task details including spec information,
        runtime state, PRD context, dependency graph, and warnings.

        Args:
            task_id: The task identifier (e.g., "T001", "F099")

        Returns:
            JSON string with task details, or error if task not found.
        """
        from lodestar.mcp.tools.task import task_get

        # Get task using the existing task_get function
        result = task_get(context, task_id)

        # Extract the structured data from the CallToolResult
        if hasattr(result, "structuredContent") and result.structuredContent:
            return json.dumps(result.structuredContent, indent=2)

        # If task not found or error, try to extract error info
        if (
            hasattr(result, "isError")
            and result.isError
            and hasattr(result, "structuredContent")
            and result.structuredContent
        ):
            return json.dumps(result.structuredContent, indent=2)

        # Fallback: return generic error
        return json.dumps({"error": f"Task {task_id} not found"})
