"""Integration tests for batch verification MCP tool."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from pathlib import Path

import pytest

from lodestar.models.spec import Project, Spec, Task, TaskStatus
from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.loader import create_default_spec, save_spec


@pytest.fixture
def test_repo(tmp_path: Path) -> Path:
    """Create a test repository with spec and runtime."""
    lodestar_dir = tmp_path / ".lodestar"
    lodestar_dir.mkdir()

    # Create spec with multiple tasks
    spec = create_default_spec("test-batch-verify")
    
    # Task F001 - independent, ready to claim
    spec.tasks["F001"] = Task(
        id="F001",
        title="Task 1",
        description="First task",
        status=TaskStatus.DONE,
        priority=1,
        labels=["batch"],
    )
    
    # Task F002 - independent, ready to claim
    spec.tasks["F002"] = Task(
        id="F002",
        title="Task 2",
        description="Second task",
        status=TaskStatus.DONE,
        priority=1,
        labels=["batch"],
    )
    
    # Task F003 - independent, ready to claim
    spec.tasks["F003"] = Task(
        id="F003",
        title="Task 3",
        description="Third task",
        status=TaskStatus.DONE,
        priority=1,
        labels=["batch"],
    )
    
    # Task F004 - depends on F001, will be unblocked
    spec.tasks["F004"] = Task(
        id="F004",
        title="Task 4",
        description="Fourth task (depends on F001)",
        status=TaskStatus.READY,  # Need to be READY to be claimable
        priority=2,
        labels=["batch"],
        depends_on=["F001"],
    )
    
    # Task F005 - depends on F002 and F003, will be unblocked
    spec.tasks["F005"] = Task(
        id="F005",
        title="Task 5",
        description="Fifth task (depends on F002 and F003)",
        status=TaskStatus.READY,  # Need to be READY to be claimable
        priority=2,
        labels=["batch"],
        depends_on=["F002", "F003"],
    )
    
    # Task F006 - not done, should fail in batch
    spec.tasks["F006"] = Task(
        id="F006",
        title="Task 6",
        description="Sixth task (not done)",
        status=TaskStatus.READY,
        priority=1,
        labels=["batch"],
    )
    
    save_spec(spec, tmp_path)
    
    # Create runtime database (automatically initializes schema)
    db = RuntimeDatabase(lodestar_dir / "runtime.sqlite")
    # Don't need to call initialize() - it's done automatically
    
    return tmp_path


def test_batch_verify_all_success(test_repo: Path):
    """Test batch verify with all tasks succeeding."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Verify F001, F002, F003 in batch
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001", "F002", "F003"],
            agent_id=agent_id,
            notes={"F001": "Verified F001", "F002": "Verified F002"},
        )
    )

    # Check result structure
    assert result.isError is None or result.isError is False
    assert result.structuredContent is not None
    
    data = result.structuredContent
    
    assert data["ok"] is True
    assert data["summary"]["total"] == 3
    assert data["summary"]["succeeded"] == 3
    assert data["summary"]["failed"] == 0
    
    # Check individual results
    results = data["results"]
    assert len(results) == 3
    
    for r in results:
        assert r["success"] is True
        assert r["status"] == "verified"
    
    # Check F001 unblocked F004
    f001_result = next(r for r in results if r["taskId"] == "F001")
    assert "F004" in f001_result["newlyReadyTaskIds"]
    
    # Check F002 and F003 together unblock F005
    # (F005 needs both, so it might appear after both are done)
    all_ready = set(data["allNewlyReadyTaskIds"])
    assert "F004" in all_ready
    assert "F005" in all_ready
    
    # Verify tasks are actually verified in spec
    context.reload_spec()
    assert context.spec.tasks["F001"].status == TaskStatus.VERIFIED
    assert context.spec.tasks["F002"].status == TaskStatus.VERIFIED
    assert context.spec.tasks["F003"].status == TaskStatus.VERIFIED
    assert context.spec.tasks["F001"].verified_by == agent_id
    
    # Verify F004 is now claimable
    assert context.spec.tasks["F004"].status == TaskStatus.READY
    verified = context.spec.get_verified_tasks()
    assert context.spec.tasks["F004"].is_claimable(verified)
    
    # Verify F005 is now claimable (all deps verified)
    assert context.spec.tasks["F005"].is_claimable(verified)


def test_batch_verify_partial_success(test_repo: Path):
    """Test batch verify with some tasks failing."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Verify F001 (success), F002 (success), F006 (fail - not done)
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001", "F002", "F006"],
            agent_id=agent_id,
        )
    )

    # Parse response
    assert result.isError is None or result.isError is False
    assert result.structuredContent is not None
    data = result.structuredContent
    
    assert data["ok"] is True  # ok if at least one succeeded
    assert data["summary"]["total"] == 3
    assert data["summary"]["succeeded"] == 2
    assert data["summary"]["failed"] == 1
    
    # Check individual results
    results = data["results"]
    
    f001 = next(r for r in results if r["taskId"] == "F001")
    assert f001["success"] is True
    
    f002 = next(r for r in results if r["taskId"] == "F002")
    assert f002["success"] is True
    
    f006 = next(r for r in results if r["taskId"] == "F006")
    assert f006["success"] is False
    assert f006["errorCode"] == "TASK_NOT_DONE"
    assert "must be done before verifying" in f006["error"]


def test_batch_verify_empty_list(test_repo: Path):
    """Test batch verify with empty task list."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=[],
            agent_id=agent_id,
        )
    )

    # Should return error
    assert result.isError is True
    text = result.content[0].text
    assert "task_ids is required and cannot be empty" in text


def test_batch_verify_invalid_task_id(test_repo: Path):
    """Test batch verify with invalid task ID."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Include an empty string as task ID
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001", "", "F002"],
            agent_id=agent_id,
        )
    )

    # Should return error before processing any tasks
    assert result.isError is True
    text = result.content[0].text
    assert "Invalid task ID" in text


def test_batch_verify_nonexistent_task(test_repo: Path):
    """Test batch verify with nonexistent task."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Include a nonexistent task
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001", "NONEXISTENT", "F002"],
            agent_id=agent_id,
        )
    )

    # Parse response - should have partial success
    assert result.isError is None or result.isError is False
    assert result.structuredContent is not None
    data = result.structuredContent
    
    assert data["ok"] is True  # F001 and F002 succeeded
    assert data["summary"]["succeeded"] == 2
    assert data["summary"]["failed"] == 1
    
    # Check nonexistent task result
    nonexistent = next(r for r in data["results"] if r["taskId"] == "NONEXISTENT")
    assert nonexistent["success"] is False
    assert nonexistent["errorCode"] == "TASK_NOT_FOUND"


def test_batch_verify_already_verified(test_repo: Path):
    """Test batch verify with already verified task."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # First verify F001
    asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001"],
            agent_id=agent_id,
        )
    )

    # Try to verify F001 again with F002
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F001", "F002"],
            agent_id=agent_id,
        )
    )

    # Parse response
    assert result.isError is None or result.isError is False
    assert result.structuredContent is not None
    data = result.structuredContent
    
    assert data["ok"] is True
    assert data["summary"]["succeeded"] == 2  # Both succeed
    assert data["summary"]["failed"] == 0
    
    # Check F001 has warning
    f001 = next(r for r in data["results"] if r["taskId"] == "F001")
    assert f001["success"] is True
    assert "warning" in f001
    assert "already verified" in f001["warning"]


def test_batch_verify_max_size(test_repo: Path):
    """Test batch verify respects maximum batch size."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Try to verify more than 100 tasks
    task_ids = [f"TASK{i:03d}" for i in range(101)]
    
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=task_ids,
            agent_id=agent_id,
        )
    )

    # Should return error
    assert result.isError is True
    text = result.content[0].text
    assert "Batch size exceeds maximum of 100 tasks" in text


def test_batch_verify_dependency_unblocking(test_repo: Path):
    """Test that batch verify correctly unblocks dependent tasks."""
    from lodestar.mcp.server import LodestarContext
    from lodestar.mcp.tools.task_mutations import task_batch_verify

    context = LodestarContext(test_repo)
    agent_id = "TEST_AGENT"

    # Verify F002 and F003 together (both required for F005)
    result = asyncio.run(
        task_batch_verify(
            context=context,
            task_ids=["F002", "F003"],
            agent_id=agent_id,
        )
    )

    # Parse response
    assert result.isError is None or result.isError is False
    assert result.structuredContent is not None
    data = result.structuredContent
    
    # F005 should be unblocked (needs both F002 and F003)
    assert "F005" in data["allNewlyReadyTaskIds"]
    
    # Verify in spec
    context.reload_spec()
    verified = context.spec.get_verified_tasks()
    assert "F002" in verified
    assert "F003" in verified
    assert context.spec.tasks["F005"].is_claimable(verified)
