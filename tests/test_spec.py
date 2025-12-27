"""Tests for spec plane operations."""

from __future__ import annotations

import tempfile
from pathlib import Path

import pytest

from lodestar.models.spec import Project, Spec, Task, TaskStatus
from lodestar.spec.dag import topological_sort, validate_dag
from lodestar.spec.loader import (
    SpecNotFoundError,
    create_default_spec,
    load_spec,
    save_spec,
)


class TestSpecLoader:
    """Test spec loading and saving."""

    def test_create_default_spec(self):
        spec = create_default_spec("test-project")
        assert spec.project.name == "test-project"
        assert spec.tasks == {}

    def test_save_and_load_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()

            spec = create_default_spec("test")
            spec.tasks["T001"] = Task(id="T001", title="Test Task", status=TaskStatus.READY)

            save_spec(spec, root)
            assert (lodestar_dir / "spec.yaml").exists()

            loaded = load_spec(root)
            assert loaded.project.name == "test"
            assert "T001" in loaded.tasks
            assert loaded.tasks["T001"].title == "Test Task"

    def test_load_nonexistent_spec(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            root = Path(tmpdir)
            lodestar_dir = root / ".lodestar"
            lodestar_dir.mkdir()

            with pytest.raises(SpecNotFoundError):
                load_spec(root)


class TestDagValidation:
    """Test DAG validation."""

    def test_valid_dag(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(id="T001", title="First", status=TaskStatus.READY),
                "T002": Task(
                    id="T002", title="Second", status=TaskStatus.READY, depends_on=["T001"]
                ),
                "T003": Task(
                    id="T003", title="Third", status=TaskStatus.READY, depends_on=["T002"]
                ),
            },
        )
        result = validate_dag(spec)
        assert result.valid is True
        assert result.cycles == []
        assert result.missing_deps == {}

    def test_missing_dependency(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T002": Task(
                    id="T002", title="Second", status=TaskStatus.READY, depends_on=["T001"]
                ),
            },
        )
        result = validate_dag(spec)
        assert result.valid is False
        assert "T002" in result.missing_deps
        assert "T001" in result.missing_deps["T002"]

    def test_cycle_detection(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(
                    id="T001", title="First", status=TaskStatus.READY, depends_on=["T003"]
                ),
                "T002": Task(
                    id="T002", title="Second", status=TaskStatus.READY, depends_on=["T001"]
                ),
                "T003": Task(
                    id="T003", title="Third", status=TaskStatus.READY, depends_on=["T002"]
                ),
            },
        )
        result = validate_dag(spec)
        assert result.valid is False
        assert len(result.cycles) > 0

    def test_topological_sort(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(id="T001", title="First", status=TaskStatus.READY),
                "T002": Task(
                    id="T002", title="Second", status=TaskStatus.READY, depends_on=["T001"]
                ),
                "T003": Task(
                    id="T003", title="Third", status=TaskStatus.READY, depends_on=["T002"]
                ),
            },
        )
        sorted_tasks = topological_sort(spec)
        assert sorted_tasks.index("T001") < sorted_tasks.index("T002")
        assert sorted_tasks.index("T002") < sorted_tasks.index("T003")

    def test_topological_sort_with_cycle(self):
        spec = Spec(
            project=Project(name="test"),
            tasks={
                "T001": Task(
                    id="T001", title="First", status=TaskStatus.READY, depends_on=["T002"]
                ),
                "T002": Task(
                    id="T002", title="Second", status=TaskStatus.READY, depends_on=["T001"]
                ),
            },
        )
        with pytest.raises(ValueError, match="cycles"):
            topological_sort(spec)
