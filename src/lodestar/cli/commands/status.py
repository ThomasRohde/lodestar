"""lodestar status command - Show repository status and next actions."""

from __future__ import annotations

import typer
from rich.panel import Panel
from rich.table import Table

from lodestar.models.envelope import (
    NEXT_ACTION_AGENT_JOIN,
    NEXT_ACTION_HELP,
    NEXT_ACTION_TASK_LIST,
    NEXT_ACTION_TASK_NEXT,
    Envelope,
)
from lodestar.models.spec import TaskStatus
from lodestar.spec.loader import SpecNotFoundError, load_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path


def status_command(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Show repository status and suggested next actions.

    This is the progressive discovery entry point - run with no args
    to see what to do next.
    """
    if explain:
        _show_explain(json_output)
        return

    root = find_lodestar_root()

    if root is None:
        _show_not_initialized(json_output)
        return

    try:
        spec = load_spec(root)
    except SpecNotFoundError:
        _show_not_initialized(json_output)
        return

    # Count tasks by status
    task_counts = dict.fromkeys(TaskStatus, 0)
    for task in spec.tasks.values():
        task_counts[task.status] += 1

    # Check runtime stats
    runtime_stats = {"agents": 0, "active_leases": 0, "total_messages": 0}
    agent_message_counts = {}
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        from lodestar.runtime.database import RuntimeDatabase

        db = RuntimeDatabase(runtime_path)
        runtime_stats = db.get_stats()
        agent_message_counts = db.get_agent_message_counts()

    # Get claimable tasks
    claimable = spec.get_claimable_tasks()

    # Build result
    result = {
        "initialized": True,
        "project": spec.project.model_dump(),
        "tasks": {
            "total": len(spec.tasks),
            "by_status": {s.value: c for s, c in task_counts.items()},
            "claimable": len(claimable),
        },
        "agents": {
            "registered": runtime_stats["agents"],
            "active_leases": runtime_stats["active_leases"],
        },
        "messages": {
            "total": runtime_stats["total_messages"],
            "by_agent": agent_message_counts,
        },
    }

    # Determine next actions
    next_actions = []
    if runtime_stats["agents"] == 0:
        next_actions.append(NEXT_ACTION_AGENT_JOIN)
    if claimable:
        next_actions.append(NEXT_ACTION_TASK_NEXT)
    next_actions.append(NEXT_ACTION_TASK_LIST)

    if json_output:
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
        return

    # Rich output
    console.print()

    # Project header
    console.print(
        Panel(
            f"[bold]{spec.project.name}[/bold]",
            subtitle=f"Branch: {spec.project.default_branch}",
            border_style="cyan",
        )
    )

    # Task summary table
    table = Table(show_header=True, header_style="bold", box=None)
    table.add_column("Status", style="dim")
    table.add_column("Count", justify="right")

    status_colors = {
        TaskStatus.TODO: "white",
        TaskStatus.READY: "cyan",
        TaskStatus.BLOCKED: "yellow",
        TaskStatus.DONE: "blue",
        TaskStatus.VERIFIED: "green",
        TaskStatus.DELETED: "red dim",
    }

    for status in TaskStatus:
        count = task_counts[status]
        if count > 0:
            table.add_row(
                f"[{status_colors[status]}]{status.value}[/{status_colors[status]}]",
                str(count),
            )

    console.print()
    console.print("[bold]Tasks[/bold]")
    console.print(table)

    # Agent summary
    console.print()
    console.print("[bold]Runtime[/bold]")
    console.print(f"  Agents registered: {runtime_stats['agents']}")
    console.print(f"  Active claims: {runtime_stats['active_leases']}")
    console.print(f"  Total messages: {runtime_stats['total_messages']}")
    if agent_message_counts:
        console.print("  Messages per agent:")
        for agent_id, count in sorted(agent_message_counts.items()):
            console.print(f"    {agent_id}: {count}")

    # Next actions
    console.print()
    console.print("[bold]Next Actions[/bold]")
    if runtime_stats["agents"] == 0:
        console.print("  [command]lodestar agent join[/command] - Register as an agent")
    if claimable:
        console.print(
            f"  [command]lodestar task next[/command] - "
            f"Get next claimable task ({len(claimable)} available)"
        )
    console.print("  [command]lodestar task list[/command] - See all tasks")
    console.print()


def _show_not_initialized(json_output: bool) -> None:
    """Show message when not initialized."""
    from lodestar.models.envelope import NextAction

    next_actions = [
        NextAction(
            intent="init",
            cmd="lodestar init",
            description="Initialize Lodestar in this repository",
        ),
        NEXT_ACTION_HELP,
    ]

    if json_output:
        print_json(
            Envelope.success(
                {"initialized": False},
                next_actions=next_actions,
            ).model_dump()
        )
    else:
        console.print()
        console.print("[warning]Not a Lodestar repository[/warning]")
        console.print()
        console.print("Run [command]lodestar init[/command] to initialize.")
        console.print()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar status",
        "purpose": "Show repository status and suggested next actions.",
        "shows": [
            "Project name and configuration",
            "Task counts by status",
            "Active agents and claims",
            "Suggested next commands",
        ],
        "notes": [
            "This is the progressive discovery entry point",
            "Running 'lodestar' with no args shows this",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar status[/info]")
        console.print()
        console.print("Show repository status and suggested next actions.")
        console.print()
