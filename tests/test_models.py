"""Tests for Pydantic models."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lodestar.models.envelope import Envelope, NextAction
from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.models.spec import Project, Spec, Task, TaskStatus


class TestEnvelope:
    """Test JSON envelope model."""

    def test_success_envelope(self):
        envelope = Envelope.success({"test": "data"})
        assert envelope.ok is True
        assert envelope.data == {"test": "data"}
        assert envelope.next == []
        assert envelope.warnings == []

    def test_success_with_next_actions(self):
        next_action = NextAction(intent="test", cmd="test cmd")
        envelope = Envelope.success({"data": 1}, next_actions=[next_action])
        assert len(envelope.next) == 1
        assert envelope.next[0].intent == "test"

    def test_error_envelope(self):
        envelope = Envelope.error("Something went wrong")
        assert envelope.ok is False
        assert envelope.data["error"] == "Something went wrong"

    def test_model_dump(self):
        envelope = Envelope.success({"key": "value"})
        data = envelope.model_dump()
        assert data["ok"] is True
        assert data["data"]["key"] == "value"


class TestTask:
    """Test Task model."""

    def test_task_creation(self):
        task = Task(id="T001", title="Test Task")
        assert task.id == "T001"
        assert task.title == "Test Task"
        assert task.status == TaskStatus.TODO
        assert task.priority == 100

    def test_task_is_claimable(self):
        task = Task(id="T001", title="Test", status=TaskStatus.READY)
        assert task.is_claimable(set())

    def test_task_not_claimable_wrong_status(self):
        task = Task(id="T001", title="Test", status=TaskStatus.TODO)
        assert not task.is_claimable(set())

    def test_task_not_claimable_missing_deps(self):
        task = Task(id="T002", title="Test", status=TaskStatus.READY, depends_on=["T001"])
        assert not task.is_claimable(set())
        assert task.is_claimable({"T001"})

    def test_task_id_validation(self):
        with pytest.raises(ValueError):
            Task(id="", title="Test")


class TestSpec:
    """Test Spec model."""

    def test_spec_creation(self):
        spec = Spec(project=Project(name="test"))
        assert spec.project.name == "test"
        assert spec.tasks == {}

    def test_get_verified_tasks(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(id="T001", title="Done", status=TaskStatus.VERIFIED),
                "T002": Task(id="T002", title="Ready", status=TaskStatus.READY),
            },
        )
        verified = spec.get_verified_tasks()
        assert verified == {"T001"}

    def test_get_claimable_tasks(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(id="T001", title="Verified", status=TaskStatus.VERIFIED),
                "T002": Task(
                    id="T002", title="Ready", status=TaskStatus.READY, depends_on=["T001"]
                ),
                "T003": Task(id="T003", title="Ready no deps", status=TaskStatus.READY),
            },
        )
        claimable = spec.get_claimable_tasks()
        ids = [t.id for t in claimable]
        assert "T002" in ids
        assert "T003" in ids
        assert "T001" not in ids  # Already verified


class TestAgent:
    """Test Agent model."""

    def test_agent_creation(self):
        agent = Agent()
        assert agent.agent_id.startswith("A")
        assert len(agent.agent_id) == 9  # A + 8 hex chars

    def test_agent_with_name(self):
        agent = Agent(display_name="TestBot")
        assert agent.display_name == "TestBot"


class TestLease:
    """Test Lease model."""

    def test_lease_creation(self):
        expires = datetime.now(UTC) + timedelta(minutes=15)
        lease = Lease(task_id="T001", agent_id="A12345678", expires_at=expires)
        assert lease.task_id == "T001"
        assert not lease.is_expired()
        assert lease.is_active()

    def test_lease_expired(self):
        expires = datetime.now(UTC) - timedelta(minutes=1)
        lease = Lease(task_id="T001", agent_id="A12345678", expires_at=expires)
        assert lease.is_expired()
        assert not lease.is_active()


class TestMessage:
    """Test Message model."""

    def test_message_creation(self):
        msg = Message(
            from_agent_id="A12345678",
            to_type=MessageType.TASK,
            to_id="T001",
            text="Hello",
        )
        assert msg.message_id.startswith("M")
        assert msg.text == "Hello"
