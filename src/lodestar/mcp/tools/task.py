"""Task management tools for MCP."""

from __future__ import annotations

from mcp.types import CallToolResult

from lodestar.core.task_service import get_unclaimed_claimable_tasks
from lodestar.mcp.output import error, format_summary, with_item, with_list
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import ValidationError, clamp_limit, validate_task_id
from lodestar.models.spec import TaskStatus
from lodestar.util.prd import check_prd_drift


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


def task_get(
    context: LodestarContext,
    task_id: str,
) -> CallToolResult:
    """
    Get detailed information about a specific task.

    Returns comprehensive task details including spec information, runtime state,
    PRD context, dependency graph, and warnings.

    Args:
        context: Lodestar server context
        task_id: Task ID to retrieve (required)

    Returns:
        CallToolResult with detailed task information
    """
    # Validate task ID
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        return error(str(e), error_code="INVALID_TASK_ID")

    # Reload spec to get latest state
    context.reload_spec()

    # Get task from spec
    task = context.spec.get_task(validated_task_id)
    if task is None:
        return error(
            f"Task {validated_task_id} not found",
            error_code="TASK_NOT_FOUND",
            details={"task_id": validated_task_id},
        )

    # Get dependency graph info
    dep_graph = context.spec.get_dependency_graph()
    dependents = dep_graph.get(validated_task_id, [])

    # Get active lease if any
    lease = context.db.get_active_lease(validated_task_id)

    # Check for claimability
    verified_tasks = context.spec.get_verified_tasks()
    is_claimable = task.is_claimable(verified_tasks)

    # Build task detail structure
    task_detail = {
        "id": task.id,
        "title": task.title,
        "description": task.description,
        "acceptanceCriteria": task.acceptance_criteria,
        "status": task.status.value,
        "priority": task.priority,
        "labels": task.labels,
        "locks": task.locks,
        "createdAt": task.created_at.isoformat(),
        "updatedAt": task.updated_at.isoformat(),
    }

    # Add dependency information
    task_detail["dependencies"] = {
        "dependsOn": task.depends_on,
        "dependents": dependents,
        "isClaimable": is_claimable,
    }

    # Add PRD context if available
    if task.prd:
        prd_data = {
            "source": task.prd.source,
            "refs": [
                {
                    "anchor": ref.anchor,
                    "lines": ref.lines,
                }
                for ref in task.prd.refs
            ],
            "excerpt": task.prd.excerpt,
            "prdHash": task.prd.prd_hash,
        }
        task_detail["prd"] = prd_data
    else:
        task_detail["prd"] = None

    # Add runtime information
    runtime_info = {
        "claimed": lease is not None,
    }

    if lease:
        runtime_info["claimedBy"] = {
            "agentId": lease.agent_id,
            "leaseId": lease.lease_id,
            "expiresAt": lease.expires_at.isoformat(),
            "createdAt": lease.created_at.isoformat(),
        }
    else:
        runtime_info["claimedBy"] = None

    task_detail["runtime"] = runtime_info

    # Generate warnings
    warnings = []

    # Check for PRD drift
    if task.prd and task.prd.prd_hash:
        prd_path = context.repo_root / task.prd.source
        if not prd_path.exists():
            warnings.append(
                {
                    "type": "MISSING_PRD_SOURCE",
                    "message": f"PRD source file not found: {task.prd.source}",
                    "severity": "warning",
                }
            )
        else:
            try:
                if check_prd_drift(task.prd.prd_hash, prd_path):
                    warnings.append(
                        {
                            "type": "PRD_DRIFT_DETECTED",
                            "message": f"PRD file {task.prd.source} has changed since task creation",
                            "severity": "info",
                        }
                    )
            except Exception:
                # If we can't check drift, add a warning
                warnings.append(
                    {
                        "type": "PRD_DRIFT_CHECK_FAILED",
                        "message": f"Could not verify PRD drift for {task.prd.source}",
                        "severity": "warning",
                    }
                )

    # Check for missing dependencies
    missing_deps = [dep for dep in task.depends_on if dep not in context.spec.tasks]
    if missing_deps:
        warnings.append(
            {
                "type": "MISSING_DEPENDENCIES",
                "message": f"Task has dependencies that don't exist: {', '.join(missing_deps)}",
                "severity": "error",
            }
        )

    task_detail["warnings"] = warnings

    # Build summary
    summary = format_summary(
        "Task",
        task.id,
        f"- {task.title} ({task.status.value})",
    )

    return with_item(summary, item=task_detail)


def task_next(
    context: LodestarContext,
    agent_id: str | None = None,
    limit: int | None = None,
) -> CallToolResult:
    """
    Get next claimable tasks for an agent.

    Returns tasks that are ready and have all dependencies satisfied,
    filtered to exclude tasks that are already claimed.

    Args:
        context: Lodestar server context
        agent_id: Agent ID for personalization (optional, currently unused)
        limit: Maximum number of tasks to return (default 5, max 20)

    Returns:
        CallToolResult with claimable tasks and rationale
    """
    # Reload spec to get latest state
    context.reload_spec()

    # Validate and clamp limit (max 20 for task next)
    validated_limit = clamp_limit(limit, default=5)
    if validated_limit > 20:
        validated_limit = 20

    # Get unclaimed claimable tasks
    claimable_tasks = get_unclaimed_claimable_tasks(context.spec, context.db)

    # Take only the requested limit
    tasks = claimable_tasks[:validated_limit]

    # Get lease information for all tasks
    lease_map = {}
    all_active_leases = context.db.get_all_active_leases()
    for lease in all_active_leases:
        lease_map[lease.task_id] = lease

    # Build task summaries
    task_summaries = []
    for task in tasks:
        summary = {
            "id": task.id,
            "title": task.title,
            "status": task.status.value,
            "priority": task.priority,
            "labels": task.labels,
            "dependencies": task.depends_on,
        }
        task_summaries.append(summary)

    # Build rationale
    total_claimable = len(claimable_tasks)
    rationale_parts = []

    if total_claimable == 0:
        rationale_parts.append("No claimable tasks available.")
        rationale_parts.append("Tasks must be in 'ready' status with all dependencies verified.")
    else:
        rationale_parts.append(
            f"Found {total_claimable} claimable task(s), showing top {len(tasks)} by priority."
        )
        rationale_parts.append("Tasks are ready for work with all dependencies satisfied.")

    rationale = " ".join(rationale_parts)

    # Build summary
    summary = format_summary(
        "Next",
        f"{len(tasks)} task(s)",
        f"({total_claimable} total claimable)" if total_claimable > 0 else "",
    )

    # Build response data
    response_data = {
        "candidates": task_summaries,
        "rationale": rationale,
        "totalClaimable": total_claimable,
    }

    return with_item(summary, item=response_data)


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

    @mcp.tool(name="lodestar.task.get")
    def get_tool(task_id: str) -> CallToolResult:
        """Get detailed information about a specific task.

        Returns comprehensive task details including description, acceptance criteria,
        PRD context, dependency graph, runtime state, and warnings.

        Args:
            task_id: Task ID to retrieve (required)

        Returns:
            Detailed task information with:
            - Task details (description, acceptance criteria, labels, locks, etc.)
            - Dependency information (dependsOn, dependents, isClaimable)
            - PRD context (source, refs, excerpt, prdHash) if available
            - Runtime state (claimed status, lease info)
            - Warnings (PRD drift, missing dependencies)
        """
        return task_get(context=context, task_id=task_id)

    @mcp.tool(name="lodestar.task.next")
    def next_tool(
        agent_id: str | None = None,
        limit: int | None = None,
    ) -> CallToolResult:
        """Get next claimable tasks.

        Returns tasks that are ready for work with all dependencies satisfied.
        Tasks are filtered to exclude already-claimed tasks and sorted by priority.

        This is the dependency-aware "what should I do next" tool.

        Args:
            agent_id: Agent ID for personalization (optional, currently unused for filtering but may be used for future prioritization)
            limit: Maximum number of tasks to return (default 5, max 20)

        Returns:
            Candidates (claimable task summaries), rationale explaining selection,
            and total number of claimable tasks available
        """
        return task_next(context=context, agent_id=agent_id, limit=limit)
