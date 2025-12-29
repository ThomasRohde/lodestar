"""Task output formatting for CLI commands.

Handles Rich console output and structured data formatting for task commands.
Separates presentation logic from business logic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from lodestar.models.envelope import Envelope, NextAction
from lodestar.models.spec import Task, TaskStatus
from lodestar.util.output import console, print_json
from lodestar.util.time import format_duration

# Status color mapping for Rich console output
STATUS_COLORS: dict[TaskStatus, str] = {
    TaskStatus.TODO: "white",
    TaskStatus.READY: "cyan",
    TaskStatus.BLOCKED: "yellow",
    TaskStatus.DONE: "blue",
    TaskStatus.VERIFIED: "green",
    TaskStatus.DELETED: "red dim",
}


def get_status_color(status: TaskStatus) -> str:
    """Get the Rich color for a task status."""
    return STATUS_COLORS.get(status, "white")


def format_task_list_item(
    task: Task,
    claimed_by: str | None = None,
) -> None:
    """Format a single task for list display.

    Args:
        task: The task to format.
        claimed_by: Agent ID if task is claimed.
    """
    color = get_status_color(task.status)
    claimed = f" [muted](claimed by {claimed_by})[/muted]" if claimed_by else ""
    labels = f" [{', '.join(task.labels)}]" if task.labels else ""

    console.print(
        f"  [task_id]{task.id}[/task_id] [{color}]{task.status.value}[/{color}]"
        f" P{task.priority}{labels}{claimed}"
    )
    console.print(f"    {task.title}")


def format_task_list(
    tasks: list[Task],
    leases: dict[str, Any],
    json_output: bool = False,
) -> None:
    """Format task list output.

    Args:
        tasks: List of tasks to display.
        leases: Dict mapping task_id to lease info.
        json_output: Whether to output JSON format.
    """
    result = {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "status": t.status.value,
                "priority": t.priority,
                "labels": t.labels,
                "depends_on": t.depends_on,
                "claimed_by": leases[t.id].agent_id if t.id in leases else None,
            }
            for t in tasks
        ],
        "count": len(tasks),
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        if not tasks:
            console.print("[muted]No tasks found.[/muted]")
        else:
            console.print(f"[bold]Tasks ({len(tasks)})[/bold]")
            console.print()
            for task in tasks:
                claimed_by = leases[task.id].agent_id if task.id in leases else None
                format_task_list_item(task, claimed_by)
        console.print()


def format_task_detail(
    task: Task,
    lease: Any | None,
    message_count: int,
    message_agents: list[str],
    claimable: bool,
    json_output: bool = False,
) -> None:
    """Format detailed task view.

    Args:
        task: The task to display.
        lease: Active lease if any.
        message_count: Number of messages in thread.
        message_agents: List of participating agent IDs.
        claimable: Whether task can be claimed.
        json_output: Whether to output JSON format.
    """
    result = task.model_dump()
    result["status"] = task.status.value
    result["created_at"] = task.created_at.isoformat()
    result["updated_at"] = task.updated_at.isoformat()

    if task.completed_at:
        result["completed_at"] = task.completed_at.isoformat()
    if task.verified_at:
        result["verified_at"] = task.verified_at.isoformat()

    if lease:
        result["claimed_by"] = {
            "agent_id": lease.agent_id,
            "expires_at": lease.expires_at.isoformat(),
        }

    result["communication"] = {
        "message_count": message_count,
        "participating_agents": message_agents,
    }
    result["claimable"] = claimable

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        status_display = task.status.value
        if task.status == TaskStatus.DELETED:
            status_display = f"[red dim]{task.status.value} (soft-deleted)[/red dim]"

        console.print(f"[bold][task_id]{task.id}[/task_id][/bold] - {task.title}")
        console.print()
        console.print(f"[muted]Status:[/muted] {status_display}")
        console.print(f"[muted]Priority:[/muted] {task.priority}")

        if task.labels:
            console.print(f"[muted]Labels:[/muted] {', '.join(task.labels)}")
        if task.depends_on:
            console.print(f"[muted]Depends on:[/muted] {', '.join(task.depends_on)}")
        if task.locks:
            console.print(f"[muted]Locks:[/muted] {', '.join(task.locks)}")

        # Display completion/verification info
        if task.completed_by:
            console.print(f"[muted]Completed by:[/muted] {task.completed_by}")
        if task.verified_by:
            console.print(f"[muted]Verified by:[/muted] {task.verified_by}")

        console.print()
        if task.description:
            console.print("[info]Description:[/info]")
            console.print(f"  {task.description}")
            console.print()

        if task.acceptance_criteria:
            console.print("[info]Acceptance Criteria:[/info]")
            for criterion in task.acceptance_criteria:
                console.print(f"  - {criterion}")
            console.print()

        if lease:
            remaining = lease.expires_at - datetime.now(UTC)
            console.print(f"[warning]Claimed by {lease.agent_id}[/warning]")
            console.print(f"  Expires in: {format_duration(remaining)}")
        elif claimable:
            console.print(
                f"[success]Claimable[/success] - run [command]lodestar task claim {task.id}[/command]"
            )

        if message_count > 0 or message_agents:
            console.print()
            console.print("[info]Communication:[/info]")
            if message_count > 0:
                console.print(f"  Messages in thread: {message_count}")
                console.print(f"  View with: [command]lodestar msg thread {task.id}[/command]")
            if message_agents:
                console.print(f"  Participating agents: {', '.join(message_agents)}")

        console.print()


def format_next_tasks(
    tasks: list[Task],
    total_claimable: int,
    json_output: bool = False,
) -> None:
    """Format next claimable tasks output.

    Args:
        tasks: List of next tasks to display.
        total_claimable: Total number of claimable tasks.
        json_output: Whether to output JSON format.
    """
    result = {
        "tasks": [
            {
                "id": t.id,
                "title": t.title,
                "priority": t.priority,
                "labels": t.labels,
            }
            for t in tasks
        ],
        "total_claimable": total_claimable,
    }

    next_actions = []
    if tasks:
        next_actions.append(
            NextAction(
                intent="task.claim",
                cmd=f"lodestar task claim {tasks[0].id}",
                description=f"Claim {tasks[0].id}",
            )
        )
        next_actions.append(
            NextAction(
                intent="task.show",
                cmd=f"lodestar task show {tasks[0].id}",
                description=f"View {tasks[0].id} details",
            )
        )

    if json_output:
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
    else:
        console.print()
        if not tasks:
            console.print("[muted]No claimable tasks available.[/muted]")
            console.print("All tasks are either claimed, blocked, or completed.")
        else:
            console.print(f"[bold]Next Claimable Tasks ({total_claimable} available)[/bold]")
            console.print()
            for task in tasks:
                labels = f" [{', '.join(task.labels)}]" if task.labels else ""
                console.print(f"  [task_id]{task.id}[/task_id] P{task.priority}{labels}")
                console.print(f"    {task.title}")
            console.print()
            console.print(f"Run [command]lodestar task claim {tasks[0].id}[/command] to claim")
        console.print()


def format_graph_dot(nodes: list[dict[str, Any]], edges: list[dict[str, Any]]) -> str:
    """Format dependency graph as Graphviz DOT.

    Args:
        nodes: List of node dicts with id, title.
        edges: List of edge dicts with from, to.

    Returns:
        DOT format string.
    """
    lines = ["digraph tasks {"]
    lines.append("  rankdir=LR;")
    for node in nodes:
        label = f"{node['id']}\\n{node['title'][:20]}"
        lines.append(f'  "{node["id"]}" [label="{label}"];')
    for edge in edges:
        lines.append(f'  "{edge["from"]}" -> "{edge["to"]}";')
    lines.append("}")
    return "\n".join(lines)


def format_graph(
    nodes: list[dict[str, Any]],
    edges: list[dict[str, Any]],
    output_format: str = "json",
    json_output: bool = False,
) -> None:
    """Format task dependency graph output.

    Args:
        nodes: List of node dicts.
        edges: List of edge dicts.
        output_format: Format type (json, dot).
        json_output: Whether to wrap in JSON envelope.
    """
    result = {"nodes": nodes, "edges": edges}

    if output_format == "dot":
        console.print(format_graph_dot(nodes, edges))
    elif json_output or output_format == "json":
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        console.print("[bold]Task Graph[/bold]")
        console.print(f"  Nodes: {len(nodes)}")
        console.print(f"  Edges: {len(edges)}")
        console.print()
        for edge in edges:
            console.print(f"  {edge['from']} -> {edge['to']}")
        console.print()


def format_deleted_tasks(
    deleted_tasks: list[dict[str, Any]],
    json_output: bool = False,
) -> None:
    """Format deleted tasks output.

    Args:
        deleted_tasks: List of dicts with id and title.
        json_output: Whether to output JSON format.
    """
    result = {
        "deleted": deleted_tasks,
        "count": len(deleted_tasks),
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        console.print(f"[success]Deleted {len(deleted_tasks)} task(s)[/success]")
        for dt in deleted_tasks:
            console.print(f"  - {dt['id']}: {dt['title']}")
        console.print()
        if len(deleted_tasks) > 1:
            console.print(
                "[muted]Tip: Use 'lodestar task list --include-deleted' to see deleted tasks[/muted]"
            )
        console.print()
