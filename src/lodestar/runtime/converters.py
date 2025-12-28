"""Convert between SQLAlchemy models and Pydantic models."""

from __future__ import annotations

from datetime import datetime, timezone

from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.runtime.models import AgentModel, LeaseModel, MessageModel


def _ensure_utc(dt: datetime) -> datetime:
    """Ensure a datetime is timezone-aware (UTC).

    Handles backward compatibility for datetimes stored without timezone info.

    Args:
        dt: A datetime that may or may not have timezone info.

    Returns:
        A timezone-aware datetime in UTC.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt


def _parse_datetime(iso_str: str) -> datetime:
    """Parse an ISO format datetime string and ensure it's UTC.

    Args:
        iso_str: ISO format datetime string.

    Returns:
        A timezone-aware datetime in UTC.
    """
    dt = datetime.fromisoformat(iso_str)
    return _ensure_utc(dt)


# Agent conversions


def agent_to_orm(agent: Agent) -> AgentModel:
    """Convert Pydantic Agent to SQLAlchemy AgentModel.

    Args:
        agent: The Pydantic Agent model.

    Returns:
        A SQLAlchemy AgentModel instance.
    """
    return AgentModel(
        agent_id=agent.agent_id,
        display_name=agent.display_name,
        role=agent.role,
        created_at=agent.created_at.isoformat(),
        last_seen_at=agent.last_seen_at.isoformat(),
        capabilities=agent.capabilities,
        session_meta=agent.session_meta,
    )


def orm_to_agent(model: AgentModel) -> Agent:
    """Convert SQLAlchemy AgentModel to Pydantic Agent.

    Handles backward compatibility for capabilities field that may
    be stored as dict in old databases.

    Args:
        model: The SQLAlchemy AgentModel instance.

    Returns:
        A Pydantic Agent model.
    """
    # Handle backward compatibility: old agents may have capabilities as dict
    capabilities = model.capabilities if isinstance(model.capabilities, list) else []

    return Agent(
        agent_id=model.agent_id,
        display_name=model.display_name,
        role=model.role or "",
        created_at=_parse_datetime(model.created_at),
        last_seen_at=_parse_datetime(model.last_seen_at),
        capabilities=capabilities,
        session_meta=model.session_meta or {},
    )


# Lease conversions


def lease_to_orm(lease: Lease) -> LeaseModel:
    """Convert Pydantic Lease to SQLAlchemy LeaseModel.

    Args:
        lease: The Pydantic Lease model.

    Returns:
        A SQLAlchemy LeaseModel instance.
    """
    return LeaseModel(
        lease_id=lease.lease_id,
        task_id=lease.task_id,
        agent_id=lease.agent_id,
        created_at=lease.created_at.isoformat(),
        expires_at=lease.expires_at.isoformat(),
    )


def orm_to_lease(model: LeaseModel) -> Lease:
    """Convert SQLAlchemy LeaseModel to Pydantic Lease.

    Args:
        model: The SQLAlchemy LeaseModel instance.

    Returns:
        A Pydantic Lease model.
    """
    return Lease(
        lease_id=model.lease_id,
        task_id=model.task_id,
        agent_id=model.agent_id,
        created_at=_parse_datetime(model.created_at),
        expires_at=_parse_datetime(model.expires_at),
    )


# Message conversions


def message_to_orm(message: Message) -> MessageModel:
    """Convert Pydantic Message to SQLAlchemy MessageModel.

    Args:
        message: The Pydantic Message model.

    Returns:
        A SQLAlchemy MessageModel instance.
    """
    return MessageModel(
        message_id=message.message_id,
        created_at=message.created_at.isoformat(),
        from_agent_id=message.from_agent_id,
        to_type=message.to_type.value,
        to_id=message.to_id,
        text=message.text,
        meta=message.meta,
        read_at=message.read_at.isoformat() if message.read_at else None,
    )


def orm_to_message(model: MessageModel) -> Message:
    """Convert SQLAlchemy MessageModel to Pydantic Message.

    Args:
        model: The SQLAlchemy MessageModel instance.

    Returns:
        A Pydantic Message model.
    """
    return Message(
        message_id=model.message_id,
        created_at=_parse_datetime(model.created_at),
        from_agent_id=model.from_agent_id,
        to_type=MessageType(model.to_type),
        to_id=model.to_id,
        text=model.text,
        meta=model.meta or {},
        read_at=_parse_datetime(model.read_at) if model.read_at else None,
    )
