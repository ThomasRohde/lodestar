"""Message repository - handles task-targeted message operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import func, select, update

from lodestar.models.runtime import Message
from lodestar.runtime.converters import message_to_orm, orm_to_message
from lodestar.runtime.engine import get_session
from lodestar.runtime.event_types import EventType
from lodestar.runtime.models import MessageModel
from lodestar.runtime.repositories.event_repo import log_event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class MessageRepository:
    """Repository for task-targeted message operations."""

    def __init__(self, session_factory: sessionmaker[Session]):
        """Initialize message repository.

        Args:
            session_factory: SQLAlchemy session factory.
        """
        self._session_factory = session_factory

    def send(self, message: Message) -> Message:
        """Send a message to a task thread.

        Args:
            message: The message to send (must be task-targeted).

        Returns:
            The sent message.
        """
        with get_session(self._session_factory) as session:
            orm_message = message_to_orm(message)
            session.add(orm_message)

            log_event(
                session,
                EventType.MESSAGE_SENT,
                agent_id=message.from_agent_id,
                task_id=message.task_id,
                target_agent_id=None,
                data={"task_id": message.task_id},
            )

            return message

    def get_task_thread(
        self,
        task_id: str,
        since: datetime | None = None,
        limit: int = 50,
        unread_by: str | None = None,
    ) -> list[Message]:
        """Get messages for a task thread.

        Args:
            task_id: The task ID to get messages for.
            since: Optional filter for messages created after this time.
            limit: Maximum number of messages to return.
            unread_by: Optional agent ID to filter for unread messages.

        Returns:
            List of messages in chronological order.
        """
        with get_session(self._session_factory) as session:
            stmt = select(MessageModel).where(MessageModel.task_id == task_id)

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            stmt = stmt.order_by(MessageModel.created_at.asc()).limit(limit)

            results = session.execute(stmt).scalars().all()
            messages = [orm_to_message(r) for r in results]

            # Filter for unread if requested
            if unread_by:
                messages = [m for m in messages if unread_by not in m.read_by]

            return messages

    def get_task_unread_messages(
        self,
        task_id: str,
        agent_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Get unread messages for a task from the perspective of an agent.

        Args:
            task_id: The task ID to get messages for.
            agent_id: The agent ID to check read status for.
            limit: Maximum number of messages to return.

        Returns:
            List of unread messages in chronological order.
        """
        return self.get_task_thread(task_id, unread_by=agent_id, limit=limit)

    def get_task_message_count(self, task_id: str, unread_by: str | None = None) -> int:
        """Get the count of messages in a task thread.

        Args:
            task_id: The task ID to count messages for.
            unread_by: Optional agent ID to count only unread messages.

        Returns:
            Number of messages (or unread messages if agent_id provided).
        """
        with get_session(self._session_factory) as session:
            # For unread count, we need to fetch and filter in Python
            # since read_by is a JSON array
            if unread_by:
                msg_stmt = select(MessageModel).where(MessageModel.task_id == task_id)
                results = session.execute(msg_stmt).scalars().all()
                messages = [orm_to_message(r) for r in results]
                return len([m for m in messages if unread_by not in m.read_by])

            count_stmt = (
                select(func.count())
                .select_from(MessageModel)
                .where(MessageModel.task_id == task_id)
            )

            result = session.execute(count_stmt).scalar()
            return result or 0

    def get_task_message_agents(self, task_id: str) -> list[str]:
        """Get unique agent IDs who have sent messages about a task.

        Args:
            task_id: The task ID to get agents for.

        Returns:
            List of unique agent IDs who sent messages to this task.
        """
        with get_session(self._session_factory) as session:
            stmt = (
                select(MessageModel.from_agent_id)
                .distinct()
                .where(MessageModel.task_id == task_id)
                .order_by(MessageModel.from_agent_id)
            )
            results = session.execute(stmt).scalars().all()
            return list(results)

    def search(
        self,
        keyword: str | None = None,
        task_id: str | None = None,
        from_agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Search messages with optional filters.

        Args:
            keyword: Search term to match in message text (case-insensitive).
            task_id: Filter by task ID.
            from_agent_id: Filter by sender agent ID.
            since: Filter messages created after this time.
            until: Filter messages created before this time.
            limit: Maximum number of messages to return.

        Returns:
            List of messages matching the search criteria.
        """
        with get_session(self._session_factory) as session:
            stmt = select(MessageModel)

            if keyword:
                stmt = stmt.where(MessageModel.text.like(f"%{keyword}%"))

            if task_id:
                stmt = stmt.where(MessageModel.task_id == task_id)

            if from_agent_id:
                stmt = stmt.where(MessageModel.from_agent_id == from_agent_id)

            if since:
                stmt = stmt.where(MessageModel.created_at > since.isoformat())

            if until:
                stmt = stmt.where(MessageModel.created_at < until.isoformat())

            stmt = stmt.order_by(MessageModel.created_at.desc()).limit(limit)

            results = session.execute(stmt).scalars().all()
            return [orm_to_message(r) for r in results]

    def mark_task_messages_read(
        self,
        task_id: str,
        agent_id: str,
        message_ids: list[str] | None = None,
    ) -> int:
        """Mark task messages as read by an agent.

        Args:
            task_id: The task ID whose messages to mark as read.
            agent_id: The agent ID marking messages as read.
            message_ids: Optional list of specific message IDs to mark.
                        If None, marks all unread messages in the task thread.

        Returns:
            Number of messages marked as read.
        """
        with get_session(self._session_factory) as session:
            # Fetch messages to update
            stmt = select(MessageModel).where(MessageModel.task_id == task_id)

            if message_ids:
                stmt = stmt.where(MessageModel.message_id.in_(message_ids))

            results = session.execute(stmt).scalars().all()

            updated_count = 0
            for msg_model in results:
                # Convert to check if already read
                msg = orm_to_message(msg_model)
                if agent_id not in msg.read_by:
                    # Add agent to read_by list
                    new_read_by = msg.read_by + [agent_id]
                    update_stmt = (
                        update(MessageModel)
                        .where(MessageModel.message_id == msg_model.message_id)
                        .values(read_by=new_read_by)
                    )
                    session.execute(update_stmt)
                    updated_count += 1

            return updated_count
