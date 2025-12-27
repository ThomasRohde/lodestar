"""Runtime plane models - agents, leases, and messages."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


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
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the agent registered",
    )
    last_seen_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="Last heartbeat timestamp",
    )
    capabilities: dict[str, Any] = Field(
        default_factory=dict,
        description="Agent capabilities (JSON)",
    )
    session_meta: dict[str, Any] = Field(
        default_factory=dict,
        description="Session metadata (tool name, model, etc.)",
    )


class Lease(BaseModel):
    """A task claim lease in the runtime plane."""

    lease_id: str = Field(
        default_factory=generate_lease_id,
        description="Unique lease identifier",
    )
    task_id: str = Field(description="The claimed task ID")
    agent_id: str = Field(description="The claiming agent ID")
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the lease was created",
    )
    expires_at: datetime = Field(description="When the lease expires")

    def is_expired(self, now: datetime | None = None) -> bool:
        """Check if the lease has expired."""
        if now is None:
            now = datetime.utcnow()
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
        default_factory=datetime.utcnow,
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
