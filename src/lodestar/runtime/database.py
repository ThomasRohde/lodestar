"""SQLite runtime database management with SQLAlchemy ORM."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import func, select, text, update
from sqlalchemy.orm import Session

from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.runtime.converters import (
    agent_to_orm,
    lease_to_orm,
    message_to_orm,
    orm_to_agent,
    orm_to_lease,
    orm_to_message,
)
from lodestar.runtime.engine import create_runtime_engine, create_session_factory, get_session
from lodestar.runtime.models import AgentModel, Base, EventModel, LeaseModel, MessageModel
from lodestar.util.paths import get_runtime_db_path


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(timezone.utc)


class RuntimeDatabase:
    """SQLite database for runtime state with WAL mode for concurrency."""

    def __init__(self, db_path: Path | None = None):
        """Initialize the runtime database.

        Args:
            db_path: Path to the database file. If None, uses default location.
        """
        self.db_path = db_path or get_runtime_db_path()
        self._engine = create_runtime_engine(self.db_path)
        self._session_factory = create_session_factory(self._engine)
        self._ensure_initialized()

    def _ensure_initialized(self) -> None:
        """Ensure database tables are created."""
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Dispose of the engine and release resources.

        Call this method to properly close all connections and release
        file locks on Windows.
        """
        self._engine.dispose()

    # Agent operations

    def register_agent(self, agent: Agent) -> Agent:
        """Register a new agent."""
        with get_session(self._session_factory) as session:
            orm_agent = agent_to_orm(agent)
            session.add(orm_agent)
            self._log_event(session, "agent.join", agent.agent_id, None, {})

        return agent

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        with get_session(self._session_factory) as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = session.execute(stmt).scalar_one_or_none()

            if result is None:
                return None

            return orm_to_agent(result)

    def list_agents(self, active_only: bool = False) -> list[Agent]:
        """List all registered agents."""
        with get_session(self._session_factory) as session:
            stmt = select(AgentModel).order_by(AgentModel.last_seen_at.desc())
            results = session.execute(stmt).scalars().all()
            return [orm_to_agent(r) for r in results]

    def find_agents_by_capability(self, capability: str) -> list[Agent]:
        """Find agents that have a specific capability.

        Args:
            capability: The capability name to search for.

        Returns:
            List of agents that have the specified capability.
        """
        import json

        with get_session(self._session_factory) as session:
            # Use SQLite's json_each to search within the capabilities array
            stmt = text("""
                SELECT DISTINCT a.* FROM agents a, json_each(a.capabilities) AS cap
                WHERE cap.value = :capability
                ORDER BY a.last_seen_at DESC
            """)
            results = session.execute(stmt, {"capability": capability}).fetchall()

            agents = []
            for row in results:
                # Handle backward compatibility for capabilities
                capabilities_raw = (
                    json.loads(row.capabilities)
                    if isinstance(row.capabilities, str)
                    else row.capabilities
                )
                capabilities = capabilities_raw if isinstance(capabilities_raw, list) else []

                session_meta = (
                    json.loads(row.session_meta)
                    if isinstance(row.session_meta, str)
                    else row.session_meta
                )

                agents.append(
                    Agent(
                        agent_id=row.agent_id,
                        display_name=row.display_name,
                        role=row.role or "",
                        created_at=datetime.fromisoformat(row.created_at),
                        last_seen_at=datetime.fromisoformat(row.last_seen_at),
                        capabilities=capabilities,
                        session_meta=session_meta or {},
                    )
                )

            return agents

    def find_agents_by_role(self, role: str) -> list[Agent]:
        """Find agents that have a specific role.

        Args:
            role: The role to search for.

        Returns:
            List of agents with the specified role.
        """
        with get_session(self._session_factory) as session:
            stmt = (
                select(AgentModel)
                .where(AgentModel.role == role)
                .order_by(AgentModel.last_seen_at.desc())
            )
            results = session.execute(stmt).scalars().all()
            return [orm_to_agent(r) for r in results]

    def update_heartbeat(self, agent_id: str) -> bool:
        """Update an agent's heartbeat timestamp."""
        with get_session(self._session_factory) as session:
            stmt = (
                update(AgentModel)
                .where(AgentModel.agent_id == agent_id)
                .values(last_seen_at=_utc_now().isoformat())
            )
            result = session.execute(stmt)
            return result.rowcount > 0

    # Lease operations

    def create_lease(self, lease: Lease) -> Lease | None:
        """Create a new lease atomically.

        Returns the lease if created, None if the task already has an active lease.
        """
        now = _utc_now()

        with get_session(self._session_factory) as session:
            # Check for existing active lease (atomic within transaction)
            stmt = select(LeaseModel).where(
                LeaseModel.task_id == lease.task_id,
                LeaseModel.expires_at > now.isoformat(),
            )
            existing = session.execute(stmt).scalar_one_or_none()

            if existing:
                return None  # Task already claimed

            # Create the lease
            orm_lease = lease_to_orm(lease)
            session.add(orm_lease)

            self._log_event(
                session,
                "task.claim",
                lease.agent_id,
                lease.task_id,
                {"lease_id": lease.lease_id},
            )

            return lease

    def get_active_lease(self, task_id: str) -> Lease | None:
        """Get the active lease for a task, if any."""
        now = _utc_now()

        with get_session(self._session_factory) as session:
            stmt = (
                select(LeaseModel)
                .where(
                    LeaseModel.task_id == task_id,
                    LeaseModel.expires_at > now.isoformat(),
                )
                .order_by(LeaseModel.expires_at.desc())
                .limit(1)
            )
            result = session.execute(stmt).scalar_one_or_none()

            if result is None:
                return None

            return orm_to_lease(result)

    def get_agent_leases(self, agent_id: str, active_only: bool = True) -> list[Lease]:
        """Get all leases for an agent."""
        now = _utc_now()

        with get_session(self._session_factory) as session:
            if active_only:
                stmt = (
                    select(LeaseModel)
                    .where(
                        LeaseModel.agent_id == agent_id,
                        LeaseModel.expires_at > now.isoformat(),
                    )
                    .order_by(LeaseModel.expires_at.desc())
                )
            else:
                stmt = (
                    select(LeaseModel)
                    .where(LeaseModel.agent_id == agent_id)
                    .order_by(LeaseModel.expires_at.desc())
                )

            results = session.execute(stmt).scalars().all()
            return [orm_to_lease(r) for r in results]

    def renew_lease(self, lease_id: str, new_expires_at: datetime, agent_id: str) -> bool:
        """Renew a lease (only if owned by agent and still active)."""
        now = _utc_now()

        with get_session(self._session_factory) as session:
            stmt = (
                update(LeaseModel)
                .where(
                    LeaseModel.lease_id == lease_id,
                    LeaseModel.agent_id == agent_id,
                    LeaseModel.expires_at > now.isoformat(),
                )
                .values(expires_at=new_expires_at.isoformat())
            )
            result = session.execute(stmt)

            if result.rowcount > 0:
                # Get task_id for logging
                lease_stmt = select(LeaseModel.task_id).where(LeaseModel.lease_id == lease_id)
                task_id = session.execute(lease_stmt).scalar_one_or_none()
                if task_id:
                    self._log_event(
                        session,
                        "task.renew",
                        agent_id,
                        task_id,
                        {"lease_id": lease_id},
                    )
                return True

            return False

    def release_lease(self, task_id: str, agent_id: str) -> bool:
        """Release a lease (set expires_at to now)."""
        now = _utc_now()

        with get_session(self._session_factory) as session:
            stmt = (
                update(LeaseModel)
                .where(
                    LeaseModel.task_id == task_id,
                    LeaseModel.agent_id == agent_id,
                    LeaseModel.expires_at > now.isoformat(),
                )
                .values(expires_at=now.isoformat())
            )
            result = session.execute(stmt)

            if result.rowcount > 0:
                self._log_event(session, "task.release", agent_id, task_id, {})
                return True

            return False

    # Message operations

    def send_message(self, message: Message) -> Message:
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

    def search_messages(
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
        import time

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

    # Statistics

    def get_stats(self) -> dict[str, Any]:
        """Get runtime statistics."""
        now = _utc_now()

        with get_session(self._session_factory) as session:
            agent_count = session.execute(select(func.count()).select_from(AgentModel)).scalar()

            active_leases = session.execute(
                select(func.count())
                .select_from(LeaseModel)
                .where(LeaseModel.expires_at > now.isoformat())
            ).scalar()

            total_messages = session.execute(
                select(func.count()).select_from(MessageModel)
            ).scalar()

            return {
                "agents": agent_count or 0,
                "active_leases": active_leases or 0,
                "total_messages": total_messages or 0,
            }

    def get_agent_message_counts(self) -> dict[str, int]:
        """Get message count per agent.

        Returns a dictionary mapping agent_id to message count.
        """
        with get_session(self._session_factory) as session:
            stmt = (
                select(MessageModel.to_id, func.count().label("count"))
                .where(MessageModel.to_type == "agent")
                .group_by(MessageModel.to_id)
            )
            results = session.execute(stmt).all()
            return {row.to_id: row.count for row in results}

    def _log_event(
        self,
        session: Session,
        event_type: str,
        agent_id: str | None,
        task_id: str | None,
        data: dict[str, Any],
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
