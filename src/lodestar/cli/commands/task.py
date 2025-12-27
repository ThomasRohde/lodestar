"""lodestar task commands - Task management and scheduling."""

from __future__ import annotations

from datetime import datetime

import typer

from lodestar.models.envelope import Envelope, NextAction
from lodestar.models.runtime import Lease
from lodestar.models.spec import Task, TaskStatus
from lodestar.runtime.database import RuntimeDatabase
from lodestar.spec.dag import validate_dag
from lodestar.spec.loader import SpecNotFoundError, load_spec, save_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path
from lodestar.util.time import format_duration, parse_duration

app = typer.Typer(help="Task management and scheduling commands.")


@app.command(name="list")
def task_list(
    status_filter: str | None = typer.Option(
        None,
        "--status",
        "-s",
        help="Filter by status (todo, ready, blocked, done, verified).",
    ),
    label: str | None = typer.Option(
        None,
        "--label",
        "-l",
        help="Filter by label.",
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
    """List all tasks with optional filtering."""
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

            status_colors = {
                TaskStatus.TODO: "white",
                TaskStatus.READY: "cyan",
                TaskStatus.BLOCKED: "yellow",
                TaskStatus.DONE: "blue",
                TaskStatus.VERIFIED: "green",
            }

            for task in tasks:
                color = status_colors.get(task.status, "white")
                claimed = (
                    f" [muted](claimed by {leases[task.id].agent_id})[/muted]"
                    if task.id in leases
                    else ""
                )
                labels = f" [{', '.join(task.labels)}]" if task.labels else ""
                console.print(
                    f"  [task_id]{task.id}[/task_id] [{color}]{task.status.value}[/{color}]"
                    f" P{task.priority}{labels}{claimed}"
                )
                console.print(f"    {task.title}")
        console.print()


@app.command(name="show")
def task_show(
    task_id: str = typer.Argument(..., help="Task ID to show."),
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

    # Check for active lease
    lease = None
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        db = RuntimeDatabase(runtime_path)
        lease = db.get_active_lease(task_id)

    result = task.model_dump()
    result["status"] = task.status.value
    result["created_at"] = task.created_at.isoformat()
    result["updated_at"] = task.updated_at.isoformat()
    if lease:
        result["claimed_by"] = {
            "agent_id": lease.agent_id,
            "expires_at": lease.expires_at.isoformat(),
        }

    # Determine claimability
    verified = spec.get_verified_tasks()
    result["claimable"] = task.is_claimable(verified) and lease is None

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        console.print(f"[bold][task_id]{task.id}[/task_id][/bold] - {task.title}")
        console.print()
        console.print(f"[muted]Status:[/muted] {task.status.value}")
        console.print(f"[muted]Priority:[/muted] {task.priority}")
        if task.labels:
            console.print(f"[muted]Labels:[/muted] {', '.join(task.labels)}")
        if task.depends_on:
            console.print(f"[muted]Depends on:[/muted] {', '.join(task.depends_on)}")
        if task.locks:
            console.print(f"[muted]Locks:[/muted] {', '.join(task.locks)}")

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
            remaining = lease.expires_at - datetime.utcnow()
            console.print(f"[warning]Claimed by {lease.agent_id}[/warning]")
            console.print(f"  Expires in: {format_duration(remaining)}")
        elif result["claimable"]:
            console.print(
                f"[success]Claimable[/success] - run [command]lodestar task claim {task.id}[/command]"
            )

        console.print()


@app.command(name="create")
def task_create(
    title: str = typer.Option(..., "--title", "-t", help="Task title."),
    task_id: str | None = typer.Option(
        None,
        "--id",
        help="Task ID (auto-generated if not provided).",
    ),
    description: str = typer.Option("", "--description", "-d", help="Task description."),
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
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Create a new task."""
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

    # Create task
    task = Task(
        id=task_id,
        title=title,
        description=description,
        priority=priority,
        status=task_status,
        depends_on=depends_on or [],
        labels=labels or [],
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
    task_id: str = typer.Argument(..., help="Task ID to update."),
    title: str | None = typer.Option(None, "--title", "-t", help="New task title."),
    description: str | None = typer.Option(None, "--description", "-d", help="New description."),
    priority: int | None = typer.Option(None, "--priority", "-p", help="New priority."),
    status: str | None = typer.Option(None, "--status", "-s", help="New status."),
    add_label: list[str] | None = typer.Option(None, "--add-label", help="Add a label."),
    remove_label: list[str] | None = typer.Option(None, "--remove-label", help="Remove a label."),
    json_output: bool = typer.Option(False, "--json", help="Output in JSON format."),
) -> None:
    """Update an existing task's properties."""
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

    task.updated_at = datetime.utcnow()
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

    # Get claimable tasks
    claimable = spec.get_claimable_tasks()

    # Filter out already claimed tasks
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        db = RuntimeDatabase(runtime_path)
        claimable = [t for t in claimable if db.get_active_lease(t.id) is None]

    # Take requested count
    tasks = claimable[:count]

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
        "total_claimable": len(claimable),
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
            console.print(f"[bold]Next Claimable Tasks ({len(claimable)} available)[/bold]")
            console.print()
            for task in tasks:
                labels = f" [{', '.join(task.labels)}]" if task.labels else ""
                console.print(f"  [task_id]{task.id}[/task_id] P{task.priority}{labels}")
                console.print(f"    {task.title}")
            console.print()
            console.print(f"Run [command]lodestar task claim {tasks[0].id}[/command] to claim")
        console.print()


@app.command(name="claim")
def task_claim(
    task_id: str = typer.Argument(..., help="Task ID to claim."),
    agent_id: str = typer.Option(..., "--agent", "-a", help="Your agent ID."),
    ttl: str = typer.Option("15m", "--ttl", "-t", help="Lease duration (e.g., 15m, 1h)."),
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

    Claims are time-limited and auto-expire. Renew with 'task renew'.
    """
    if explain:
        _show_explain_claim(json_output)
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

    lease = Lease(
        task_id=task_id,
        agent_id=agent_id,
        expires_at=datetime.utcnow() + duration,
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
                remaining = existing.expires_at - datetime.utcnow()
                console.print(f"  Claimed by: {existing.agent_id}")
                console.print(f"  Expires in: {format_duration(remaining)}")
        raise typer.Exit(1)

    result = {
        "lease_id": created_lease.lease_id,
        "task_id": task_id,
        "agent_id": agent_id,
        "expires_at": created_lease.expires_at.isoformat(),
        "ttl_seconds": int(duration.total_seconds()),
    }

    next_actions = [
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
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
    else:
        console.print()
        console.print(f"[success]Claimed task[/success] [task_id]{task_id}[/task_id]")
        console.print(f"  Lease: {created_lease.lease_id}")
        console.print(f"  Expires in: {format_duration(duration)}")
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
    task_id: str = typer.Argument(..., help="Task ID to renew."),
    agent_id: str = typer.Option(..., "--agent", "-a", help="Your agent ID."),
    ttl: str = typer.Option("15m", "--ttl", "-t", help="New lease duration."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Renew your claim on a task."""
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
    new_expires = datetime.utcnow() + duration
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
    task_id: str = typer.Argument(..., help="Task ID to release."),
    agent_id: str = typer.Option(..., "--agent", "-a", help="Your agent ID."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Release your claim on a task."""
    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(get_runtime_db_path(root))
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
    task_id: str = typer.Argument(..., help="Task ID to mark as done."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Mark a task as done."""
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

    task.status = TaskStatus.DONE
    task.updated_at = datetime.utcnow()
    save_spec(spec, root)

    if json_output:
        print_json(Envelope.success({"task_id": task_id, "status": "done"}).model_dump())
    else:
        console.print(f"[success]Marked {task_id} as done[/success]")
        console.print(f"Run [command]lodestar task verify {task_id}[/command] after review")


@app.command(name="verify")
def task_verify(
    task_id: str = typer.Argument(..., help="Task ID to verify."),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Mark a task as verified (unblocks dependents)."""
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

    task.status = TaskStatus.VERIFIED
    task.updated_at = datetime.utcnow()
    save_spec(spec, root)

    # Check what tasks are now unblocked
    new_claimable = spec.get_claimable_tasks()
    newly_unblocked = [t for t in new_claimable if task_id in t.depends_on]

    result = {
        "task_id": task_id,
        "status": "verified",
        "unblocked": [t.id for t in newly_unblocked],
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Verified {task_id}[/success]")
        if newly_unblocked:
            console.print(
                f"[info]Unblocked tasks:[/info] {', '.join(t.id for t in newly_unblocked)}"
            )


@app.command(name="graph")
def task_graph(
    output_format: str = typer.Option(
        "json",
        "--format",
        "-f",
        help="Output format: json, dot.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Export the task dependency graph."""
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

    nodes = [
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

    result = {"nodes": nodes, "edges": edges}

    if output_format == "dot":
        dot_lines = ["digraph tasks {"]
        dot_lines.append("  rankdir=LR;")
        for node in nodes:
            label = f"{node['id']}\\n{node['title'][:20]}"
            dot_lines.append(f'  "{node["id"]}" [label="{label}"];')
        for edge in edges:
            dot_lines.append(f'  "{edge["from"]}" -> "{edge["to"]}";')
        dot_lines.append("}")
        console.print("\n".join(dot_lines))
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
        "notes": [
            "Leases auto-expire (default 15m)",
            "Only one agent can claim a task at a time",
            "Renew with 'task renew' before expiry",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar task claim[/info]\n")
        console.print("Claim a task with a time-limited lease.\n")
