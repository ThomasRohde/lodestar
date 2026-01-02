"""Agent repository - handles agent registration and queries."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, text, update

from lodestar.models.runtime import Agent
from lodestar.runtime.converters import _parse_datetime, agent_to_orm, orm_to_agent
from lodestar.runtime.engine import get_session
from lodestar.runtime.event_types import EventType
from lodestar.runtime.models import AgentModel
from lodestar.runtime.repositories.event_repo import log_event

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class AgentRepository:
    """Repository for agent operations."""

    def __init__(self, session_factory: sessionmaker[Session]):
        """Initialize agent repository.

        Args:
            session_factory: SQLAlchemy session factory.
        """
        self._session_factory = session_factory

    def register(self, agent: Agent) -> Agent:
        """Register a new agent."""
        with get_session(self._session_factory) as session:
            orm_agent = agent_to_orm(agent)
            session.add(orm_agent)
            log_event(session, EventType.AGENT_JOIN, agent_id=agent.agent_id)

        return agent

    def get(self, agent_id: str) -> Agent | None:
        """Get an agent by ID."""
        with get_session(self._session_factory) as session:
            stmt = select(AgentModel).where(AgentModel.agent_id == agent_id)
            result = session.execute(stmt).scalar_one_or_none()

            if result is None:
                return None

            return orm_to_agent(result)

    def exists(self, agent_id: str) -> bool:
        """Check if an agent exists in the registry.

        Args:
            agent_id: Agent ID to check.

        Returns:
            True if the agent exists, False otherwise.
        """
        with get_session(self._session_factory) as session:
            from sqlalchemy import func

            stmt = (
                select(func.count()).select_from(AgentModel).where(AgentModel.agent_id == agent_id)
            )
            count = session.execute(stmt).scalar()
            return bool(count and count > 0)

    def list_all(self, active_only: bool = False) -> list[Agent]:
        """List all registered agents."""
        with get_session(self._session_factory) as session:
            stmt = select(AgentModel).order_by(AgentModel.last_seen_at.desc())
            results = session.execute(stmt).scalars().all()
            return [orm_to_agent(r) for r in results]

    def find_by_capability(self, capability: str) -> list[Agent]:
        """Find agents that have a specific capability.

        Args:
            capability: The capability name to search for.

        Returns:
            List of agents that have the specified capability.
        """
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
                        created_at=_parse_datetime(row.created_at),
                        last_seen_at=_parse_datetime(row.last_seen_at),
                        capabilities=capabilities,
                        session_meta=session_meta or {},
                    )
                )

            return agents

    def find_by_role(self, role: str) -> list[Agent]:
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
            return bool(result.rowcount > 0)  # type: ignore[attr-defined]

    def mark_offline(self, agent_id: str, reason: str | None = None) -> bool:
        """Mark an agent as offline gracefully.

        Sets the agent's last_seen_at to a timestamp that triggers offline status
        and logs an AGENT_LEAVE event.

        Args:
            agent_id: Agent ID to mark offline.
            reason: Optional reason for leaving.

        Returns:
            True if the agent was found and marked offline, False otherwise.
        """
        from datetime import timedelta

        from lodestar.models.runtime import DEFAULT_OFFLINE_THRESHOLD_MINUTES

        # Set last_seen_at to a time beyond the offline threshold
        offline_time = _utc_now() - timedelta(minutes=DEFAULT_OFFLINE_THRESHOLD_MINUTES + 1)

        with get_session(self._session_factory) as session:
            stmt = (
                update(AgentModel)
                .where(AgentModel.agent_id == agent_id)
                .values(last_seen_at=offline_time.isoformat())
            )
            result = session.execute(stmt)

            if result.rowcount > 0:  # type: ignore[attr-defined]
                # Log the leave event
                event_data = {"reason": reason} if reason else None
                log_event(
                    session,
                    EventType.AGENT_LEAVE,
                    agent_id=agent_id,
                    data=event_data,
                )
                return True

            return False
