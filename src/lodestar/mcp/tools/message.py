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
