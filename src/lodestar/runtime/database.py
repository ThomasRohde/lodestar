"""SQLite runtime database management - facade over repositories."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any

from sqlalchemy import func, select

from lodestar.models.runtime import Agent, Lease, Message
from lodestar.runtime.engine import create_runtime_engine, create_session_factory, get_session
from lodestar.runtime.models import AgentModel, Base, LeaseModel, MessageModel
from lodestar.runtime.repositories import AgentRepository, LeaseRepository, MessageRepository
from lodestar.util.paths import get_runtime_db_path


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    from datetime import UTC

    return datetime.now(UTC)


class RuntimeDatabase:
    """SQLite database facade - delegates to specialized repositories.

    This class maintains backward compatibility while delegating
    actual operations to AgentRepository, LeaseRepository, and MessageRepository.
    """

    def __init__(self, db_path: Path | None = None, use_pool: bool = False):
        """Initialize the runtime database.

        Args:
            db_path: Path to the database file. If None, uses default location.
            use_pool: Whether to use connection pooling. Set True for HTTP transport
                (handles concurrent sessions), False for stdio (CLI default).
        """
        self.db_path = db_path or get_runtime_db_path()
        self._engine = create_runtime_engine(self.db_path, use_pool=use_pool)
        self._session_factory = create_session_factory(self._engine)
        self._ensure_initialized()

        # Initialize repositories
        self._agents = AgentRepository(self._session_factory)
        self._leases = LeaseRepository(self._session_factory)
        self._messages = MessageRepository(self._session_factory)

    def _ensure_initialized(self) -> None:
        """Ensure database tables are created."""
        Base.metadata.create_all(self._engine)

    def dispose(self) -> None:
        """Dispose of the engine and release resources."""
        self._engine.dispose()

    # Agent operations (delegate to AgentRepository)

    def register_agent(self, agent: Agent) -> Agent:
        """Register a new agent."""
        return self._agents.register(agent)

    def get_agent(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        return self._agents.get(agent_id)

    def list_agents(self, active_only: bool = False) -> list[Agent]:
        """List all registered agents."""
        return self._agents.list_all(active_only)

    def find_agents_by_capability(self, capability: str) -> list[Agent]:
        """Find agents that have a specific capability."""
        return self._agents.find_by_capability(capability)

    def find_agents_by_role(self, role: str) -> list[Agent]:
        """Find agents that have a specific role."""
        return self._agents.find_by_role(role)

    def update_heartbeat(self, agent_id: str) -> bool:
        """Update an agent's heartbeat timestamp."""
        return self._agents.update_heartbeat(agent_id)

    def mark_agent_offline(self, agent_id: str, reason: str | None = None) -> bool:
        """Mark an agent as offline gracefully."""
        return self._agents.mark_offline(agent_id, reason)

    def agent_exists(self, agent_id: str) -> bool:
        """Check if an agent exists in the registry."""
        return self._agents.exists(agent_id)

    # Lease operations (delegate to LeaseRepository)

    def create_lease(self, lease: Lease) -> Lease | None:
        """Create a new lease atomically."""
        return self._leases.create(lease)

    def get_active_lease(self, task_id: str) -> Lease | None:
        """Get the active lease for a task, if any."""
        return self._leases.get_active(task_id)

    def get_agent_leases(self, agent_id: str, active_only: bool = True) -> list[Lease]:
        """Get all leases for an agent."""
        return self._leases.get_by_agent(agent_id, active_only)

    def get_all_active_leases(self) -> list[Lease]:
        """Get all currently active (non-expired) leases."""
        return self._leases.get_all_active()

    def renew_lease(self, lease_id: str, new_expires_at: datetime, agent_id: str) -> bool:
        """Renew a lease (only if owned by agent and still active)."""
        return self._leases.renew(lease_id, new_expires_at, agent_id)

    def release_lease(self, task_id: str, agent_id: str) -> bool:
        """Release a lease (set expires_at to now)."""
        return self._leases.release(task_id, agent_id)

    def cleanup_orphaned_leases(self) -> int:
        """Clean up leases held by non-existent agents.

        Returns:
            Number of leases cleaned up.
        """
        # Get all valid agent IDs
        agents = self._agents.list_all()
        valid_agent_ids = {a.agent_id for a in agents}
        return self._leases.cleanup_orphaned(valid_agent_ids)

    # Message operations (delegate to MessageRepository)

    def send_message(self, message: Message) -> Message:
        """Send a message to a task thread."""
        return self._messages.send(message)

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
            unread_by: Optional agent ID to filter for unread messages only.
        """
        return self._messages.get_task_thread(task_id, since, limit, unread_by)

    def get_task_unread_messages(
        self,
        task_id: str,
        agent_id: str,
        limit: int = 50,
    ) -> list[Message]:
        """Get unread messages for a task from an agent's perspective."""
        return self._messages.get_task_unread_messages(task_id, agent_id, limit)

    def get_task_message_count(self, task_id: str, unread_by: str | None = None) -> int:
        """Get the count of messages in a task thread.

        Args:
            task_id: The task ID to count messages for.
            unread_by: Optional agent ID to count only unread messages.
        """
        return self._messages.get_task_message_count(task_id, unread_by)

    def get_task_message_agents(self, task_id: str) -> list[str]:
        """Get unique agent IDs who have sent messages about a task."""
        return self._messages.get_task_message_agents(task_id)

    def search_messages(
        self,
        keyword: str | None = None,
        task_id: str | None = None,
        from_agent_id: str | None = None,
        since: datetime | None = None,
        until: datetime | None = None,
        limit: int = 50,
    ) -> list[Message]:
        """Search messages with optional filters."""
        return self._messages.search(keyword, task_id, from_agent_id, since, until, limit)

    def mark_task_messages_read(
        self,
        task_id: str,
        agent_id: str,
        message_ids: list[str] | None = None,
    ) -> int:
        """Mark task messages as read by an agent.

        Args:
            task_id: The task ID whose messages to mark.
            agent_id: The agent ID marking messages as read.
            message_ids: Optional list of specific message IDs. If None, marks all unread.

        Returns:
            Number of messages marked as read.
        """
        return self._messages.mark_task_messages_read(task_id, agent_id, message_ids)

    # Statistics (kept in facade for now)

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

    def get_task_message_summary(self) -> dict[str, int]:
        """Get message count per task."""
        with get_session(self._session_factory) as session:
            stmt = select(MessageModel.task_id, func.count().label("count")).group_by(
                MessageModel.task_id
            )
            results = session.execute(stmt).all()
            return {row.task_id: row[1] for row in results}
