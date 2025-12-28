"""Runtime plane models - agents, leases, and messages."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

# Default inactivity thresholds for agent status calculation
# These can be overridden via environment variables:
#   LODESTAR_AGENT_IDLE_THRESHOLD_MINUTES (default: 15)
#   LODESTAR_AGENT_OFFLINE_THRESHOLD_MINUTES (default: 60)
DEFAULT_IDLE_THRESHOLD_MINUTES = 15
DEFAULT_OFFLINE_THRESHOLD_MINUTES = 60


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class AgentStatus(str, Enum):
    """Agent availability status based on activity."""

    ACTIVE = "active"  # Recently active (within idle threshold)
    IDLE = "idle"  # No recent activity (between idle and offline thresholds)
    OFFLINE = "offline"  # No activity for extended period (beyond offline threshold)


def get_agent_thresholds() -> tuple[int, int]:
    """Get agent status thresholds from environment or defaults.

    Returns:
        Tuple of (idle_threshold_minutes, offline_threshold_minutes)
    """
    import os

    idle = int(
        os.environ.get("LODESTAR_AGENT_IDLE_THRESHOLD_MINUTES", DEFAULT_IDLE_THRESHOLD_MINUTES)
    )
    offline = int(
        os.environ.get(
            "LODESTAR_AGENT_OFFLINE_THRESHOLD_MINUTES", DEFAULT_OFFLINE_THRESHOLD_MINUTES
        )
    )
    return idle, offline


def generate_agent_id() -> str:
    """Generate a unique agent ID."""
    return f"A{uuid4().hex[:8].upper()}"


def generate_lease_id() -> str:
    """Generate a unique lease ID."""
    return f"L{uuid4().hex[:8].upper()}"


def generate_message_id() -> str:
    """Generate a unique message ID."""
    return f"M{uuid4().hex[:12].upper()}"


class Agent(BaseModel):
    """An agent registered in the runtime plane."""

    agent_id: str = Field(
        default_factory=generate_agent_id,
        description="Unique agent identifier",
    )
    display_name: str = Field(
        default="",
        description="Human-readable agent name",
    )
    role: str = Field(
        default="",
        description="Agent role (e.g., 'code-review', 'testing', 'documentation')",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="When the agent registered",
    )
    last_seen_at: datetime = Field(
        default_factory=_utc_now,
        description="Last heartbeat timestamp",
    )
    capabilities: list[str] = Field(
        default_factory=list,
        description="Agent capabilities (list of capability names)",
    )
    session_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Session metadata (tool name, model, etc.)",
    )

    def get_status(self, now: datetime | None = None) -> AgentStatus:
        """Calculate agent status based on last activity.

        Args:
            now: Current time for comparison. Uses UTC now if not provided.

        Returns:
            AgentStatus based on time since last_seen_at.
        """
        if now is None:
            now = _utc_now()

        idle_threshold, offline_threshold = get_agent_thresholds()
        time_since_seen = now - self.last_seen_at

        if time_since_seen < timedelta(minutes=idle_threshold):
            return AgentStatus.ACTIVE
        elif time_since_seen < timedelta(minutes=offline_threshold):
            return AgentStatus.IDLE
        else:
            return AgentStatus.OFFLINE


class Lease(BaseModel):
    """A task claim lease in the runtime plane."""

    lease_id: str = Field(
        default_factory=generate_lease_id,
        description="Unique lease identifier",
    )
    task_id: str = Field(description="The claimed task ID")
    agent_id: str = Field(description="The claiming agent ID")
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="When the lease was created",
    )
    expires_at: datetime = Field(description="When the lease expires")

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the lease has expired."""
        if now is None:
            now = _utc_now()
        return now >= self.expires_at

    def is_active(self, now: datetime | None = None) -> bool:
        """Check if the lease is still active."""
        return not self.is_expired(now)


class MessageType(str, Enum):
    """Type of message recipient."""

    AGENT = "agent"
    TASK = "task"


class Message(BaseModel):
    """A message in the runtime plane."""

    message_id: str = Field(
        default_factory=generate_message_id,
        description="Unique message identifier",
    )
    created_at: datetime = Field(
        default_factory=_utc_now,
        description="When the message was sent",
    )
    from_agent_id: str = Field(description="Sender agent ID")
    to_type: MessageType = Field(description="Recipient type (agent or task)")
    to_id: str = Field(description="Recipient ID (agent_id or task_id)")
    text: str = Field(description="Message content")
    meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional message metadata",
    )
    read_at: datetime | None = Field(
        default=None,
        description="When the message was read (None if unread)",
    )
