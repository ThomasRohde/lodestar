"""SQLAlchemy ORM models for the runtime database."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator


class JSONField(TypeDecorator[Any]):
    """Store JSON as TEXT in SQLite."""

    impl = Text
    cache_ok = True

    def process_bind_param(self, value: Any, dialect: Any) -> str | None:
        if value is not None:
            return json.dumps(value)
        return None

    def process_result_value(self, value: str | None, dialect: Any) -> Any:
        if value is not None:
            return json.loads(value)
        return None


class Base(DeclarativeBase):
    """Base class for all ORM models."""

    pass


class SchemaVersion(Base):
    """Track database schema version."""

    __tablename__ = "schema_version"

    version: Mapped[int] = mapped_column(Integer, primary_key=True)


class AgentModel(Base):
    """SQLAlchemy model for agents table."""

    __tablename__ = "agents"

    agent_id: Mapped[str] = mapped_column(String, primary_key=True)
    display_name: Mapped[str] = mapped_column(String, default="")
    role: Mapped[str] = mapped_column(String, default="")
    created_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO format
    last_seen_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO format
    capabilities: Mapped[list[str]] = mapped_column(JSONField, default=list)  # JSON list
    session_meta: Mapped[dict[str, Any]] = mapped_column(JSONField, default=dict)  # JSON dict

    # Relationships
    leases: Mapped[list[LeaseModel]] = relationship(
        "LeaseModel", back_populates="agent", cascade="all, delete-orphan"
    )
    sent_messages: Mapped[list[MessageModel]] = relationship(
        "MessageModel", back_populates="sender", cascade="all, delete-orphan"
    )


class LeaseModel(Base):
    """SQLAlchemy model for leases table."""

    __tablename__ = "leases"

    lease_id: Mapped[str] = mapped_column(String, primary_key=True)
    task_id: Mapped[str] = mapped_column(String, nullable=False, index=True)
    agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.agent_id"), nullable=False, index=True
    )
    created_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO format
    expires_at: Mapped[str] = mapped_column(String, nullable=False, index=True)  # ISO format

    # Relationship
    agent: Mapped[AgentModel] = relationship("AgentModel", back_populates="leases")

    __table_args__ = (Index("idx_leases_agent_id", "agent_id"),)


class MessageModel(Base):
    """SQLAlchemy model for messages table (task-targeted only)."""

    __tablename__ = "messages"

    message_id: Mapped[str] = mapped_column(String, primary_key=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO format
    from_agent_id: Mapped[str] = mapped_column(
        String, ForeignKey("agents.agent_id"), nullable=False
    )
    task_id: Mapped[str] = mapped_column(String, nullable=False)
    text: Mapped[str] = mapped_column(Text, nullable=False)
    meta: Mapped[dict[str, Any]] = mapped_column(JSONField, default=dict)
    read_by: Mapped[list[str]] = mapped_column(JSONField, default=list)  # Agent IDs who read this

    # Relationship
    sender: Mapped[AgentModel] = relationship("AgentModel", back_populates="sent_messages")

    __table_args__ = (
        Index("idx_messages_task", "task_id"),
        Index("idx_messages_from", "from_agent_id"),
        Index("idx_messages_created", "created_at"),
    )


class EventModel(Base):
    """SQLAlchemy model for events table (audit log)."""

    __tablename__ = "events"

    event_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[str] = mapped_column(String, nullable=False)  # ISO format
    event_type: Mapped[str] = mapped_column(String, nullable=False)
    agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    task_id: Mapped[str | None] = mapped_column(String, nullable=True)
    target_agent_id: Mapped[str | None] = mapped_column(String, nullable=True)
    correlation_id: Mapped[str | None] = mapped_column(String, nullable=True)
    data: Mapped[dict[str, Any]] = mapped_column(JSONField, default=dict)

    __table_args__ = (
        Index("idx_events_created", "created_at"),
        Index("idx_events_type", "event_type"),
        Index("idx_events_correlation", "correlation_id"),
    )
