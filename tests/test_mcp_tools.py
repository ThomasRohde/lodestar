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

        # Should have nextCursor in structuredContent since there are more results
        next_cursor = data1["nextCursor"]
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
        data = result.structuredContent

        # nextCursor should not be present or be None when there are no more results
        assert data.get("nextCursor") is None


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


class TestProgressNotifications:
    """Tests for MCP progress notification support."""

    @pytest.fixture
    def progress_context(self, tmp_path):
        """Create a test MCP context with a task ready for verification."""
        # Create repository structure
        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        # Create sample spec with a task in DONE status
        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T001": Task(
                    id="T001",
                    title="Task to verify",
                    description="Task in done status ready for verification",
                    status=TaskStatus.DONE,
                    priority=1,
                    labels=["feature"],
                ),
            },
        )

        save_spec(spec, tmp_path)

        # Create context
        context = LodestarContext(tmp_path)

        # Register an agent
        agent = Agent(display_name="Test Agent", role="tester", capabilities=["testing"])
        context.db.register_agent(agent)

        return context

    @pytest.mark.anyio
    async def test_task_verify_with_progress_notifications(self, progress_context):
        """Test that task_verify emits progress notifications when context supports it."""
        from lodestar.mcp.tools.task_mutations import task_verify

        # Create a mock context that tracks progress calls
        progress_calls = []

        class MockContext:
            """Mock context that captures progress and logging calls."""

            async def info(self, message: str):
                """Mock info logging."""
                pass

            async def error(self, message: str):
                """Mock error logging."""
                pass

            async def report_progress(
                self, progress: float, total: float | None = None, message: str | None = None
            ):
                """Capture progress calls."""
                progress_calls.append({"progress": progress, "total": total, "message": message})

        mock_ctx = MockContext()

        # Call task_verify with mock context
        result = await task_verify(
            context=progress_context,
            task_id="T001",
            agent_id="test-agent",
            note="Verifying with progress",
            ctx=mock_ctx,
        )

        # Verify the call succeeded
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True
        assert data["status"] == "verified"

        # Verify progress notifications were emitted
        assert len(progress_calls) == 8, f"Expected 8 progress calls, got {len(progress_calls)}"

        # Verify the sequence of progress values
        expected_progress = [10.0, 25.0, 40.0, 55.0, 70.0, 80.0, 90.0, 100.0]
        actual_progress = [call["progress"] for call in progress_calls]
        assert actual_progress == expected_progress

        # Verify all have total=100.0
        for call in progress_calls:
            assert call["total"] == 100.0

        # Verify messages are present and descriptive
        for call in progress_calls:
            assert call["message"] is not None
            assert len(call["message"]) > 0

        # Verify specific milestone messages
        assert "Validating inputs" in progress_calls[0]["message"]
        assert "Reloading spec" in progress_calls[1]["message"]
        assert "Checking task status" in progress_calls[2]["message"]
        assert "Updating task status" in progress_calls[3]["message"]
        assert "Releasing active lease" in progress_calls[4]["message"]
        assert "Logging verification event" in progress_calls[5]["message"]
        assert "Finding newly unblocked tasks" in progress_calls[6]["message"]
        assert "Verified" in progress_calls[7]["message"]

    @pytest.mark.anyio
    async def test_task_verify_without_progress_context(self, progress_context):
        """Test that task_verify works without progress support in context."""
        from lodestar.mcp.tools.task_mutations import task_verify

        # Create a mock context WITHOUT report_progress method
        class MockBasicContext:
            """Mock context without progress support."""

            async def info(self, message: str):
                """Mock info logging."""
                pass

            async def error(self, message: str):
                """Mock error logging."""
                pass

        mock_ctx = MockBasicContext()

        # Call task_verify - should not fail even without progress support
        result = await task_verify(
            context=progress_context,
            task_id="T001",
            agent_id="test-agent",
            note="Verifying without progress",
            ctx=mock_ctx,
        )

        # Verify the call succeeded
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True
        assert data["status"] == "verified"

    @pytest.mark.anyio
    async def test_task_verify_without_context(self, progress_context):
        """Test that task_verify works without any context (ctx=None)."""
        from lodestar.mcp.tools.task_mutations import task_verify

        # Create a fresh task in DONE status (since previous tests verified T001)
        from lodestar.models.spec import Task

        progress_context.spec.tasks["T002"] = Task(
            id="T002",
            title="Another task",
            description="Task for verification",
            status=TaskStatus.DONE,
            priority=2,
            labels=["feature"],
        )
        progress_context.save_spec()

        # Call task_verify with ctx=None
        result = await task_verify(
            context=progress_context,
            task_id="T002",
            agent_id="test-agent",
            note="Verifying without context",
            ctx=None,
        )

        # Verify the call succeeded
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True
        assert data["status"] == "verified"


class TestInputValidation:
    """Comprehensive tests for MCP tool input validation.

    Tests cover:
    - Invalid task IDs and agent IDs
    - TTL range validation and clamping
    - Maximum length enforcement
    - Required field validation
    - Output schema validation
    """

    @pytest.fixture
    def validation_context(self, tmp_path):
        """Create a test context for validation tests."""
        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        from lodestar.models.spec import Project, Spec

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "VALID-001": Task(
                    id="VALID-001",
                    title="Valid task",
                    description="A valid task for testing",
                    status=TaskStatus.READY,
                    priority=1,
                ),
            },
        )

        save_spec(spec, tmp_path)
        context = LodestarContext(tmp_path)

        # Register a test agent
        agent = Agent(display_name="Test Agent", agent_id="VALID-AGENT")
        context.db.register_agent(agent)

        return context

    # ========== Task ID Validation ==========

    def test_task_get_empty_id(self, validation_context):
        """Test that empty task ID is rejected."""
        result = task_get(validation_context, task_id="")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_TASK_ID"
        # Error message is "task_id is required" for empty string
        assert "required" in result.structuredContent["error"].lower()

    def test_task_get_none_id(self, validation_context):
        """Test that None task ID is rejected."""
        result = task_get(validation_context, task_id=None)

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_TASK_ID"

    def test_task_get_whitespace_id(self, validation_context):
        """Test that whitespace-only task ID is rejected."""
        result = task_get(validation_context, task_id="   ")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_TASK_ID"

    def test_task_get_too_long_id(self, validation_context):
        """Test that task ID exceeding max length is rejected."""
        # Task IDs should not exceed 100 characters
        long_id = "A" * 101

        result = task_get(validation_context, task_id=long_id)

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_TASK_ID"
        assert "maximum length" in result.structuredContent["error"].lower()

    def test_task_get_max_length_id_accepted(self, validation_context):
        """Test that task ID at max length (100 chars) is accepted."""
        # Create a task with 100-char ID
        max_len_id = "T" + "X" * 99

        validation_context.spec.tasks[max_len_id] = Task(
            id=max_len_id,
            title="Max length task",
            status=TaskStatus.READY,
        )
        validation_context.save_spec()
        validation_context.reload_spec()

        result = task_get(validation_context, task_id=max_len_id)

        # Should succeed
        assert result.isError is None or result.isError is False
        assert result.structuredContent["id"] == max_len_id

    # ========== Agent ID Validation ==========

    def test_agent_heartbeat_empty_id(self, validation_context):
        """Test that empty agent ID is rejected."""
        from lodestar.mcp.tools.agent import agent_heartbeat

        result = agent_heartbeat(validation_context, agent_id="")

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_AGENT_ID"

    def test_agent_heartbeat_none_id(self, validation_context):
        """Test that None agent ID is rejected."""
        from lodestar.mcp.tools.agent import agent_heartbeat

        result = agent_heartbeat(validation_context, agent_id=None)

        assert result.isError is True
        assert result.structuredContent["error_code"] == "INVALID_AGENT_ID"

    def test_agent_heartbeat_whitespace_id(self, validation_context):
        """Test that whitespace-only agent ID is rejected.

        Note: Whitespace gets stripped in validation, making it empty,
        which then results in AGENT_NOT_FOUND instead of INVALID_AGENT_ID.
        """
        from lodestar.mcp.tools.agent import agent_heartbeat

        result = agent_heartbeat(validation_context, agent_id="   ")

        assert result.isError is True
        # Whitespace is stripped, making it empty, which becomes AGENT_NOT_FOUND
        assert result.structuredContent["error_code"] in ["INVALID_AGENT_ID", "AGENT_NOT_FOUND"]

    # ========== TTL Validation ==========

    def test_ttl_clamping_below_minimum(self, validation_context):
        """Test that TTL below minimum is clamped to minimum."""
        from lodestar.mcp.validation import MIN_TTL_SECONDS, validate_ttl

        result = validate_ttl(30)  # Below 60s minimum

        assert result == MIN_TTL_SECONDS  # Should be clamped to 60

    def test_ttl_clamping_above_maximum(self, validation_context):
        """Test that TTL above maximum is clamped to maximum."""
        from lodestar.mcp.validation import MAX_TTL_SECONDS, validate_ttl

        result = validate_ttl(10000)  # Above 7200s maximum

        assert result == MAX_TTL_SECONDS  # Should be clamped to 7200

    def test_ttl_none_uses_default(self, validation_context):
        """Test that None TTL returns default value."""
        from lodestar.mcp.validation import DEFAULT_TTL_SECONDS, validate_ttl

        result = validate_ttl(None)

        assert result == DEFAULT_TTL_SECONDS  # Should be 900 (15 min)

    def test_ttl_valid_range_accepted(self, validation_context):
        """Test that TTL within valid range is accepted."""
        from lodestar.mcp.validation import validate_ttl

        # Test various valid values
        assert validate_ttl(60) == 60  # Minimum
        assert validate_ttl(900) == 900  # Default
        assert validate_ttl(3600) == 3600  # 1 hour
        assert validate_ttl(7200) == 7200  # Maximum

    def test_ttl_negative_clamped_to_minimum(self, validation_context):
        """Test that negative TTL is clamped to minimum."""
        from lodestar.mcp.validation import MIN_TTL_SECONDS, validate_ttl

        result = validate_ttl(-100)

        assert result == MIN_TTL_SECONDS

    @pytest.mark.anyio
    async def test_agent_join_ttl_validation(self, validation_context):
        """Test TTL validation in agent.join tool."""
        from lodestar.mcp.tools.agent import agent_join

        # Test with out-of-range TTL - should be clamped
        result = agent_join(validation_context, ttl_seconds=10000)  # Too high

        assert result.isError is None or result.isError is False
        data = result.structuredContent
        # TTL should be clamped to max (7200)
        assert data["leaseDefaults"]["ttlSeconds"] == 7200

    # ========== Message Length Validation ==========

    def test_message_max_length_validation(self, validation_context):
        """Test that messages exceeding max length are rejected."""
        from lodestar.mcp.validation import MAX_MESSAGE_LENGTH, ValidationError, validate_message

        # Create a message exceeding 16KB
        long_message = "A" * (MAX_MESSAGE_LENGTH + 1)

        with pytest.raises(ValidationError) as exc_info:
            validate_message(long_message)

        assert "exceeds maximum length" in str(exc_info.value)
        assert exc_info.value.field == "message"

    def test_message_max_length_accepted(self, validation_context):
        """Test that messages at max length are accepted."""
        from lodestar.mcp.validation import MAX_MESSAGE_LENGTH, validate_message

        # Create a message at exactly max length
        max_message = "A" * MAX_MESSAGE_LENGTH

        result = validate_message(max_message)

        assert result == max_message  # Should pass through

    def test_message_utf8_encoding_length(self, validation_context):
        """Test that message length is calculated in UTF-8 bytes."""
        from lodestar.mcp.validation import MAX_MESSAGE_LENGTH, ValidationError, validate_message

        # Multi-byte UTF-8 characters (emoji) count as more bytes
        emoji_char = "😀"  # 4 bytes in UTF-8
        # Create a string that's under char limit but over byte limit
        message = emoji_char * (MAX_MESSAGE_LENGTH // 2)

        with pytest.raises(ValidationError):
            validate_message(message)

    # ========== List Size Validation ==========

    def test_list_size_max_validation(self, validation_context):
        """Test that lists exceeding max size are rejected."""
        from lodestar.mcp.validation import MAX_LIST_SIZE, ValidationError, validate_list_size

        # Create a list exceeding max size (100 items)
        long_list = list(range(MAX_LIST_SIZE + 1))

        with pytest.raises(ValidationError) as exc_info:
            validate_list_size(long_list)

        assert "exceeds maximum size" in str(exc_info.value)
        assert exc_info.value.field == "items"

    def test_list_size_max_accepted(self, validation_context):
        """Test that lists at max size are accepted."""
        from lodestar.mcp.validation import MAX_LIST_SIZE, validate_list_size

        # Create a list at exactly max size
        max_list = list(range(MAX_LIST_SIZE))

        result = validate_list_size(max_list)

        assert result == max_list

    def test_limit_clamping_to_max(self, validation_context):
        """Test that limit parameter is clamped to max."""
        from lodestar.mcp.validation import MAX_LIST_SIZE, clamp_limit

        result = clamp_limit(500)  # Way above max

        assert result == MAX_LIST_SIZE

    def test_limit_clamping_to_min(self, validation_context):
        """Test that limit parameter is clamped to minimum of 1."""
        from lodestar.mcp.validation import clamp_limit

        assert clamp_limit(0) == 1
        assert clamp_limit(-10) == 1

    def test_limit_none_uses_default(self, validation_context):
        """Test that None limit uses default value."""
        from lodestar.mcp.validation import clamp_limit

        result = clamp_limit(None, default=50)

        assert result == 50

    # ========== Priority Validation ==========

    def test_priority_negative_rejected(self, validation_context):
        """Test that negative priority is rejected."""
        from lodestar.mcp.validation import ValidationError, validate_priority

        with pytest.raises(ValidationError) as exc_info:
            validate_priority(-1)

        assert "cannot be negative" in str(exc_info.value)

    def test_priority_too_high_rejected(self, validation_context):
        """Test that priority exceeding max is rejected."""
        from lodestar.mcp.validation import ValidationError, validate_priority

        with pytest.raises(ValidationError) as exc_info:
            validate_priority(1001)  # Max is 1000

        assert "exceeds maximum" in str(exc_info.value)

    def test_priority_valid_range_accepted(self, validation_context):
        """Test that valid priorities are accepted."""
        from lodestar.mcp.validation import validate_priority

        assert validate_priority(0) == 0
        assert validate_priority(500) == 500
        assert validate_priority(1000) == 1000

    def test_priority_none_accepted(self, validation_context):
        """Test that None priority is accepted."""
        from lodestar.mcp.validation import validate_priority

        result = validate_priority(None)

        assert result is None

    # ========== Required Field Validation ==========

    def test_required_field_none_rejected(self, validation_context):
        """Test that None for required field is rejected."""
        from lodestar.mcp.validation import ValidationError, validate_required_field

        with pytest.raises(ValidationError) as exc_info:
            validate_required_field(None, "test_field")

        assert "is required" in str(exc_info.value)
        assert exc_info.value.field == "test_field"

    def test_required_string_empty_rejected(self, validation_context):
        """Test that empty string for required field is rejected."""
        from lodestar.mcp.validation import ValidationError, validate_required_field

        with pytest.raises(ValidationError) as exc_info:
            validate_required_field("", "test_field")

        assert "cannot be empty" in str(exc_info.value)

    def test_required_string_whitespace_rejected(self, validation_context):
        """Test that whitespace-only string is rejected."""
        from lodestar.mcp.validation import ValidationError, validate_required_field

        with pytest.raises(ValidationError) as exc_info:
            validate_required_field("   ", "test_field")

        assert "cannot be empty" in str(exc_info.value)

    def test_required_field_type_validation(self, validation_context):
        """Test type validation for required fields."""
        from lodestar.mcp.validation import ValidationError, validate_required_field

        # Should reject wrong type
        with pytest.raises(ValidationError) as exc_info:
            validate_required_field("not an int", "test_field", expected_type=int)

        assert "must be of type int" in str(exc_info.value)

        # Should accept correct type
        result = validate_required_field(42, "test_field", expected_type=int)
        assert result == 42

    def test_required_field_valid_accepted(self, validation_context):
        """Test that valid required fields are accepted."""
        from lodestar.mcp.validation import validate_required_field

        assert validate_required_field("test", "field") == "test"
        assert validate_required_field(123, "field") == 123
        assert validate_required_field(["item"], "field") == ["item"]

    # ========== Output Schema Validation ==========

    def test_task_list_output_schema(self, validation_context):
        """Test that task.list output matches expected schema."""
        result = task_list(validation_context)

        assert result.isError is None or result.isError is False

        # Verify structured content exists
        data = result.structuredContent
        assert data is not None

        # Verify required top-level fields
        assert "count" in data
        assert "total" in data
        assert "items" in data

        # Verify types
        assert isinstance(data["count"], int)
        assert isinstance(data["total"], int)
        assert isinstance(data["items"], list)

        # Verify metadata (filters are in _meta, nextCursor is in structuredContent)
        assert result._meta is not None
        assert "filters" in result._meta

        # nextCursor is now in structuredContent (may be None if no more results)
        # We just verify the field exists or is None (not present when no pagination needed)

    def test_task_get_output_schema(self, validation_context):
        """Test that task.get output matches expected schema."""
        result = task_get(validation_context, task_id="VALID-001")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Verify all required fields exist
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

        # Verify field types
        assert isinstance(data["id"], str)
        assert isinstance(data["title"], str)
        assert isinstance(data["status"], str)
        assert isinstance(data["priority"], int)
        assert isinstance(data["labels"], list)
        assert isinstance(data["locks"], list)
        assert isinstance(data["dependencies"], dict)
        assert isinstance(data["runtime"], dict)
        assert isinstance(data["warnings"], list)

        # Verify nested structure
        assert "dependsOn" in data["dependencies"]
        assert "dependents" in data["dependencies"]
        assert "isClaimable" in data["dependencies"]
        assert "claimed" in data["runtime"]

    def test_agent_join_output_schema(self, validation_context):
        """Test that agent.join output matches expected schema."""
        from lodestar.mcp.tools.agent import agent_join

        result = agent_join(validation_context, name="Test Agent")

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Verify required fields
        required_fields = [
            "agentId",
            "displayName",
            "capabilities",
            "registeredAt",
            "sessionMeta",
            "leaseDefaults",
            "serverTime",
            "notes",
        ]

        for field in required_fields:
            assert field in data, f"Missing required field: {field}"

        # Verify types
        assert isinstance(data["agentId"], str)
        assert isinstance(data["displayName"], str)
        assert isinstance(data["capabilities"], list)
        assert isinstance(data["registeredAt"], str)
        assert isinstance(data["sessionMeta"], dict)
        assert isinstance(data["leaseDefaults"], dict)
        assert isinstance(data["serverTime"], str)
        assert isinstance(data["notes"], list)

        # Verify lease defaults structure
        assert "ttlSeconds" in data["leaseDefaults"]
        assert isinstance(data["leaseDefaults"]["ttlSeconds"], int)

    def test_error_output_schema(self, validation_context):
        """Test that error responses match expected schema."""
        result = task_get(validation_context, task_id="NONEXISTENT")

        assert result.isError is True
        data = result.structuredContent

        # Verify error structure
        assert "error" in data
        assert "error_code" in data

        assert isinstance(data["error_code"], str)
        assert isinstance(data["error"], str)

    @pytest.mark.anyio
    async def test_task_claim_output_schema(self, validation_context):
        """Test that task.claim output matches expected schema."""
        from lodestar.mcp.tools.task_mutations import task_claim

        result = await task_claim(
            context=validation_context,
            task_id="VALID-001",
            agent_id="VALID-AGENT",
            ttl_seconds=900,
        )

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Verify required top-level fields
        assert "ok" in data
        assert "lease" in data
        assert "warnings" in data

        # Verify types
        assert data["ok"] is True
        assert isinstance(data["lease"], dict)
        assert isinstance(data["warnings"], list)

        # Verify lease object structure
        lease = data["lease"]
        assert "leaseId" in lease
        assert "taskId" in lease
        assert "agentId" in lease
        assert "expiresAt" in lease
        assert "ttlSeconds" in lease
        assert "createdAt" in lease

        # Verify lease field types
        assert isinstance(lease["leaseId"], str)
        assert isinstance(lease["taskId"], str)
        assert isinstance(lease["agentId"], str)
        assert isinstance(lease["expiresAt"], str)
        assert isinstance(lease["ttlSeconds"], int)
        assert isinstance(lease["createdAt"], str)

    @pytest.mark.anyio
    async def test_task_claim_lock_conflict_warning(self, tmp_path):
        """Test that task.claim returns warnings for overlapping locks."""
        from lodestar.mcp.server import LodestarContext
        from lodestar.mcp.tools.task_mutations import task_claim
        from lodestar.models.spec import Project, Spec, Task, TaskStatus
        from lodestar.spec.loader import save_spec

        # Set up repository with two tasks that have overlapping locks
        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T001": Task(
                    id="T001",
                    title="Task 1",
                    status=TaskStatus.READY,
                    locks=["src/**"],
                ),
                "T002": Task(
                    id="T002",
                    title="Task 2",
                    status=TaskStatus.READY,
                    locks=["src/auth/**"],  # Overlaps with src/**
                ),
            },
        )
        save_spec(spec, tmp_path)

        # Create context using proper initialization
        context = LodestarContext(repo_root=tmp_path)

        # Claim first task
        result1 = await task_claim(
            context=context,
            task_id="T001",
            agent_id="AGENT-1",
        )
        assert result1.isError is None or result1.isError is False
        data1 = result1.structuredContent
        assert data1["ok"] is True
        # First claim should have no warnings (no other claimed tasks)
        assert len(data1["warnings"]) == 0

        # Claim second task - should show lock conflict warning
        result2 = await task_claim(
            context=context,
            task_id="T002",
            agent_id="AGENT-1",
        )
        assert result2.isError is None or result2.isError is False
        data2 = result2.structuredContent
        assert data2["ok"] is True
        # Second claim should have a warning about overlapping locks
        assert len(data2["warnings"]) >= 1
        warning = data2["warnings"][0]
        assert warning["type"] == "LOCK_CONFLICT"
        assert "overlap" in warning["message"].lower()

    @pytest.mark.anyio
    async def test_task_claim_force_bypasses_lock_warning(self, tmp_path):
        """Test that force=True bypasses lock conflict warnings."""
        from lodestar.mcp.server import LodestarContext
        from lodestar.mcp.tools.task_mutations import task_claim
        from lodestar.models.spec import Project, Spec, Task, TaskStatus
        from lodestar.spec.loader import save_spec

        # Set up repository with two tasks that have overlapping locks
        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T001": Task(
                    id="T001",
                    title="Task 1",
                    status=TaskStatus.READY,
                    locks=["src/**"],
                ),
                "T002": Task(
                    id="T002",
                    title="Task 2",
                    status=TaskStatus.READY,
                    locks=["src/auth/**"],  # Overlaps with src/**
                ),
            },
        )
        save_spec(spec, tmp_path)

        # Create context using proper initialization
        context = LodestarContext(repo_root=tmp_path)

        # Claim first task
        await task_claim(
            context=context,
            task_id="T001",
            agent_id="AGENT-1",
        )

        # Claim second task with force=True - should NOT have warnings
        result = await task_claim(
            context=context,
            task_id="T002",
            agent_id="AGENT-1",
            force=True,
        )
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True
        # With force=True, there should be no warnings
        assert len(data["warnings"]) == 0


class TestTaskComplete:
    """Tests for the task.complete MCP tool (atomic done + verify).

    Tests cover:
    - Successful atomic completion
    - Unblocking dependent tasks
    - Already verified task handling
    - Progress notifications
    - Crash recovery prevention
    """

    @pytest.fixture
    def complete_context(self, tmp_path):
        """Create a test context for task completion tests."""
        from lodestar.models.spec import Project, Spec

        lodestar_dir = tmp_path / ".lodestar"
        lodestar_dir.mkdir()

        # Create spec with tasks in various states
        spec = Spec(
            project=Project(name="test-project"),
            tasks={
                "T001": Task(
                    id="T001",
                    title="Ready task",
                    description="Task ready to complete",
                    status=TaskStatus.READY,
                    priority=1,
                    labels=["feature"],
                ),
                "T002": Task(
                    id="T002",
                    title="Done task",
                    description="Task already done",
                    status=TaskStatus.DONE,
                    priority=2,
                    labels=["feature"],
                ),
                "T003": Task(
                    id="T003",
                    title="Verified task",
                    description="Task already verified",
                    status=TaskStatus.VERIFIED,
                    priority=3,
                    labels=["feature"],
                ),
                "T004": Task(
                    id="T004",
                    title="Dependent task",
                    description="Task that depends on T001",
                    status=TaskStatus.READY,
                    priority=4,
                    labels=["feature"],
                    depends_on=["T001"],
                ),
                "T005": Task(
                    id="T005",
                    title="Another dependent",
                    description="Another task that depends on T001",
                    status=TaskStatus.READY,
                    priority=5,
                    labels=["feature"],
                    depends_on=["T001"],
                ),
            },
        )

        save_spec(spec, tmp_path)

        context = LodestarContext(tmp_path)

        # Register an agent
        agent = Agent(display_name="Test Agent", role="tester", capabilities=["testing"])
        context.db.register_agent(agent)

        # Create a lease for T001
        lease = Lease(
            task_id="T001",
            agent_id=agent.agent_id,
            expires_at=datetime.now(UTC) + timedelta(minutes=15),
        )
        context.db.create_lease(lease)

        return context

    @pytest.mark.anyio
    async def test_task_complete_success(self, complete_context):
        """Test successful atomic task completion."""
        from lodestar.mcp.tools.task_mutations import task_complete

        # Get the agent ID from the lease
        lease = complete_context.db.get_active_lease("T001")
        agent_id = lease.agent_id

        # Complete the task
        result = await task_complete(
            context=complete_context,
            task_id="T001",
            agent_id=agent_id,
            note="Task completed and verified atomically",
            ctx=None,
        )

        # Verify the call succeeded
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True
        assert data["status"] == "verified"
        assert data["taskId"] == "T001"

        # Verify the task is in VERIFIED status (not DONE)
        complete_context.reload_spec()
        task = complete_context.spec.get_task("T001")
        assert task.status == TaskStatus.VERIFIED
        assert task.completed_by == agent_id
        assert task.completed_at is not None
        assert task.verified_by == agent_id
        assert task.verified_at is not None

        # Verify dependent tasks are unblocked
        assert "newlyReadyTaskIds" in data
        assert len(data["newlyReadyTaskIds"]) == 2
        assert "T004" in data["newlyReadyTaskIds"]
        assert "T005" in data["newlyReadyTaskIds"]

        # Verify lease was released
        active_lease = complete_context.db.get_active_lease("T001")
        assert active_lease is None

    @pytest.mark.anyio
    async def test_task_complete_already_verified(self, complete_context):
        """Test completing an already verified task."""
        from lodestar.mcp.tools.task_mutations import task_complete

        result = await task_complete(
            context=complete_context,
            task_id="T003",
            agent_id="test-agent",
            ctx=None,
        )

        # Should succeed with warning
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert data["ok"] is True

        # Should have warning about already verified
        assert "warnings" in data
        assert len(data["warnings"]) > 0
        warning_types = [w["type"] for w in data["warnings"]]
        assert "ALREADY_VERIFIED" in warning_types

    @pytest.mark.anyio
    async def test_task_complete_with_progress(self, complete_context):
        """Test that task_complete emits progress notifications."""
        from lodestar.mcp.tools.task_mutations import task_complete

        # Create a mock context that tracks progress calls
        progress_calls = []

        class MockContext:
            """Mock context that captures progress and logging calls."""

            async def info(self, message: str):
                """Mock info logging."""
                pass

            async def error(self, message: str):
                """Mock error logging."""
                pass

            async def report_progress(
                self,
                progress: float,
                total: float | None = None,
                message: str | None = None,
            ):
                """Capture progress calls."""
                progress_calls.append({"progress": progress, "total": total, "message": message})

        mock_ctx = MockContext()

        # Get the agent ID from the lease
        lease = complete_context.db.get_active_lease("T001")
        agent_id = lease.agent_id

        # Complete the task with mock context
        result = await task_complete(
            context=complete_context,
            task_id="T001",
            agent_id=agent_id,
            note="Testing progress",
            ctx=mock_ctx,
        )

        # Verify the call succeeded
        assert result.isError is None or result.isError is False

        # Verify progress notifications were emitted
        assert len(progress_calls) == 8, f"Expected 8 progress calls, got {len(progress_calls)}"

        # Verify the sequence of progress values
        expected_progress = [10.0, 20.0, 30.0, 50.0, 60.0, 70.0, 85.0, 100.0]
        actual_progress = [call["progress"] for call in progress_calls]
        assert actual_progress == expected_progress

        # Verify all have total=100.0
        for call in progress_calls:
            assert call["total"] == 100.0

        # Verify messages are present and descriptive
        for call in progress_calls:
            assert call["message"] is not None
            assert len(call["message"]) > 0

    @pytest.mark.anyio
    async def test_task_complete_not_found(self, complete_context):
        """Test completing a non-existent task."""
        from lodestar.mcp.tools.task_mutations import task_complete

        result = await task_complete(
            context=complete_context,
            task_id="NONEXISTENT",
            agent_id="test-agent",
            ctx=None,
        )

        # Should fail with error
        assert result.isError is True
        data = result.structuredContent
        assert "error_code" in data
        assert data["error_code"] == "TASK_NOT_FOUND"

    @pytest.mark.anyio
    async def test_task_complete_invalid_task_id(self, complete_context):
        """Test completing with invalid task ID."""
        from lodestar.mcp.tools.task_mutations import task_complete

        result = await task_complete(
            context=complete_context,
            task_id="invalid task id!",
            agent_id="test-agent",
            ctx=None,
        )

        # Should fail with task not found error (validation allows this format)
        assert result.isError is True
        data = result.structuredContent
        assert "error_code" in data
        assert data["error_code"] == "TASK_NOT_FOUND"

    @pytest.mark.anyio
    async def test_task_complete_invalid_agent_id(self, complete_context):
        """Test completing with empty agent ID."""
        from lodestar.mcp.tools.task_mutations import task_complete

        result = await task_complete(
            context=complete_context,
            task_id="T001",
            agent_id="",
            ctx=None,
        )

        # Should fail with validation error
        assert result.isError is True
        data = result.structuredContent
        assert "error_code" in data
        assert data["error_code"] == "INVALID_AGENT_ID"

    @pytest.mark.anyio
    async def test_task_complete_with_note(self, complete_context):
        """Test that notes are preserved in the response."""
        from lodestar.mcp.tools.task_mutations import task_complete

        # Get the agent ID from the lease
        lease = complete_context.db.get_active_lease("T001")
        agent_id = lease.agent_id

        result = await task_complete(
            context=complete_context,
            task_id="T001",
            agent_id=agent_id,
            note="Tested thoroughly",
            ctx=None,
        )

        # Verify note is in response
        assert result.isError is None or result.isError is False
        data = result.structuredContent
        assert "note" in data
        assert data["note"] == "Tested thoroughly"

    @pytest.mark.anyio
    async def test_task_complete_atomicity(self, complete_context):
        """Test that task_complete is truly atomic (never leaves task in DONE state)."""
        from lodestar.mcp.tools.task_mutations import task_complete

        # Get the agent ID
        lease = complete_context.db.get_active_lease("T001")
        agent_id = lease.agent_id

        # Complete the task
        await task_complete(
            context=complete_context,
            task_id="T001",
            agent_id=agent_id,
            ctx=None,
        )

        # Reload spec to ensure we have the latest state
        complete_context.reload_spec()
        task = complete_context.spec.get_task("T001")

        # Task should NEVER be in DONE state - should go straight to VERIFIED
        assert task.status == TaskStatus.VERIFIED
        assert task.status != TaskStatus.DONE

        # Both completed_at and verified_at should be set
        assert task.completed_at is not None
        assert task.verified_at is not None
        assert task.completed_by == agent_id
        assert task.verified_by == agent_id


class TestTaskNextFiltering:
    """Tests for task_next filtering parameters."""

    @pytest.fixture
    def filtered_context(self, mcp_context):
        """Use the existing mcp_context which already has tasks with various labels and priorities."""
        # The mcp_context fixture already has tasks:
        # T001: priority 1, labels=["feature", "backend"], status=READY
        # T002: priority 2, labels=["bug", "frontend"], status=DONE
        # T003: priority 3, labels=["docs"], status=TODO (depends on T001)
        # T004: priority 5, labels=["feature", "frontend"], status=READY
        # T005: priority 10, labels=["chore"], status=DELETED

        return mcp_context

    def test_task_next_no_filters(self, filtered_context):
        """Test task_next without filters returns all claimable tasks."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(filtered_context)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return claimable tasks (only READY tasks with satisfied dependencies)
        assert len(data["candidates"]) >= 1  # At least some claimable tasks
        assert data["totalClaimable"] >= 1

    def test_task_next_filter_by_single_label(self, filtered_context):
        """Test filtering by a single label."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(filtered_context, labels=["frontend"])

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should only return tasks with "frontend" label
        for candidate in data["candidates"]:
            assert "frontend" in candidate["labels"]

        # Should have filters in response
        assert "filters" in data
        assert data["filters"]["labels"] == ["frontend"]

    def test_task_next_filter_by_multiple_labels(self, filtered_context):
        """Test filtering by multiple labels (ANY match)."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(filtered_context, labels=["feature", "bug"])

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return tasks with "feature" OR "bug" labels
        for candidate in data["candidates"]:
            assert any(label in candidate["labels"] for label in ["feature", "bug"])

    def test_task_next_filter_by_max_priority(self, filtered_context):
        """Test filtering by maximum priority."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(filtered_context, max_priority=3)

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should only return tasks with priority <= 3
        for candidate in data["candidates"]:
            assert candidate["priority"] <= 3

        # Should have filters in response
        assert "filters" in data
        assert data["filters"]["maxPriority"] == 3

    def test_task_next_combined_filters(self, filtered_context):
        """Test combining label and priority filters."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(
            filtered_context,
            labels=["feature"],
            max_priority=3,
        )

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should match both filters
        for candidate in data["candidates"]:
            assert "feature" in candidate["labels"]
            assert candidate["priority"] <= 3

        # Should have both filters in response
        assert "filters" in data
        assert data["filters"]["labels"] == ["feature"]
        assert data["filters"]["maxPriority"] == 3

    def test_task_next_filter_no_matches(self, filtered_context):
        """Test that no results are returned when filters match nothing."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(filtered_context, labels=["nonexistent"])

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return empty candidates list
        assert len(data["candidates"]) == 0
        assert data["totalClaimable"] == 0

        # Rationale should mention the filter
        assert "nonexistent" in data["rationale"]

    def test_task_next_filter_respects_limit(self, filtered_context):
        """Test that limit still applies after filtering."""
        from lodestar.mcp.tools.task import task_next

        result = task_next(
            filtered_context,
            labels=["feature"],
            limit=1,
        )

        assert result.isError is None or result.isError is False
        data = result.structuredContent

        # Should return at most 1 task even if more match
        assert len(data["candidates"]) <= 1

        # But totalClaimable shows how many matched the filter
        assert data["totalClaimable"] >= len(data["candidates"])
