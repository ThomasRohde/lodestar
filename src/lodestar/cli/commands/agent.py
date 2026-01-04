"""lodestar agent commands - Agent identity and management."""

from __future__ import annotations

import typer

from lodestar.cli.formatters.brief_formatter import BriefFormat, format_task_brief
from lodestar.models.envelope import (
    NEXT_ACTION_STATUS,
    NEXT_ACTION_TASK_LIST,
    NEXT_ACTION_TASK_NEXT,
    Envelope,
)
from lodestar.models.runtime import Agent, AgentStatus
from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.loader import SpecNotFoundError, load_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

app = typer.Typer(
    help="Agent identity and management commands.",
    no_args_is_help=False,
)


def _get_status_style(status: AgentStatus) -> str:
    """Get Rich style for agent status."""
    styles = {
        AgentStatus.ACTIVE: "green",
        AgentStatus.IDLE: "yellow",
        AgentStatus.OFFLINE: "dim",
    }
    return styles.get(status, "white")


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
        console.print("  [command]lodestar agent find --capability <name>[/command]")
        console.print("      Find agents with a specific capability")
        console.print()
        console.print("  [command]lodestar agent brief --task <id>[/command]")
        console.print("      Get context for spawning a sub-agent on a task")
        console.print()
        console.print("[info]Typical workflow:[/info]")
        console.print(
            "  1. lodestar agent join --name 'My Agent' --role backend --capability python"
        )
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
    role: str | None = typer.Option(
        None,
        "--role",
        "-r",
        help="Agent role (e.g., 'code-review', 'testing', 'documentation').",
    ),
    capabilities: list[str] | None = typer.Option(
        None,
        "--capability",
        "-c",
        help="Agent capability (can be repeated, e.g., -c python -c testing).",
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
        role=role or "",
        capabilities=capabilities or [],
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
        "role": agent.role,
        "capabilities": agent.capabilities,
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
        if role:
            console.print(f"  Role: {role}")
        if capabilities:
            console.print(f"  Capabilities: {', '.join(capabilities)}")
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
    _agent: str | None = typer.Option(
        None,
        "--agent",
        hidden=True,
        help="Ignored parameter (accepted for CLI consistency).",
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
                "role": a.role,
                "status": a.get_status().value,
                "capabilities": a.capabilities,
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
                status = agent.get_status()
                status_style = _get_status_style(status)
                name_part = f" ({agent.display_name})" if agent.display_name else ""
                status_badge = f"[{status_style}]{status.value}[/{status_style}]"
                console.print(f"  [agent_id]{agent.agent_id}[/agent_id]{name_part} {status_badge}")
                if agent.role:
                    console.print(f"    Role: {agent.role}")
                if agent.capabilities:
                    console.print(f"    Capabilities: {', '.join(agent.capabilities)}")
                console.print(f"    Last seen: {agent.last_seen_at.isoformat()}")
                if agent.session_meta:
                    meta_str = ", ".join(f"{k}={v}" for k, v in agent.session_meta.items())
                    console.print(f"    Meta: {meta_str}")
        console.print()


@app.command(name="find")
def agent_find(
    capability: str | None = typer.Option(
        None,
        "--capability",
        "-c",
        help="Find agents with this capability.",
    ),
    role: str | None = typer.Option(
        None,
        "--role",
        "-r",
        help="Find agents with this role.",
    ),
    _agent: str | None = typer.Option(
        None,
        "--agent",
        hidden=True,
        help="Ignored parameter (accepted for CLI consistency).",
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
    """Find agents by capability or role.

    Search for agents that have specific capabilities or roles.
    Use this to discover which agents can help with particular tasks.
    """
    if explain:
        _show_explain_find(json_output)
        return

    if not capability and not role:
        if json_output:
            print_json(Envelope.error("Must specify --capability or --role to search").model_dump())
        else:
            console.print("[error]Must specify --capability or --role to search[/error]")
            console.print()
            console.print("Examples:")
            console.print("  [command]lodestar agent find --capability python[/command]")
            console.print("  [command]lodestar agent find --role code-review[/command]")
        raise typer.Exit(1)

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
        if capability:
            agents = db.find_agents_by_capability(capability)
        elif role:
            agents = db.find_agents_by_role(role)
        else:
            agents = []

    search_term = capability if capability else role
    search_type = "capability" if capability else "role"

    result = {
        "search": {
            "type": search_type,
            "term": search_term,
        },
        "agents": [
            {
                "agent_id": a.agent_id,
                "display_name": a.display_name,
                "role": a.role,
                "status": a.get_status().value,
                "capabilities": a.capabilities,
                "last_seen_at": a.last_seen_at.isoformat(),
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
            console.print(f"[muted]No agents found with {search_type} '{search_term}'[/muted]")
        else:
            console.print(f"[bold]Agents with {search_type} '{search_term}' ({len(agents)})[/bold]")
            console.print()
            for agent in agents:
                status = agent.get_status()
                status_style = _get_status_style(status)
                name_part = f" ({agent.display_name})" if agent.display_name else ""
                status_badge = f"[{status_style}]{status.value}[/{status_style}]"
                console.print(f"  [agent_id]{agent.agent_id}[/agent_id]{name_part} {status_badge}")
                if agent.role:
                    console.print(f"    Role: {agent.role}")
                if agent.capabilities:
                    console.print(f"    Capabilities: {', '.join(agent.capabilities)}")
                console.print(f"    Last seen: {agent.last_seen_at.isoformat()}")
        console.print()


@app.command(name="heartbeat")
def agent_heartbeat(
    agent_id: str | None = typer.Argument(None, help="Agent ID to update."),
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
    """Update agent heartbeat timestamp."""
    if explain:
        _show_explain_heartbeat(json_output)
        return

    if agent_id is None:
        console.print("[error]Missing argument 'AGENT_ID'[/error]")
        raise typer.Exit(1)

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
        help="Brief format: claude (XML tags), copilot (GitHub markdown), generic (plain text).",
    ),
    _agent: str | None = typer.Option(
        None,
        "--agent",
        hidden=True,
        help="Ignored parameter (accepted for CLI consistency).",
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
    """Get a concise brief for spawning a sub-agent on a task.

    Formats output differently based on the target agent type:
    \b
    - claude: XML-style tags optimized for Claude's structured prompts
    - copilot: GitHub-flavored markdown with headers and code fences
    - generic: Plain labeled sections (TASK, CONTEXT, CRITERIA, COMMANDS)
    \b
    Example:
        lodestar agent brief --task F001 --format copilot
    """
    if explain:
        _show_explain_brief(json_output)
        return

    # Validate format type
    valid_formats = [f.value for f in BriefFormat]
    if format_type not in valid_formats:
        valid = ", ".join(valid_formats)
        if json_output:
            print_json(
                Envelope.error(f"Invalid format '{format_type}'. Valid: {valid}").model_dump()
            )
        else:
            console.print(f"[error]Invalid format '{format_type}'. Valid: {valid}[/error]")
        raise typer.Exit(1)

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

    # Format the brief using the extracted formatter
    formatted_brief = format_task_brief(
        task_id=task.id,
        title=task.title,
        description=task.description or "",
        acceptance_criteria=task.acceptance_criteria,
        locks=task.locks,
        labels=task.labels,
        format_type=format_type,
    )

    # Build structured brief for JSON output
    brief = {
        "task_id": task.id,
        "title": task.title,
        "goal": task.description,
        "acceptance_criteria": task.acceptance_criteria,
        "locks": task.locks,
        "labels": task.labels,
        "format": format_type,
        "formatted_output": formatted_brief,
        "commands": {
            "claim": f"lodestar task claim {task.id} --agent <your-agent-id>",
            "report_progress": f"lodestar msg send --task {task.id} --from <your-agent-id> --text 'Progress update'",
            "mark_done": f"lodestar task done {task.id}",
        },
    }

    if json_output:
        print_json(Envelope.success(brief).model_dump())
    else:
        # Print the formatted brief directly (no Rich styling to preserve format)
        console.print()
        console.print(formatted_brief)
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
        "formats": {
            "claude": "XML-style tags (<task>, <context>, <acceptance_criteria>) optimized for Claude",
            "copilot": "GitHub-flavored markdown with ## headers, checkboxes, and code fences",
            "generic": "Plain text with labeled sections (TASK:, CONTEXT:, CRITERIA:, COMMANDS:)",
        },
        "examples": [
            "lodestar agent brief --task F001",
            "lodestar agent brief --task F001 --format claude",
            "lodestar agent brief --task F001 --format copilot",
        ],
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
        console.print("[info]Formats:[/info]")
        console.print("  claude  - XML-style tags for Claude's structured prompts")
        console.print("  copilot - GitHub markdown with headers and code fences")
        console.print("  generic - Plain text with labeled sections (default)")
        console.print()
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar agent brief --task F001[/command]")
        console.print("  [command]lodestar agent brief --task F001 --format claude[/command]")
        console.print("  [command]lodestar agent brief --task F001 --format copilot[/command]")
        console.print()


def _show_explain_find(json_output: bool) -> None:
    """Show find command explanation."""
    explanation = {
        "command": "lodestar agent find",
        "purpose": "Find agents by capability or role.",
        "examples": [
            "lodestar agent find --capability python",
            "lodestar agent find --capability testing",
            "lodestar agent find --role code-review",
        ],
        "notes": [
            "Search for agents that can help with specific tasks",
            "Use --capability to find agents with a specific skill",
            "Use --role to find agents with a specific job function",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar agent find[/info]")
        console.print()
        console.print("Find agents by capability or role.")
        console.print()
        console.print("Examples:")
        console.print("  [command]lodestar agent find --capability python[/command]")
        console.print("  [command]lodestar agent find --role code-review[/command]")
        console.print()


def _show_explain_heartbeat(json_output: bool) -> None:
    """Show heartbeat command explanation."""
    explanation = {
        "command": "lodestar agent heartbeat",
        "purpose": "Update agent heartbeat timestamp to show activity.",
        "examples": [
            "lodestar agent heartbeat A1234ABCD",
        ],
        "notes": [
            "Updates last_seen_at timestamp for the agent",
            "Keeps agent status as 'active' instead of 'idle' or 'offline'",
            "Call periodically during long-running work",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar agent heartbeat[/info]")
        console.print()
        console.print("Update agent heartbeat timestamp to show activity.")
        console.print()
        console.print("[info]Example:[/info]")
        console.print("  [command]lodestar agent heartbeat A1234ABCD[/command]")
        console.print()
