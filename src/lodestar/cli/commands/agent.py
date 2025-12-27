"""lodestar agent commands - Agent identity and management."""

from __future__ import annotations

import typer

from lodestar.models.envelope import (
    NEXT_ACTION_STATUS,
    NEXT_ACTION_TASK_LIST,
    NEXT_ACTION_TASK_NEXT,
    Envelope,
)
from lodestar.models.runtime import Agent
from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.loader import SpecNotFoundError, load_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

app = typer.Typer(
    help="Agent identity and management commands.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def agent_callback(ctx: typer.Context) -> None:
    """Agent identity and management.

    Use these commands to register as an agent and manage your session.
    """
    if ctx.invoked_subcommand is None:
        # Show helpful workflow instead of error
        console.print()
        console.print("[bold]Agent Commands[/bold]")
        console.print()
        console.print("  [command]lodestar agent join[/command]")
        console.print("      Register as an agent and get your ID (do this first)")
        console.print()
        console.print("  [command]lodestar agent list[/command]")
        console.print("      List all registered agents")
        console.print()
        console.print("  [command]lodestar agent brief --task <id>[/command]")
        console.print("      Get context for spawning a sub-agent on a task")
        console.print()
        console.print("[info]Typical workflow:[/info]")
        console.print("  1. lodestar agent join --name 'My Agent'")
        console.print("  2. Save the agent ID (e.g., A1234ABCD)")
        console.print("  3. Use this ID in task claim: --agent A1234ABCD")
        console.print()


@app.command(name="join")
def agent_join(
    name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Display name for this agent.",
    ),
    model: str | None = typer.Option(
        None,
        "--model",
        "-m",
        help="Model name (e.g., claude-3.5-sonnet).",
    ),
    tool: str | None = typer.Option(
        None,
        "--tool",
        "-t",
        help="Tool name (e.g., claude-code, copilot).",
    ),
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
    """Register as an agent and get your identity.

    This is the canonical entrypoint for agents. Run this first to get
    your agent_id and see suggested next actions.
    """
    if explain:
        _show_explain_join(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
            console.print("Run [command]lodestar init[/command] first.")
        raise typer.Exit(1)

    # Create runtime database if needed
    db = RuntimeDatabase(get_runtime_db_path(root))

    # Build session metadata
    session_meta = {}
    if model:
        session_meta["model"] = model
    if tool:
        session_meta["tool"] = tool

    # Create and register agent
    agent = Agent(
        display_name=name or "",
        session_meta=session_meta,
    )
    db.register_agent(agent)

    # Get spec for context
    try:
        spec = load_spec(root)
        claimable_count = len(spec.get_claimable_tasks())
    except SpecNotFoundError:
        claimable_count = 0

    # Build response
    result = {
        "agent_id": agent.agent_id,
        "display_name": agent.display_name,
        "registered_at": agent.created_at.isoformat(),
        "session_meta": session_meta,
    }

    next_actions = [
        NEXT_ACTION_TASK_NEXT,
        NEXT_ACTION_TASK_LIST,
        NEXT_ACTION_STATUS,
    ]

    if json_output:
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
    else:
        console.print()
        console.print(
            f"[success]Registered as agent[/success] [agent_id]{agent.agent_id}[/agent_id]"
        )
        if name:
            console.print(f"  Name: {name}")
        console.print()
        console.print("[info]Next steps:[/info]")
        console.print(
            f"  [command]lodestar task next[/command] - Get next task ({claimable_count} claimable)"
        )
        console.print("  [command]lodestar task list[/command] - See all tasks")
        console.print("  [command]lodestar status[/command] - Repository overview")
        console.print()


@app.command(name="list")
def agent_list(
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
    """List all registered agents."""
    if explain:
        _show_explain_list(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        agents = []
    else:
        db = RuntimeDatabase(runtime_path)
        agents = db.list_agents()

    result = {
        "agents": [
            {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "last_seen_at": a.last_seen_at.isoformat(),
                "session_meta": a.session_meta,
            }
            for a in agents
        ],
        "count": len(agents),
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        if not agents:
            console.print("[muted]No agents registered yet.[/muted]")
            console.print("Run [command]lodestar agent join[/command] to register.")
        else:
            console.print(f"[bold]Agents ({len(agents)})[/bold]")
            console.print()
            for agent in agents:
                name_part = f" ({agent.display_name})" if agent.display_name else ""
                console.print(f"  [agent_id]{agent.agent_id}[/agent_id]{name_part}")
                console.print(f"    Last seen: {agent.last_seen_at.isoformat()}")
                if agent.session_meta:
                    meta_str = ", ".join(f"{k}={v}" for k, v in agent.session_meta.items())
                    console.print(f"    Meta: {meta_str}")
        console.print()


@app.command(name="heartbeat")
def agent_heartbeat(
    agent_id: str = typer.Argument(..., help="Agent ID to update."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Update agent heartbeat timestamp."""
    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        if json_output:
            print_json(Envelope.error("Agent not found").model_dump())
        else:
            console.print("[error]Agent not found[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(runtime_path)
    success = db.update_heartbeat(agent_id)

    if not success:
        if json_output:
            print_json(Envelope.error(f"Agent {agent_id} not found").model_dump())
        else:
            console.print(f"[error]Agent {agent_id} not found[/error]")
        raise typer.Exit(1)

    if json_output:
        print_json(Envelope.success({"agent_id": agent_id, "updated": True}).model_dump())
    else:
        console.print(f"[success]Heartbeat updated for {agent_id}[/success]")


@app.command(name="brief")
def agent_brief(
    task_id: str = typer.Option(..., "--task", "-t", help="Task ID to get brief for."),
    format_type: str = typer.Option(
        "generic",
        "--format",
        "-f",
        help="Brief format: claude, copilot, generic.",
    ),
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
    """Get a concise brief for spawning a sub-agent on a task."""
    if explain:
        _show_explain_brief(json_output)
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

    task = spec.get_task(task_id)
    if task is None:
        if json_output:
            print_json(Envelope.error(f"Task {task_id} not found").model_dump())
        else:
            console.print(f"[error]Task {task_id} not found[/error]")
        raise typer.Exit(1)

    # Build brief
    brief = {
        "task_id": task.id,
        "title": task.title,
        "goal": task.description,
        "acceptance_criteria": task.acceptance_criteria,
        "locks": task.locks,
        "labels": task.labels,
        "commands": {
            "claim": f"lodestar task claim {task.id} --agent <your-agent-id>",
            "report_progress": f"lodestar msg send --to task:{task.id} --from <your-agent-id> --text 'Progress update'",
            "mark_done": f"lodestar task done {task.id}",
        },
    }

    if json_output:
        print_json(Envelope.success(brief).model_dump())
    else:
        console.print()
        console.print(f"[bold]Brief for {task.id}[/bold]")
        console.print()
        console.print(f"[info]Goal:[/info] {task.description or task.title}")
        console.print()
        if task.acceptance_criteria:
            console.print("[info]Acceptance Criteria:[/info]")
            for criterion in task.acceptance_criteria:
                console.print(f"  - {criterion}")
            console.print()
        if task.locks:
            console.print("[info]Owned paths:[/info]")
            for lock in task.locks:
                console.print(f"  - {lock}")
            console.print()
        console.print("[info]Commands (replace <your-agent-id>):[/info]")
        console.print(f"  Claim:  [command]lodestar task claim {task.id} --agent <id>[/command]")
        console.print(
            f"  Report: [command]lodestar msg send --to task:{task.id} --from <id> --text '...'[/command]"
        )
        console.print(f"  Done:   [command]lodestar task done {task.id}[/command]")
        console.print()
        console.print("[muted]Get your agent ID from 'lodestar agent join'[/muted]")
        console.print()


def _show_explain_join(json_output: bool) -> None:
    """Show join command explanation."""
    explanation = {
        "command": "lodestar agent join",
        "purpose": "Register as an agent and receive your identity.",
        "returns": [
            "agent_id - Your unique identifier for all operations",
            "Suggested next actions based on current state",
        ],
        "notes": [
            "This is the canonical entrypoint for agents",
            "Agent IDs persist across sessions",
            "Use --name and --model to add metadata",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar agent join[/info]")
        console.print()
        console.print("Register as an agent and receive your identity.")
        console.print()


def _show_explain_list(json_output: bool) -> None:
    """Show list command explanation."""
    explanation = {
        "command": "lodestar agent list",
        "purpose": "List all registered agents.",
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar agent list[/info]")
        console.print()
        console.print("List all registered agents.")
        console.print()


def _show_explain_brief(json_output: bool) -> None:
    """Show brief command explanation."""
    explanation = {
        "command": "lodestar agent brief",
        "purpose": "Get a concise brief for spawning a sub-agent on a task.",
        "returns": [
            "Task goal and acceptance criteria",
            "Allowed file paths (locks)",
            "Commands for claiming, reporting, and completing",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar agent brief[/info]")
        console.print()
        console.print("Get a concise brief for spawning a sub-agent on a task.")
        console.print()
