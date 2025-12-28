"""Task management tools for MCP."""

from __future__ import annotations

from mcp.types import CallToolResult

from lodestar.mcp.output import format_summary, with_list
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import ValidationError, clamp_limit
from lodestar.models.spec import TaskStatus


def task_list(
    context: LodestarContext,
    status: str | None = None,
    label: str | None = None,
    limit: int | None = None,
    cursor: str | None = None,
) -> CallToolResult:
    """
    List tasks with optional filtering.

    Args:
        context: Lodestar server context
        status: Filter by status (ready|done|verified|deleted|all) (optional)
        label: Filter by label (optional)
        limit: Maximum number of tasks to return (default 50, max 200)
        cursor: Pagination cursor - task ID to start after (optional)

    Returns:
        CallToolResult with tasks array and pagination info
    """
    # Reload spec to get latest state
    context.reload_spec()

    # Validate and clamp limit (max 200 for task list)
    validated_limit = clamp_limit(limit, default=50)
    if validated_limit > 200:
        validated_limit = 200

    # Parse status filter
    status_filter: TaskStatus | None = None
    include_deleted = False
    if status:
        status = status.strip().lower()
        if status == "all":
            # Include all statuses except deleted
            status_filter = None
            include_deleted = False
        elif status == "deleted":
            # Only show deleted
            status_filter = TaskStatus.DELETED
            include_deleted = True
        else:
            # Validate status value
            try:
                status_filter = TaskStatus(status)
            except ValueError:
                valid_statuses = [s.value for s in TaskStatus] + ["all"]
                raise ValidationError(
                    f"Invalid status '{status}'. Must be one of: {', '.join(valid_statuses)}",
                    field="status",
                )

    # Filter tasks
    tasks = []
    for task_id, task in context.spec.tasks.items():
        # Skip if cursor provided and we haven't reached it yet
        if cursor and task_id <= cursor:
            continue

        # Filter by status
        if status_filter is not None:
            if task.status != status_filter:
                continue
        else:
            # If no status filter and not showing deleted, exclude deleted tasks
            if not include_deleted and task.status == TaskStatus.DELETED:
                continue

        # Filter by label
        if label and label not in task.labels:
            continue

        tasks.append(task)

    # Sort by priority, then ID
    tasks.sort(key=lambda t: (t.priority, t.id))

    # Apply limit and track if there are more results
    has_more = len(tasks) > validated_limit
    tasks = tasks[:validated_limit]

    # Get lease information for all tasks
    lease_map = {}
    all_active_leases = context.db.get_all_active_leases()
    for lease in all_active_leases:
        lease_map[lease.task_id] = lease

    # Build task summaries
    task_summaries = []
    for task in tasks:
        lease = lease_map.get(task.id)

        summary = {
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority,
            "labels": task.labels,
            "dependencies": task.depends_on,
            "claimedByAgentId": lease.agent_id if lease else None,
            "leaseExpiresAt": lease.expires_at.isoformat() if lease else None,
            "updatedAt": task.updated_at.isoformat(),
        }
        task_summaries.append(summary)

    # Build pagination data
    next_cursor = tasks[-1].id if has_more and tasks else None

    # Build human-readable summary
    filter_parts = []
    if status:
        filter_parts.append(f"status={status}")
    if label:
        filter_parts.append(f"label={label}")

    filter_desc = f" ({', '.join(filter_parts)})" if filter_parts else ""

    summary = format_summary(
        "Found",
        f"{len(task_summaries)} task(s)",
        filter_desc,
    )

    # Build metadata with pagination and filter info
    meta = {
        "nextCursor": next_cursor,
        "filters": {
            "status": status if status else None,
            "label": label if label else None,
        },
    }

    return with_list(
        summary,
        items=task_summaries,
        total=len(context.spec.tasks),
        meta=meta,
    )


def register_task_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register task management tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.task.list")
    def list_tool(
        status: str | None = None,
        label: str | None = None,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> CallToolResult:
        """List tasks with optional filtering and pagination.

        Returns tasks sorted by priority (lower priority values first), then by ID.
        By default, excludes deleted tasks unless status="deleted" or status="all".

        Args:
            status: Filter by status - one of: ready, done, verified, deleted, or all (optional)
            label: Filter by label - only tasks with this label (optional)
            limit: Maximum number of tasks to return (default 50, max 200)
            cursor: Pagination cursor - task ID to start after (optional)

        Returns:
            List of task summaries with pagination info and nextCursor for fetching more results
        """
        return task_list(
            context=context,
            status=status,
            label=label,
            limit=limit,
            cursor=cursor,
        )
