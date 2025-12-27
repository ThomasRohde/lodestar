"""DAG validation for task dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from lodestar.models.spec import Spec


@dataclass
class DagValidationResult:
    """Result of DAG validation."""

    valid: bool
    cycles: list[list[str]]
    missing_deps: dict[str, list[str]]
    orphan_tasks: list[str]

    @property
    def errors(self) -> list[str]:
        """Get all validation errors as strings."""
        errors = []

        for cycle in self.cycles:
            cycle_str = " -> ".join(cycle)
            errors.append(f"Cycle detected: {cycle_str}")

        for task_id, deps in self.missing_deps.items():
            for dep in deps:
                errors.append(f"Task {task_id} depends on missing task: {dep}")

        return errors

    @property
    def warnings(self) -> list[str]:
        """Get all validation warnings as strings."""
        warnings = []

        for task_id in self.orphan_tasks:
            warnings.append(f"Task {task_id} has no dependents and is not verified")

        return warnings


def _find_cycles(
    task_id: str,
    graph: dict[str, list[str]],
    visited: set[str],
    rec_stack: set[str],
    path: list[str],
) -> list[list[str]]:
    """Find cycles using DFS."""
    cycles: list[list[str]] = []

    visited.add(task_id)
    rec_stack.add(task_id)
    path.append(task_id)

    for dep in graph.get(task_id, []):
        if dep not in visited:
            cycles.extend(_find_cycles(dep, graph, visited, rec_stack, path))
        elif dep in rec_stack:
            # Found a cycle - extract it
            cycle_start = path.index(dep)
            cycle = path[cycle_start:] + [dep]
            cycles.append(cycle)

    path.pop()
    rec_stack.remove(task_id)

    return cycles


def validate_dag(spec: Spec) -> DagValidationResult:
    """Validate the task dependency DAG.

    Checks for:
    - Cycles in dependencies
    - Missing dependency references
    - Orphan tasks (optional warning)

    Args:
        spec: The spec to validate.

    Returns:
        DagValidationResult with validation details.
    """
    # Build dependency graph (task -> dependencies)
    dep_graph: dict[str, list[str]] = {}
    for task_id, task in spec.tasks.items():
        dep_graph[task_id] = list(task.depends_on)

    # Check for missing dependencies
    missing_deps: dict[str, list[str]] = {}
    for task_id, deps in dep_graph.items():
        missing = [d for d in deps if d not in spec.tasks]
        if missing:
            missing_deps[task_id] = missing

    # Find cycles
    cycles: list[list[str]] = []
    visited: set[str] = set()
    rec_stack: set[str] = set()

    for task_id in spec.tasks:
        if task_id not in visited:
            found = _find_cycles(task_id, dep_graph, visited, rec_stack, [])
            cycles.extend(found)

    # Find orphan tasks (tasks with no dependents and not verified)
    has_dependents: set[str] = set()
    for task in spec.tasks.values():
        has_dependents.update(task.depends_on)

    orphan_tasks = [
        task_id
        for task_id, task in spec.tasks.items()
        if task_id not in has_dependents and task.status.value != "verified"
    ]

    is_valid = len(cycles) == 0 and len(missing_deps) == 0

    return DagValidationResult(
        valid=is_valid,
        cycles=cycles,
        missing_deps=missing_deps,
        orphan_tasks=orphan_tasks,
    )


def topological_sort(spec: Spec) -> list[str]:
    """Return tasks in topological order (dependencies first).

    Args:
        spec: The spec to sort.

    Returns:
        List of task IDs in topological order.

    Raises:
        ValueError: If the graph has cycles.
    """
    result = validate_dag(spec)
    if result.cycles:
        raise ValueError(f"Cannot sort: graph has cycles: {result.cycles}")

    # Kahn's algorithm
    in_degree: dict[str, int] = dict.fromkeys(spec.tasks, 0)
    for task in spec.tasks.values():
        for dep in task.depends_on:
            if dep in in_degree:
                in_degree[task.id] += 0  # dep contributes to task's in-degree
            # Actually we need reverse: dep -> task
    # Fix: in_degree counts how many deps a task has
    for task in spec.tasks.values():
        in_degree[task.id] = len([d for d in task.depends_on if d in spec.tasks])

    # Start with tasks that have no dependencies
    queue = [t for t, deg in in_degree.items() if deg == 0]
    sorted_tasks: list[str] = []

    # Build reverse graph (task -> tasks that depend on it)
    reverse_graph: dict[str, list[str]] = {t: [] for t in spec.tasks}
    for task in spec.tasks.values():
        for dep in task.depends_on:
            if dep in reverse_graph:
                reverse_graph[dep].append(task.id)

    while queue:
        task_id = queue.pop(0)
        sorted_tasks.append(task_id)

        for dependent in reverse_graph.get(task_id, []):
            in_degree[dependent] -= 1
            if in_degree[dependent] == 0:
                queue.append(dependent)

    return sorted_tasks
