"""MCP notification utilities for Lodestar.

Provides helper functions for sending MCP notifications to clients
about resource changes, task updates, and other events.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import Context
    from mcp.server.session import ServerSession

logger = logging.getLogger("lodestar.mcp.notifications")


async def notify_task_updated(
    ctx: Context | ServerSession | None,
    task_id: str,
) -> None:
    """
    Send a notification that a task resource has been updated.

    Args:
        ctx: MCP context or session (optional)
        task_id: ID of the task that was updated
    """
    if ctx is None:
        return

    # Get session from context
    session = getattr(ctx, "session", ctx)
    if not hasattr(session, "send_resource_updated"):
        logger.debug(f"Session does not support notifications for task {task_id}")
        return

    try:
        # Import here to avoid circular dependency
        from anyurl import AnyUrl

        # Send resource update notification
        uri = AnyUrl(f"lodestar://task/{task_id}")
        await session.send_resource_updated(uri)
        logger.debug(f"Sent resource update notification for task {task_id}")
    except Exception as e:
        # Don't fail the operation if notification fails
        logger.warning(f"Failed to send notification for task {task_id}: {e}")


async def notify_spec_updated(
    ctx: Context | ServerSession | None,
) -> None:
    """
    Send a notification that the spec resource has been updated.

    Args:
        ctx: MCP context or session (optional)
    """
    if ctx is None:
        return

    session = getattr(ctx, "session", ctx)
    if not hasattr(session, "send_resource_updated"):
        logger.debug("Session does not support notifications for spec")
        return

    try:
        from anyurl import AnyUrl

        uri = AnyUrl("lodestar://spec")
        await session.send_resource_updated(uri)
        logger.debug("Sent resource update notification for spec")
    except Exception as e:
        logger.warning(f"Failed to send notification for spec: {e}")


async def notify_status_updated(
    ctx: Context | ServerSession | None,
) -> None:
    """
    Send a notification that the status resource has been updated.

    Args:
        ctx: MCP context or session (optional)
    """
    if ctx is None:
        return

    session = getattr(ctx, "session", ctx)
    if not hasattr(session, "send_resource_updated"):
        logger.debug("Session does not support notifications for status")
        return

    try:
        from anyurl import AnyUrl

        uri = AnyUrl("lodestar://status")
        await session.send_resource_updated(uri)
        logger.debug("Sent resource update notification for status")
    except Exception as e:
        logger.warning(f"Failed to send notification for status: {e}")


async def notify_message_sent(
    ctx: Context | ServerSession | None,
    message_id: str,
    to_agent_id: str | None = None,
    task_id: str | None = None,
) -> None:
    """
    Send a notification that a new message has been sent.

    Args:
        ctx: MCP context or session (optional)
        message_id: ID of the message that was sent
        to_agent_id: ID of the recipient agent (if agent message)
        task_id: ID of the task (if task message)
    """
    if ctx is None:
        return

    session = getattr(ctx, "session", ctx)
    if not hasattr(session, "send_resource_updated"):
        logger.debug(f"Session does not support notifications for message {message_id}")
        return

    try:
        from anyurl import AnyUrl

        # Notify about the specific message
        message_uri = AnyUrl(f"lodestar://message/{message_id}")
        await session.send_resource_updated(message_uri)

        # If targeted to an agent, notify about their inbox
        if to_agent_id:
            inbox_uri = AnyUrl(f"lodestar://agent/{to_agent_id}/inbox")
            await session.send_resource_updated(inbox_uri)

        # If related to a task, notify about the task thread
        if task_id:
            thread_uri = AnyUrl(f"lodestar://task/{task_id}/thread")
            await session.send_resource_updated(thread_uri)

        logger.debug(f"Sent notifications for message {message_id}")
    except Exception as e:
        logger.warning(f"Failed to send notification for message {message_id}: {e}")
