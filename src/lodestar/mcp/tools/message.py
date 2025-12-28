"""Message tools for MCP (send, list, ack)."""

from __future__ import annotations

import contextlib

from mcp.types import CallToolResult

from lodestar.mcp.output import error, format_summary, with_item
from lodestar.mcp.server import LodestarContext
from lodestar.models.runtime import Message, MessageType


def message_send(
    context: LodestarContext,
    from_agent_id: str,
    body: str,
    to_agent_id: str | None = None,
    task_id: str | None = None,
    subject: str | None = None,
    severity: str | None = None,
) -> CallToolResult:
    """
    Send a message to an agent or task thread.

    Sends a message either to a specific agent (direct messaging) or to a task
    thread (visible to all agents working on that task). Either to_agent_id or
    task_id must be provided.

    Args:
        context: Lodestar server context
        from_agent_id: Agent ID sending the message (required)
        body: Message body text (required, max 16KB)
        to_agent_id: Target agent ID for direct messaging (optional)
        task_id: Task ID for task thread messaging (optional)
        subject: Message subject line (optional)
        severity: Message severity level: info|warning|handoff|blocker (optional)

    Returns:
        CallToolResult with message ID and delivery info
    """
    # Validate inputs
    if not from_agent_id or not from_agent_id.strip():
        return error(
            "from_agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
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

    # Validate that either to_agent_id or task_id is provided (not both)
    if to_agent_id and task_id:
        return error(
            "Cannot specify both to_agent_id and task_id. Choose one.",
            error_code="AMBIGUOUS_RECIPIENT",
        )

    if not to_agent_id and not task_id:
        return error(
            "Must specify either to_agent_id or task_id",
            error_code="MISSING_RECIPIENT",
        )

    # Validate severity if provided
    valid_severities = ["info", "warning", "handoff", "blocker"]
    if severity and severity.lower() not in valid_severities:
        return error(
            f"Invalid severity '{severity}'. Must be one of: {', '.join(valid_severities)}",
            error_code="INVALID_SEVERITY",
            details={"severity": severity, "valid_values": valid_severities},
        )

    # Determine message type and recipient
    if to_agent_id:
        to_type = MessageType.AGENT
        to_id = to_agent_id
    else:
        to_type = MessageType.TASK
        to_id = task_id

    # Create message
    message = Message(
        from_agent_id=from_agent_id,
        to_type=to_type,
        to_id=to_id,
        text=body,  # Note: Message model uses 'text' field
    )

    # Send message via database
    context.db.send_message(message)

    # Log event (message.send)
    event_data = {
        "message_id": message.message_id,
        "to_type": to_type.value,
        "to_id": to_id,
    }
    if subject:
        event_data["subject"] = subject
    if severity:
        event_data["severity"] = severity

    with contextlib.suppress(Exception):
        context.emit_event(
            event_type="message.send",
            task_id=task_id,  # Can be None
            agent_id=from_agent_id,
            data=event_data,
        )

    # Build delivered_to array
    delivered_to = []
    if to_agent_id:
        delivered_to.append(f"agent:{to_agent_id}")
    if task_id:
        delivered_to.append(f"task:{task_id}")

    # Build summary
    recipient_str = f"agent:{to_agent_id}" if to_agent_id else f"task:{task_id}"
    summary = format_summary(
        "Sent",
        message.message_id,
        f"to {recipient_str}",
    )

    # Build response
    response_data = {
        "ok": True,
        "messageId": message.message_id,
        "deliveredTo": delivered_to,
        "sentAt": message.created_at.isoformat(),
    }

    if subject:
        response_data["subject"] = subject
    if severity:
        response_data["severity"] = severity

    return with_item(summary, item=response_data)


def message_list(
    context: LodestarContext,
    agent_id: str,
    unread_only: bool = True,
    limit: int = 50,
    since_id: str | None = None,
) -> CallToolResult:
    """
    List messages for an agent.

    Retrieves messages from an agent's inbox with optional filtering.
    Supports pagination via cursor-based pagination using message IDs.

    Args:
        context: Lodestar server context
        agent_id: Agent ID to retrieve messages for (required)
        unread_only: If True, only return unread messages (default: True)
        limit: Maximum number of messages to return (default: 50, max: 200)
        since_id: Message ID cursor for incremental fetching (optional)

    Returns:
        CallToolResult with messages array and nextCursor for pagination
    """
    # Validate agent_id
    if not agent_id or not agent_id.strip():
        return error(
            "agent_id is required and cannot be empty",
            error_code="INVALID_AGENT_ID",
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

    # Fetch messages from database
    # Note: We fetch limit + 1 to determine if there are more messages (for cursor)
    messages = context.db._messages.get_inbox(
        agent_id=agent_id,
        unread_only=unread_only,
        limit=limit + 1,
    )

    # Filter by since_id if provided (cursor-based pagination)
    if since_id:
        # Find the position of since_id in results and keep only messages after it
        filtered_messages = []
        found_cursor = False
        for msg in messages:
            if found_cursor:
                filtered_messages.append(msg)
            elif msg.message_id == since_id:
                found_cursor = True
        messages = filtered_messages

    # Determine if there are more messages (for pagination)
    has_more = len(messages) > limit
    if has_more:
        # Remove the extra message we fetched for pagination check
        messages = messages[:limit]

    # Determine next cursor
    next_cursor = messages[-1].message_id if has_more and messages else None

    # Format messages for response
    formatted_messages = []
    for msg in messages:
        formatted_msg = {
            "id": msg.message_id,
            "createdAt": msg.created_at.isoformat(),
            "from": msg.from_agent_id,
            "to": msg.to_id,
            "body": msg.text,
        }

        # Add optional fields if present
        if msg.to_type == MessageType.TASK:
            formatted_msg["taskId"] = msg.to_id

        # Extract subject and severity from meta if present
        if msg.meta:
            if "subject" in msg.meta:
                formatted_msg["subject"] = msg.meta["subject"]
            if "severity" in msg.meta:
                formatted_msg["severity"] = msg.meta["severity"]

        # Add read status
        if msg.read_at:
            formatted_msg["readAt"] = msg.read_at.isoformat()

        formatted_messages.append(formatted_msg)

    # Build summary
    count_str = f"{len(formatted_messages)} message{'s' if len(formatted_messages) != 1 else ''}"
    filter_parts = []
    if unread_only:
        filter_parts.append("unread")
    summary = format_summary(
        "Listed",
        count_str,
        " ".join(filter_parts) if filter_parts else None,
    )

    # Build response
    response_data = {
        "ok": True,
        "messages": formatted_messages,
        "count": len(formatted_messages),
    }

    if next_cursor:
        response_data["nextCursor"] = next_cursor

    return with_item(summary, item=response_data)


def register_message_tools(mcp: object, context: LodestarContext) -> None:
    """
    Register message tools with the FastMCP server.

    Args:
        mcp: FastMCP server instance
        context: Lodestar context to use for all tools
    """

    @mcp.tool(name="lodestar.message.send")
    def send_tool(
        from_agent_id: str,
        body: str,
        to_agent_id: str | None = None,
        task_id: str | None = None,
        subject: str | None = None,
        severity: str | None = None,
    ) -> CallToolResult:
        """Send a message to an agent or task thread.

        Sends a message either to a specific agent (direct messaging) or to a task
        thread (visible to all agents working on that task).

        Either to_agent_id or task_id must be provided (not both).

        Args:
            from_agent_id: Agent ID sending the message (required)
            body: Message body text (required, max 16KB)
            to_agent_id: Target agent ID for direct messaging (optional)
            task_id: Task ID for task thread messaging (optional)
            subject: Message subject line (optional, for organization)
            severity: Message severity level - one of: info, warning, handoff, blocker (optional)

        Returns:
            Success response with messageId, deliveredTo array (e.g., ["agent:A123"] or ["task:F001"]),
            and sentAt timestamp.
            Returns error if both or neither recipients are specified, or if body exceeds 16KB.
        """
        return message_send(
            context=context,
            from_agent_id=from_agent_id,
            body=body,
            to_agent_id=to_agent_id,
            task_id=task_id,
            subject=subject,
            severity=severity,
        )

    @mcp.tool(name="lodestar.message.list")
    def list_tool(
        agent_id: str,
        unread_only: bool = True,
        limit: int = 50,
        since_id: str | None = None,
    ) -> CallToolResult:
        """List messages for an agent.

        Retrieves messages from an agent's inbox with optional filtering.
        Supports cursor-based pagination using message IDs.

        Args:
            agent_id: Agent ID to retrieve messages for (required)
            unread_only: If True, only return unread messages (default: True)
            limit: Maximum number of messages to return (default: 50, max: 200)
            since_id: Message ID cursor for incremental fetching - returns messages after this ID (optional)

        Returns:
            Success response with:
            - messages: Array of message objects with fields (id, createdAt, from, to, body, taskId, subject, severity, readAt)
            - count: Number of messages returned
            - nextCursor: Message ID to use for next page (if more messages available)

            Returns error if agent_id is missing or limit is invalid.
        """
        return message_list(
            context=context,
            agent_id=agent_id,
            unread_only=unread_only,
            limit=limit,
            since_id=since_id,
        )
