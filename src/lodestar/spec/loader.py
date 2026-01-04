"""Spec plane loader - YAML loading, validation, and saving."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import portalocker
import yaml
from atomicwrites import atomic_write
from pydantic import ValidationError

from lodestar.models.spec import Project, Spec, Task, TaskStatus
from lodestar.util.paths import get_spec_path
from lodestar.util.retry import retry_on_windows_error


class SpecError(Exception):
    """Base exception for spec-related errors."""

    def __init__(self, message: str, retriable: bool = False, suggested_action: str | None = None):
        """Initialize SpecError with retriable flag and suggested action.

        Args:
            message: Error message
            retriable: Whether this error is transient and can be retried
            suggested_action: Suggested action for the user/agent
        """
        super().__init__(message)
        self.retriable = retriable
        self.suggested_action = suggested_action


class SpecNotFoundError(SpecError):
    """Spec file not found."""

    def __init__(self, message: str):
        """Initialize SpecNotFoundError (not retriable - file doesn't exist)."""
        super().__init__(
            message,
            retriable=False,
            suggested_action="Run 'lodestar init' to initialize the repository",
        )


class SpecValidationError(SpecError):
    """Spec validation failed."""

    def __init__(self, message: str):
        """Initialize SpecValidationError (not retriable - spec is invalid)."""
        super().__init__(
            message,
            retriable=False,
            suggested_action="Fix the spec file or restore from backup",
        )


class SpecLockError(SpecError):
    """Failed to acquire spec lock (transient)."""

    def __init__(self, message: str, timeout: float = 5.0):
        """Initialize SpecLockError (retriable - another process has the lock).

        Args:
            message: Error message
            timeout: Lock timeout that was attempted
        """
        super().__init__(
            message,
            retriable=True,
            suggested_action=f"Retry immediately (lock timeout was {timeout}s)",
        )
        self.timeout = timeout


class SpecFileAccessError(SpecError):
    """File system access error (transient on Windows)."""

    def __init__(self, message: str, operation: str = "file operation"):
        """Initialize SpecFileAccessError (retriable - Windows file lock).

        Args:
            message: Error message
            operation: The operation that failed (e.g., 'atomic rename')
        """
        super().__init__(
            message,
            retriable=True,
            suggested_action=f"Retry immediately (transient Windows file lock during {operation})",
        )
        self.operation = operation


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

    Acquires a shared lock to prevent reading during concurrent writes.

    Args:
        root: Repository root. If None, searches for it.

    Returns:
        The loaded Spec object.

    Raises:
        SpecNotFoundError: If spec.yaml doesn't exist.
        SpecValidationError: If the spec is invalid.
        SpecLockError: If the read lock cannot be acquired.
    """
    spec_path = get_spec_path(root)
    lock_path = spec_path.with_suffix(".lock")

    if not spec_path.exists():
        raise SpecNotFoundError(f"Spec not found: {os.path.normpath(spec_path)}")

    try:
        # Acquire shared lock for reading (allows multiple readers, blocks during writes)
        with (
            portalocker.Lock(
                lock_path,
                timeout=10,
                flags=portalocker.LOCK_SH | portalocker.LOCK_NB,
            ) as _,
            open(spec_path, encoding="utf-8") as f,
        ):
            raw = yaml.safe_load(f)
    except portalocker.LockException as e:
        raise SpecLockError(f"Failed to acquire spec read lock: {e}", timeout=10.0) from e
    except yaml.YAMLError as e:
        raise SpecValidationError(f"Invalid YAML: {e}") from e

    if raw is None:
        raw = {}

    # Parsing happens outside the lock - it's CPU-bound, not I/O-bound
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

    Uses atomicwrites for robust atomic file operations on Windows,
    with portalocker for cross-process coordination.

    Args:
        spec: The Spec object to save.
        root: Repository root. If None, searches for it.

    Raises:
        SpecLockError: If the lock cannot be acquired.
        SpecFileAccessError: If file system access fails (transient on Windows).
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

    def do_atomic_write() -> None:
        """Perform atomic write using atomicwrites library.

        atomicwrites uses MoveFileEx on Windows with proper flags,
        handles unique temp file names, and cleans up on failure.
        """
        with atomic_write(str(spec_path), mode="w", overwrite=True) as f:
            yaml.dump(data, f, default_flow_style=False, sort_keys=False)

    try:
        # Acquire exclusive lock with extended timeout for Windows
        with portalocker.Lock(
            lock_path, timeout=10, flags=portalocker.LOCK_EX | portalocker.LOCK_NB
        ) as _:
            # Retry the entire atomic write operation (not just rename)
            # Extended retry window for Windows Defender / antivirus interference
            retry_on_windows_error(
                do_atomic_write,
                max_attempts=10,
                base_delay_ms=150,
                jitter_factor=0.3,
            )
    except portalocker.LockException as e:
        raise SpecLockError(f"Failed to acquire spec lock: {e}", timeout=10.0) from e
    except (OSError, PermissionError) as e:
        raise SpecFileAccessError(
            f"Failed to save spec to {os.path.normpath(spec_path)} after retries: {e}",
            operation="atomic write",
        ) from e


def create_default_spec(project_name: str) -> Spec:
    """Create a default empty spec for initialization."""
    return Spec(
        project=Project(name=project_name),
        tasks={},
        features={},
    )
