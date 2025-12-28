"""Tests for MCP tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lodestar.mcp.server import LodestarContext
from lodestar.mcp.tools.message import message_list
from lodestar.mcp.tools.task import task_get, task_list
from lodestar.models.runtime import Agent, Lease, Message, MessageType
from lodestar.models.spec import PrdContext, PrdRef, Task, TaskStatus
from lodestar.spec.loader import save_spec
from lodestar.util.prd import compute_prd_hash


@pytest.fixture
def mcp_context(tmp_path):
    """Create a test MCP context with sample data."""
    # Create repository structure
    lodestar_dir = tmp_path / ".lodestar"
    lodestar_dir.mkdir()

    # Create sample spec
    from lodestar.models.spec import Project, Spec

    spec = Spec(
        project=Project(name="test-project"),
        tasks={
            "T001": Task(
                id="T001",
                title="First task",
                description="Ready task",
                status=TaskStatus.READY,
                priority=1,
                labels=["feature"],
            ),
            "T002": Task(
                id="T002",
                title="Second task",
                description="Done task",
                status=TaskStatus.DONE,
                priority=2,
                labels=["bug"],
            ),
            "T003": Task(
                id="T003",
                title="Third task",
                description="Verified task",
                status=TaskStatus.VERIFIED,
                priority=3,
                labels=["feature"],
            ),
            "T004": Task(
                id="T004",
                title="Fourth task",
                description="Another ready task",
                status=TaskStatus.READY,
                priority=4,
                labels=["refactor"],
            ),
            "T005": Task(
                id="T005",
                title="Deleted task",
                description="Deleted task",
                status=TaskStatus.DELETED,
                priority=5,
                labels=["feature"],
            ),
        },
    )

    save_spec(spec, tmp_path)

    # Create context
    context = LodestarContext(tmp_path)

    # Register an agent and create a lease for T001
    agent = Agent(display_name="Test Agent", role="tester", capabilities=["testing"])
    context.db.register_agent(agent)

    lease = Lease(
        task_id="T001",
        agent_id=agent.agent_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=15),
    )
    context.db.create_lease(lease)

    return context


class TestTaskList:
    """Tests for the task.list MCP tool."""

    def test_list_all_tasks(self, mcp_context):
        """Test listing all tasks (excludes deleted by default)."""
        result = task_list(mcp_context)

        assert result.isError is None or result.isError is False
        assert result.structuredContent is not None

        data = result.structuredContent
        assert data["count"] == 4  # T001-T004 (excludes T005 deleted)
        assert data["total"] == 5  # Total includes deleted
        assert len(data["items"]) == 4

        # Verify tasks are sorted by priority
        assert data["items"][0]["id"] == "T001"
        assert data["items"][1]["id"] == "T002"
        assert data["items"][2]["id"] == "T003"
        assert data["items"][3]["id"] == "T004"

    def test_filter_by_status_ready(self, mcp_context):
        """Test filtering tasks by ready status."""
        result = task_list(mcp_context, status="ready")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 2  # T001 and T004
        assert all(item["status"] == "ready" for item in data["items"])
        assert {item["id"] for item in data["items"]} == {"T001", "T004"}

    def test_filter_by_status_done(self, mcp_context):
        """Test filtering tasks by done status."""
        result = task_list(mcp_context, status="done")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 1  # T002 only
        assert data["items"][0]["id"] == "T002"
        assert data["items"][0]["status"] == "done"

    def test_filter_by_status_verified(self, mcp_context):
        """Test filtering tasks by verified status."""
        result = task_list(mcp_context, status="verified")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 1  # T003 only
        assert data["items"][0]["id"] == "T003"
        assert data["items"][0]["status"] == "verified"

    def test_filter_by_status_deleted(self, mcp_context):
        """Test filtering tasks by deleted status."""
        result = task_list(mcp_context, status="deleted")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 1  # T005 only
        assert data["items"][0]["id"] == "T005"
        assert data["items"][0]["status"] == "deleted"

    def test_filter_by_status_all(self, mcp_context):
        """Test showing all tasks including deleted."""
        result = task_list(mcp_context, status="all")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # "all" shows all tasks except deleted
        assert data["count"] == 4  # T001-T004
        assert data["total"] == 5

    def test_filter_by_label_feature(self, mcp_context):
        """Test filtering tasks by label."""
        result = task_list(mcp_context, label="feature")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # T001, T003 have "feature" label (T005 is deleted and excluded)
        assert data["count"] == 2
        assert {item["id"] for item in data["items"]} == {"T001", "T003"}

    def test_filter_by_label_bug(self, mcp_context):
        """Test filtering by bug label."""
        result = task_list(mcp_context, label="bug")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 1
        assert data["items"][0]["id"] == "T002"

    def test_combined_filters(self, mcp_context):
        """Test combining status and label filters."""
        result = task_list(mcp_context, status="ready", label="feature")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 1  # Only T001
        assert data["items"][0]["id"] == "T001"

    def test_limit_results(self, mcp_context):
        """Test limiting number of results."""
        result = task_list(mcp_context, limit=2)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 2
        assert len(data["items"]) == 2
        # Should get first 2 by priority
        assert data["items"][0]["id"] == "T001"
        assert data["items"][1]["id"] == "T002"

    def test_limit_exceeds_max(self, mcp_context):
        """Test that limit is clamped to maximum of 200."""
        result = task_list(mcp_context, limit=500)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should get all tasks (4 < 200 max)
        assert data["count"] == 4

    def test_pagination_cursor(self, mcp_context):
        """Test pagination with cursor."""
        # Get first page with limit 2
        result1 = task_list(mcp_context, limit=2)
        data1 = result1.structuredContent

        assert data1["count"] == 2
        assert data1["items"][0]["id"] == "T001"
        assert data1["items"][1]["id"] == "T002"

        # Should have nextCursor since there are more results
        next_cursor = result1._meta["nextCursor"]
        assert next_cursor == "T002"

        # Get second page using cursor
        result2 = task_list(mcp_context, limit=2, cursor=next_cursor)
        data2 = result2.structuredContent

        # Should get next 2 tasks
        assert data2["count"] == 2
        assert data2["items"][0]["id"] == "T003"
        assert data2["items"][1]["id"] == "T004"

    def test_task_summary_includes_lease_info(self, mcp_context):
        """Test that task summaries include lease information."""
        result = task_list(mcp_context, status="ready")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Find T001 which has a lease
        t001 = next(item for item in data["items"] if item["id"] == "T001")

        assert t001["claimedByAgentId"] is not None
        assert t001["leaseExpiresAt"] is not None

        # Find T004 which doesn't have a lease
        t004 = next(item for item in data["items"] if item["id"] == "T004")

        assert t004["claimedByAgentId"] is None
        assert t004["leaseExpiresAt"] is None

    def test_task_summary_structure(self, mcp_context):
        """Test that task summaries have correct structure."""
        result = task_list(mcp_context, limit=1)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        task = data["items"][0]

        # Verify all required fields are present
        assert "id" in task
        assert "title" in task
        assert "status" in task
        assert "priority" in task
        assert "labels" in task
        assert "dependencies" in task
        assert "claimedByAgentId" in task
        assert "leaseExpiresAt" in task
        assert "updatedAt" in task

        # Verify types
        assert isinstance(task["id"], str)
        assert isinstance(task["title"], str)
        assert isinstance(task["status"], str)
        assert isinstance(task["priority"], int)
        assert isinstance(task["labels"], list)
        assert isinstance(task["dependencies"], list)
        assert isinstance(task["updatedAt"], str)

    def test_invalid_status_raises_error(self, mcp_context):
        """Test that invalid status value raises validation error."""
        from lodestar.mcp.validation import ValidationError

        with pytest.raises(ValidationError) as exc_info:
            task_list(mcp_context, status="invalid_status")

        assert "Invalid status" in str(exc_info.value)

    def test_empty_results(self, mcp_context):
        """Test handling of empty results."""
        result = task_list(mcp_context, label="nonexistent")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 0
        assert len(data["items"]) == 0
        assert data["total"] == 5  # Total in spec unchanged

    def test_metadata_includes_filters(self, mcp_context):
        """Test that metadata includes applied filters."""
        result = task_list(mcp_context, status="ready", label="feature")

        assert result._meta is not None
        assert result._meta["filters"]["status"] == "ready"
        assert result._meta["filters"]["label"] == "feature"

    def test_next_cursor_none_when_no_more_results(self, mcp_context):
        """Test that nextCursor is None when all results returned."""
        result = task_list(mcp_context, limit=100)

        assert result._meta["nextCursor"] is None


class TestTaskGet:
    """Tests for the task.get MCP tool."""

    def test_get_basic_task(self, mcp_context):
        """Test getting basic task information."""
        result = task_get(mcp_context, task_id="T001")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Verify basic task fields
        assert data["id"] == "T001"
        assert data["title"] == "First task"
        assert data["description"] == "Ready task"
        assert data["status"] == "ready"
        assert data["priority"] == 1
        assert data["labels"] == ["feature"]

    def test_get_task_with_dependencies(self, mcp_context):
        """Test task with dependency information."""
        # Add a task that depends on T001

        spec = mcp_context.spec
        spec.tasks["T006"] = Task(
            id="T006",
            title="Depends on T001",
            status=TaskStatus.READY,
            depends_on=["T001"],
        )
        save_spec(spec, mcp_context.repo_root)
        mcp_context.reload_spec()

        result = task_get(mcp_context, task_id="T001")
        data = result.structuredContent

        # Verify dependency information
        assert "dependencies" in data
        assert data["dependencies"]["dependsOn"] == []
        assert "T006" in data["dependencies"]["dependents"]

    def test_get_task_with_lease(self, mcp_context):
        """Test task with active lease."""
        result = task_get(mcp_context, task_id="T001")
        data = result.structuredContent

        # T001 has a lease in the fixture
        assert data["runtime"]["claimed"] is True
        assert data["runtime"]["claimedBy"] is not None
        assert "agentId" in data["runtime"]["claimedBy"]
        assert "leaseId" in data["runtime"]["claimedBy"]
        assert "expiresAt" in data["runtime"]["claimedBy"]

    def test_get_task_without_lease(self, mcp_context):
        """Test task without active lease."""
        result = task_get(mcp_context, task_id="T002")
        data = result.structuredContent

        # T002 does not have a lease
        assert data["runtime"]["claimed"] is False
        assert data["runtime"]["claimedBy"] is None

    def test_get_task_claimability(self, mcp_context):
        """Test isClaimable field."""
        # T001 is ready with no dependencies - should be claimable
        result = task_get(mcp_context, task_id="T001")
        data = result.structuredContent
        assert data["dependencies"]["isClaimable"] is True

        # Create a task that depends on a non-verified task

        spec = mcp_context.spec
        spec.tasks["T007"] = Task(
            id="T007",
            title="Depends on ready task",
            status=TaskStatus.READY,
            depends_on=["T001"],  # T001 is ready, not verified
        )
        save_spec(spec, mcp_context.repo_root)
        mcp_context.reload_spec()

        result = task_get(mcp_context, task_id="T007")
        data = result.structuredContent
        # Should not be claimable because T001 is not verified
        assert data["dependencies"]["isClaimable"] is False

    def test_get_task_with_prd(self, tmp_path):
        """Test task with PRD context."""
        # Create a PRD file
        prd_file = tmp_path / "PRD.md"
        prd_content = """# Product Requirements

## Task Details
This is a test section.
"""
        prd_file.write_text(prd_content)

        # Create spec with PRD context
        from lodestar.models.spec import Project, Spec

        prd_hash = compute_prd_hash(prd_file)

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T100": Task(
                    id="T100",
                    title="Task with PRD",
                    status=TaskStatus.READY,
                    prd=PrdContext(
                        source="PRD.md",
                        refs=[PrdRef(anchor="task-details")],
                        excerpt="This is a test excerpt",
                        prd_hash=prd_hash,
                    ),
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T100")
        data = result.structuredContent

        # Verify PRD context
        assert data["prd"] is not None
        assert data["prd"]["source"] == "PRD.md"
        assert len(data["prd"]["refs"]) == 1
        assert data["prd"]["refs"][0]["anchor"] == "task-details"
        assert data["prd"]["excerpt"] == "This is a test excerpt"
        assert data["prd"]["prdHash"] == prd_hash

        # Should have no warnings since PRD hasn't drifted
        assert len(data["warnings"]) == 0

    def test_get_task_prd_drift_detection(self, tmp_path):
        """Test PRD drift detection."""
        # Create a PRD file
        prd_file = tmp_path / "PRD.md"
        prd_file.write_text("Original content")

        original_hash = compute_prd_hash(prd_file)

        # Create spec with PRD context
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T101": Task(
                    id="T101",
                    title="Task with drifting PRD",
                    status=TaskStatus.READY,
                    prd=PrdContext(
                        source="PRD.md",
                        refs=[],
                        prd_hash=original_hash,
                    ),
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        # Modify the PRD to cause drift
        prd_file.write_text("Modified content - drift!")

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T101")
        data = result.structuredContent

        # Should have a drift warning
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["type"] == "PRD_DRIFT_DETECTED"
        assert data["warnings"][0]["severity"] == "info"

    def test_get_task_missing_prd_source(self, tmp_path):
        """Test warning when PRD source file is missing."""
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T102": Task(
                    id="T102",
                    title="Task with missing PRD",
                    status=TaskStatus.READY,
                    prd=PrdContext(
                        source="nonexistent.md",
                        refs=[],
                        prd_hash="fakehash",
                    ),
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T102")
        data = result.structuredContent

        # Should have a missing source warning
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["type"] == "MISSING_PRD_SOURCE"
        assert data["warnings"][0]["severity"] == "warning"

    def test_get_task_missing_dependencies(self, tmp_path):
        """Test warning when task has missing dependencies."""
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T103": Task(
                    id="T103",
                    title="Task with missing dep",
                    status=TaskStatus.READY,
                    depends_on=["NONEXISTENT"],
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T103")
        data = result.structuredContent

        # Should have a missing dependencies warning
        assert len(data["warnings"]) == 1
        assert data["warnings"][0]["type"] == "MISSING_DEPENDENCIES"
        assert data["warnings"][0]["severity"] == "error"
        assert "NONEXISTENT" in data["warnings"][0]["message"]

    def test_get_task_not_found(self, mcp_context):
        """Test error when task doesn't exist."""
        result = task_get(mcp_context, task_id="NONEXISTENT")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "TASK_NOT_FOUND"

    def test_get_task_invalid_id(self, mcp_context):
        """Test error with invalid task ID."""
        result = task_get(mcp_context, task_id="")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_TASK_ID"

    def test_get_task_structure(self, mcp_context):
        """Test that returned task has complete structure."""
        result = task_get(mcp_context, task_id="T001")
        data = result.structuredContent

        # Verify all required top-level fields
        required_fields = [
            "id",
            "title",
            "description",
            "acceptanceCriteria",
            "status",
            "priority",
            "labels",
            "locks",
            "createdAt",
            "updatedAt",
            "dependencies",
            "prd",
            "runtime",
            "warnings",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify dependencies structure
        assert "dependsOn" in data["dependencies"]
        assert "dependents" in data["dependencies"]
        assert "isClaimable" in data["dependencies"]

        # Verify runtime structure
        assert "claimed" in data["runtime"]
        assert "claimedBy" in data["runtime"]

    def test_get_task_timestamps(self, mcp_context):
        """Test that timestamps are ISO formatted."""
        result = task_get(mcp_context, task_id="T001")
        data = result.structuredContent

        # Verify timestamps are strings (ISO format)
        assert isinstance(data["createdAt"], str)
        assert isinstance(data["updatedAt"], str)

        # Should be parseable as datetime
        from datetime import datetime

        datetime.fromisoformat(data["createdAt"])
        datetime.fromisoformat(data["updatedAt"])

    def test_get_task_acceptance_criteria(self, tmp_path):
        """Test task with acceptance criteria."""
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T104": Task(
                    id="T104",
                    title="Task with acceptance criteria",
                    status=TaskStatus.READY,
                    acceptance_criteria=[
                        "Criterion 1",
                        "Criterion 2",
                        "Criterion 3",
                    ],
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T104")
        data = result.structuredContent

        assert len(data["acceptanceCriteria"]) == 3
        assert data["acceptanceCriteria"][0] == "Criterion 1"

    def test_get_task_locks(self, tmp_path):
        """Test task with file locks."""
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T105": Task(
                    id="T105",
                    title="Task with locks",
                    status=TaskStatus.READY,
                    locks=["src/**/*.py", "tests/test_*.py"],
                ),
            },
        )

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()
        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        result = task_get(context, task_id="T105")
        data = result.structuredContent

        assert len(data["locks"]) == 2
        assert "src/**/*.py" in data["locks"]


class TestMessageList:
    """Tests for the message.list MCP tool."""

    @pytest.fixture
    def message_context(self, tmp_path):
        """Create a test context with sample messages."""
        # Create repository structure
        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        # Create minimal spec
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={},
        )
        save_spec(spec, tmp_path)

        # Create context
        context = LodestarContext(tmp_path)

        # Register two agents
        agent1 = Agent(agent_id="A001", display_name="Agent 1")
        agent2 = Agent(agent_id="A002", display_name="Agent 2")
        context.db.register_agent(agent1)
        context.db.register_agent(agent2)

        # Send messages to agent1
        msg1 = Message(
            from_agent_id="A002",
            to_type=MessageType.AGENT,
            to_id="A001",
            text="First message",
        )
        msg2 = Message(
            from_agent_id="A002",
            to_type=MessageType.AGENT,
            to_id="A001",
            text="Second message",
        )
        msg3 = Message(
            from_agent_id="A002",
            to_type=MessageType.AGENT,
            to_id="A001",
            text="Third message",
        )
        context.db.send_message(msg1)
        context.db.send_message(msg2)
        context.db.send_message(msg3)

        # Mark msg1 as read
        context.db._messages.get_inbox(agent_id="A001", limit=1, mark_as_read=True)

        return context

    def test_list_unread_messages(self, message_context):
        """Test listing unread messages (default behavior)."""
        result = message_list(message_context, agent_id="A001")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return 2 unread messages (msg2 and msg3)
        assert data["count"] == 2
        assert len(data["messages"]) == 2

        # Verify message structure
        msg = data["messages"][0]
        assert "id" in msg
        assert "createdAt" in msg
        assert "from" in msg
        assert "to" in msg
        assert "body" in msg
        assert msg["from"] == "A002"
        assert msg["to"] == "A001"

    def test_list_all_messages(self, message_context):
        """Test listing all messages including read ones."""
        result = message_list(message_context, agent_id="A001", unread_only=False)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return all 3 messages
        assert data["count"] == 3
        assert len(data["messages"]) == 3

    def test_list_with_limit(self, message_context):
        """Test limiting number of messages returned."""
        result = message_list(message_context, agent_id="A001", unread_only=False, limit=2)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 2
        assert len(data["messages"]) == 2

    def test_pagination_with_cursor(self, message_context):
        """Test cursor-based pagination."""
        # Get first page with limit 1
        result1 = message_list(message_context, agent_id="A001", unread_only=False, limit=1)
        data1 = result1.structuredContent

        assert data1["count"] == 1
        assert "nextCursor" in data1
        first_cursor = data1["nextCursor"]

        # Get second page using cursor
        result2 = message_list(
            message_context, agent_id="A001", unread_only=False, limit=1, since_id=first_cursor
        )
        data2 = result2.structuredContent

        assert data2["count"] == 1
        # Message IDs should be different
        assert data1["messages"][0]["id"] != data2["messages"][0]["id"]

    def test_no_cursor_when_all_returned(self, message_context):
        """Test that nextCursor is not present when all messages returned."""
        result = message_list(message_context, agent_id="A001", unread_only=False, limit=100)
        data = result.structuredContent

        assert "nextCursor" not in data or data["nextCursor"] is None

    def test_empty_inbox(self, message_context):
        """Test listing messages for agent with no messages."""
        result = message_list(message_context, agent_id="A002")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        assert data["count"] == 0
        assert len(data["messages"]) == 0

    def test_invalid_agent_id_empty(self, message_context):
        """Test error with empty agent_id."""
        result = message_list(message_context, agent_id="")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_AGENT_ID"

    def test_invalid_limit_too_small(self, message_context):
        """Test error with limit less than 1."""
        result = message_list(message_context, agent_id="A001", limit=0)

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_LIMIT"

    def test_invalid_limit_too_large(self, message_context):
        """Test error with limit exceeding maximum."""
        result = message_list(message_context, agent_id="A001", limit=300)

        assert result.isError is True
        assert result.structuredContent["error_code"] == "LIMIT_TOO_LARGE"

    def test_message_with_metadata(self, message_context):
        """Test that message metadata is properly extracted."""
        # Send a message with subject and severity in meta
        msg = Message(
            from_agent_id="A002",
            to_type=MessageType.AGENT,
            to_id="A001",
            text="Message with metadata",
            meta={"subject": "Test Subject", "severity": "warning"},
        )
        message_context.db.send_message(msg)

        result = message_list(message_context, agent_id="A001", unread_only=True)
        data = result.structuredContent

        # Find the message with metadata
        msg_data = next((m for m in data["messages"] if m["body"] == "Message with metadata"), None)
        assert msg_data is not None
        assert msg_data.get("subject") == "Test Subject"
        assert msg_data.get("severity") == "warning"

    def test_message_read_status(self, message_context):
        """Test that read status is properly included."""
        result = message_list(message_context, agent_id="A001", unread_only=False)
        data = result.structuredContent

        # Check that messages have correct read status
        # Note: messages are returned in descending order (newest first),
        # and the first message (newest) was marked as read
        read_count = sum(1 for msg in data["messages"] if "readAt" in msg)
        unread_count = sum(1 for msg in data["messages"] if "readAt" not in msg)

        # Should have 1 read message and 2 unread messages
        assert read_count == 1
        assert unread_count == 2
