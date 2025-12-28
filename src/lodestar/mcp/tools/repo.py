"""Repository status and information tools for MCP."""

from __future__ import annotations

from mcp.types import CallToolResult

from lodestar.mcp.output import success
from lodestar.mcp.server import LodestarContext
from lodestar.models.spec import TaskStatus


def repo_status(context: LodestarContext) -> CallToolResult:
    """
    Get repository status and statistics.

    Returns comprehensive information about the Lodestar repository including:
    - Repository paths (root, spec, runtime DB)
    - Task counts by status
    - Active leases count
    - Registered agents count
    - Message statistics
    - Suggested next actions

    Args:
        context: Lodestar server context with DB and spec access

    Returns:
        CallToolResult with repository status information
    """
    # Reload spec to get latest state
    context.reload_spec()

    # Count tasks by status
    task_counts: dict[str, int] = {}
    for status in TaskStatus:
        task_counts[status.value] = 0

    for task in context.spec.tasks.values():
        task_counts[task.status.value] += 1

    # Get runtime statistics
    runtime_stats = context.db.get_stats()

    # Get claimable tasks
    claimable_tasks = context.spec.get_claimable_tasks()

    # Determine suggested next actions
    suggested_actions = []
    if runtime_stats["agents"] == 0:
        suggested_actions.append(
            {
                "action": "agent.join",
                "description": "Register as an agent",
            }
        )
    if claimable_tasks:
        suggested_actions.append(
            {
                "action": "task.next",
                "description": f"Get next claimable task ({len(claimable_tasks)} available)",
            }
        )
    suggested_actions.append(
        {
            "action": "task.list",
            "description": "See all tasks",
        }
    )

    # Build structured data
    data = {
        "repoRoot": str(context.repo_root),
        "specPath": str(context.repo_root / ".lodestar" / "spec.yaml"),
        "runtimePath": str(context.db_path),
        "project": {
            "name": context.spec.project.name,
            "defaultBranch": context.spec.project.default_branch,
        },
        "counts": {
            "tasks": {
                "total": len(context.spec.tasks),
                "byStatus": task_counts,
                "claimable": len(claimable_tasks),
            },
            "agents": {
                "registered": runtime_stats["agents"],
                "activeLeases": runtime_stats["active_leases"],
            },
            "messages": {
                "total": runtime_stats["total_messages"],
                "unread": runtime_stats.get("unread_messages", 0),
            },
        },
        "suggestedNextActions": suggested_actions,
    }

    # Build human-readable summary
    summary_parts = [
        f"Repository: {context.spec.project.name}",
        f"Tasks: {len(context.spec.tasks)} total, {len(claimable_tasks)} claimable",
        f"Agents: {runtime_stats['agents']} registered, {runtime_stats['active_leases']} active claims",
        f"Messages: {runtime_stats['total_messages']} total",
    ]
    summary = "\n".join(summary_parts)

    return success(summary, data=data)


def register_repo_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register repository tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.repo.status")
    def status_tool() -> CallToolResult:
        """Get repository status and statistics.

        Returns information about the Lodestar repository including task counts,
        agent statistics, and suggested next actions.
        """
        return repo_status(context)
