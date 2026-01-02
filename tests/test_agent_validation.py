"""Tests for agent validation and lease cleanup."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lodestar.models.runtime import Agent, Lease
from lodestar.runtime.database import RuntimeDatabase


@pytest.fixture
def temp_db(tmp_path: Path) -> RuntimeDatabase:
    """Create a temporary runtime database."""
    db_path = tmp_path / "test_runtime.db"
    db = RuntimeDatabase(db_path)
    return db


def test_agent_exists_returns_false_for_unregistered_agent(temp_db: RuntimeDatabase) -> None:
    """Test that agent_exists returns False for unregistered agents."""
    assert not temp_db.agent_exists("non-existent-agent")


def test_agent_exists_returns_true_for_registered_agent(temp_db: RuntimeDatabase) -> None:
    """Test that agent_exists returns True for registered agents."""
    # Register an agent
    agent = Agent(
        agent_id="test-agent-001",
        display_name="Test Agent",
        role="tester",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        capabilities=["testing"],
        session_meta={},
    )
    temp_db.register_agent(agent)

    # Verify it exists
    assert temp_db.agent_exists("test-agent-001")


def test_cleanup_orphaned_leases_removes_leases_from_unregistered_agents(
    temp_db: RuntimeDatabase,
) -> None:
    """Test that cleanup_orphaned_leases removes leases held by non-existent agents."""
    # Create two agents
    agent1 = Agent(
        agent_id="agent-1",
        display_name="Agent 1",
        role="worker",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        capabilities=[],
        session_meta={},
    )
    agent2 = Agent(
        agent_id="agent-2",
        display_name="Agent 2",
        role="worker",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        capabilities=[],
        session_meta={},
    )
    temp_db.register_agent(agent1)
    temp_db.register_agent(agent2)

    # Create leases for both agents
    now = datetime.now(UTC)
    lease1 = Lease(
        task_id="TASK-001",
        agent_id="agent-1",
        expires_at=now + timedelta(minutes=15),
    )
    lease2 = Lease(
        task_id="TASK-002",
        agent_id="agent-2",
        expires_at=now + timedelta(minutes=15),
    )
    # Create a lease for an unregistered agent
    lease3 = Lease(
        task_id="TASK-003",
        agent_id="unregistered-agent",
        expires_at=now + timedelta(minutes=15),
    )

    temp_db.create_lease(lease1)
    temp_db.create_lease(lease2)
    temp_db.create_lease(lease3)

    # Verify all leases are active
    assert temp_db.get_active_lease("TASK-001") is not None
    assert temp_db.get_active_lease("TASK-002") is not None
    assert temp_db.get_active_lease("TASK-003") is not None

    # Run cleanup
    cleaned = temp_db.cleanup_orphaned_leases()

    # Should have cleaned up 1 lease (the unregistered agent)
    assert cleaned == 1

    # Verify valid leases still exist
    assert temp_db.get_active_lease("TASK-001") is not None
    assert temp_db.get_active_lease("TASK-002") is not None

    # Verify orphaned lease is gone
    assert temp_db.get_active_lease("TASK-003") is None


def test_cleanup_orphaned_leases_returns_zero_when_all_valid(
    temp_db: RuntimeDatabase,
) -> None:
    """Test that cleanup_orphaned_leases returns 0 when all leases are valid."""
    # Create an agent
    agent = Agent(
        agent_id="agent-1",
        display_name="Agent 1",
        role="worker",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        capabilities=[],
        session_meta={},
    )
    temp_db.register_agent(agent)

    # Create lease for the agent
    now = datetime.now(UTC)
    lease = Lease(
        task_id="TASK-001",
        agent_id="agent-1",
        expires_at=now + timedelta(minutes=15),
    )
    temp_db.create_lease(lease)

    # Run cleanup
    cleaned = temp_db.cleanup_orphaned_leases()

    # Should have cleaned up 0 leases
    assert cleaned == 0

    # Verify lease still exists
    assert temp_db.get_active_lease("TASK-001") is not None


def test_cleanup_orphaned_leases_ignores_expired_leases(temp_db: RuntimeDatabase) -> None:
    """Test that cleanup only affects active leases, not expired ones."""
    # Create lease for unregistered agent that's already expired
    now = datetime.now(UTC)
    expired_lease = Lease(
        task_id="TASK-001",
        agent_id="unregistered-agent",
        expires_at=now - timedelta(minutes=5),  # Expired 5 minutes ago
    )
    temp_db.create_lease(expired_lease)

    # Run cleanup
    cleaned = temp_db.cleanup_orphaned_leases()

    # Should have cleaned up 0 leases (already expired)
    assert cleaned == 0


def test_cleanup_orphaned_leases_handles_multiple_orphaned_leases(
    temp_db: RuntimeDatabase,
) -> None:
    """Test that cleanup handles multiple orphaned leases at once."""
    # Create multiple leases for unregistered agents
    now = datetime.now(UTC)
    for i in range(5):
        lease = Lease(
            task_id=f"TASK-{i:03d}",
            agent_id=f"unregistered-agent-{i}",
            expires_at=now + timedelta(minutes=15),
        )
        temp_db.create_lease(lease)

    # Run cleanup
    cleaned = temp_db.cleanup_orphaned_leases()

    # Should have cleaned up all 5 leases
    assert cleaned == 5

    # Verify all leases are gone
    for i in range(5):
        assert temp_db.get_active_lease(f"TASK-{i:03d}") is None


def test_agent_exists_case_sensitive(temp_db: RuntimeDatabase) -> None:
    """Test that agent_exists is case-sensitive."""
    # Register an agent
    agent = Agent(
        agent_id="Test-Agent-001",
        display_name="Test Agent",
        role="tester",
        created_at=datetime.now(UTC),
        last_seen_at=datetime.now(UTC),
        capabilities=[],
        session_meta={},
    )
    temp_db.register_agent(agent)

    # Should match exact case
    assert temp_db.agent_exists("Test-Agent-001")

    # Should not match different case
    assert not temp_db.agent_exists("test-agent-001")
    assert not temp_db.agent_exists("TEST-AGENT-001")
