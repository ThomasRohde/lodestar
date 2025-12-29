"""lodestar task commands - Task management and scheduling."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import typer

from lodestar.cli.formatters.task_formatter import (
    format_deleted_tasks,
    format_graph,
    format_next_tasks,
    format_task_detail,
    format_task_list,
)
from lodestar.core.task_service import (
    compute_cascade_delete,
    detect_lock_conflicts,
    get_unclaimed_claimable_tasks,
)
from lodestar.models.envelope import Envelope, NextAction
from lodestar.models.runtime import Lease
from lodestar.models.spec import PrdContext, PrdRef, Task, TaskStatus
from lodestar.runtime.database import RuntimeDatabase
from lodestar.runtime.engine import (
    create_runtime_engine,
    create_session_factory,
    get_session,
)
from lodestar.runtime.event_types import EventType
from lodestar.runtime.repositories.event_repo import log_event
from lodestar.spec.dag import validate_dag
from lodestar.spec.loader import SpecNotFoundError, load_spec, save_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path
from lodestar.util.prd import check_prd_drift, extract_prd_section, truncate_to_budget
from lodestar.util.time import format_duration, parse_duration

app = typer.Typer(
    help="Task management and scheduling commands.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def task_callback(ctx: typer.Context) -> None:
    """Task management and scheduling.

    Use these commands to find, claim, and complete tasks.
    """
    if ctx.invoked_subcommand is None:
        # Show helpful workflow instead of error
        console.print()
        console.print("[bold]Task Commands[/bold]")
        console.print()
        console.print("[info]Finding work:[/info]")
        console.print("  [command]lodestar task next[/command]       Find claimable tasks")
        console.print("  [command]lodestar task list[/command]       List all tasks")
        console.print("  [command]lodestar task show <id>[/command]  View task details")
        console.print()
        console.print("[info]Working on tasks:[/info]")
        console.print("  [command]lodestar task claim <id> --agent <agent-id>[/command]")
        console.print("      Claim a task (required before working)")
        console.print()
        console.print("  [command]lodestar task renew <id>[/command]")
        console.print("      Extend your lease (do this every 10-15 min)")
        console.print()
        console.print("  [command]lodestar task release <id>[/command]")
        console.print("      Release if you can't complete")
        console.print()
        console.print("[info]Completing tasks:[/info]")
        console.print("  [command]lodestar task done <id>[/command]    Mark as done")
        console.print("  [command]lodestar task verify <id>[/command]  Verify complete")
        console.print()
        console.print("[info]Creating tasks (planning agents):[/info]")
        console.print("  [command]lodestar task create --title '...' --description '...'[/command]")
        console.print("      Write detailed descriptions: WHAT, WHERE, WHY, ACCEPT, CONTEXT")
        console.print()
        console.print("[muted]Tip: Get your agent ID from 'lodestar agent join'[/muted]")
        console.print()


@app.command(name="list")
def task_list(
    status_filter: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (todo, ready, blocked, done, verified, deleted).",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label.",
    ),
    include_deleted: bool = typer.Option(
        False,
        "--include-deleted",
        help="Include deleted tasks in the list.",
    ),
    agent: str | None = typer.Option(
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
    """List all tasks with optional filtering.

    By default, deleted tasks are hidden. Use --include-deleted to show them.
    """
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

    try:
        spec = load_spec(root)
    except SpecNotFoundError:
        if json_output:
            print_json(Envelope.error("Spec not found").model_dump())
        else:
            console.print("[error]Spec not found[/error]")
        raise typer.Exit(1)

    # Filter tasks
    tasks = list(spec.tasks.values())

    # Filter out deleted tasks by default (unless --include-deleted is used or filtering by status=deleted)
    if not include_deleted and (not status_filter or status_filter.lower() != "deleted"):
        tasks = [t for t in tasks if t.status != TaskStatus.DELETED]

    if status_filter:
        try:
            filter_status = TaskStatus(status_filter.lower())
            tasks = [t for t in tasks if t.status == filter_status]
        except ValueError:
            if json_output:
                print_json(Envelope.error(f"Invalid status: {status_filter}").model_dump())
            else:
                console.print(f"[error]Invalid status: {status_filter}[/error]")
            raise typer.Exit(1)

    if label:
        tasks = [t for t in tasks if label in t.labels]

    # Sort by priority then ID
    tasks.sort(key=lambda t: (t.priority, t.id))

    # Get active leases
    leases: dict[str, Lease] = {}
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        db = RuntimeDatabase(runtime_path)
        for task in tasks:
            lease = db.get_active_lease(task.id)
            if lease:
                leases[task.id] = lease

    format_task_list(tasks, leases, json_output)


@app.command(name="show")
def task_show(
    task_id: str = typer.Argument(..., help="Task ID to show."),
    agent: str | None = typer.Option(
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
    """Show detailed information about a task."""
    if explain:
        _show_explain_show(json_output)
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

    # Check for active lease and communication context
    lease = None
    message_count = 0
    message_agents = []
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        db = RuntimeDatabase(runtime_path)
        lease = db.get_active_lease(task_id)
        message_count = db.get_task_message_count(task_id)
        message_agents = db.get_task_message_agents(task_id)

    # Determine claimability
    verified = spec.get_verified_tasks()
    claimable = task.is_claimable(verified) and lease is None

    format_task_detail(task, lease, message_count, message_agents, claimable, json_output)


@app.command(name="context")
def task_context(
    task_id: str = typer.Argument(..., help="Task ID to get context for."),
    max_chars: int = typer.Option(
        1000,
        "--max-chars",
        "-m",
        help="Maximum characters for context output.",
    ),
    agent: str | None = typer.Option(
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
    """Get PRD context for a task.

    Returns the task's PRD references, frozen excerpt, and live PRD sections
    (if available). Respects --max-chars budget for context window management.
    """
    if explain:
        _show_explain_context(json_output)
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

    # Build context bundle
    context_bundle: dict[str, Any] = {
        "task_id": task_id,
        "title": task.title,
        "description": task.description,
    }

    warnings = []
    prd_sections = []

    if task.prd:
        context_bundle["prd_source"] = task.prd.source
        context_bundle["prd_refs"] = [ref.model_dump() for ref in task.prd.refs]

        # Include frozen excerpt if available
        if task.prd.excerpt:
            context_bundle["prd_excerpt"] = task.prd.excerpt

        # Check for PRD drift
        if task.prd.prd_hash:
            prd_path = root / task.prd.source
            if prd_path.exists():
                try:
                    if check_prd_drift(task.prd.prd_hash, prd_path):
                        warnings.append(
                            f"PRD has changed since task creation. "
                            f"Review {task.prd.source} for updates."
                        )
                except Exception:
                    pass  # Ignore hash check errors

        # Try to extract live PRD sections
        prd_path = root / task.prd.source
        if prd_path.exists():
            for ref in task.prd.refs:
                try:
                    lines_tuple: tuple[int, int] | None = None
                    if ref.lines and len(ref.lines) == 2:
                        lines_tuple = (ref.lines[0], ref.lines[1])
                    section = extract_prd_section(
                        prd_path,
                        anchor=ref.anchor,
                        lines=lines_tuple,
                    )
                    prd_sections.append(
                        {
                            "anchor": ref.anchor,
                            "content": section,
                        }
                    )
                except (ValueError, FileNotFoundError):
                    pass  # Section not found

    if prd_sections:
        context_bundle["prd_sections"] = prd_sections

    # Truncate to budget
    total_content = task.description or ""
    if task.prd and task.prd.excerpt:
        total_content += "\n" + task.prd.excerpt
    for sec in prd_sections:
        total_content += "\n" + sec["content"]

    truncated_content = truncate_to_budget(total_content, max_chars)
    context_bundle["content"] = truncated_content
    context_bundle["truncated"] = len(total_content) > max_chars

    if json_output:
        print_json(Envelope.success(context_bundle, warnings=warnings).model_dump())
    else:
        console.print()
        console.print(f"[bold]Context for[/bold] [task_id]{task_id}[/task_id]")
        console.print()

        if warnings:
            for warning in warnings:
                console.print(f"[warning]⚠ {warning}[/warning]")
            console.print()

        if task.prd:
            console.print(f"[muted]PRD Source:[/muted] {task.prd.source}")
            if task.prd.refs:
                refs_str = ", ".join(ref.anchor for ref in task.prd.refs)
                console.print(f"[muted]References:[/muted] {refs_str}")
            console.print()

        console.print("[info]Content:[/info]")
        console.print(truncated_content)

        if context_bundle["truncated"]:
            console.print()
            console.print(f"[muted](Truncated to {max_chars} chars)[/muted]")

        console.print()


def _show_explain_context(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task context",
        "purpose": "Get PRD context for a task.",
        "returns": [
            "Task description",
            "PRD references and excerpts",
            "Live PRD sections if available",
        ],
        "notes": [
            "Respects --max-chars budget for context window management",
            "Warns if PRD has changed since task creation (drift detection)",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task context[/info]\n")
        console.print("Get PRD context for a task.\n")


@app.command(name="create")
def task_create(
    title: str | None = typer.Option(None, "--title", "-t", help="Task title."),
    task_id: str | None = typer.Option(
        None,
        "--id",
        help="Task ID (auto-generated if not provided).",
    ),
    description: str = typer.Option(
        "",
        "--description",
        "-d",
        help="Task description. Include: WHAT (goal), WHERE (files), WHY (context), ACCEPT (criteria).",
    ),
    priority: int = typer.Option(100, "--priority", "-p", help="Priority (lower = higher)."),
    status: str = typer.Option("ready", "--status", "-s", help="Initial status."),
    depends_on: list[str] | None = typer.Option(
        None,
        "--depends-on",
        help="Task IDs this depends on.",
    ),
    labels: list[str] | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Labels for the task.",
    ),
    prd_source: str | None = typer.Option(
        None,
        "--prd-source",
        help="Path to PRD file (e.g., PRD.md).",
    ),
    prd_refs: list[str] | None = typer.Option(
        None,
        "--prd-ref",
        help="PRD section anchors (e.g., #task-claiming). Can specify multiple.",
    ),
    prd_excerpt: str | None = typer.Option(
        None,
        "--prd-excerpt",
        help="Frozen PRD excerpt to attach to task.",
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
    """Create a new task.

    Write detailed descriptions so executing agents have context:

    \b
    Example:
        lodestar task create --id F001 --title "Add feature" \\
            --description "WHAT: Add X. WHERE: src/x/. ACCEPT: tests pass" \\
            --depends-on F000 --label feature
    """
    if explain:
        _show_explain_create(json_output)
        return

    if title is None:
        console.print("[error]Missing option '--title'[/error]")
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

    # Generate task ID if not provided
    if task_id is None:
        existing_ids = [int(t[1:]) for t in spec.tasks if t.startswith("T") and t[1:].isdigit()]
        next_num = max(existing_ids, default=0) + 1
        task_id = f"T{next_num:03d}"

    # Check for duplicate
    if task_id in spec.tasks:
        if json_output:
            print_json(Envelope.error(f"Task {task_id} already exists").model_dump())
        else:
            console.print(f"[error]Task {task_id} already exists[/error]")
        raise typer.Exit(1)

    # Validate status
    try:
        task_status = TaskStatus(status.lower())
    except ValueError:
        if json_output:
            print_json(Envelope.error(f"Invalid status: {status}").model_dump())
        else:
            console.print(f"[error]Invalid status: {status}[/error]")
        raise typer.Exit(1)

    # Check dependencies exist
    if depends_on:
        missing = [d for d in depends_on if d not in spec.tasks]
        if missing:
            if json_output:
                print_json(Envelope.error(f"Unknown dependencies: {missing}").model_dump())
            else:
                console.print(f"[error]Unknown dependencies: {missing}[/error]")
            raise typer.Exit(1)

    # Build PRD context if provided
    prd_context = None
    if prd_source:
        import contextlib

        from lodestar.util.prd import compute_prd_hash

        prd_path = root / prd_source
        prd_hash = None
        if prd_path.exists():
            with contextlib.suppress(Exception):
                prd_hash = compute_prd_hash(prd_path)

        prd_context = PrdContext(
            source=prd_source,
            refs=[PrdRef(anchor=ref) for ref in (prd_refs or [])],
            excerpt=prd_excerpt,
            prd_hash=prd_hash,
        )

    # Create task
    task = Task(
        id=task_id,
        title=title,
        description=description,
        priority=priority,
        status=task_status,
        depends_on=depends_on or [],
        labels=labels or [],
        prd=prd_context,
    )

    spec.tasks[task_id] = task

    # Validate DAG
    dag_result = validate_dag(spec)
    if not dag_result.valid:
        if json_output:
            print_json(Envelope.error(f"Invalid dependencies: {dag_result.errors}").model_dump())
        else:
            console.print("[error]Invalid dependencies:[/error]")
            for error in dag_result.errors:
                console.print(f"  {error}")
        raise typer.Exit(1)

    # Save spec
    save_spec(spec, root)

    result = task.model_dump()
    result["status"] = task.status.value
    result["created_at"] = task.created_at.isoformat()
    result["updated_at"] = task.updated_at.isoformat()

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        console.print(f"[success]Created task[/success] [task_id]{task_id}[/task_id]")
        console.print(f"  Title: {title}")
        console.print(f"  Status: {task_status.value}")
        console.print()


@app.command(name="update")
def task_update(
    task_id: str | None = typer.Argument(None, help="Task ID to update."),
    title: str | None = typer.Option(None, "--title", "-t", help="New task title."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description."),
    priority: int | None = typer.Option(None, "--priority", "-p", help="New priority."),
    status: str | None = typer.Option(None, "--status", "-s", help="New status."),
    add_label: list[str] | None = typer.Option(None, "--add-label", help="Add a label."),
    remove_label: list[str] | None = typer.Option(None, "--remove-label", help="Remove a label."),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format."),
    explain: bool = typer.Option(False, "--explain", help="Show what this command does."),
) -> None:
    """Update an existing task's properties."""
    if explain:
        _show_explain_update(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
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

    updated_fields = []

    if title is not None:
        task.title = title
        updated_fields.append("title")

    if description is not None:
        task.description = description
        updated_fields.append("description")

    if priority is not None:
        task.priority = priority
        updated_fields.append("priority")

    if status is not None:
        try:
            task.status = TaskStatus(status.lower())
            updated_fields.append("status")
        except ValueError:
            if json_output:
                print_json(Envelope.error(f"Invalid status: {status}").model_dump())
            else:
                console.print(f"[error]Invalid status: {status}[/error]")
            raise typer.Exit(1)

    if add_label:
        for label in add_label:
            if label not in task.labels:
                task.labels.append(label)
        updated_fields.append("labels")

    if remove_label:
        task.labels = [lb for lb in task.labels if lb not in remove_label]
        updated_fields.append("labels")

    if not updated_fields:
        if json_output:
            print_json(Envelope.error("No updates specified").model_dump())
        else:
            console.print("[warning]No updates specified[/warning]")
        raise typer.Exit(1)

    task.updated_at = datetime.now(UTC)
    save_spec(spec, root)

    result = task.model_dump()
    result["status"] = task.status.value
    result["updated_at"] = task.updated_at.isoformat()
    result["updated_fields"] = updated_fields

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Updated task {task_id}[/success]")
        console.print(f"  Fields: {', '.join(updated_fields)}")


@app.command(name="next")
def task_next(
    count: int = typer.Option(1, "--count", "-n", help="Number of tasks to return."),
    agent: str | None = typer.Option(
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
    """Get the next claimable task(s).

    Returns tasks that are ready and have all dependencies satisfied.
    Tasks are sorted by priority.
    """
    if explain:
        _show_explain_next(json_output)
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

    # Get unclaimed claimable tasks using service
    db = RuntimeDatabase(get_runtime_db_path(root))
    claimable = get_unclaimed_claimable_tasks(spec, db)

    # Take requested count
    tasks = claimable[:count]

    format_next_tasks(tasks, len(claimable), json_output)


@app.command(name="claim")
def task_claim(
    task_id: str | None = typer.Argument(None, help="Task ID to claim."),
    agent_id: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="(REQUIRED) Your agent ID. Get it from 'lodestar agent join'.",
    ),
    ttl: str = typer.Option("15m", "--ttl", "-t", help="Lease duration (e.g., 15m, 1h)."),
    no_context: bool = typer.Option(
        False,
        "--no-context",
        help="Don't include PRD context in output.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Bypass lock conflict warnings.",
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
    """Claim a task with a lease.

    Claims are time-limited (default 15min) and auto-expire.
    Renew with 'lodestar task renew <id>' before expiry.

    Example:
        lodestar task claim F001 --agent A1234ABCD
    """
    if explain:
        _show_explain_claim(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
        raise typer.Exit(1)

    if agent_id is None:
        console.print("[error]Missing option '--agent'[/error]")
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

    # Check task exists
    task = spec.get_task(task_id)
    if task is None:
        if json_output:
            print_json(Envelope.error(f"Task {task_id} not found").model_dump())
        else:
            console.print(f"[error]Task {task_id} not found[/error]")
        raise typer.Exit(1)

    # Check task is claimable
    verified = spec.get_verified_tasks()
    if not task.is_claimable(verified):
        if json_output:
            print_json(
                Envelope.error(
                    f"Task {task_id} is not claimable (status: {task.status.value})"
                ).model_dump()
            )
        else:
            console.print(f"[error]Task {task_id} is not claimable[/error]")
            console.print(f"  Status: {task.status.value}")
            if task.depends_on:
                unmet = [d for d in task.depends_on if d not in verified]
                if unmet:
                    console.print(f"  Unmet dependencies: {', '.join(unmet)}")
        raise typer.Exit(1)

    # Parse TTL
    try:
        duration = parse_duration(ttl)
    except ValueError as e:
        if json_output:
            print_json(Envelope.error(str(e)).model_dump())
        else:
            console.print(f"[error]{e}[/error]")
        raise typer.Exit(1)

    # Create lease
    db = RuntimeDatabase(get_runtime_db_path(root))

    # Check for lock conflicts with actively-leased tasks using service
    lock_warnings: list[str] = []
    if task.locks and not force:
        lock_warnings = detect_lock_conflicts(task, spec, db)

    lease = Lease(
        task_id=task_id,
        agent_id=agent_id,
        expires_at=datetime.now(UTC) + duration,
    )

    created_lease = db.create_lease(lease)

    if created_lease is None:
        # Task already claimed
        existing = db.get_active_lease(task_id)
        if json_output:
            print_json(
                Envelope.error(
                    f"Task {task_id} already claimed by {existing.agent_id if existing else 'unknown'}"
                ).model_dump()
            )
        else:
            console.print(f"[error]Task {task_id} already claimed[/error]")
            if existing:
                remaining = existing.expires_at - datetime.now(UTC)
                console.print(f"  Claimed by: {existing.agent_id}")
                console.print(f"  Expires in: {format_duration(remaining)}")
        raise typer.Exit(1)

    result: dict[str, Any] = {
        "lease_id": created_lease.lease_id,
        "task_id": task_id,
        "agent_id": agent_id,
        "expires_at": created_lease.expires_at.isoformat(),
        "ttl_seconds": int(duration.total_seconds()),
    }

    # Build context bundle unless --no-context specified
    warnings: list[str] = lock_warnings.copy()  # Start with lock conflict warnings
    if not no_context:
        context: dict[str, Any] = {
            "title": task.title,
            "description": task.description,
        }
        if task.prd:
            context["prd_source"] = task.prd.source
            if task.prd.excerpt:
                context["prd_excerpt"] = truncate_to_budget(task.prd.excerpt, 1000)

            # Check for PRD drift
            if task.prd.prd_hash:
                prd_path = root / task.prd.source
                if prd_path.exists():
                    try:
                        if check_prd_drift(task.prd.prd_hash, prd_path):
                            warnings.append(
                                f"PRD has changed since task creation. "
                                f"Review {task.prd.source} for updates."
                            )
                    except Exception:
                        pass  # Ignore hash check errors
        result["context"] = context

    next_actions = [
        NextAction(
            intent="task.context",
            cmd=f"lodestar task context {task_id}",
            description="Get full PRD context",
        ),
        NextAction(
            intent="task.show",
            cmd=f"lodestar task show {task_id}",
            description="View task details",
        ),
        NextAction(
            intent="task.renew",
            cmd=f"lodestar task renew {task_id} --agent {agent_id}",
            description="Renew your claim",
        ),
        NextAction(
            intent="task.done",
            cmd=f"lodestar task done {task_id}",
            description="Mark task as done",
        ),
    ]

    if json_output:
        print_json(
            Envelope.success(result, next_actions=next_actions, warnings=warnings).model_dump()
        )
    else:
        console.print()
        console.print(f"[success]Claimed task[/success] [task_id]{task_id}[/task_id]")
        console.print(f"  Lease: {created_lease.lease_id}")
        console.print(f"  Expires in: {format_duration(duration)}")

        if warnings:
            console.print()
            for warning in warnings:
                console.print(f"[warning]⚠ {warning}[/warning]")
            if lock_warnings:
                console.print()
                console.print("[muted]Use --force to bypass lock conflict warnings[/muted]")

        if not no_context:
            console.print()
            console.print("[info]Task Context:[/info]")
            console.print(f"  {task.title}")
            if task.description:
                desc_preview = (
                    task.description[:200] + "..."
                    if len(task.description) > 200
                    else task.description
                )
                console.print(f"  {desc_preview}")
            if task.prd and task.prd.source:
                console.print(f"  [muted]PRD: {task.prd.source}[/muted]")

        console.print()
        console.print("[info]Remember to:[/info]")
        console.print(
            f"  - Renew with [command]lodestar task renew {task_id}[/command] before expiry"
        )
        console.print(
            f"  - Mark done with [command]lodestar task done {task_id}[/command] when complete"
        )
        console.print()


@app.command(name="renew")
def task_renew(
    task_id: str | None = typer.Argument(None, help="Task ID to renew."),
    agent_id: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="(REQUIRED) Your agent ID. Same ID used when claiming.",
    ),
    ttl: str = typer.Option("15m", "--ttl", "-t", help="New lease duration."),
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
    """Renew your claim on a task.

    Extend the lease before it expires (default 15min).
    Only the agent who claimed the task can renew it.

    \b
    Examples:
        lodestar task renew F001 --agent A1234ABCD
        lodestar task renew F001 --agent A1234ABCD --ttl 30m
    """
    if explain:
        _show_explain_renew(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
        raise typer.Exit(1)

    if agent_id is None:
        console.print("[error]Missing option '--agent'[/error]")
        raise typer.Exit(1)

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Parse TTL
    try:
        duration = parse_duration(ttl)
    except ValueError as e:
        if json_output:
            print_json(Envelope.error(str(e)).model_dump())
        else:
            console.print(f"[error]{e}[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(get_runtime_db_path(root))

    # Get current lease
    lease = db.get_active_lease(task_id)
    if lease is None:
        if json_output:
            print_json(Envelope.error(f"No active lease for {task_id}").model_dump())
        else:
            console.print(f"[error]No active lease for {task_id}[/error]")
        raise typer.Exit(1)

    if lease.agent_id != agent_id:
        if json_output:
            print_json(
                Envelope.error(
                    f"Task {task_id} is claimed by {lease.agent_id}, not {agent_id}"
                ).model_dump()
            )
        else:
            console.print(f"[error]Task {task_id} is claimed by {lease.agent_id}[/error]")
        raise typer.Exit(1)

    # Renew
    new_expires = datetime.now(UTC) + duration
    success = db.renew_lease(lease.lease_id, new_expires, agent_id)

    if not success:
        if json_output:
            print_json(Envelope.error("Failed to renew lease").model_dump())
        else:
            console.print("[error]Failed to renew lease[/error]")
        raise typer.Exit(1)

    result = {
        "task_id": task_id,
        "lease_id": lease.lease_id,
        "new_expires_at": new_expires.isoformat(),
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Renewed lease for {task_id}[/success]")
        console.print(f"  Expires in: {format_duration(duration)}")


@app.command(name="release")
def task_release(
    task_id: str | None = typer.Argument(None, help="Task ID to release."),
    agent_id: str | None = typer.Option(
        None,
        "--agent",
        "-a",
        help="Your agent ID. If omitted, infers from active lease.",
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
    """Release your claim on a task.

    Frees the task for others to claim. Use this when you're blocked
    or can't complete the task. Consider leaving a message with context.

    Note: You don't need to release after 'task done' or 'task verify' -
    those commands auto-release the lease.

    \b
    Examples:
        lodestar task release F001
        lodestar task release F001 --agent A1234ABCD
        lodestar msg send --to task:F001 --from A1234ABCD --text 'Blocked on X'
    """
    if explain:
        _show_explain_release(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
        raise typer.Exit(1)

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(get_runtime_db_path(root))

    # If agent_id not provided, infer from active lease
    if agent_id is None:
        active_lease = db.get_active_lease(task_id)
        if active_lease is None:
            if json_output:
                print_json(Envelope.error(f"No active lease for {task_id}").model_dump())
            else:
                console.print(f"[error]No active lease for {task_id}[/error]")
            raise typer.Exit(1)
        agent_id = active_lease.agent_id

    success = db.release_lease(task_id, agent_id)

    if not success:
        if json_output:
            print_json(Envelope.error(f"No active lease for {task_id} by {agent_id}").model_dump())
        else:
            console.print(f"[error]No active lease for {task_id}[/error]")
        raise typer.Exit(1)

    if json_output:
        print_json(Envelope.success({"task_id": task_id, "released": True}).model_dump())
    else:
        console.print(f"[success]Released claim on {task_id}[/success]")


@app.command(name="done")
def task_done(
    task_id: str | None = typer.Argument(None, help="Task ID to mark as done."),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Agent ID (auto-detects from active lease if omitted).",
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
    """Mark a task as done.

    Sets the task status to 'done'. After review, use 'task verify'
    to fully complete the task and unblock dependents.

    \b
    Example:
        lodestar task done F001
        lodestar task done F001 --agent A1234ABCD
    """
    if explain:
        _show_explain_done(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
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

    # Auto-detect agent from active lease if not provided
    if agent is None:
        db_path = get_runtime_db_path(root)
        db = RuntimeDatabase(db_path)
        lease = db.get_active_lease(task_id)
        if lease:
            agent = lease.agent_id

    # Update task status and tracking fields
    task.status = TaskStatus.DONE
    task.updated_at = datetime.now(UTC)
    if agent:
        task.completed_by = agent
        task.completed_at = datetime.now(UTC)
    save_spec(spec, root)

    # Log event to runtime database
    db_path = get_runtime_db_path(root)
    engine = create_runtime_engine(db_path)
    session_factory = create_session_factory(engine)
    with get_session(session_factory) as session:
        log_event(session, EventType.TASK_DONE, agent_id=agent, task_id=task_id)
    engine.dispose()

    result = {"task_id": task_id, "status": "done"}
    if agent:
        result["completed_by"] = agent

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Marked {task_id} as done[/success]")
        console.print(f"Run [command]lodestar task verify {task_id}[/command] after review")


@app.command(name="verify")
def task_verify(
    task_id: str | None = typer.Argument(None, help="Task ID to verify."),
    agent: str | None = typer.Option(
        None,
        "--agent",
        help="Agent ID (auto-detects from active lease if omitted).",
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
    """Mark a task as verified (unblocks dependents).

    Verifies the task is complete and releases any active lease.
    Dependent tasks become claimable after verification.

    \b
    Example:
        lodestar task verify F001
        lodestar task verify F001 --agent A1234ABCD
    """
    if explain:
        _show_explain_verify(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
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

    if task.status != TaskStatus.DONE:
        if json_output:
            print_json(Envelope.error(f"Task {task_id} must be done before verifying").model_dump())
        else:
            console.print("[error]Task must be done before verifying[/error]")
            console.print(f"Current status: {task.status.value}")
        raise typer.Exit(1)

    # Auto-detect agent from active lease if not provided
    db_path = get_runtime_db_path(root)
    db = RuntimeDatabase(db_path)
    if agent is None:
        lease = db.get_active_lease(task_id)
        if lease:
            agent = lease.agent_id

    # Update task status and tracking fields
    task.status = TaskStatus.VERIFIED
    task.updated_at = datetime.now(UTC)
    if agent:
        task.verified_by = agent
        task.verified_at = datetime.now(UTC)
    save_spec(spec, root)

    # Log event to runtime database
    engine = create_runtime_engine(db_path)
    session_factory = create_session_factory(engine)
    with get_session(session_factory) as session:
        log_event(session, EventType.TASK_VERIFIED, agent_id=agent, task_id=task_id)
    engine.dispose()

    # Auto-release any active lease (task is complete, lease no longer needed)
    active_lease = db.get_active_lease(task_id)
    if active_lease:
        db.release_lease(task_id, active_lease.agent_id)

    # Check what tasks are now unblocked
    new_claimable = spec.get_claimable_tasks()
    newly_unblocked = [t for t in new_claimable if task_id in t.depends_on]

    result = {
        "task_id": task_id,
        "status": "verified",
        "unblocked": [t.id for t in newly_unblocked],
    }
    if agent:
        result["verified_by"] = agent

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Verified {task_id}[/success]")
        if newly_unblocked:
            console.print(
                f"[info]Unblocked tasks:[/info] {', '.join(t.id for t in newly_unblocked)}"
            )


@app.command(name="delete")
def task_delete(
    task_id: str | None = typer.Argument(None, help="Task ID to delete."),
    cascade: bool = typer.Option(
        False,
        "--cascade",
        help="Cascade delete to dependent tasks.",
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
    """Soft-delete a task (status=deleted).

    Tasks are soft-deleted, not physically removed. Deleted tasks are
    hidden from list by default (use --include-deleted to show them).

    If the task is depended on by other tasks:
    - Without --cascade: error with list of dependents
    - With --cascade: delete this task and all its dependents

    Example:
        lodestar task delete F001              # Delete if no dependents
        lodestar task delete F001 --cascade    # Delete and cascade to dependents
    """
    if explain:
        _show_explain_delete(json_output)
        return

    if task_id is None:
        console.print("[error]Missing argument 'TASK_ID'[/error]")
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

    if task.status == TaskStatus.DELETED:
        if json_output:
            print_json(Envelope.error(f"Task {task_id} is already deleted").model_dump())
        else:
            console.print(f"[warning]Task {task_id} is already deleted[/warning]")
        raise typer.Exit(1)

    # Use service to compute cascade delete targets
    result = compute_cascade_delete(task_id, spec, cascade)

    if result.blocked_by:
        if json_output:
            print_json(
                Envelope.error(
                    f"Task {task_id} has {len(result.blocked_by)} dependent(s). Use --cascade to delete all."
                ).model_dump()
            )
        else:
            console.print(f"[error]Cannot delete {task_id}[/error]")
            console.print(f"  {len(result.blocked_by)} task(s) depend on this task:")
            for dep in result.blocked_by:
                console.print(f"    - {dep}: {spec.tasks[dep].title}")
            console.print()
            console.print(
                "  Use [command]--cascade[/command] to delete this task and all dependents"
            )
        raise typer.Exit(1)

    # Mark all tasks as deleted
    deleted_tasks = []
    for tid in result.tasks_to_delete:
        t = spec.tasks[tid]
        t.status = TaskStatus.DELETED
        t.updated_at = datetime.now(UTC)
        deleted_tasks.append({"id": tid, "title": t.title})

    save_spec(spec, root)

    format_deleted_tasks(deleted_tasks, json_output)


@app.command(name="graph")
def task_graph(
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, dot.",
    ),
    agent: str | None = typer.Option(
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
    """Export the task dependency graph.

    Outputs all tasks and their dependency relationships.
    Use --format dot for Graphviz visualization.

    \b
    Examples:
        lodestar task graph
        lodestar task graph --format dot > graph.dot
        lodestar task graph --json
    """
    if explain:
        _show_explain_graph(json_output)
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

    nodes: list[dict[str, Any]] = [
        {
            "id": t.id,
            "title": t.title,
            "status": t.status.value,
            "priority": t.priority,
        }
        for t in spec.tasks.values()
    ]

    edges = [
        {"from": dep, "to": task.id} for task in spec.tasks.values() for dep in task.depends_on
    ]

    format_graph(nodes, edges, output_format, json_output)


def _show_explain_list(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task list",
        "purpose": "List all tasks with optional filtering.",
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task list[/info]\n")
        console.print("List all tasks with optional filtering.\n")


def _show_explain_show(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task show",
        "purpose": "Show detailed information about a task.",
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task show[/info]\n")
        console.print("Show detailed information about a task.\n")


def _show_explain_next(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task next",
        "purpose": "Get the next claimable task(s).",
        "returns": ["Tasks with status=ready and all deps verified", "Sorted by priority"],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task next[/info]\n")
        console.print("Get the next claimable task(s).\n")


def _show_explain_claim(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task claim",
        "purpose": "Claim a task with a time-limited lease.",
        "examples": [
            "lodestar task claim F001 --agent A1234ABCD",
            "lodestar task claim F001 --agent A1234ABCD --ttl 30m",
            "lodestar task claim F001 --agent A1234ABCD --force",
        ],
        "notes": [
            "Leases auto-expire (default 15m)",
            "Only one agent can claim a task at a time",
            "Renew with 'task renew' before expiry",
            "Shows warnings if task locks overlap with other claimed tasks",
            "Use --force to bypass lock conflict warnings",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task claim[/info]\n")
        console.print("Claim a task with a time-limited lease.\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task claim F001 --agent A1234ABCD[/command]")
        console.print("  [command]lodestar task claim F001 --agent A1234ABCD --ttl 30m[/command]")
        console.print("  [command]lodestar task claim F001 --agent A1234ABCD --force[/command]")
        console.print()
        console.print("[info]Lock Conflicts:[/info]")
        console.print("  If another agent has claimed a task with overlapping file locks,")
        console.print("  you'll see a warning. Use --force to proceed anyway.")
        console.print()


def _show_explain_create(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task create",
        "purpose": "Create a new task with detailed context for executing agents.",
        "options": {
            "--id": "Task ID (auto-generated as T001, T002... if omitted)",
            "--title, -t": "Task title (required)",
            "--description, -d": "Task description - use WHAT/WHERE/WHY/ACCEPT format",
            "--priority, -p": "Priority number (lower = higher priority, default: 100)",
            "--status, -s": "Initial status (default: ready)",
            "--depends-on": "Task ID this depends on (repeatable for multiple)",
            "--label, -l": "Label for categorization (repeatable for multiple)",
            "--prd-source": "Path to PRD file (e.g., PRD.md)",
            "--prd-ref": "PRD section anchor (e.g., #feature-requirements, repeatable)",
            "--prd-excerpt": "Frozen PRD excerpt text to embed in task",
        },
        "examples": [
            "lodestar task create --title 'Fix login bug' --label bug --priority 1",
            "lodestar task create --id F001 --title 'Add auth' --depends-on F000 --label feature",
            "lodestar task create --title 'Add caching' --prd-source PRD.md --prd-ref '#caching'",
            "lodestar task create --title 'Rate limit' --prd-excerpt 'Limit: 100 req/min'",
        ],
        "notes": [
            "Write detailed descriptions: WHAT (goal), WHERE (files), WHY (context), ACCEPT (criteria)",
            "Task ID auto-generates as T001, T002... if --id is omitted",
            "Dependencies must exist before creating the task",
            "Use --prd-source with --prd-ref to link PRD sections",
            "Use --prd-excerpt for frozen requirements that shouldn't change",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task create[/info]\n")
        console.print("Create a new task with detailed context for executing agents.\n")
        console.print("[info]Options:[/info]")
        console.print("  [muted]--id[/muted]           Task ID (auto-generated if omitted)")
        console.print("  [muted]--title, -t[/muted]    Task title (required)")
        console.print("  [muted]--description, -d[/muted] Task description")
        console.print("  [muted]--priority, -p[/muted] Priority (lower = higher, default: 100)")
        console.print("  [muted]--status, -s[/muted]   Initial status (default: ready)")
        console.print("  [muted]--depends-on[/muted]   Task IDs this depends on (repeatable)")
        console.print("  [muted]--label, -l[/muted]    Labels (repeatable)")
        console.print("  [muted]--prd-source[/muted]   Path to PRD file")
        console.print("  [muted]--prd-ref[/muted]      PRD section anchors (repeatable)")
        console.print("  [muted]--prd-excerpt[/muted]  Frozen PRD excerpt to embed")
        console.print()
        console.print("[info]Examples:[/info]")
        console.print(
            "  [command]lodestar task create --title 'Fix bug' --label bug --priority 1[/command]"
        )
        console.print(
            "  [command]lodestar task create --id F001 --title 'Add auth' --depends-on F000[/command]"
        )
        console.print(
            "  [command]lodestar task create --title 'Cache' --prd-source PRD.md --prd-ref '#cache'[/command]"
        )
        console.print()
        console.print("[info]Notes:[/info]")
        console.print("  - Use WHAT/WHERE/WHY/ACCEPT format in descriptions")
        console.print("  - Dependencies must exist before creating the task")
        console.print("  - Use --prd-source + --prd-ref to link PRD sections")
        console.print()


def _show_explain_update(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task update",
        "purpose": "Update an existing task's properties.",
        "examples": [
            "lodestar task update F001 --title 'New title'",
            "lodestar task update F001 --priority 1 --add-label urgent",
            "lodestar task update F001 --status blocked",
        ],
        "notes": [
            "Only specified fields are updated",
            "Use --add-label and --remove-label to modify labels",
            "Updates the task's updated_at timestamp",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task update[/info]\n")
        console.print("Update an existing task's properties.\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task update F001 --title 'New title'[/command]")
        console.print(
            "  [command]lodestar task update F001 --priority 1 --add-label urgent[/command]"
        )
        console.print()


def _show_explain_renew(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task renew",
        "purpose": "Extend your lease on a claimed task.",
        "examples": [
            "lodestar task renew F001 --agent A1234ABCD",
            "lodestar task renew F001 --agent A1234ABCD --ttl 30m",
        ],
        "notes": [
            "Only the agent who claimed the task can renew it",
            "Default extension is 15 minutes",
            "Renew before your lease expires to keep working",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task renew[/info]\n")
        console.print("Extend your lease on a claimed task.\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task renew F001 --agent A1234ABCD[/command]")
        console.print("  [command]lodestar task renew F001 --agent A1234ABCD --ttl 30m[/command]")
        console.print()


def _show_explain_release(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task release",
        "purpose": "Release your claim on a task so others can work on it.",
        "examples": [
            "lodestar task release F001",
            "lodestar task release F001 --agent A1234ABCD",
        ],
        "notes": [
            "Use when you're blocked or can't complete the task",
            "Consider leaving a message with context for the next agent",
            "Not needed after 'task done' or 'task verify' (auto-releases)",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task release[/info]\n")
        console.print("Release your claim on a task so others can work on it.\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task release F001[/command]")
        console.print("  [command]lodestar task release F001 --agent A1234ABCD[/command]")
        console.print()


def _show_explain_done(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task done",
        "purpose": "Mark a task as done (implementation complete).",
        "examples": [
            "lodestar task done F001",
        ],
        "notes": [
            "Sets task status to 'done'",
            "Next step is 'task verify' after review",
            "Does not auto-release lease (verify does)",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task done[/info]\n")
        console.print("Mark a task as done (implementation complete).\n")
        console.print("[info]Example:[/info]")
        console.print("  [command]lodestar task done F001[/command]")
        console.print()


def _show_explain_verify(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task verify",
        "purpose": "Mark a task as verified, unblocking dependent tasks.",
        "examples": [
            "lodestar task verify F001",
        ],
        "notes": [
            "Task must be in 'done' status first",
            "Unblocks tasks that depend on this one",
            "Auto-releases any active lease",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task verify[/info]\n")
        console.print("Mark a task as verified, unblocking dependent tasks.\n")
        console.print("[info]Example:[/info]")
        console.print("  [command]lodestar task verify F001[/command]")
        console.print()


def _show_explain_delete(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task delete",
        "purpose": "Soft-delete a task (sets status to 'deleted').",
        "examples": [
            "lodestar task delete F001",
            "lodestar task delete F001 --cascade",
        ],
        "notes": [
            "Tasks are soft-deleted, not physically removed",
            "Deleted tasks hidden from list (use --include-deleted)",
            "Use --cascade to delete tasks that depend on this one",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task delete[/info]\n")
        console.print("Soft-delete a task (sets status to 'deleted').\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task delete F001[/command]")
        console.print("  [command]lodestar task delete F001 --cascade[/command]")
        console.print()


def _show_explain_graph(json_output: bool) -> None:
    explanation = {
        "command": "lodestar task graph",
        "purpose": "Export the task dependency graph.",
        "examples": [
            "lodestar task graph",
            "lodestar task graph --format dot",
            "lodestar task graph --json",
        ],
        "notes": [
            "Default format is JSON with nodes and edges",
            "Use --format dot for Graphviz DOT output",
            "Useful for visualizing task dependencies",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task graph[/info]\n")
        console.print("Export the task dependency graph.\n")
        console.print("[info]Examples:[/info]")
        console.print("  [command]lodestar task graph[/command]")
        console.print("  [command]lodestar task graph --format dot[/command]")
        console.print()
