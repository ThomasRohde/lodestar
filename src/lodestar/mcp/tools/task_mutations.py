"""Task mutation tools for MCP (claim, release, done, verify)."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from mcp.types import CallToolResult

from lodestar.core.task_service import detect_lock_conflicts
from lodestar.mcp.output import error, format_summary, with_item
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import ValidationError, validate_task_id
from lodestar.models.runtime import Lease


def task_claim(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    ttl_seconds: int | None = None,
    force: bool = False,
) -> CallToolResult:
    """
    Claim a task with a time-limited lease.

    Creates an exclusive claim on a task that auto-expires after the TTL period.
    Claims fail if the task is already claimed or not claimable.

    Args:
        context: Lodestar server context
        task_id: Task ID to claim (required)
        agent_id: Agent ID making the claim (required)
        ttl_seconds: Lease duration in seconds (optional, default 900 = 15min, server clamps to bounds)
        force: Bypass lock conflict warnings (optional, default False)

    Returns:
        CallToolResult with lease object on success or conflict details on failure
    """
    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        return error(str(e), error_code="INVALID_TASK_ID")

    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

    # Validate and clamp TTL (default 15min = 900s, min 60s, max 86400s = 24h)
    if ttl_seconds is None:
        ttl_seconds = 900  # 15 minutes
    elif ttl_seconds < 60:
        ttl_seconds = 60  # Min 1 minute
    elif ttl_seconds > 86400:
        ttl_seconds = 86400  # Max 24 hours

    # Reload spec to get latest state
    context.reload_spec()

    # Check task exists
    task = context.spec.get_task(validated_task_id)
    if task is None:
        return error(
            f"Task {validated_task_id} not found",
            error_code="TASK_NOT_FOUND",
            details={"task_id": validated_task_id},
        )

    # Check task is claimable
    verified = context.spec.get_verified_tasks()
    if not task.is_claimable(verified):
        unmet_deps = [d for d in task.depends_on if d not in verified]
        return error(
            f"Task {validated_task_id} is not claimable (status: {task.status.value})",
            error_code="TASK_NOT_CLAIMABLE",
            details={
                "task_id": validated_task_id,
                "status": task.status.value,
                "unmet_dependencies": unmet_deps,
            },
        )

    # Check for lock conflicts with actively-leased tasks
    warnings = []
    if task.locks and not force:
        lock_warnings = detect_lock_conflicts(task, context.spec, context.db)
        for warning in lock_warnings:
            warnings.append(
                {
                    "type": "LOCK_CONFLICT",
                    "message": warning,
                    "severity": "warning",
                }
            )

    # Create lease
    duration = timedelta(seconds=ttl_seconds)
    lease = Lease(
        task_id=validated_task_id,
        agent_id=agent_id,
        expires_at=datetime.now(UTC) + duration,
    )

    created_lease = context.db.create_lease(lease)

    if created_lease is None:
        # Task already claimed
        existing = context.db.get_active_lease(validated_task_id)
        conflict_details = {
            "task_id": validated_task_id,
            "claimed_by": existing.agent_id if existing else "unknown",
        }
        if existing:
            conflict_details["expires_at"] = existing.expires_at.isoformat()
            remaining = existing.expires_at - datetime.now(UTC)
            conflict_details["expires_in_seconds"] = int(remaining.total_seconds())

        return error(
            f"Task {validated_task_id} already claimed by {existing.agent_id if existing else 'unknown'}",
            error_code="TASK_ALREADY_CLAIMED",
            details={"conflict": conflict_details},
        )

    # Log event (task.claim) - don't fail the claim if event logging fails
    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="task.claim",
            task_id=validated_task_id,
            agent_id=agent_id,
            data={
                "lease_id": created_lease.lease_id,
                "ttl_seconds": ttl_seconds,
            },
        )

    # Build lease object for response
    lease_data = {
        "leaseId": created_lease.lease_id,
        "taskId": validated_task_id,
        "agentId": agent_id,
        "expiresAt": created_lease.expires_at.isoformat(),
        "ttlSeconds": ttl_seconds,
        "createdAt": created_lease.created_at.isoformat(),
    }

    # Build summary
    summary = format_summary(
        "Claimed",
        validated_task_id,
        f"by {agent_id}",
    )

    # Build response with warnings
    response_data = {
        "ok": True,
        "lease": lease_data,
        "warnings": warnings,
    }

    return with_item(summary, item=response_data)


def task_release(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    reason: str | None = None,
) -> CallToolResult:
    """
    Release a claim on a task before TTL expiry.

    Frees the task for other agents to claim. Use this when blocked or
    unable to complete the task.

    Args:
        context: Lodestar server context
        task_id: Task ID to release (required)
        agent_id: Agent ID releasing the claim (required)
        reason: Optional reason for releasing (for logging/audit)

    Returns:
        CallToolResult with success status and previous lease details
    """
    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        return error(str(e), error_code="INVALID_TASK_ID")

    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

    # Get active lease before releasing
    active_lease = context.db.get_active_lease(validated_task_id)

    if active_lease is None:
        return error(
            f"No active lease for task {validated_task_id}",
            error_code="NO_ACTIVE_LEASE",
            details={"task_id": validated_task_id},
        )

    # Verify the agent_id matches the lease
    if active_lease.agent_id != agent_id:
        return error(
            f"Task {validated_task_id} is claimed by {active_lease.agent_id}, not {agent_id}",
            error_code="LEASE_MISMATCH",
            details={
                "task_id": validated_task_id,
                "claimed_by": active_lease.agent_id,
                "requested_by": agent_id,
            },
        )

    # Release the lease
    success = context.db.release_lease(validated_task_id, agent_id)

    if not success:
        # This shouldn't happen since we checked for active lease above
        return error(
            f"Failed to release lease for task {validated_task_id}",
            error_code="RELEASE_FAILED",
            details={"task_id": validated_task_id, "agent_id": agent_id},
        )

    # Log event (task.release)
    event_data = {
        "lease_id": active_lease.lease_id,
    }
    if reason:
        event_data["reason"] = reason

    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="task.release",
            task_id=validated_task_id,
            agent_id=agent_id,
            data=event_data,
        )

    # Build previous lease object for response
    previous_lease = {
        "leaseId": active_lease.lease_id,
        "taskId": validated_task_id,
        "agentId": agent_id,
        "expiresAt": active_lease.expires_at.isoformat(),
        "createdAt": active_lease.created_at.isoformat(),
    }

    # Build summary
    summary = format_summary(
        "Released",
        validated_task_id,
        f"by {agent_id}",
    )

    # Build response
    response_data = {
        "ok": True,
        "previousLease": previous_lease,
    }

    if reason:
        response_data["reason"] = reason

    return with_item(summary, item=response_data)


def register_task_mutation_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register task mutation tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.task.claim")
    def claim_tool(
        task_id: str,
        agent_id: str,
        ttl_seconds: int | None = None,
        force: bool = False,
    ) -> CallToolResult:
        """Claim a task with a time-limited lease.

        Creates an exclusive claim on a task that auto-expires after the TTL period.
        This prevents other agents from claiming the same task while you work on it.

        Claims will fail if:
        - Task is already claimed by another agent
        - Task is not in 'ready' status
        - Task has unmet dependencies (not all dependencies are verified)

        Args:
            task_id: Task ID to claim (required)
            agent_id: Agent ID making the claim (required)
            ttl_seconds: Lease duration in seconds (optional, default 900 = 15min, min 60, max 86400 = 24h)
            force: Bypass lock conflict warnings (optional, default False)

        Returns:
            Success response with lease object (leaseId, taskId, agentId, expiresAt, ttlSeconds)
            or error with conflict details if task is already claimed or not claimable.
            May include lock conflict warnings if task locks overlap with other active leases.
        """
        return task_claim(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            ttl_seconds=ttl_seconds,
            force=force,
        )

    @mcp.tool(name="lodestar.task.release")
    def release_tool(
        task_id: str,
        agent_id: str,
        reason: str | None = None,
    ) -> CallToolResult:
        """Release a claim on a task before TTL expiry.

        Frees the task for other agents to claim. Use this when you're blocked
        or unable to complete the task. The lease is immediately removed and
        the task becomes available for others to claim.

        Note: You don't need to release after marking a task as done or verified -
        those operations automatically release the lease.

        Args:
            task_id: Task ID to release (required)
            agent_id: Agent ID releasing the claim (required)
            reason: Optional reason for releasing (for logging/audit purposes)

        Returns:
            Success response with previous lease details (leaseId, taskId, agentId, expiresAt)
            or error if no active lease exists or agent_id doesn't match the lease holder.
        """
        return task_release(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            reason=reason,
        )
