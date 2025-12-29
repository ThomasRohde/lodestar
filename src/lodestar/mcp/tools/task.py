"""Task management tools for MCP."""

from __future__ import annotations

from mcp.types import CallToolResult

from lodestar.core.task_service import get_unclaimed_claimable_tasks
from lodestar.mcp.output import error, format_summary, with_item, with_list
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import ValidationError, clamp_limit, validate_task_id
from lodestar.models.spec import TaskStatus
from lodestar.util.prd import check_prd_drift, extract_prd_section, truncate_to_budget


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
    labels: list[str] | None = None,
    max_priority: int | None = None,
) -> CallToolResult:
    """
    Get next claimable tasks for an agent.

    Returns tasks that are ready and have all dependencies satisfied,
    filtered to exclude tasks that are already claimed. Optional filters
    allow agents to focus on specific types of work.

    Args:
        context: Lodestar server context
        agent_id: Agent ID for personalization (optional, currently unused)
        limit: Maximum number of tasks to return (default 5, max 20)
        labels: Filter to tasks with ANY of these labels (optional)
        max_priority: Filter to tasks with priority <= this value (lower numbers = higher priority) (optional)

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

    # Apply label filter if provided
    if labels:
        claimable_tasks = [
            task for task in claimable_tasks
            if any(label in task.labels for label in labels)
        ]

    # Apply max_priority filter if provided
    if max_priority is not None:
        claimable_tasks = [
            task for task in claimable_tasks
            if task.priority <= max_priority
        ]

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
        rationale_parts.append("No claimable tasks available")
        if labels:
            rationale_parts.append(f"with labels {', '.join(labels)}")
        if max_priority is not None:
            rationale_parts.append(f"with priority <= {max_priority}")
        if not labels and max_priority is None:
            rationale_parts.append("(tasks must be in 'ready' status with all dependencies verified)")
    else:
        rationale_parts.append(
            f"Found {total_claimable} claimable task(s), showing top {len(tasks)} by priority."
        )
        if labels:
            rationale_parts.append(f"Filtered to labels: {', '.join(labels)}.")
        if max_priority is not None:
            rationale_parts.append(f"Filtered to priority <= {max_priority}.")
        rationale_parts.append("Tasks are ready for work with all dependencies satisfied")

    rationale = " ".join(rationale_parts)

    # Build summary
    summary_parts = [f"{len(tasks)} task(s)"]
    if labels:
        summary_parts.append(f"labels={','.join(labels)}")
    if max_priority is not None:
        summary_parts.append(f"priority<={max_priority}")

    summary = format_summary(
        "Next",
        " ".join(summary_parts),
        f"({total_claimable} total claimable)" if total_claimable > 0 else "",
    )

    # Build response data
    response_data = {
        "candidates": task_summaries,
        "rationale": rationale,
        "totalClaimable": total_claimable,
    }

    # Include filter info in metadata
    if labels or max_priority is not None:
        response_data["filters"] = {}
        if labels:
            response_data["filters"]["labels"] = labels
        if max_priority is not None:
            response_data["filters"]["maxPriority"] = max_priority

    return with_item(summary, item=response_data)


def task_context(
    context: LodestarContext,
    task_id: str,
    max_chars: int | None = None,
) -> CallToolResult:
    """
    Get PRD context for a task.

    Returns the task's PRD references, frozen excerpt, and live PRD sections
    (if available). Includes drift detection to warn if the PRD has changed
    since task creation.

    Args:
        context: Lodestar server context
        task_id: Task ID to get context for (required)
        max_chars: Maximum characters for context output (default 1000)

    Returns:
        CallToolResult with PRD context bundle and drift warnings
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

    # Validate and set default for max_chars
    if max_chars is None:
        max_chars = 1000
    elif max_chars <= 0:
        raise ValidationError("max_chars must be positive", field="max_chars")

    # Build context bundle
    context_bundle: dict = {
        "taskId": task.id,
        "title": task.title,
        "description": task.description,
    }

    warnings = []
    prd_sections = []

    if task.prd:
        # Add PRD metadata
        context_bundle["prdSource"] = task.prd.source
        context_bundle["prdRefs"] = [
            {
                "anchor": ref.anchor,
                "lines": ref.lines,
            }
            for ref in task.prd.refs
        ]

        # Include frozen excerpt if available
        if task.prd.excerpt:
            context_bundle["prdExcerpt"] = task.prd.excerpt

        # Check for PRD drift
        drift_info = {
            "changed": False,
            "details": None,
        }

        if task.prd.prd_hash:
            prd_path = context.repo_root / task.prd.source
            if prd_path.exists():
                try:
                    if check_prd_drift(task.prd.prd_hash, prd_path):
                        drift_info["changed"] = True
                        drift_info["details"] = (
                            f"PRD has changed since task creation. "
                            f"Review {task.prd.source} for updates."
                        )
                        warnings.append(
                            {
                                "type": "PRD_DRIFT_DETECTED",
                                "message": drift_info["details"],
                                "severity": "info",
                            }
                        )
                except Exception:
                    pass  # Ignore hash check errors

        context_bundle["drift"] = drift_info

        # Try to extract live PRD sections
        prd_path = context.repo_root / task.prd.source
        if prd_path.exists():
            for ref in task.prd.refs:
                try:
                    lines_tuple: tuple[int, int] | None = None
                    if ref.lines and len(ref.lines) == 2:
                        lines_tuple = (ref.lines[0], ref.lines[1])
                    section = extract_prd_section(
                        prd_path,
                        anchor=ref.anchor,
                        lines=lines_tuple,
                    )
                    prd_sections.append(
                        {
                            "anchor": ref.anchor,
                            "content": section,
                        }
                    )
                except (ValueError, FileNotFoundError):
                    pass  # Section not found
        else:
            warnings.append(
                {
                    "type": "MISSING_PRD_SOURCE",
                    "message": f"PRD source file not found: {task.prd.source}",
                    "severity": "warning",
                }
            )

    else:
        # No PRD context available
        context_bundle["prdSource"] = None
        context_bundle["prdRefs"] = []
        context_bundle["prdExcerpt"] = None
        context_bundle["drift"] = None

    if prd_sections:
        context_bundle["prdSections"] = prd_sections

    # Build combined content and truncate to budget
    total_content = task.description or ""
    if task.prd and task.prd.excerpt:
        total_content += "\n" + task.prd.excerpt
    for sec in prd_sections:
        total_content += "\n" + sec["content"]

    truncated_content = truncate_to_budget(total_content, max_chars)
    context_bundle["content"] = truncated_content
    context_bundle["truncated"] = len(total_content) > max_chars

    # Add warnings to bundle
    context_bundle["warnings"] = warnings

    # Build summary
    has_prd = task.prd is not None
    prd_status = "with PRD context" if has_prd else "no PRD context"
    summary = format_summary(
        "Context",
        task.id,
        f"- {prd_status}",
    )

    return with_item(summary, item=context_bundle)


def register_task_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register task management tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar_task_list")
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

    @mcp.tool(name="lodestar_task_get")
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

    @mcp.tool(name="lodestar_task_next")
    def next_tool(
        agent_id: str | None = None,
        limit: int | None = None,
        labels: list[str] | None = None,
        max_priority: int | None = None,
    ) -> CallToolResult:
        """Get next claimable tasks with optional filtering.

        Returns tasks that are ready for work with all dependencies satisfied.
        Tasks are filtered to exclude already-claimed tasks and sorted by priority.
        Optional filters allow focusing on specific types of work.

        This is the dependency-aware "what should I do next" tool.

        Args:
            agent_id: Agent ID for personalization (optional, currently unused for filtering but may be used for future prioritization)
            limit: Maximum number of tasks to return (default 5, max 20)
            labels: Filter to tasks with ANY of these labels (optional, e.g., ["frontend", "backend"])
            max_priority: Filter to tasks with priority <= this value (lower numbers = higher priority) (optional, e.g., 10 to skip priority 11+)

        Returns:
            Candidates (claimable task summaries), rationale explaining selection,
            total number of claimable tasks available, and applied filters (if any)

        Example:
            # Get next 3 frontend tasks with priority <= 5
            lodestar_task_next(limit=3, labels=["frontend"], max_priority=5)

            # Get any 10 high-priority tasks
            lodestar_task_next(limit=10, max_priority=3)
        """
        return task_next(
            context=context,
            agent_id=agent_id,
            limit=limit,
            labels=labels,
            max_priority=max_priority,
        )

    @mcp.tool(name="lodestar_task_context")
    def context_tool(
        task_id: str,
        max_chars: int | None = None,
    ) -> CallToolResult:
        """Get PRD context for a task.

        Returns the task's PRD references, frozen excerpt, and live PRD sections
        (if available). This delivers "just enough PRD context" for understanding
        what needs to be done.

        Includes drift detection to warn if the PRD file has changed since the
        task was created.

        Args:
            task_id: Task ID to get context for (required)
            max_chars: Maximum characters for context output (default 1000)

        Returns:
            Context bundle with:
            - Task metadata (taskId, title, description)
            - PRD information (prdSource, prdRefs, prdExcerpt)
            - Live PRD sections extracted from the source file
            - Drift detection (changed flag and details)
            - Combined content truncated to max_chars
            - Warnings (PRD drift, missing source file)
        """
        return task_context(context=context, task_id=task_id, max_chars=max_chars)
