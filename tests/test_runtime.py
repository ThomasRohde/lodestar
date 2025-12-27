"""Tests for runtime database operations."""

from __future__ import annotations

import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.runtime.database import RuntimeDatabase


@pytest.fixture
def db():
    """Create a temporary runtime database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "runtime.sqlite"
        yield RuntimeDatabase(db_path)


class TestAgentOperations:
    """Test agent database operations."""

    def test_register_agent(self, db):
        agent = Agent(display_name="TestBot")
        registered = db.register_agent(agent)
        assert registered.agent_id == agent.agent_id

    def test_get_agent(self, db):
        agent = Agent(display_name="TestBot")
        db.register_agent(agent)
        retrieved = db.get_agent(agent.agent_id)
        assert retrieved is not None
        assert retrieved.display_name == "TestBot"

    def test_get_nonexistent_agent(self, db):
        result = db.get_agent("nonexistent")
        assert result is None

    def test_list_agents(self, db):
        db.register_agent(Agent(display_name="Bot1"))
        db.register_agent(Agent(display_name="Bot2"))
        agents = db.list_agents()
        assert len(agents) == 2

    def test_update_heartbeat(self, db):
        agent = Agent(display_name="TestBot")
        db.register_agent(agent)
        success = db.update_heartbeat(agent.agent_id)
        assert success is True


class TestLeaseOperations:
    """Test lease database operations."""

    def test_create_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        created = db.create_lease(lease)

        assert created is not None
        assert created.task_id == "T001"

    def test_create_duplicate_lease_fails(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease1 = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease1)

        lease2 = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        result = db.create_lease(lease2)
        assert result is None  # Should fail

    def test_get_active_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        active = db.get_active_lease("T001")
        assert active is not None
        assert active.agent_id == agent.agent_id

    def test_expired_lease_not_active(self, db):
        agent = Agent()
        db.register_agent(agent)

        # Create an already expired lease
        expires = datetime.utcnow() - timedelta(minutes=1)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        # Directly insert the lease bypassing the check

        with db._connect() as conn:
            conn.execute(
                """
                INSERT INTO leases (lease_id, task_id, agent_id, created_at, expires_at)
                VALUES (?, ?, ?, ?, ?)
                """,
                (
                    lease.lease_id,
                    lease.task_id,
                    lease.agent_id,
                    lease.created_at.isoformat(),
                    lease.expires_at.isoformat(),
                ),
            )

        active = db.get_active_lease("T001")
        assert active is None  # Expired lease should not be returned

    def test_renew_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        created = db.create_lease(lease)

        new_expires = datetime.utcnow() + timedelta(minutes=30)
        success = db.renew_lease(created.lease_id, new_expires, agent.agent_id)
        assert success is True

        updated = db.get_active_lease("T001")
        assert updated.expires_at > expires

    def test_release_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        success = db.release_lease("T001", agent.agent_id)
        assert success is True

        active = db.get_active_lease("T001")
        assert active is None


class TestMessageOperations:
    """Test message database operations."""

    def test_send_message(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T001",
            text="Hello",
        )
        sent = db.send_message(msg)
        assert sent.message_id == msg.message_id

    def test_get_task_thread(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg1 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T001",
            text="First",
        )
        msg2 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T001",
            text="Second",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        thread = db.get_task_thread("T001")
        assert len(thread) == 2
        assert thread[0].text == "First"
        assert thread[1].text == "Second"

    def test_get_inbox(self, db):
        sender = Agent()
        receiver = Agent()
        db.register_agent(sender)
        db.register_agent(receiver)

        msg = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="Hello",
        )
        db.send_message(msg)

        inbox = db.get_inbox(receiver.agent_id)
        assert len(inbox) == 1
        assert inbox[0].text == "Hello"


class TestStats:
    """Test statistics."""

    def test_get_stats(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.utcnow() + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        stats = db.get_stats()
        assert stats["agents"] == 1
        assert stats["active_leases"] == 1
