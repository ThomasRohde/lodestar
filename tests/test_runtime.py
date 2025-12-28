"""Tests for runtime database operations."""

from __future__ import annotations

import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from lodestar.models.runtime import Agent, Lease, Message, MessageType
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

    def test_get_inbox_with_from_filter(self, db):
        sender1 = Agent()
        sender2 = Agent()
        receiver = Agent()
        db.register_agent(sender1)
        db.register_agent(sender2)
        db.register_agent(receiver)

        msg1 = Message(
            from_agent_id=sender1.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="From sender1",
        )
        msg2 = Message(
            from_agent_id=sender2.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="From sender2",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        # Filter by sender1
        inbox = db.get_inbox(receiver.agent_id, from_agent_id=sender1.agent_id)
        assert len(inbox) == 1
        assert inbox[0].text == "From sender1"

    def test_get_inbox_with_date_filters(self, db):
        import time

        sender = Agent()
        receiver = Agent()
        db.register_agent(sender)
        db.register_agent(receiver)

        # Send first message
        msg1 = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="First message",
        )
        db.send_message(msg1)

        # Wait a bit
        time.sleep(0.1)
        timestamp = datetime.now(UTC)
        time.sleep(0.1)

        # Send second message
        msg2 = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="Second message",
        )
        db.send_message(msg2)

        # Test since filter
        inbox = db.get_inbox(receiver.agent_id, since=timestamp)
        assert len(inbox) == 1
        assert inbox[0].text == "Second message"

        # Test until filter
        inbox = db.get_inbox(receiver.agent_id, until=timestamp)
        assert len(inbox) == 1
        assert inbox[0].text == "First message"

    def test_search_messages_by_keyword(self, db):
        agent = Agent()
        db.register_agent(agent)

        msg1 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T001",
            text="This is a bug report",
        )
        msg2 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T002",
            text="This is a feature request",
        )
        msg3 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T003",
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
            to_type=MessageType.TASK,
            to_id="T001",
            text="From agent1",
        )
        msg2 = Message(
            from_agent_id=agent2.agent_id,
            to_type=MessageType.TASK,
            to_id="T002",
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
            to_type=MessageType.TASK,
            to_id="T001",
            text="Old message",
        )
        db.send_message(msg1)

        time.sleep(0.1)
        since_time = datetime.now(UTC)
        time.sleep(0.1)

        msg2 = Message(
            from_agent_id=agent.agent_id,
            to_type=MessageType.TASK,
            to_id="T002",
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
            to_type=MessageType.TASK,
            to_id="T001",
            text="bug in feature A",
        )
        msg2 = Message(
            from_agent_id=agent2.agent_id,
            to_type=MessageType.TASK,
            to_id="T002",
            text="bug in feature B",
        )
        msg3 = Message(
            from_agent_id=agent1.agent_id,
            to_type=MessageType.TASK,
            to_id="T003",
            text="feature C completed",
        )
        db.send_message(msg1)
        db.send_message(msg2)
        db.send_message(msg3)

        # Search for messages from agent1 with keyword "bug"
        results = db.search_messages(keyword="bug", from_agent_id=agent1.agent_id)
        assert len(results) == 1
        assert results[0].text == "bug in feature A"

    def test_message_read_status_tracking(self, db):
        """Test that messages can be marked as read."""
        sender = Agent()
        receiver = Agent()
        db.register_agent(sender)
        db.register_agent(receiver)

        msg = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="Test message",
        )
        db.send_message(msg)

        # Get inbox without marking as read
        inbox = db.get_inbox(receiver.agent_id, mark_as_read=False)
        assert len(inbox) == 1
        assert inbox[0].read_at is None  # Should be unread

        # Get inbox and mark as read
        inbox = db.get_inbox(receiver.agent_id, mark_as_read=True)
        assert len(inbox) == 1
        assert inbox[0].read_at is not None  # Should be marked as read

        # Verify read status persists
        inbox = db.get_inbox(receiver.agent_id, mark_as_read=False)
        assert len(inbox) == 1
        assert inbox[0].read_at is not None  # Should still be read

    def test_unread_only_filter(self, db):
        """Test filtering for unread messages only."""
        sender = Agent()
        receiver = Agent()
        db.register_agent(sender)
        db.register_agent(receiver)

        # Send two messages
        msg1 = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="Message 1",
        )
        msg2 = Message(
            from_agent_id=sender.agent_id,
            to_type=MessageType.AGENT,
            to_id=receiver.agent_id,
            text="Message 2",
        )
        db.send_message(msg1)
        db.send_message(msg2)

        # Mark first message as read (msg2 since DESC order)
        inbox = db.get_inbox(receiver.agent_id, limit=1, mark_as_read=True)
        assert len(inbox) == 1

        # Get all messages
        all_messages = db.get_inbox(receiver.agent_id, mark_as_read=False)
        assert len(all_messages) == 2

        # Get only unread messages
        unread_messages = db.get_inbox(receiver.agent_id, unread_only=True, mark_as_read=False)
        assert len(unread_messages) == 1
        assert unread_messages[0].text == "Message 1"  # The one not read yet

    def test_mark_as_read_updates_multiple_messages(self, db):
        """Test that mark_as_read works with multiple messages."""
        sender = Agent()
        receiver = Agent()
        db.register_agent(sender)
        db.register_agent(receiver)

        # Send three messages
        for i in range(3):
            msg = Message(
                from_agent_id=sender.agent_id,
                to_type=MessageType.AGENT,
                to_id=receiver.agent_id,
                text=f"Message {i}",
            )
            db.send_message(msg)

        # Get all messages and mark as read
        inbox = db.get_inbox(receiver.agent_id, mark_as_read=True)
        assert len(inbox) == 3
        assert all(msg.read_at is not None for msg in inbox)

        # Verify no unread messages remain
        unread = db.get_inbox(receiver.agent_id, unread_only=True, mark_as_read=False)
        assert len(unread) == 0


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
