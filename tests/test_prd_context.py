"""Tests for PRD context functionality."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

import pytest
from typer.testing import CliRunner

from lodestar.cli.app import app
from lodestar.models.spec import PrdContext, PrdRef, Task
from lodestar.util.prd import (
    check_prd_drift,
    compute_prd_hash,
    extract_prd_section,
    truncate_to_budget,
)

runner = CliRunner()


@pytest.fixture
def temp_repo():
    """Create a temporary directory for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        original_cwd = os.getcwd()
        os.chdir(tmpdir)
        yield Path(tmpdir)
        os.chdir(original_cwd)


@pytest.fixture
def temp_repo_with_prd(temp_repo):
    """Create a temp repo with a PRD file."""
    runner.invoke(app, ["init"])
    prd_content = """# Product Requirements

## Summary
This is a test PRD.

## Task Claiming
Agents should claim tasks before working on them.
Claims use time-limited leases.

## Dependencies
Tasks can depend on other tasks.
"""
    (temp_repo / "PRD.md").write_text(prd_content, encoding="utf-8")
    return temp_repo


class TestPrdModels:
    """Test PrdRef and PrdContext models."""

    def test_prd_ref_basic(self):
        ref = PrdRef(anchor="#task-claiming")
        assert ref.anchor == "#task-claiming"
        assert ref.lines is None

    def test_prd_ref_with_lines(self):
        ref = PrdRef(anchor="#task-claiming", lines=[10, 20])
        assert ref.anchor == "#task-claiming"
        assert ref.lines == [10, 20]

    def test_prd_context_basic(self):
        ctx = PrdContext(source="PRD.md")
        assert ctx.source == "PRD.md"
        assert ctx.refs == []
        assert ctx.excerpt is None
        assert ctx.prd_hash is None

    def test_prd_context_full(self):
        ctx = PrdContext(
            source="PRD.md",
            refs=[PrdRef(anchor="#task-claiming")],
            excerpt="Test excerpt",
            prd_hash="abc123",
        )
        assert ctx.source == "PRD.md"
        assert len(ctx.refs) == 1
        assert ctx.excerpt == "Test excerpt"
        assert ctx.prd_hash == "abc123"

    def test_task_with_prd_context(self):
        task = Task(
            id="T001",
            title="Test Task",
            prd=PrdContext(
                source="PRD.md",
                refs=[PrdRef(anchor="#task-claiming")],
            ),
        )
        assert task.prd is not None
        assert task.prd.source == "PRD.md"

    def test_task_without_prd_context(self):
        task = Task(id="T001", title="Test Task")
        assert task.prd is None


class TestPrdUtilities:
    """Test PRD utility functions."""

    def test_compute_prd_hash(self, temp_repo):
        prd_path = temp_repo / "test.md"
        prd_path.write_text("Test content", encoding="utf-8")
        hash1 = compute_prd_hash(prd_path)
        assert len(hash1) == 64  # SHA256 hex

        # Same content = same hash
        hash2 = compute_prd_hash(prd_path)
        assert hash1 == hash2

        # Different content = different hash
        prd_path.write_text("Different content", encoding="utf-8")
        hash3 = compute_prd_hash(prd_path)
        assert hash1 != hash3

    def test_check_prd_drift(self, temp_repo):
        prd_path = temp_repo / "test.md"
        prd_path.write_text("Original content", encoding="utf-8")
        original_hash = compute_prd_hash(prd_path)

        # No drift
        assert not check_prd_drift(original_hash, prd_path)

        # After modification - drift detected
        prd_path.write_text("Modified content", encoding="utf-8")
        assert check_prd_drift(original_hash, prd_path)

    def test_extract_prd_section_by_lines(self, temp_repo):
        prd_path = temp_repo / "test.md"
        prd_path.write_text("Line 1\nLine 2\nLine 3\nLine 4\n", encoding="utf-8")

        section = extract_prd_section(prd_path, lines=(2, 3))
        assert "Line 2" in section
        assert "Line 3" in section
        assert "Line 1" not in section

    def test_extract_prd_section_by_anchor(self, temp_repo):
        prd_path = temp_repo / "test_prd.md"
        prd_content = """# Product Requirements

## Summary
This is a test PRD.

## Task Claiming
Agents should claim tasks before working on them.
Claims use time-limited leases.

## Dependencies
Tasks can depend on other tasks.
"""
        prd_path.write_text(prd_content, encoding="utf-8")
        section = extract_prd_section(prd_path, anchor="#task-claiming")
        assert "Agents should claim tasks" in section

    def test_truncate_to_budget(self):
        content = "A" * 2000
        truncated = truncate_to_budget(content, 1000)
        assert len(truncated) <= 1000
        assert truncated.endswith("...")

    def test_truncate_short_content(self):
        content = "Short content"
        truncated = truncate_to_budget(content, 1000)
        assert truncated == content


class TestTaskContextCommand:
    """Test lodestar task context command."""

    def test_context_basic(self, temp_repo_with_prd):
        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "context", "T001"])
        assert result.exit_code == 0
        assert "T001" in result.stdout

    def test_context_json(self, temp_repo_with_prd):
        runner.invoke(app, ["task", "create", "--title", "Test Task"])
        result = runner.invoke(app, ["task", "context", "T001", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["task_id"] == "T001"

    def test_context_with_prd(self, temp_repo_with_prd):
        runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--prd-ref",
                "#task-claiming",
            ],
        )
        result = runner.invoke(app, ["task", "context", "T001", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["prd_source"] == "PRD.md"

    def test_context_max_chars(self, temp_repo_with_prd):
        runner.invoke(
            app,
            ["task", "create", "--title", "Test", "--description", "A" * 2000],
        )
        result = runner.invoke(app, ["task", "context", "T001", "--max-chars", "500", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["content"]) <= 500


class TestTaskCreateWithPrd:
    """Test task creation with PRD context."""

    def test_create_with_prd_source(self, temp_repo_with_prd):
        result = runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["ok"] is True
        assert data["data"]["prd"]["source"] == "PRD.md"

    def test_create_with_prd_refs(self, temp_repo_with_prd):
        result = runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--prd-ref",
                "#task-claiming",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["data"]["prd"]["refs"]) == 1
        assert data["data"]["prd"]["refs"][0]["anchor"] == "#task-claiming"

    def test_create_with_prd_excerpt(self, temp_repo_with_prd):
        result = runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--prd-excerpt",
                "Agents should claim tasks",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["prd"]["excerpt"] == "Agents should claim tasks"

    def test_create_computes_prd_hash(self, temp_repo_with_prd):
        result = runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--json",
            ],
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert data["data"]["prd"]["prd_hash"] is not None
        assert len(data["data"]["prd"]["prd_hash"]) == 64


class TestTaskClaimWithContext:
    """Test task claim includes context by default."""

    def test_claim_includes_context(self, temp_repo_with_prd):
        runner.invoke(app, ["agent", "join", "--json"])
        result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(result.stdout)["data"]["agent_id"]

        runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--description",
                "Task description",
            ],
        )

        result = runner.invoke(app, ["task", "claim", "T001", "--agent", agent_id, "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "context" in data["data"]
        assert data["data"]["context"]["title"] == "Test Task"

    def test_claim_no_context_flag(self, temp_repo_with_prd):
        result = runner.invoke(app, ["agent", "join", "--json"])
        agent_id = json.loads(result.stdout)["data"]["agent_id"]

        runner.invoke(app, ["task", "create", "--title", "Test Task"])

        result = runner.invoke(
            app, ["task", "claim", "T001", "--agent", agent_id, "--no-context", "--json"]
        )
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert "context" not in data["data"]


class TestPrdDriftDetection:
    """Test PRD drift detection."""

    def test_drift_warning_on_context(self, temp_repo_with_prd):
        # Create task with PRD hash
        runner.invoke(
            app,
            [
                "task",
                "create",
                "--title",
                "Test Task",
                "--prd-source",
                "PRD.md",
                "--json",
            ],
        )

        # Modify PRD
        prd_path = temp_repo_with_prd / "PRD.md"
        prd_path.write_text("Modified content", encoding="utf-8")

        # Check context - should warn about drift
        result = runner.invoke(app, ["task", "context", "T001", "--json"])
        assert result.exit_code == 0
        data = json.loads(result.stdout)
        assert len(data["warnings"]) > 0
        assert "changed" in data["warnings"][0].lower()
