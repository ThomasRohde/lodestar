"""Tests for MCP tools."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from lodestar.mcp.server import LodestarContext
from lodestar.mcp.tools.task import task_list
from lodestar.models.runtime import Agent, Lease
from lodestar.models.spec import Task, TaskStatus
from lodestar.spec.loader import save_spec


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
