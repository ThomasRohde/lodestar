"""Event type constants for runtime event logging."""

from __future__ import annotations


class EventType:
    """Constants for event types logged to the events table."""

    # Agent lifecycle events
    AGENT_JOIN = "agent.join"
    AGENT_HEARTBEAT = "agent.heartbeat"
    AGENT_LEAVE = "agent.leave"

    # Task claim/lease events
    TASK_CLAIM = "task.claim"
    TASK_RENEW = "task.renew"
    TASK_RELEASE = "task.release"
    LEASE_EXPIRED = "lease.expired"

    # Task status events
    TASK_DONE = "task.done"
    TASK_VERIFIED = "task.verified"

    # Messaging events
    MESSAGE_SENT = "message.sent"
    MESSAGE_READ = "message.read"


# Mapping of legacy event names to standardized names (for compatibility)
_LEGACY_EVENT_NAMES = {
    "message.send": EventType.MESSAGE_SENT,
}


def normalize_event_type(event_type: str) -> str:
    """
    Normalize event type name to standard form.

    Args:
        event_type: Event type string (may be legacy format).

    Returns:
        Normalized event type string.
    """
    return _LEGACY_EVENT_NAMES.get(event_type, event_type)
