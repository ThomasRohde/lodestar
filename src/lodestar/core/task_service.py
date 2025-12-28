"""Task business logic - scheduling, claims, and dependency management.

This module contains pure business logic extracted from CLI commands
for better testability and separation of concerns.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from lodestar.models.spec import Spec, Task, TaskStatus
from lodestar.util.locks import find_overlapping_patterns

if TYPE_CHECKING:
    from lodestar.runtime.database import RuntimeDatabase


@dataclass
class ClaimValidation:
    """Result of validating a task claim."""

    can_claim: bool
    error: str | None = None
    lock_warnings: list[str] | None = None


@dataclass
class CascadeDeleteResult:
    """Result of computing cascade delete targets."""

    tasks_to_delete: list[str]
    blocked_by: list[str] | None = None


def get_unclaimed_claimable_tasks(
    spec: Spec,
    db: RuntimeDatabase,
) -> list[Task]:
    """Get tasks that are claimable and not currently claimed.

    Args:
        spec: The spec containing all tasks.
        db: Runtime database to check active leases.

    Returns:
        List of claimable, unclaimed tasks sorted by priority.
    """
    claimable = spec.get_claimable_tasks()
    return [t for t in claimable if db.get_active_lease(t.id) is None]


def validate_task_claim(
    task: Task,
    spec: Spec,
    db: RuntimeDatabase,
    force: bool = False,
) -> ClaimValidation:
    """Validate whether a task can be claimed.

    Checks:
    - Task is in claimable status (ready with deps verified)
    - No existing active lease
    - Lock conflict warnings (unless force=True)

    Args:
        task: The task to validate for claiming.
        spec: The spec containing all tasks.
        db: Runtime database to check leases.
        force: If True, bypass lock conflict warnings.

    Returns:
        ClaimValidation with result and any warnings.
    """
    # Check if task is claimable by status/deps
    verified = spec.get_verified_tasks()
    if not task.is_claimable(verified):
        unmet_deps = [d for d in task.depends_on if d not in verified]
        if unmet_deps:
            return ClaimValidation(
                can_claim=False,
                error=f"Task has unmet dependencies: {', '.join(unmet_deps)}",
            )
        return ClaimValidation(
            can_claim=False,
            error=f"Task is not claimable (status: {task.status.value})",
        )

    # Check for existing lease
    existing_lease = db.get_active_lease(task.id)
    if existing_lease:
        return ClaimValidation(
            can_claim=False,
            error=f"Task already claimed by {existing_lease.agent_id}",
        )

    # Check for lock conflicts (warning only, unless force)
    lock_warnings: list[str] = []
    if task.locks and not force:
        lock_warnings = detect_lock_conflicts(task, spec, db)

    return ClaimValidation(
        can_claim=True,
        lock_warnings=lock_warnings if lock_warnings else None,
    )


def detect_lock_conflicts(
    task: Task,
    spec: Spec,
    db: RuntimeDatabase,
) -> list[str]:
    """Detect lock conflicts between a task and actively-leased tasks.

    Args:
        task: The task to check for conflicts.
        spec: The spec containing all tasks.
        db: Runtime database to check active leases.

    Returns:
        List of warning messages for overlapping locks.
    """
    if not task.locks:
        return []

    warnings: list[str] = []
    active_leases = db.get_all_active_leases()

    for active_lease in active_leases:
        if active_lease.task_id == task.id:
            continue  # Skip self

        leased_task = spec.get_task(active_lease.task_id)
        if leased_task and leased_task.locks:
            overlaps = find_overlapping_patterns(task.locks, leased_task.locks)
            for our_pattern, their_pattern in overlaps:
                warnings.append(
                    f"Lock '{our_pattern}' overlaps with '{their_pattern}' "
                    f"(task {active_lease.task_id}, claimed by {active_lease.agent_id})"
                )

    return warnings


def compute_cascade_delete(
    task_id: str,
    spec: Spec,
    cascade: bool = False,
) -> CascadeDeleteResult:
    """Compute which tasks to delete, handling dependents.

    Args:
        task_id: The task to delete.
        spec: The spec containing all tasks.
        cascade: If True, include all downstream dependents.

    Returns:
        CascadeDeleteResult with tasks to delete or blocking dependents.
    """
    task = spec.get_task(task_id)
    if task is None:
        return CascadeDeleteResult(tasks_to_delete=[], blocked_by=[task_id])

    if task.status == TaskStatus.DELETED:
        return CascadeDeleteResult(tasks_to_delete=[], blocked_by=None)

    # Find tasks that depend on this one
    dependency_graph = spec.get_dependency_graph()
    dependents = dependency_graph.get(task_id, [])

    # Filter out already deleted tasks
    active_dependents = [d for d in dependents if spec.tasks[d].status != TaskStatus.DELETED]

    if active_dependents and not cascade:
        return CascadeDeleteResult(
            tasks_to_delete=[],
            blocked_by=active_dependents,
        )

    # Collect all tasks to delete
    tasks_to_delete = [task_id]

    if cascade and active_dependents:
        # Recursively collect all downstream dependents
        to_process = active_dependents[:]
        while to_process:
            current = to_process.pop(0)
            if current not in tasks_to_delete:
                tasks_to_delete.append(current)
                current_deps = dependency_graph.get(current, [])
                active_current_deps = [
                    d for d in current_deps if spec.tasks[d].status != TaskStatus.DELETED
                ]
                to_process.extend(active_current_deps)

    return CascadeDeleteResult(tasks_to_delete=tasks_to_delete)


def get_newly_unblocked_tasks(
    verified_task_id: str,
    spec: Spec,
) -> list[Task]:
    """Get tasks that become claimable after a task is verified.

    Args:
        verified_task_id: The ID of the just-verified task.
        spec: The spec containing all tasks.

    Returns:
        List of tasks that are now claimable and depend on the verified task.
    """
    new_claimable = spec.get_claimable_tasks()
    return [t for t in new_claimable if verified_task_id in t.depends_on]
