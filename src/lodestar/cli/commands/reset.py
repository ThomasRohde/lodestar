"""lodestar reset command - Reset repository to clean state."""

from __future__ import annotations

from pathlib import Path

import typer

from lodestar.models.envelope import (
    NEXT_ACTION_AGENT_JOIN,
    NEXT_ACTION_STATUS,
    Envelope,
)
from lodestar.spec.loader import SpecNotFoundError, load_spec, save_spec
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path


def reset_command(
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Skip confirmation prompt (required for non-interactive use).",
    ),
    hard: bool = typer.Option(
        False,
        "--hard",
        help="Also delete all tasks from spec.yaml (keeps project metadata).",
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
    """Reset .lodestar to clean state.

    By default (soft reset), only runtime data is deleted:
    - Agents, leases, and messages are cleared
    - Tasks in spec.yaml are preserved

    With --hard flag:
    - Runtime data is deleted
    - All tasks are removed from spec.yaml
    - Project metadata is preserved
    """
    if explain:
        _show_explain(json_output)
        return

    root = find_lodestar_root()

    if root is None:
        if json_output:
            from lodestar.models.envelope import NextAction

            print_json(
                Envelope.error(
                    "Not a Lodestar repository",
                    next_actions=[
                        NextAction(
                            intent="init",
                            cmd="lodestar init",
                            description="Initialize Lodestar in this repository",
                        ),
                    ],
                ).model_dump()
            )
        else:
            console.print()
            console.print("[error]Not a Lodestar repository[/error]")
            console.print()
            console.print("Run [command]lodestar init[/command] to initialize.")
            console.print()
        raise typer.Exit(1)

    # Load spec to get task count
    try:
        spec = load_spec(root)
        task_count = len(spec.tasks)
    except SpecNotFoundError:
        if json_output:
            print_json(
                Envelope.error(
                    "spec.yaml not found. Repository may be corrupted.",
                    next_actions=[NEXT_ACTION_STATUS],
                ).model_dump()
            )
        else:
            console.print()
            console.print("[error]spec.yaml not found[/error]")
            console.print()
        raise typer.Exit(1)

    # Get runtime stats
    runtime_stats = {"agents": 0, "active_leases": 0, "total_messages": 0}
    runtime_path = get_runtime_db_path(root)
    if runtime_path.exists():
        from lodestar.runtime.database import RuntimeDatabase

        db = RuntimeDatabase(runtime_path)
        runtime_stats = db.get_stats()

    # Confirm before reset (unless --force)
    if not force:
        if json_output:
            # In JSON mode, require --force
            print_json(
                Envelope.error(
                    "Confirmation required. Use --force to proceed without prompt.",
                    data={
                        "reset_type": "hard" if hard else "soft",
                        "tasks_to_delete": task_count if hard else 0,
                        "agents_to_clear": runtime_stats["agents"],
                        "leases_to_clear": runtime_stats["active_leases"],
                        "messages_to_clear": runtime_stats["total_messages"],
                    },
                ).model_dump()
            )
            raise typer.Exit(1)
        else:
            # Interactive confirmation
            console.print()
            console.print("[warning]⚠ Reset .lodestar to clean state[/warning]")
            console.print()
            console.print(f"Reset type: [info]{'HARD' if hard else 'SOFT'}[/info]")
            console.print()
            console.print("Will delete:")
            console.print(
                f"  • Runtime data: {runtime_stats['agents']} agents, "
                f"{runtime_stats['active_leases']} leases, "
                f"{runtime_stats['total_messages']} messages"
            )
            if hard:
                console.print(f"  • Tasks: {task_count} tasks from spec.yaml")
            else:
                console.print("  • Tasks: [muted]None (spec.yaml preserved)[/muted]")
            console.print()

            if not typer.confirm("Continue?", default=False):
                console.print()
                console.print("[muted]Aborted.[/muted]")
                console.print()
                raise typer.Exit(0)

    # Perform reset
    warnings = []

    # Delete runtime files
    runtime_deleted = _delete_runtime_files(runtime_path)
    if not runtime_deleted:
        warnings.append("Runtime database not found or already deleted")

    # Hard reset: clear tasks and features from spec
    tasks_deleted = 0
    if hard:
        spec.tasks = {}
        spec.features = {}
        save_spec(spec, root)
        tasks_deleted = task_count

    # Delete lock files (after save_spec to clean up any lingering locks)
    _delete_lock_files(root)

    # Build result
    result = {
        "reset_type": "hard" if hard else "soft",
        "runtime_deleted": runtime_deleted,
        "tasks_deleted": tasks_deleted,
        "agents_cleared": runtime_stats["agents"] if runtime_deleted else 0,
        "leases_cleared": runtime_stats["active_leases"] if runtime_deleted else 0,
        "messages_cleared": runtime_stats["total_messages"] if runtime_deleted else 0,
    }

    next_actions = [NEXT_ACTION_AGENT_JOIN, NEXT_ACTION_STATUS]

    if json_output:
        print_json(
            Envelope.success(result, next_actions=next_actions, warnings=warnings).model_dump()
        )
    else:
        console.print()
        console.print("[success]✓ Reset complete[/success]")
        console.print()
        console.print("Deleted:")
        if runtime_deleted:
            console.print(
                f"  • Runtime data: {runtime_stats['agents']} agents, "
                f"{runtime_stats['active_leases']} leases, "
                f"{runtime_stats['total_messages']} messages"
            )
        else:
            console.print("  • Runtime data: [muted]None (already empty)[/muted]")
        if hard:
            console.print(f"  • Tasks: {tasks_deleted} tasks from spec.yaml")
        console.print()
        console.print("[info]Next steps:[/info]")
        console.print("  1. Run [command]lodestar agent join[/command] to register")
        if hard:
            console.print("  2. Run [command]lodestar task create[/command] to add tasks")
        console.print("  3. Run [command]lodestar status[/command] to see overview")
        console.print()


def _delete_runtime_files(runtime_path: Path) -> bool:
    """Delete runtime SQLite files. Returns True if any files were deleted."""
    deleted = False

    # Delete main database and WAL files
    for suffix in ["", "-wal", "-shm"]:
        file_path = runtime_path.parent / f"{runtime_path.name}{suffix}"
        if file_path.exists():
            file_path.unlink()
            deleted = True

    return deleted


def _delete_lock_files(root: Path) -> None:
    """Delete lock files from .lodestar directory."""
    from lodestar.util.paths import get_lodestar_dir

    lodestar_dir = get_lodestar_dir(root)

    # Delete spec.lock and any other .lock files
    for lock_file in lodestar_dir.glob("*.lock"):
        if lock_file.exists():
            lock_file.unlink()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar reset",
        "purpose": "Reset .lodestar to clean state for fresh start.",
        "modes": {
            "soft (default)": {
                "deletes": ["Runtime database (agents, leases, messages)"],
                "preserves": ["spec.yaml (all tasks)"],
                "use_case": "Clear runtime state while keeping task definitions",
            },
            "hard (--hard)": {
                "deletes": [
                    "Runtime database (agents, leases, messages)",
                    "All tasks from spec.yaml",
                ],
                "preserves": ["Project metadata in spec.yaml"],
                "use_case": "Complete reset for starting over",
            },
        },
        "safety": [
            "Requires confirmation unless --force is used",
            "Only modifies files inside .lodestar directory",
            "Does not touch repository code or git history",
        ],
        "options": {
            "--force": "Skip confirmation prompt (required for automation/agents)",
            "--hard": "Also delete all tasks from spec.yaml",
            "--json": "Output in JSON format",
        },
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar reset[/info]")
        console.print()
        console.print("Reset .lodestar to clean state for fresh start.")
        console.print()
        console.print("[bold]Modes:[/bold]")
        console.print()
        console.print("  [info]Soft (default):[/info]")
        console.print("    • Deletes runtime data (agents, leases, messages)")
        console.print("    • Preserves all tasks in spec.yaml")
        console.print("    • Use when you want to clear runtime state")
        console.print()
        console.print("  [info]Hard (--hard):[/info]")
        console.print("    • Deletes runtime data AND all tasks")
        console.print("    • Preserves project metadata")
        console.print("    • Use when starting completely fresh")
        console.print()
        console.print("[bold]Safety:[/bold]")
        console.print("  • Requires confirmation (use --force to skip)")
        console.print("  • Only modifies .lodestar directory")
        console.print("  • Does not touch repository code or git")
        console.print()
