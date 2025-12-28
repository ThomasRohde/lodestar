"""Message repository - handles message operations."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from lodestar.models.runtime import Message, MessageType
from lodestar.runtime.converters import message_to_orm, orm_to_message
from lodestar.runtime.engine import get_session
from lodestar.runtime.models import EventModel, MessageModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class MessageRepository:
    """Repository for message operations."""

    def __init__(self, session_factory: sessionmaker[Session]):
        """Initialize message repository.

        Args:
            session_factory: SQLAlchemy session factory.
        """
        self._session_factory = session_factory

    def send(self, message: Message) -> Message:
        """Send a message."""
        with get_session(self._session_factory) as session:
            orm_message = message_to_orm(message)
            session.add(orm_message)

            self._log_event(
                session,
                "message.send",
                message.from_agent_id,
                message.to_id if message.to_type == MessageType.TASK else None,
                {"to_type": message.to_type.value, "to_id": message.to_id},
            )

            return message

    def get_inbox(
        self,
        agent_id: str,
        since: datetime | None = None,
        until: datetime | None = None,
        from_agent_id: str | None = None,
        limit: int = 50,
        unread_only: bool = False,
        mark_as_read: bool = False,
    ) -> list[Message]:
        """Get messages for an agent.

        Args:
            agent_id: The agent whose inbox to retrieve
            since: Filter messages created after this time
            until: Filter messages created before this time
            from_agent_id: Filter by sender agent ID
            limit: Maximum number of messages to return
            unread_only: If True, only return unread messages (read_at IS NULL)
            mark_as_read: If True, mark returned messages as read

        Returns:
            List of messages matching the criteria
        """
        with get_session(self._session_factory) as session:
            # Build query with filters
            stmt = select(MessageModel).where(
                MessageModel.to_type == "agent",
                MessageModel.to_id == agent_id,
            )

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            if until:
                stmt = stmt.where(MessageModel.created_at < until.isoformat())

            if from_agent_id:
                stmt = stmt.where(MessageModel.from_agent_id == from_agent_id)

            if unread_only:
                stmt = stmt.where(MessageModel.read_at.is_(None))

            stmt = stmt.order_by(MessageModel.created_at.desc()).limit(limit)

            results = session.execute(stmt).scalars().all()
            messages = [orm_to_message(r) for r in results]

            # Mark messages as read if requested
            if mark_as_read and messages:
                now = _utc_now()
                message_ids = [msg.message_id for msg in messages]
                update_stmt = (
                    update(MessageModel)
                    .where(MessageModel.message_id.in_(message_ids))
                    .values(read_at=now.isoformat())
                )
                session.execute(update_stmt)
                # Update the messages in-memory to reflect the read status
                for msg in messages:
                    if msg.read_at is None:
                        msg.read_at = now

            return messages

    def get_task_thread(
        self, task_id: str, since: datetime | None = None, limit: int = 50
    ) -> list[Message]:
        """Get messages for a task thread."""
        with get_session(self._session_factory) as session:
            stmt = select(MessageModel).where(
                MessageModel.to_type == "task",
                MessageModel.to_id == task_id,
            )

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            stmt = stmt.order_by(MessageModel.created_at.asc()).limit(limit)

            results = session.execute(stmt).scalars().all()
            return [orm_to_message(r) for r in results]

    def get_task_message_count(self, task_id: str) -> int:
        """Get the count of messages in a task thread."""
        with get_session(self._session_factory) as session:
            stmt = (
                select(func.count())
                .select_from(MessageModel)
                .where(
                    MessageModel.to_type == "task",
                    MessageModel.to_id == task_id,
                )
            )
            result = session.execute(stmt).scalar()
            return result or 0

    def get_task_message_agents(self, task_id: str) -> list[str]:
        """Get unique agent IDs who have sent messages about a task."""
        with get_session(self._session_factory) as session:
            stmt = (
                select(MessageModel.from_agent_id)
                .distinct()
                .where(
                    MessageModel.to_type == "task",
                    MessageModel.to_id == task_id,
                )
                .order_by(MessageModel.from_agent_id)
            )
            results = session.execute(stmt).scalars().all()
            return list(results)

    def search(
        self,
        keyword: str | None = None,
        from_agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Search messages with optional filters.

        Args:
            keyword: Search term to match in message text (case-insensitive)
            from_agent_id: Filter by sender agent ID
            since: Filter messages created after this time
            until: Filter messages created before this time
            limit: Maximum number of messages to return

        Returns:
            List of messages matching the search criteria
        """
        with get_session(self._session_factory) as session:
            stmt = select(MessageModel)

            if keyword:
                stmt = stmt.where(MessageModel.text.like(f"%{keyword}%"))

            if from_agent_id:
                stmt = stmt.where(MessageModel.from_agent_id == from_agent_id)

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            if until:
                stmt = stmt.where(MessageModel.created_at < until.isoformat())

            stmt = stmt.order_by(MessageModel.created_at.desc()).limit(limit)

            results = session.execute(stmt).scalars().all()
            return [orm_to_message(r) for r in results]

    def get_inbox_count(self, agent_id: str, since: datetime | None = None) -> int:
        """Get count of messages in inbox."""
        with get_session(self._session_factory) as session:
            stmt = (
                select(func.count())
                .select_from(MessageModel)
                .where(
                    MessageModel.to_type == "agent",
                    MessageModel.to_id == agent_id,
                )
            )

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            result = session.execute(stmt).scalar()
            return result or 0

    def wait_for_message(
        self, agent_id: str, timeout_seconds: float | None = None, since: datetime | None = None
    ) -> bool:
        """Wait for a new message to arrive.

        Returns True if a message was received, False if timeout occurred.
        Uses polling with exponential backoff to check for new messages.
        """
        # Check if there are already messages
        if self.get_inbox_count(agent_id, since=since) > 0:
            return True

        # Poll with exponential backoff
        start_time = time.time()
        sleep_time = 0.1  # Start with 100ms
        max_sleep = 2.0  # Cap at 2 seconds

        while True:
            # Check for timeout
            if timeout_seconds is not None:
                elapsed = time.time() - start_time
                if elapsed >= timeout_seconds:
                    return False

            # Sleep before next check
            time.sleep(sleep_time)

            # Check for new messages
            if self.get_inbox_count(agent_id, since=since) > 0:
                return True

            # Increase sleep time with exponential backoff
            sleep_time = min(sleep_time * 1.5, max_sleep)

    def _log_event(
        self,
        session: Session,
        event_type: str,
        agent_id: str | None,
        task_id: str | None,
        data: dict,
    ) -> None:
        """Log an event to the events table."""
        event = EventModel(
            created_at=_utc_now().isoformat(),
            event_type=event_type,
            agent_id=agent_id,
            task_id=task_id,
            data=data,
        )
        session.add(event)
