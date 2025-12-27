"""Spec plane models - tasks, dependencies, and project configuration."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field, field_validator


class TaskStatus(str, Enum):
    """Task status in the spec plane.

    Note: 'claimed' is a runtime state, not a spec state.
    """

    TODO = "todo"
    READY = "ready"
    BLOCKED = "blocked"
    DONE = "done"
    VERIFIED = "verified"
    DELETED = "deleted"


class Task(BaseModel):
    """A task in the spec plane."""

    id: str = Field(description="Unique task identifier (e.g., T001, AUTH-001)")
    title: str = Field(description="Short task title")
    description: str = Field(default="", description="Detailed task description")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="List of acceptance criteria",
    )
    depends_on: list[str] = Field(
        default_factory=list,
        description="List of task IDs this task depends on",
    )
    labels: list[str] = Field(
        default_factory=list,
        description="Tags/labels for categorization",
    )
    locks: list[str] = Field(
        default_factory=list,
        description="Glob patterns of files/dirs owned by this task",
    )
    priority: int = Field(
        default=100,
        description="Priority (lower = higher priority)",
    )
    status: TaskStatus = Field(
        default=TaskStatus.TODO,
        description="Current task status",
    )
    created_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the task was created",
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow,
        description="When the task was last updated",
    )

    @field_validator("id")
    @classmethod
    def validate_id(cls, v: str) -> str:
        """Validate task ID format."""
        if not v or not v.strip():
            raise ValueError("Task ID cannot be empty")
        return v.strip()

    def is_claimable(self, verified_tasks: set[str]) -> bool:
        """Check if this task can be claimed.

        A task is claimable when:
        - status is READY
        - all depends_on tasks are VERIFIED
        - task is not deleted
        """
        if self.status != TaskStatus.READY:
            return False
        return all(dep in verified_tasks for dep in self.depends_on)


class Project(BaseModel):
    """Project configuration in the spec plane."""

    name: str = Field(description="Project name")
    default_branch: str = Field(
        default="main",
        description="Default git branch",
    )
    conventions: dict[str, Any] = Field(
        default_factory=dict,
        description="Optional project conventions",
    )


class Spec(BaseModel):
    """The complete spec.yaml structure."""

    project: Project = Field(description="Project configuration")
    tasks: dict[str, Task] = Field(
        default_factory=dict,
        description="Dictionary of tasks keyed by task ID",
    )
    features: dict[str, list[str]] = Field(
        default_factory=dict,
        description="Optional feature groupings (feature_id -> task_ids)",
    )

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def get_verified_tasks(self) -> set[str]:
        """Get the set of verified task IDs."""
        return {
            task_id for task_id, task in self.tasks.items() if task.status == TaskStatus.VERIFIED
        }

    def get_claimable_tasks(self) -> list[Task]:
        """Get all tasks that can be claimed, sorted by priority."""
        verified = self.get_verified_tasks()
        claimable = [task for task in self.tasks.values() if task.is_claimable(verified)]
        return sorted(claimable, key=lambda t: (t.priority, t.id))

    def get_dependency_graph(self) -> dict[str, list[str]]:
        """Get the dependency graph (task_id -> list of dependents)."""
        graph: dict[str, list[str]] = {task_id: [] for task_id in self.tasks}
        for task in self.tasks.values():
            for dep in task.depends_on:
                if dep in graph:
                    graph[dep].append(task.id)
        return graph
