"""Spec plane loader - YAML loading, validation, and saving."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import portalocker
import yaml
from pydantic import ValidationError

from lodestar.models.spec import PrdContext, PrdRef, Project, Spec, Task, TaskStatus
from lodestar.util.paths import get_spec_path


class SpecError(Exception):
    """Base exception for spec-related errors."""


class SpecNotFoundError(SpecError):
    """Spec file not found."""


class SpecValidationError(SpecError):
    """Spec validation failed."""


class SpecLockError(SpecError):
    """Failed to acquire spec lock."""


def _parse_task(task_id: str, data: dict[str, Any]) -> Task:
    """Parse a task from YAML data."""
    # Ensure ID is set
    data["id"] = task_id

    # Handle status as string
    if "status" in data and isinstance(data["status"], str):
        data["status"] = TaskStatus(data["status"])

    return Task(**data)


def _serialize_task(task: Task) -> dict[str, Any]:
    """Serialize a task to YAML-friendly format."""
    data = task.model_dump()
    # Convert status enum to string
    data["status"] = task.status.value
    # Convert datetimes to ISO strings
    data["created_at"] = task.created_at.isoformat()
    data["updated_at"] = task.updated_at.isoformat()
    # Remove id from dict (it's the key)
    del data["id"]
    # Remove None values for cleaner YAML (especially prd when not set)
    data = {k: v for k, v in data.items() if v is not None}
    return data


def load_spec(root: Path | None = None) -> Spec:
    """Load and validate the spec from disk.

    Args:
        root: Repository root. If None, searches for it.

    Returns:
        The loaded Spec object.

    Raises:
        SpecNotFoundError: If spec.yaml doesn't exist.
        SpecValidationError: If the spec is invalid.
    """
    spec_path = get_spec_path(root)

    if not spec_path.exists():
        raise SpecNotFoundError(f"Spec not found: {spec_path}")

    try:
        with open(spec_path, encoding="utf-8") as f:
            raw = yaml.safe_load(f)
    except yaml.YAMLError as e:
        raise SpecValidationError(f"Invalid YAML: {e}") from e

    if raw is None:
        raw = {}

    try:
        # Parse project
        project_data = raw.get("project", {})
        if not project_data.get("name"):
            project_data["name"] = "unnamed"
        project = Project(**project_data)

        # Parse tasks
        tasks: dict[str, Task] = {}
        for task_id, task_data in raw.get("tasks", {}).items():
            tasks[task_id] = _parse_task(task_id, task_data)

        # Parse features
        features = raw.get("features", {})

        return Spec(project=project, tasks=tasks, features=features)

    except ValidationError as e:
        raise SpecValidationError(f"Spec validation failed: {e}") from e


def save_spec(spec: Spec, root: Path | None = None) -> None:
    """Save the spec to disk atomically with file locking.

    Args:
        spec: The Spec object to save.
        root: Repository root. If None, searches for it.

    Raises:
        SpecLockError: If the lock cannot be acquired.
    """
    spec_path = get_spec_path(root)
    lock_path = spec_path.with_suffix(".lock")

    # Prepare YAML data
    data: dict[str, Any] = {
        "project": spec.project.model_dump(),
    }

    if spec.tasks:
        data["tasks"] = {task_id: _serialize_task(task) for task_id, task in spec.tasks.items()}

    if spec.features:
        data["features"] = spec.features

    # Atomic write with file locking
    try:
        with portalocker.Lock(lock_path, timeout=5) as _:
            # Write to temp file first
            temp_path = spec_path.with_suffix(".tmp")
            with open(temp_path, "w", encoding="utf-8") as f:
                yaml.dump(data, f, default_flow_style=False, sort_keys=False)

            # Atomic rename
            temp_path.replace(spec_path)

    except portalocker.LockException as e:
        raise SpecLockError(f"Failed to acquire spec lock: {e}") from e


def create_default_spec(project_name: str) -> Spec:
    """Create a default empty spec for initialization."""
    return Spec(
        project=Project(name=project_name),
        tasks={},
        features={},
    )
