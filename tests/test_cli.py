"""Tests for CLI commands."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lodestar.cli.app import app

runner = CliRunner()


@pytest.fixture
def temp_repo():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(original_cwd)


class TestVersion:
    """Test version output."""

    def test_version_flag(self):
        result = runner.invoke(app, ["--version"])
        assert result.exit_code == 0
        assert "lodestar" in result.stdout
        assert "0.1.0" in result.stdout


class TestInit:
    """Test init command."""

    def test_init_creates_files(self, temp_repo):
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 0
        assert (temp_repo / ".lodestar").is_dir()
        assert (temp_repo / ".lodestar" / "spec.yaml").exists()
        assert (temp_repo / ".lodestar" / ".gitignore").exists()
        assert (temp_repo / "AGENTS.md").exists()

    def test_init_json_output(self, temp_repo):
        result = runner.invoke(app, ["init", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["initialized"] is True

    def test_init_fails_if_exists(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["init"])
        assert result.exit_code == 1


class TestStatus:
    """Test status command."""

    def test_status_not_initialized(self, temp_repo):
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0
        assert "Not a Lodestar" in result.stdout or "init" in result.stdout

    def test_status_json_not_initialized(self, temp_repo):
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["initialized"] is False

    def test_status_after_init(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["status"])
        assert result.exit_code == 0

    def test_status_json_after_init(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["initialized"] is True
        assert "tasks" in data["data"]


class TestDoctor:
    """Test doctor command."""

    def test_doctor_not_initialized(self, temp_repo):
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0

    def test_doctor_after_init(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["doctor"])
        assert result.exit_code == 0
        assert "passed" in result.stdout.lower() or "✓" in result.stdout

    def test_doctor_json(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["doctor", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["healthy"] is True


class TestAgent:
    """Test agent commands."""

    def test_agent_join(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["agent", "join", "--name", "TestAgent"])
        assert result.exit_code == 0
        assert "Registered" in result.stdout

    def test_agent_join_json(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["agent", "join", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "agent_id" in data["data"]

    def test_agent_list(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["agent", "join", "--name", "Agent1"])
        result = runner.invoke(app, ["agent", "list"])
        assert result.exit_code == 0

    def test_agent_list_json(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["agent", "join"])
        result = runner.invoke(app, ["agent", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["count"] == 1


class TestTask:
    """Test task commands."""

    def test_task_create(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["task", "create", "--title", "Test Task"])
        assert result.exit_code == 0
        assert "Created" in result.stdout

    def test_task_create_json(self, temp_repo):
        runner.invoke(app, ["init"])
        result = runner.invoke(app, ["task", "create", "--title", "Test", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "T001" in data["data"]["id"]

    def test_task_list(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task 1"])
        runner.invoke(app, ["task", "create", "--title", "Task 2"])
        result = runner.invoke(app, ["task", "list"])
        assert result.exit_code == 0

    def test_task_list_json(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task 1"])
        result = runner.invoke(app, ["task", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["count"] == 1

    def test_task_show(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "show", "T001"])
        assert result.exit_code == 0
        assert "T001" in result.stdout

    def test_task_next(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "next"])
        assert result.exit_code == 0

    def test_task_next_json(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "next", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["total_claimable"] >= 1

    def test_task_dependencies(self, temp_repo):
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "First"])
        runner.invoke(app, ["task", "create", "--title", "Second", "--depends-on", "T001"])
        result = runner.invoke(app, ["task", "next", "--json"])
        data = json.loads(result.stdout)
        # Only T001 should be claimable since T002 depends on it
        assert len(data["data"]["tasks"]) == 1
        assert data["data"]["tasks"][0]["id"] == "T001"


class TestTaskClaim:
    """Test task claiming."""

    def test_claim_and_release(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])

        # Claim
        result = runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id])
        assert result.exit_code == 0
        assert "Claimed" in result.stdout

        # Release
        result = runner.invoke(app, ["task", "release", "T001", "--agent", agent_id])
        assert result.exit_code == 0

    def test_claim_json(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "lease_id" in data["data"]

    def test_cannot_double_claim(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id])

        # Second claim should fail
        result = runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id])
        assert result.exit_code == 1


class TestTaskWorkflow:
    """Test complete task workflow."""

    def test_full_workflow(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        # Create tasks with dependencies
        runner.invoke(app, ["task", "create", "--title", "First Task"])
        runner.invoke(app, ["task", "create", "--title", "Second Task", "--depends-on", "T001"])

        # Claim first task
        runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id])

        # Mark done and verify
        runner.invoke(app, ["task", "done", "T001"])
        result = runner.invoke(app, ["task", "verify", "T001"])
        assert "Verified" in result.stdout

        # Now T002 should be claimable
        result = runner.invoke(app, ["task", "next", "--json"])
        data = json.loads(result.stdout)
        assert len(data["data"]["tasks"]) == 1
        assert data["data"]["tasks"][0]["id"] == "T002"


class TestMessaging:
    """Test messaging commands."""

    def test_send_message(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])

        result = runner.invoke(
            app,
            ["msg", "send", "--to", "task:T001", "--text", "Hello", "--from", agent_id],
        )
        assert result.exit_code == 0
        assert "sent" in result.stdout.lower()

    def test_message_thread(self, temp_repo):
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        runner.invoke(
            app,
            ["msg", "send", "--to", "task:T001", "--text", "Hello", "--from", agent_id],
        )

        result = runner.invoke(app, ["msg", "thread", "T001"])
        assert result.exit_code == 0
        assert "Hello" in result.stdout

    def test_inbox_count(self, temp_repo):
        """Test --count flag on inbox command."""
        runner.invoke(app, ["init"])
        agent1_result = runner.invoke(app, ["agent", "join", "--json"])
        agent1_id = json.loads(agent1_result.stdout)["data"]["agent_id"]

        agent2_result = runner.invoke(app, ["agent", "join", "--json"])
        agent2_id = json.loads(agent2_result.stdout)["data"]["agent_id"]

        # Send messages to agent2
        runner.invoke(
            app,
            [
                "msg",
                "send",
                "--to",
                f"agent:{agent2_id}",
                "--text",
                "Message 1",
                "--from",
                agent1_id,
            ],
        )
        runner.invoke(
            app,
            [
                "msg",
                "send",
                "--to",
                f"agent:{agent2_id}",
                "--text",
                "Message 2",
                "--from",
                agent1_id,
            ],
        )

        # Test count-only mode
        result = runner.invoke(app, ["msg", "inbox", "--agent", agent2_id, "--count"])
        assert result.exit_code == 0
        assert "2" in result.stdout

        # Test count in JSON output
        result = runner.invoke(app, ["msg", "inbox", "--agent", agent2_id, "--count", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["count"] == 2

    def test_msg_wait_with_existing_messages(self, temp_repo):
        """Test msg wait returns immediately when messages already exist."""
        runner.invoke(app, ["init"])
        agent1_result = runner.invoke(app, ["agent", "join", "--json"])
        agent1_id = json.loads(agent1_result.stdout)["data"]["agent_id"]

        agent2_result = runner.invoke(app, ["agent", "join", "--json"])
        agent2_id = json.loads(agent2_result.stdout)["data"]["agent_id"]

        # Send a message to agent2
        runner.invoke(
            app,
            ["msg", "send", "--to", f"agent:{agent2_id}", "--text", "Hello", "--from", agent1_id],
        )

        # Wait should return immediately since message exists
        result = runner.invoke(app, ["msg", "wait", "--agent", agent2_id, "--timeout", "1"])
        assert result.exit_code == 0
        assert "received" in result.stdout.lower()

    def test_msg_wait_timeout(self, temp_repo):
        """Test msg wait times out when no messages arrive."""
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        # Wait should timeout after 1 second
        result = runner.invoke(app, ["msg", "wait", "--agent", agent_id, "--timeout", "1"])
        assert result.exit_code == 0
        assert "timeout" in result.stdout.lower()

    def test_msg_wait_json(self, temp_repo):
        """Test msg wait JSON output."""
        runner.invoke(app, ["init"])
        agent_result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(agent_result.stdout)["data"]["agent_id"]

        # Test timeout in JSON
        result = runner.invoke(
            app, ["msg", "wait", "--agent", agent_id, "--timeout", "1", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["received"] is False
        assert data["data"]["timeout"] is True

    def test_status_includes_message_counts(self, temp_repo):
        """Test that status command includes message counts."""
        runner.invoke(app, ["init"])
        agent1_result = runner.invoke(app, ["agent", "join", "--json"])
        agent1_id = json.loads(agent1_result.stdout)["data"]["agent_id"]

        agent2_result = runner.invoke(app, ["agent", "join", "--json"])
        agent2_id = json.loads(agent2_result.stdout)["data"]["agent_id"]

        # Send messages
        runner.invoke(
            app,
            ["msg", "send", "--to", f"agent:{agent2_id}", "--text", "Test", "--from", agent1_id],
        )

        # Check status includes messages
        result = runner.invoke(app, ["status", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert "messages" in data["data"]
        assert data["data"]["messages"]["total"] >= 1
        assert agent2_id in data["data"]["messages"]["by_agent"]


class TestTaskDelete:
    """Test task delete command with soft-delete semantics."""

    def test_delete_simple_task(self, temp_repo):
        """Test deleting a task with no dependents."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task to delete"])

        result = runner.invoke(app, ["task", "delete", "T001"])
        assert result.exit_code == 0
        assert "Deleted" in result.stdout

    def test_delete_json_output(self, temp_repo):
        """Test delete with JSON output."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task to delete"])

        result = runner.invoke(app, ["task", "delete", "T001", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["count"] == 1
        assert data["data"]["deleted"][0]["id"] == "T001"

    def test_delete_with_dependents_fails(self, temp_repo):
        """Test that deleting a task with dependents fails without --cascade."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Parent Task"])
        runner.invoke(app, ["task", "create", "--title", "Child Task", "--depends-on", "T001"])

        result = runner.invoke(app, ["task", "delete", "T001"])
        assert result.exit_code == 1
        assert "depend" in result.stdout.lower()

    def test_delete_with_cascade(self, temp_repo):
        """Test cascade delete removes task and all dependents."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Parent"])
        runner.invoke(app, ["task", "create", "--title", "Child1", "--depends-on", "T001"])
        runner.invoke(app, ["task", "create", "--title", "Child2", "--depends-on", "T001"])

        result = runner.invoke(app, ["task", "delete", "T001", "--cascade", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["count"] == 3  # Parent + 2 children

    def test_deleted_tasks_hidden_from_list(self, temp_repo):
        """Test that deleted tasks are hidden from task list by default."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Active Task"])
        runner.invoke(app, ["task", "create", "--title", "Task to Delete"])
        runner.invoke(app, ["task", "delete", "T002"])

        result = runner.invoke(app, ["task", "list", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["count"] == 1
        assert data["data"]["tasks"][0]["id"] == "T001"

    def test_include_deleted_flag(self, temp_repo):
        """Test --include-deleted flag shows deleted tasks."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Active Task"])
        runner.invoke(app, ["task", "create", "--title", "Deleted Task"])
        runner.invoke(app, ["task", "delete", "T002"])

        result = runner.invoke(app, ["task", "list", "--include-deleted", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["count"] == 2
        deleted_task = [t for t in data["data"]["tasks"] if t["id"] == "T002"][0]
        assert deleted_task["status"] == "deleted"

    def test_show_deleted_task(self, temp_repo):
        """Test that task show indicates deleted status."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task to Delete"])
        runner.invoke(app, ["task", "delete", "T001"])

        result = runner.invoke(app, ["task", "show", "T001"])
        assert result.exit_code == 0
        assert "deleted" in result.stdout.lower()

    def test_delete_already_deleted(self, temp_repo):
        """Test that deleting an already deleted task fails gracefully."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task"])
        runner.invoke(app, ["task", "delete", "T001"])

        result = runner.invoke(app, ["task", "delete", "T001"])
        assert result.exit_code == 1
        assert "already deleted" in result.stdout.lower()

    def test_deleted_tasks_not_claimable(self, temp_repo):
        """Test that deleted tasks don't appear in task next."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Task 1"])
        runner.invoke(app, ["task", "create", "--title", "Task 2"])
        runner.invoke(app, ["task", "delete", "T001"])

        result = runner.invoke(app, ["task", "next", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["tasks"]) == 1
        assert data["data"]["tasks"][0]["id"] == "T002"

    def test_cascade_delete_complex_tree(self, temp_repo):
        """Test cascade delete on a complex dependency tree."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Root"])
        runner.invoke(app, ["task", "create", "--title", "Child1", "--depends-on", "T001"])
        runner.invoke(app, ["task", "create", "--title", "Child2", "--depends-on", "T001"])
        runner.invoke(app, ["task", "create", "--title", "Grandchild", "--depends-on", "T002"])

        result = runner.invoke(app, ["task", "delete", "T001", "--cascade", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        # Should delete: T001, T002, T003, T004
        assert data["data"]["count"] == 4

    def test_filter_by_deleted_status(self, temp_repo):
        """Test filtering task list by deleted status."""
        runner.invoke(app, ["init"])
        runner.invoke(app, ["task", "create", "--title", "Active"])
        runner.invoke(app, ["task", "create", "--title", "Deleted"])
        runner.invoke(app, ["task", "delete", "T002"])

        result = runner.invoke(app, ["task", "list", "--status", "deleted", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["count"] == 1
        assert data["data"]["tasks"][0]["id"] == "T002"
