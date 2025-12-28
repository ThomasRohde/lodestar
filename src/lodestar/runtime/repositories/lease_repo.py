"""Lease repository - handles task lease operations."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import TYPE_CHECKING

from sqlalchemy import select, update

from lodestar.models.runtime import Lease
from lodestar.runtime.converters import lease_to_orm, orm_to_lease
from lodestar.runtime.engine import get_session
from lodestar.runtime.models import EventModel, LeaseModel

if TYPE_CHECKING:
    from sqlalchemy.orm import Session, sessionmaker


def _utc_now() -> datetime:
    """Return current UTC datetime (timezone-aware)."""
    return datetime.now(UTC)


class LeaseRepository:
    """Repository for lease operations."""

    def __init__(self, session_factory: sessionmaker[Session]):
        """Initialize lease repository.

        Args:
            session_factory: SQLAlchemy session factory.
        """
        self._session_factory = session_factory

    def create(self, lease: Lease) -> Lease | None:
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

    def get_active(self, task_id: str) -> Lease | None:
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

    def get_by_agent(self, agent_id: str, active_only: bool = True) -> list[Lease]:
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

    def get_all_active(self) -> list[Lease]:
        """Get all currently active (non-expired) leases.

        Used for lock conflict detection during task claim.

        Returns:
            List of all active leases.
        """
        now = _utc_now()

        with get_session(self._session_factory) as session:
            stmt = (
                select(LeaseModel)
                .where(LeaseModel.expires_at > now.isoformat())
                .order_by(LeaseModel.created_at.desc())
            )
            results = session.execute(stmt).scalars().all()
            return [orm_to_lease(r) for r in results]

    def renew(self, lease_id: str, new_expires_at: datetime, agent_id: str) -> bool:
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

            if result.rowcount > 0:  # type: ignore[attr-defined]
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

    def release(self, task_id: str, agent_id: str) -> bool:
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

            if result.rowcount > 0:  # type: ignore[attr-defined]
                self._log_event(session, "task.release", agent_id, task_id, {})
                return True

            return False

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
