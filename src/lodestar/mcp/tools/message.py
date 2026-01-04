"""Message tools for MCP (send, list, ack)."""

from __future__ import annotations

import contextlib

from mcp.server.fastmcp import Context
from mcp.types import CallToolResult

from lodestar.mcp.notifications import notify_message_sent
from lodestar.mcp.output import error, format_summary, with_item
from lodestar.mcp.server import LodestarContext
from lodestar.models.runtime import Message


async def message_send(
    context: LodestarContext,
    from_agent_id: str,
    task_id: str,
    body: str,
    subject: str | None = None,
    severity: str | None = None,
    ctx: Context | None = None,
) -> CallToolResult:
    """
    Send a message to a task thread.

    Sends a message to a task thread, visible to all agents working on that task.
    Task-targeted messaging only - agent-to-agent messaging is not supported.

    Args:
        context: Lodestar server context
        from_agent_id: Agent ID sending the message (required)
        task_id: Task ID to send message to (required)
        body: Message body text (required, max 16KB)
        subject: Message subject line (optional, stored in meta)
        severity: Message severity level: info|warning|handoff|blocker (optional, stored in meta)

    Returns:
        CallToolResult with message ID and delivery info
    """
    # Validate inputs
    if not from_agent_id or not from_agent_id.strip():
        return error(
            "from_agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

    if not task_id or not task_id.strip():
        return error(
            "task_id is required and cannot be empty",
            error_code="INVALID_TASK_ID",
        )

    if not body or not body.strip():
        return error(
            "body is required and cannot be empty",
            error_code="INVALID_BODY",
        )

    # Enforce 16KB limit on body
    if len(body) > 16 * 1024:
        return error(
            f"body exceeds maximum size of 16KB (current: {len(body)} bytes)",
            error_code="BODY_TOO_LARGE",
            details={"max_size": 16 * 1024, "current_size": len(body)},
        )

    # Validate severity if provided
    valid_severities = ["info", "warning", "handoff", "blocker"]
    if severity and severity.lower() not in valid_severities:
        return error(
            f"Invalid severity '{severity}'. Must be one of: {', '.join(valid_severities)}",
            error_code="INVALID_SEVERITY",
            details={"severity": severity, "valid_values": valid_severities},
        )

    # Build meta dict
    meta: dict[str, str] = {}
    if subject:
        meta["subject"] = subject
    if severity:
        meta["severity"] = severity

    # Create message
    message = Message(
        from_agent_id=from_agent_id,
        task_id=task_id,
        text=body,
        meta=meta,
    )

    # Send message via database
    context.db.send_message(message)

    # Log event (message.send)
    event_data = {
        "message_id": message.message_id,
        "task_id": task_id,
    }
    if subject:
        event_data["subject"] = subject
    if severity:
        event_data["severity"] = severity

    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="message.send",
            task_id=task_id,
            agent_id=from_agent_id,
            data=event_data,
        )

    # Notify clients of new message
    await notify_message_sent(
        ctx,
        message_id=message.message_id,
        to_agent_id=None,
        task_id=task_id,
    )

    # Build summary
    summary = format_summary(
        "Sent",
        message.message_id,
        f"to task:{task_id}",
    )

    # Build response
    response_data = {
        "ok": True,
        "messageId": message.message_id,
        "deliveredTo": [f"task:{task_id}"],
        "sentAt": message.created_at.isoformat(),
    }

    if subject:
        response_data["subject"] = subject
    if severity:
        response_data["severity"] = severity

    return with_item(summary, item=response_data)


def message_list(
    context: LodestarContext,
    task_id: str,
    unread_by: str | None = None,
    limit: int = 50,
    since: str | None = None,
) -> CallToolResult:
    """
    List messages in a task thread.

    Retrieves messages for a task thread with optional filtering.
    Supports filtering by unread status for a specific agent.

    Args:
        context: Lodestar server context
        task_id: Task ID to retrieve messages for (required)
        unread_by: Agent ID to filter for unread messages (optional)
        limit: Maximum number of messages to return (default: 50, max: 200)
        since: ISO timestamp to filter messages after this time (optional)

    Returns:
        CallToolResult with messages array
    """
    # Validate task_id
    if not task_id or not task_id.strip():
        return error(
            "task_id is required and cannot be empty",
            error_code="INVALID_TASK_ID",
        )

    # Validate and constrain limit
    if limit < 1:
        return error(
            "limit must be at least 1",
            error_code="INVALID_LIMIT",
            details={"limit": limit, "min": 1},
        )

    if limit > 200:
        return error(
            "limit exceeds maximum of 200",
            error_code="LIMIT_TOO_LARGE",
            details={"limit": limit, "max": 200},
        )

    # Parse since timestamp if provided
    since_dt = None
    if since:
        try:
            from datetime import datetime

            since_dt = datetime.fromisoformat(since)
        except ValueError:
            return error(
                f"Invalid timestamp: {since}",
                error_code="INVALID_TIMESTAMP",
            )

    # Fetch messages from database
    messages = context.db.get_task_thread(
        task_id=task_id,
        since=since_dt,
        limit=limit,
        unread_by=unread_by,
    )

    # Format messages for response
    formatted_messages = []
    for msg in messages:
        formatted_msg = {
            "message_id": msg.message_id,
            "from_agent_id": msg.from_agent_id,
            "task_id": msg.task_id,
            "text": msg.text,
            "created_at": msg.created_at.isoformat(),
            "read_by": msg.read_by,
        }

        # Extract subject and severity from meta if present
        if msg.meta:
            formatted_msg["meta"] = msg.meta

        formatted_messages.append(formatted_msg)

    # Build summary
    count_str = f"{len(formatted_messages)} message{'s' if len(formatted_messages) != 1 else ''}"
    filter_parts = []
    if unread_by:
        filter_parts.append(f"unread by {unread_by}")
    summary = format_summary(
        "Listed",
        count_str,
        " ".join(filter_parts) if filter_parts else None,
    )

    # Build response
    response_data = {
        "ok": True,
        "task_id": task_id,
        "messages": formatted_messages,
        "count": len(formatted_messages),
    }

    return with_item(summary, item=response_data)


def message_ack(
    context: LodestarContext,
    task_id: str,
    agent_id: str,
    message_ids: list[str] | None = None,
) -> CallToolResult:
    """
    Mark task messages as read for an agent.

    Marks messages in a task thread as read by a specific agent.
    If message_ids is not provided, marks all unread messages in the task as read.

    Args:
        context: Lodestar server context
        task_id: Task ID whose messages to mark as read (required)
        agent_id: Agent ID marking messages as read (required)
        message_ids: List of specific message IDs to mark (optional, marks all if None)

    Returns:
        CallToolResult with number of messages marked as read
    """
    # Validate task_id
    if not task_id or not task_id.strip():
        return error(
            "task_id is required and cannot be empty",
            error_code="INVALID_TASK_ID",
        )

    # Validate agent_id
    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
        )

    # Filter out empty strings if message_ids provided
    valid_message_ids = None
    if message_ids is not None:
        valid_message_ids = [mid for mid in message_ids if mid and mid.strip()]
        if not valid_message_ids:
            return error(
                "message_ids must contain at least one non-empty message ID",
                error_code="INVALID_MESSAGE_IDS",
            )

    # Mark messages as read via database
    updated_count = context.db.mark_task_messages_read(
        task_id=task_id,
        agent_id=agent_id,
        message_ids=valid_message_ids,
    )

    # Log event (message.ack)
    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="message.ack",
            task_id=task_id,
            agent_id=agent_id,
            data={
                "task_id": task_id,
                "message_ids": valid_message_ids,
                "updated_count": updated_count,
            },
        )

    # Build summary
    count_str = f"{updated_count} message{'s' if updated_count != 1 else ''}"
    summary = format_summary(
        "Marked",
        count_str,
        f"as read in task:{task_id}",
    )

    # Build response
    response_data = {
        "ok": True,
        "task_id": task_id,
        "updatedCount": updated_count,
    }

    return with_item(summary, item=response_data)


def register_message_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register message tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar_message_send")
    async def send_tool(
        from_agent_id: str,
        task_id: str,
        body: str,
        subject: str | None = None,
        severity: str | None = None,
        ctx: Context | None = None,
    ) -> CallToolResult:
        """Send a message to a task thread.

        Sends a message to a task thread, visible to all agents working on that task.
        Task-targeted messaging only - agent-to-agent messaging is not supported.

        Sends MCP resource update notifications when supported by the client.

        Args:
            from_agent_id: Agent ID sending the message (required)
            task_id: Task ID to send message to (required)
            body: Message body text (required, max 16KB)
            subject: Message subject line (optional, stored in meta)
            severity: Message severity level - one of: info, warning, handoff, blocker (optional, stored in meta)
            ctx: MCP context for notifications (optional, auto-injected)

        Returns:
            Success response with messageId, deliveredTo array (["task:F001"]),
            and sentAt timestamp.
            Returns error if body exceeds 16KB or required fields are missing.
        """
        return await message_send(
            context=context,
            from_agent_id=from_agent_id,
            task_id=task_id,
            body=body,
            subject=subject,
            severity=severity,
            ctx=ctx,
        )

    @mcp.tool(name="lodestar_message_list")
    def list_tool(
        task_id: str,
        unread_by: str | None = None,
        limit: int = 50,
        since: str | None = None,
    ) -> CallToolResult:
        """List messages in a task thread.

        Retrieves messages for a task thread with optional filtering.
        Supports filtering by unread status for a specific agent.

        Args:
            task_id: Task ID to retrieve messages for (required)
            unread_by: Agent ID to filter for unread messages (optional)
            limit: Maximum number of messages to return (default: 50, max: 200)
            since: ISO timestamp to filter messages after this time (optional)

        Returns:
            Success response with:
            - task_id: The task ID
            - messages: Array of message objects with fields (message_id, from_agent_id, task_id, text, created_at, read_by, meta)
            - count: Number of messages returned

            Returns error if task_id is missing or limit is invalid.
        """
        return message_list(
            context=context,
            task_id=task_id,
            unread_by=unread_by,
            limit=limit,
            since=since,
        )

    @mcp.tool(name="lodestar_message_ack")
    def ack_tool(
        task_id: str,
        agent_id: str,
        message_ids: list[str] | None = None,
    ) -> CallToolResult:
        """Mark task messages as read for an agent.

        Marks messages in a task thread as read by a specific agent.
        If message_ids is not provided, marks all unread messages in the task as read.

        Args:
            task_id: Task ID whose messages to mark as read (required)
            agent_id: Agent ID marking messages as read (required)
            message_ids: List of specific message IDs to mark (optional, marks all if None)

        Returns:
            Success response with:
            - ok: True if successful
            - task_id: The task ID
            - updatedCount: Number of messages marked as read

            Returns error if task_id or agent_id is missing.
        """
        return message_ack(
            context=context,
            task_id=task_id,
            agent_id=agent_id,
            message_ids=message_ids,
        )
