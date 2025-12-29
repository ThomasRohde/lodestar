"""Task mutation tools for MCP (claim, release, done, verify)."""

from __future__ import annotations

import contextlib
from datetime import UTC, datetime, timedelta

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from lodestar.core.task_service import detect_lock_conflicts
from lodestar.mcp.notifications import notify_task_updated
from lodestar.mcp.output import error, format_summary, with_item
from lodestar.mcp.server import LodestarContext
from lodestar.mcp.validation import ValidationError, validate_task_id
from lodestar.models.runtime import Lease
from lodestar.models.spec import TaskStatus


async def task_claim(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    ttl_seconds: int | None = None,
    force: bool = False,
    ctx: Context | None = None,
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
    # Log the claim attempt
    if ctx:
        await ctx.info(f"Claiming task {task_id} for agent {agent_id}")

    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        if ctx:
            await ctx.error(f"Invalid task ID: {task_id}")
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

        if ctx:
            await ctx.warning(
                f"Task {validated_task_id} already claimed by {existing.agent_id if existing else 'unknown'}"
            )

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

    # Notify clients of task update
    await notify_task_updated(ctx, validated_task_id)

    # Log successful claim
    if ctx:
        await ctx.info(
            f"Successfully claimed task {validated_task_id} (lease: {created_lease.lease_id}, expires in {ttl_seconds}s)"
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


async def task_release(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    reason: str | None = None,
    ctx: Context | None = None,
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
    # Log the release attempt
    if ctx:
        reason_msg = f" (reason: {reason})" if reason else ""
        await ctx.info(f"Releasing task {task_id} for agent {agent_id}{reason_msg}")

    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        if ctx:
            await ctx.error(f"Invalid task ID: {task_id}")
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
        if ctx:
            await ctx.error(f"Failed to release lease for task {validated_task_id}")
        return error(
            f"Failed to release lease for task {validated_task_id}",
            error_code="RELEASE_FAILED",
            details={"task_id": validated_task_id, "agent_id": agent_id},
        )

    # Log successful release
    if ctx:
        await ctx.info(f"Successfully released task {validated_task_id}")

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

    # Notify clients of task update
    await notify_task_updated(ctx, validated_task_id)

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


async def task_done(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    note: str | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    """
    Mark a task as done (pending verification).

    Sets the task status to 'done'. The task is considered complete but
    still needs verification before it unblocks dependent tasks.

    Args:
        context: Lodestar server context
        task_id: Task ID to mark as done (required)
        agent_id: Agent ID marking the task as done (required)
        note: Optional note about completion (for logging/audit)

    Returns:
        CallToolResult with success status and warnings
    """
    # Log the done marking attempt
    if ctx:
        note_msg = f" ({note})" if note else ""
        await ctx.info(f"Marking task {task_id} as done by agent {agent_id}{note_msg}")

    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        if ctx:
            await ctx.error(f"Invalid task ID: {task_id}")
        return error(str(e), error_code="INVALID_TASK_ID")

    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

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

    # Check if task is already done or verified
    warnings = []
    if task.status == TaskStatus.DONE:
        warnings.append(
            {
                "type": "ALREADY_DONE",
                "message": f"Task {validated_task_id} is already marked as done",
                "severity": "info",
            }
        )
    elif task.status == TaskStatus.VERIFIED:
        warnings.append(
            {
                "type": "ALREADY_VERIFIED",
                "message": f"Task {validated_task_id} is already verified",
                "severity": "info",
            }
        )

    # Check if task is claimed by the agent
    active_lease = context.db.get_active_lease(validated_task_id)
    if active_lease and active_lease.agent_id != agent_id:
        warnings.append(
            {
                "type": "NOT_CLAIMED_BY_YOU",
                "message": f"Task {validated_task_id} is claimed by {active_lease.agent_id}, not {agent_id}",
                "severity": "warning",
            }
        )

    # Update task status
    task.status = TaskStatus.DONE
    task.updated_at = datetime.now(UTC)
    context.save_spec()

    # Release lease if exists
    if active_lease:
        context.db.release_lease(validated_task_id, active_lease.agent_id)

    # Log successful marking as done
    if ctx:
        await ctx.info(f"Successfully marked task {validated_task_id} as done")

    # Log event (task.done)
    event_data = {
        "agent_id": agent_id,
    }
    if note:
        event_data["note"] = note

    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="task.done",
            task_id=validated_task_id,
            agent_id=agent_id,
            data=event_data,
        )

    # Notify clients of task update
    await notify_task_updated(ctx, validated_task_id)

    # Build summary
    summary = format_summary(
        "Done",
        validated_task_id,
        "- pending verification",
    )

    # Build response
    response_data = {
        "ok": True,
        "taskId": validated_task_id,
        "status": "done",
        "warnings": warnings,
    }

    if note:
        response_data["note"] = note

    return with_item(summary, item=response_data)


async def task_verify(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    note: str | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    """
    Mark a task as verified (unblocks dependents).

    Verifies that the task is complete. This changes the status from 'done'
    to 'verified' and unblocks any dependent tasks that are waiting on this one.

    If the client provides a progressToken in the request metadata, this operation
    will emit progress notifications at key stages.

    Args:
        context: Lodestar server context
        task_id: Task ID to verify (required)
        agent_id: Agent ID verifying the task (required)
        note: Optional note about verification (for logging/audit)
        ctx: Optional MCP context for logging and progress notifications

    Returns:
        CallToolResult with success status and list of newly unblocked task IDs
    """
    # Log the verify attempt
    if ctx:
        note_msg = f" ({note})" if note else ""
        await ctx.info(f"Verifying task {task_id} by agent {agent_id}{note_msg}")

    # Report progress: validating inputs (10%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(10.0, 100.0, "Validating inputs...")

    # Validate inputs
    try:
        validated_task_id = validate_task_id(task_id)
    except ValidationError as e:
        if ctx:
            await ctx.error(f"Invalid task ID: {task_id}")
        return error(str(e), error_code="INVALID_TASK_ID")

    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

    # Report progress: reloading spec (25%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(25.0, 100.0, "Reloading spec from disk...")

    # Reload spec to get latest state
    context.reload_spec()

    # Report progress: checking task status (40%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(40.0, 100.0, "Checking task status...")

    # Get task from spec
    task = context.spec.get_task(validated_task_id)
    if task is None:
        return error(
            f"Task {validated_task_id} not found",
            error_code="TASK_NOT_FOUND",
            details={"task_id": validated_task_id},
        )

    # Check if task is in DONE status
    warnings = []
    if task.status == TaskStatus.VERIFIED:
        warnings.append(
            {
                "type": "ALREADY_VERIFIED",
                "message": f"Task {validated_task_id} is already verified",
                "severity": "info",
            }
        )
    elif task.status != TaskStatus.DONE:
        return error(
            f"Task {validated_task_id} must be done before verifying (current status: {task.status.value})",
            error_code="TASK_NOT_DONE",
            details={
                "task_id": validated_task_id,
                "current_status": task.status.value,
            },
        )

    # Report progress: updating task status (55%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(55.0, 100.0, "Updating task status to verified...")

    # Update task status
    task.status = TaskStatus.VERIFIED
    task.updated_at = datetime.now(UTC)
    context.save_spec()

    # Report progress: releasing lease (70%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(70.0, 100.0, "Releasing active lease...")

    # Auto-release any active lease
    active_lease = context.db.get_active_lease(validated_task_id)
    if active_lease:
        context.db.release_lease(validated_task_id, active_lease.agent_id)

    # Report progress: logging event (80%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(80.0, 100.0, "Logging verification event...")

    # Log event (task.verify)
    event_data = {
        "agent_id": agent_id,
    }
    if note:
        event_data["note"] = note

    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="task.verify",
            task_id=validated_task_id,
            agent_id=agent_id,
            data=event_data,
        )

    # Notify clients of task update
    await notify_task_updated(ctx, validated_task_id)

    # Report progress: finding unblocked tasks (90%)
    if ctx and hasattr(ctx, "report_progress"):
        await ctx.report_progress(90.0, 100.0, "Finding newly unblocked tasks...")

    # Check what tasks are now unblocked
    context.reload_spec()  # Reload to get updated state
    new_claimable = context.spec.get_claimable_tasks()
    newly_unblocked = [t for t in new_claimable if validated_task_id in t.depends_on]
    newly_ready_ids = [t.id for t in newly_unblocked]

    # Notify clients about newly unblocked tasks
    for unblocked_id in newly_ready_ids:
        await notify_task_updated(ctx, unblocked_id)

    # Report progress: complete (100%)
    if ctx and hasattr(ctx, "report_progress"):
        if newly_ready_ids:
            await ctx.report_progress(
                100.0,
                100.0,
                f"Verified - unblocked {len(newly_ready_ids)} task(s)",
            )
        else:
            await ctx.report_progress(100.0, 100.0, "Verified - no tasks unblocked")

    # Log successful verification
    if ctx:
        if newly_ready_ids:
            await ctx.info(
                f"Successfully verified task {validated_task_id}, unblocked {len(newly_ready_ids)} task(s): {', '.join(newly_ready_ids)}"
            )
        else:
            await ctx.info(f"Successfully verified task {validated_task_id}")

    # Build summary
    summary = format_summary(
        "Verified",
        validated_task_id,
        f"- unblocked {len(newly_ready_ids)} task(s)" if newly_ready_ids else "",
    )

    # Build response
    response_data = {
        "ok": True,
        "taskId": validated_task_id,
        "status": "verified",
        "newlyReadyTaskIds": newly_ready_ids,
        "warnings": warnings,
    }

    if note:
        response_data["note"] = note

    return with_item(summary, item=response_data)


def register_task_mutation_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register task mutation tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.task.claim")
    async def claim_tool(
        task_id: str,
        agent_id: str,
        ttl_seconds: int | None = None,
        force: bool = False,
        ctx: Context | None = None,
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
        return await task_claim(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            ttl_seconds=ttl_seconds,
            force=force,
            ctx=ctx,
        )

    @mcp.tool(name="lodestar.task.release")
    async def release_tool(
        task_id: str,
        agent_id: str,
        reason: str | None = None,
        ctx: Context | None = None,
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
        return await task_release(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            reason=reason,
            ctx=ctx,
        )

    @mcp.tool(name="lodestar.task.done")
    async def done_tool(
        task_id: str,
        agent_id: str,
        note: str | None = None,
        ctx: Context | None = None,
    ) -> CallToolResult:
        """Mark a task as done (pending verification).

        Sets the task status to 'done'. The task is considered complete but
        still requires verification (via task.verify) before it unblocks
        dependent tasks.

        Automatically releases the lease if the task is currently claimed.

        Args:
            task_id: Task ID to mark as done (required)
            agent_id: Agent ID marking the task as done (required)
            note: Optional note about completion (for logging/audit purposes)

        Returns:
            Success response with status='done' and any warnings.
            Warnings may include:
            - Task already done or verified
            - Task claimed by different agent (still marks as done)
        """
        return await task_done(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            note=note,
            ctx=ctx,
        )

    @mcp.tool(name="lodestar.task.verify")
    async def verify_tool(
        task_id: str,
        agent_id: str,
        note: str | None = None,
        ctx: Context | None = None,
    ) -> CallToolResult:
        """Mark a task as verified (unblocks dependents).

        Verifies that the task is complete. This changes the status from 'done'
        to 'verified' and unblocks any dependent tasks that were waiting on this one.

        Task must be in 'done' status before it can be verified.
        Automatically releases the lease if the task is currently claimed.

        If the client provides a progressToken in request metadata, this operation
        emits progress notifications at key stages (10%, 25%, 40%, 55%, 70%, 80%, 90%, 100%).

        Args:
            task_id: Task ID to verify (required)
            agent_id: Agent ID verifying the task (required)
            note: Optional note about verification (for logging/audit purposes)
            ctx: Optional MCP context for logging and progress notifications

        Returns:
            Success response with status='verified' and list of newly unblocked task IDs.
            Returns error if task is not in 'done' status.
            Returns warning if task is already verified.
        """
        return await task_verify(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            note=note,
            ctx=ctx,
        )
