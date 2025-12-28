"""Event repository - handles event logging and queries."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

from sqlalchemy import select

from lodestar.runtime.models import EventModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


def log_event(
    session: Session,
    event_type: str,
    agent_id: str | None = None,
    task_id: str | None = None,
    target_agent_id: str | None = None,
    correlation_id: str | None = None,
    data: dict[str, Any] | None = None,
) -> EventModel:
    """
    Log an event to the events table atomically within a transaction.

    This function should be called within an active database session/transaction
    to ensure the event is logged atomically with the operation it describes.

    Args:
        session: Active SQLAlchemy session (with transaction).
        event_type: Type of event (use EventType constants).
        agent_id: ID of the agent performing the action (nullable).
        task_id: ID of the task involved (nullable).
        target_agent_id: ID of the target agent (for messages, etc.) (nullable).
        correlation_id: Correlation ID for related events (nullable).
        data: Additional event data as JSON (nullable).

    Returns:
        The created EventModel instance.
    """
    event = EventModel(
        created_at=_utc_now().isoformat(),
        event_type=event_type,
        agent_id=agent_id,
        task_id=task_id,
        target_agent_id=target_agent_id,
        correlation_id=correlation_id,
        data=data or {},
    )
    session.add(event)
    return event


def get_events_since(
    session: Session,
    since_event_id: int,
    limit: int = 100,
) -> list[EventModel]:
    """
    Get events since a given event ID (for event stream polling).

    Args:
        session: Active SQLAlchemy session.
        since_event_id: Get events with event_id > this value.
        limit: Maximum number of events to return.

    Returns:
        List of EventModel instances ordered by event_id.
    """
    stmt = (
        select(EventModel)
        .where(EventModel.event_id > since_event_id)
        .order_by(EventModel.event_id.asc())
        .limit(limit)
    )
    results = session.execute(stmt).scalars().all()
    return list(results)


def get_events_since_filtered(
    session: Session,
    since_event_id: int,
    limit: int = 100,
    filter_types: list[str] | None = None,
) -> list[EventModel]:
    """
    Get events since a given event ID with optional type filtering.

    Args:
        session: Active SQLAlchemy session.
        since_event_id: Get events with event_id > this value.
        limit: Maximum number of events to return.
        filter_types: Optional list of event types to filter by.

    Returns:
        List of EventModel instances ordered by event_id.
    """
    stmt = select(EventModel).where(EventModel.event_id > since_event_id)

    if filter_types:
        stmt = stmt.where(EventModel.event_type.in_(filter_types))

    stmt = stmt.order_by(EventModel.event_id.asc()).limit(limit)
    results = session.execute(stmt).scalars().all()
    return list(results)


def get_latest_event_id(session: Session) -> int:
    """
    Get the latest event ID in the events table.

    Args:
        session: Active SQLAlchemy session.

    Returns:
        Latest event_id, or 0 if no events exist.
    """
    stmt = select(EventModel.event_id).order_by(EventModel.event_id.desc()).limit(1)
    result = session.execute(stmt).scalar_one_or_none()
    return result if result is not None else 0
