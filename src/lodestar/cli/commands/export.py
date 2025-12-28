"""lodestar export commands - Export repository state."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import typer

from lodestar.models.envelope import Envelope
from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.loader import SpecNotFoundError, load_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

app = typer.Typer(help="Export repository state commands.")


@app.command(name="snapshot")
def export_snapshot(
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    include_messages: bool = typer.Option(
        False,
        "--include-messages",
        help="Include messages in the snapshot.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Export a complete snapshot of spec and runtime state.

    Useful for CI validation, debugging, and auditing.

    \b
    Examples:
        lodestar export snapshot
        lodestar export snapshot --json > snapshot.json
        lodestar export snapshot --include-messages --json
    """
    if explain:
        _show_explain(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    try:
        spec = load_spec(root)
    except SpecNotFoundError:
        if json_output:
            print_json(Envelope.error("Spec not found").model_dump())
        else:
            console.print("[error]Spec not found[/error]")
        raise typer.Exit(1)

    # Build spec snapshot
    snapshot: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "spec": {
            "project": spec.project.model_dump(),
            "tasks": {
                task_id: {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status.value,
                    "priority": task.priority,
                    "depends_on": task.depends_on,
                    "labels": task.labels,
                    "locks": task.locks,
                    "acceptance_criteria": task.acceptance_criteria,
                }
                for task_id, task in spec.tasks.items()
            },
            "features": spec.features,
        },
        "runtime": None,
    }

    # Add runtime data if available
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        db = RuntimeDatabase(runtime_path)
        agents = db.list_agents()

        # Get all active leases
        active_leases = []
        for task_id in spec.tasks:
            lease = db.get_active_lease(task_id)
            if lease:
                active_leases.append(
                    {
                        "lease_id": lease.lease_id,
                        "task_id": lease.task_id,
                        "agent_id": lease.agent_id,
                        "expires_at": lease.expires_at.isoformat(),
                    }
                )

        snapshot["runtime"] = {
            "agents": [
                {
                    "agent_id": a.agent_id,
                    "display_name": a.display_name,
                    "last_seen_at": a.last_seen_at.isoformat(),
                    "session_meta": a.session_meta,
                }
                for a in agents
            ],
            "active_leases": active_leases,
        }

        # Add messages if requested
        if include_messages:
            messages = []
            for task_id in spec.tasks:
                thread = db.get_task_thread(task_id)
                for msg in thread:
                    messages.append(
                        {
                            "message_id": msg.message_id,
                            "created_at": msg.created_at.isoformat(),
                            "from_agent_id": msg.from_agent_id,
                            "to_type": msg.to_type.value,
                            "to_id": msg.to_id,
                            "text": msg.text,
                        }
                    )
            snapshot["runtime"]["messages"] = messages

    if json_output:
        print_json(Envelope.success(snapshot).model_dump())
    else:
        # Pretty print as JSON since it's complex data
        print_json(snapshot)


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar export snapshot",
        "purpose": "Export a complete snapshot of spec and runtime state.",
        "includes": [
            "Project configuration",
            "All tasks with their status and dependencies",
            "Registered agents",
            "Active task claims/leases",
            "Messages (with --include-messages)",
        ],
        "use_cases": [
            "CI validation and reporting",
            "Debugging coordination issues",
            "Audit and compliance",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar export snapshot[/info]")
        console.print()
        console.print("Export a complete snapshot of spec and runtime state.")
        console.print()
