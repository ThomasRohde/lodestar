"""Tests for runtime database operations."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lodestar.models.runtime import Agent, Lease, Message
from lodestar.runtime.database import RuntimeDatabase


@pytest.fixture
def db():
    """Create a temporary runtime database."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "runtime.sqlite"
        database = RuntimeDatabase(db_path)
        yield database
        # Properly dispose of the engine to release file locks on Windows
        database.dispose()


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

    def test_register_agent_with_role_and_capabilities(self, db):
        """Test registering an agent with role and capabilities metadata."""
        agent = Agent(
            display_name="CodeReviewer",
            role="code-review",
            capabilities=["python", "testing", "documentation"],
        )
        registered = db.register_agent(agent)
        assert registered.role == "code-review"
        assert registered.capabilities == ["python", "testing", "documentation"]

        # Verify it persists
        retrieved = db.get_agent(agent.agent_id)
        assert retrieved.role == "code-review"
        assert retrieved.capabilities == ["python", "testing", "documentation"]

    def test_find_agents_by_capability(self, db):
        """Test finding agents by capability."""
        # Register agents with different capabilities
        agent1 = Agent(
            display_name="PythonDev",
            capabilities=["python", "testing"],
        )
        agent2 = Agent(
            display_name="JSDev",
            capabilities=["javascript", "testing"],
        )
        agent3 = Agent(
            display_name="DocWriter",
            capabilities=["documentation"],
        )
        db.register_agent(agent1)
        db.register_agent(agent2)
        db.register_agent(agent3)

        # Find by python capability
        python_agents = db.find_agents_by_capability("python")
        assert len(python_agents) == 1
        assert python_agents[0].display_name == "PythonDev"

        # Find by testing capability
        testing_agents = db.find_agents_by_capability("testing")
        assert len(testing_agents) == 2

        # Find by non-existent capability
        rust_agents = db.find_agents_by_capability("rust")
        assert len(rust_agents) == 0

    def test_find_agents_by_role(self, db):
        """Test finding agents by role."""
        # Register agents with different roles
        agent1 = Agent(
            display_name="Reviewer1",
            role="code-review",
        )
        agent2 = Agent(
            display_name="Reviewer2",
            role="code-review",
        )
        agent3 = Agent(
            display_name="Tester",
            role="testing",
        )
        db.register_agent(agent1)
        db.register_agent(agent2)
        db.register_agent(agent3)

        # Find by code-review role
        reviewers = db.find_agents_by_role("code-review")
        assert len(reviewers) == 2

        # Find by testing role
        testers = db.find_agents_by_role("testing")
        assert len(testers) == 1
        assert testers[0].display_name == "Tester"

        # Find by non-existent role
        designers = db.find_agents_by_role("design")
        assert len(designers) == 0

    def test_mark_agent_offline(self, db):
        """Test marking an agent as offline."""
        from datetime import timedelta

        from lodestar.models.runtime import DEFAULT_OFFLINE_THRESHOLD_MINUTES, AgentStatus

        # Register an agent
        agent = Agent(display_name="TestBot")
        db.register_agent(agent)

        # Verify agent is initially active (or will be based on recent registration)
        retrieved = db.get_agent(agent.agent_id)
        assert retrieved is not None

        # Mark agent offline
        success = db.mark_agent_offline(agent.agent_id, reason="Testing offline status")
        assert success is True

        # Retrieve agent and verify last_seen_at is beyond offline threshold
        offline_agent = db.get_agent(agent.agent_id)
        assert offline_agent is not None

        # Check that last_seen_at is old enough to trigger offline status
        from datetime import UTC, datetime

        time_since_seen = datetime.now(UTC) - offline_agent.last_seen_at
        assert time_since_seen > timedelta(minutes=DEFAULT_OFFLINE_THRESHOLD_MINUTES)

        # Verify status is offline
        assert offline_agent.get_status() == AgentStatus.OFFLINE

    def test_mark_nonexistent_agent_offline(self, db):
        """Test marking a non-existent agent offline returns False."""
        success = db.mark_agent_offline("nonexistent", reason="Testing")
        assert success is False


class TestLeaseOperations:
    """Test lease database operations."""

    def test_create_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        created = db.create_lease(lease)

        assert created is not None
        assert created.task_id == "T001"

    def test_create_duplicate_lease_fails(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease1 = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease1)

        lease2 = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        result = db.create_lease(lease2)
        assert result is None  # Should fail

    def test_get_active_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        active = db.get_active_lease("T001")
        assert active is not None
        assert active.agent_id == agent.agent_id

    def test_expired_lease_not_active(self, db):
        agent = Agent()
        db.register_agent(agent)

        # Create an already expired lease
        expires = datetime.now(UTC) - timedelta(minutes=1)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        # Directly insert the lease bypassing the check using SQLAlchemy session

        from lodestar.runtime.converters import lease_to_orm
        from lodestar.runtime.engine import get_session

        with get_session(db._session_factory) as session:
            orm_lease = lease_to_orm(lease)
            session.add(orm_lease)

        active = db.get_active_lease("T001")
        assert active is None  # Expired lease should not be returned

    def test_renew_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        created = db.create_lease(lease)

        new_expires = datetime.now(UTC) + timedelta(minutes=30)
        success = db.renew_lease(created.lease_id, new_expires, agent.agent_id)
        assert success is True

        updated = db.get_active_lease("T001")
        assert updated.expires_at > expires

    def test_release_lease(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        success = db.release_lease("T001", agent.agent_id)
        assert success is True

        active = db.get_active_lease("T001")
        assert active is None

    def test_get_all_active_leases(self, db):
        """Test getting all active leases."""
        agent = Agent()
        db.register_agent(agent)

        # Create multiple active leases
        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease1 = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        lease2 = Lease(task_id="T002", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease1)
        db.create_lease(lease2)

        active = db.get_all_active_leases()
        assert len(active) == 2
        task_ids = {lease.task_id for lease in active}
        assert task_ids == {"T001", "T002"}

    def test_get_all_active_leases_excludes_expired(self, db):
        """Test that expired leases are not returned."""
        agent = Agent()
        db.register_agent(agent)

        # Create one active and one expired lease
        active_expires = datetime.now(UTC) + timedelta(minutes=15)
        expired_expires = datetime.now(UTC) - timedelta(minutes=1)

        active_lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=active_expires)
        db.create_lease(active_lease)

        # Directly insert expired lease bypassing check
        from lodestar.runtime.converters import lease_to_orm
        from lodestar.runtime.engine import get_session

        expired_lease = Lease(task_id="T002", agent_id=agent.agent_id, expires_at=expired_expires)
        with get_session(db._session_factory) as session:
            session.add(lease_to_orm(expired_lease))

        active = db.get_all_active_leases()
        assert len(active) == 1
        assert active[0].task_id == "T001"

    def test_get_all_active_leases_empty(self, db):
        """Test that empty list is returned when no leases exist."""
        active = db.get_all_active_leases()
        assert active == []


class TestMessageOperations:
    """Test message database operations."""

    def test_send_message(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg = Message(
            from_agent_id=agent.agent_id,
            task_id="T001",
            text="Hello",
        )
        sent = db.send_message(msg)
        assert sent.message_id == msg.message_id

    def test_get_task_thread(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg1 = Message(
            from_agent_id=agent.agent_id,
            task_id="T001",
            text="First",
        )
        msg2 = Message(
            from_agent_id=agent.agent_id,
            task_id="T001",
            text="Second",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        thread = db.get_task_thread("T001")
        assert len(thread) == 2
        assert thread[0].text == "First"
        assert thread[1].text == "Second"

    def test_search_messages_by_keyword(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg1 = Message(
            from_agent_id=agent.agent_id,
            task_id="T001",
            text="This is a bug report",
        )
        msg2 = Message(
            from_agent_id=agent.agent_id,
            task_id="T002",
            text="This is a feature request",
        )
        msg3 = Message(
            from_agent_id=agent.agent_id,
            task_id="T003",
            text="Another bug was found",
        )
        db.send_message(msg1)
        db.send_message(msg2)
        db.send_message(msg3)

        # Search for "bug"
        results = db.search_messages(keyword="bug")
        assert len(results) == 2
        assert all("bug" in msg.text.lower() for msg in results)

    def test_search_messages_by_from_agent(self, db):
        agent1 = Agent()
        agent2 = Agent()
        db.register_agent(agent1)
        db.register_agent(agent2)

        msg1 = Message(
            from_agent_id=agent1.agent_id,
            task_id="T001",
            text="From agent1",
        )
        msg2 = Message(
            from_agent_id=agent2.agent_id,
            task_id="T002",
            text="From agent2",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        # Search by agent1
        results = db.search_messages(from_agent_id=agent1.agent_id)
        assert len(results) == 1
        assert results[0].from_agent_id == agent1.agent_id

    def test_search_messages_with_date_range(self, db):
        import time

        agent = Agent()
        db.register_agent(agent)

        msg1 = Message(
            from_agent_id=agent.agent_id,
            task_id="T001",
            text="Old message",
        )
        db.send_message(msg1)

        time.sleep(0.1)
        since_time = datetime.now(UTC)
        time.sleep(0.1)

        msg2 = Message(
            from_agent_id=agent.agent_id,
            task_id="T002",
            text="Recent message",
        )
        db.send_message(msg2)

        time.sleep(0.1)
        until_time = datetime.now(UTC)

        # Search with since
        results = db.search_messages(since=since_time)
        assert len(results) == 1
        assert results[0].text == "Recent message"

        # Search with until
        results = db.search_messages(until=until_time)
        assert len(results) == 2

    def test_search_messages_combined_filters(self, db):
        agent1 = Agent()
        agent2 = Agent()
        db.register_agent(agent1)
        db.register_agent(agent2)

        msg1 = Message(
            from_agent_id=agent1.agent_id,
            task_id="T001",
            text="bug in feature A",
        )
        msg2 = Message(
            from_agent_id=agent2.agent_id,
            task_id="T002",
            text="bug in feature B",
        )
        msg3 = Message(
            from_agent_id=agent1.agent_id,
            task_id="T003",
            text="feature C completed",
        )
        db.send_message(msg1)
        db.send_message(msg2)
        db.send_message(msg3)

        # Search for messages from agent1 with keyword "bug"
        results = db.search_messages(keyword="bug", from_agent_id=agent1.agent_id)
        assert len(results) == 1
        assert results[0].text == "bug in feature A"

    def test_mark_task_messages_read(self, db):
        """Test marking task messages as read by an agent."""
        agent1 = Agent()
        agent2 = Agent()
        db.register_agent(agent1)
        db.register_agent(agent2)

        # Send messages to task
        msg1 = Message(
            from_agent_id=agent1.agent_id,
            task_id="T001",
            text="First message",
        )
        msg2 = Message(
            from_agent_id=agent1.agent_id,
            task_id="T001",
            text="Second message",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        # Mark messages as read by agent2
        count = db.mark_task_messages_read("T001", agent2.agent_id)
        assert count == 2

        # Verify messages are marked as read
        thread = db.get_task_thread("T001")
        assert len(thread) == 2
        for msg in thread:
            assert agent2.agent_id in msg.read_by

    def test_get_task_unread_messages(self, db):
        """Test getting unread messages for a task from agent perspective."""
        agent1 = Agent()
        agent2 = Agent()
        db.register_agent(agent1)
        db.register_agent(agent2)

        # Send three messages to task
        for i in range(3):
            msg = Message(
                from_agent_id=agent1.agent_id,
                task_id="T001",
                text=f"Message {i}",
            )
            db.send_message(msg)

        # Get unread messages for agent2
        unread = db.get_task_unread_messages("T001", agent2.agent_id)
        assert len(unread) == 3

        # Mark first message as read
        thread = db.get_task_thread("T001", limit=1)
        db.mark_task_messages_read("T001", agent2.agent_id, [thread[0].message_id])

        # Should now have 2 unread
        unread = db.get_task_unread_messages("T001", agent2.agent_id)
        assert len(unread) == 2


class TestStats:
    """Test statistics."""

    def test_get_stats(self, db):
        agent = Agent()
        db.register_agent(agent)

        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id=agent.agent_id, expires_at=expires)
        db.create_lease(lease)

        stats = db.get_stats()
        assert stats["agents"] == 1
        assert stats["active_leases"] == 1
