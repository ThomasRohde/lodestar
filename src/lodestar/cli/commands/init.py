"""lodestar init command - Initialize a Lodestar repository."""

from __future__ import annotations

from pathlib import Path

import typer

from lodestar.models.envelope import (
    NEXT_ACTION_AGENT_JOIN,
    NEXT_ACTION_STATUS,
    Envelope,
    NextAction,
)
from lodestar.spec.loader import create_default_spec, save_spec
from lodestar.util.output import console, print_json, print_rich
from lodestar.util.paths import LODESTAR_DIR, find_lodestar_root


def init_command(
    path: Path | None = typer.Argument(
        None,
        help="Path to initialize. Defaults to current directory.",
    ),
    project_name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Project name. Defaults to directory name.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing .lodestar directory.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Initialize a new Lodestar repository.

    Creates the .lodestar directory with spec.yaml and runtime database.
    """
    if explain:
        _show_explain(json_output)
        return

    # Resolve path
    root = (path or Path.cwd()).resolve()

    # Check if already initialized
    existing = find_lodestar_root(root)
    if existing and not force:
        if json_output:
            print_json(
                Envelope.error(
                    f"Already initialized at {existing}. Use --force to reinitialize.",
                    next_actions=[NEXT_ACTION_STATUS],
                ).model_dump()
            )
        else:
            print_rich(
                f"[error]Already initialized at {existing}[/error]",
                style="error",
            )
            print_rich("Use --force to reinitialize.", style="muted")
        raise typer.Exit(1)

    # Determine project name
    name = project_name or root.name

    # Create .lodestar directory
    lodestar_dir = root / LODESTAR_DIR
    lodestar_dir.mkdir(exist_ok=True)

    # Create .gitignore for runtime files
    gitignore_path = lodestar_dir / ".gitignore"
    gitignore_path.write_text(
        "# Runtime files (ephemeral, not versioned)\n"
        "runtime.sqlite\n"
        "runtime.sqlite-wal\n"
        "runtime.sqlite-shm\n"
        "runtime.jsonl\n"
        "*.lock\n"
    )

    # Create default spec
    spec = create_default_spec(name)
    save_spec(spec, root)

    # Create AGENTS.md
    agents_md = root / "AGENTS.md"
    if not agents_md.exists() or force:
        agents_md.write_text(_agents_md_content(name))

    # Build response
    result = {
        "initialized": True,
        "path": str(root),
        "project_name": name,
        "files_created": [
            str(lodestar_dir / "spec.yaml"),
            str(gitignore_path),
            str(agents_md),
        ],
    }

    next_actions = [
        NEXT_ACTION_AGENT_JOIN,
        NextAction(
            intent="task.create",
            cmd="lodestar task create",
            description="Create your first task",
        ),
        NEXT_ACTION_STATUS,
    ]

    if json_output:
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
    else:
        console.print()
        console.print(f"[success]Initialized Lodestar in {root}[/success]")
        console.print()
        console.print("[muted]Created:[/muted]")
        console.print(f"  {LODESTAR_DIR}/spec.yaml")
        console.print(f"  {LODESTAR_DIR}/.gitignore")
        console.print("  AGENTS.md")
        console.print()
        console.print("[info]Next steps:[/info]")
        console.print("  1. Run [command]lodestar agent join[/command] to register")
        console.print("  2. Run [command]lodestar task create[/command] to add tasks")
        console.print("  3. Run [command]lodestar status[/command] to see overview")
        console.print()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar init",
        "purpose": "Initialize a new Lodestar repository for multi-agent coordination.",
        "creates": [
            ".lodestar/spec.yaml - Task definitions and dependencies (versioned)",
            ".lodestar/.gitignore - Excludes runtime files from git",
            "AGENTS.md - Quick reference for agents entering the repo",
        ],
        "notes": [
            "Run this once per repository",
            "The spec.yaml should be committed to git",
            "Runtime files (SQLite) are auto-generated and gitignored",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar init[/info]")
        console.print()
        console.print("Initialize a new Lodestar repository for multi-agent coordination.")
        console.print()
        console.print("[muted]Creates:[/muted]")
        for item in explanation["creates"]:
            console.print(f"  - {item}")
        console.print()


def _agents_md_content(project_name: str) -> str:
    """Generate AGENTS.md content."""
    return f"""# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## Session Start (Do This First)

```bash
# 1. Check repository health
lodestar doctor

# 2. Register and save your agent ID
lodestar agent join --name "Your Name"
# Output: Registered as agent A1234ABCD  <-- SAVE THIS ID

# 3. Find available work
lodestar task next
```

## Working on a Task

```bash
# Claim BEFORE starting (--agent is required)
lodestar task claim <task-id> --agent <your-agent-id>

# If work takes > 10 minutes, renew your lease
lodestar task renew <task-id>

# When done
lodestar task done <task-id>
lodestar task verify <task-id>
```

## If You Get Blocked

```bash
# Release the task
lodestar task release <task-id>

# Leave context for the next agent (--from and --to are required)
lodestar msg send --to task:<task-id> --from <your-agent-id> --text "Blocked: reason here"
```

## Creating Tasks

```bash
# Create with good descriptions and dependencies
lodestar task create \\
    --id "F001" \\
    --title "Short, clear title" \\
    --description "What needs to be done, acceptance criteria, relevant files" \\
    --priority 1 \\
    --label feature \\
    --depends-on "F000"  # Task that must be verified first
```

## Command Reference

| Action | Command |
|--------|---------|
| Check health | `lodestar doctor` |
| View status | `lodestar status` |
| List all tasks | `lodestar task list` |
| Find claimable work | `lodestar task next` |
| View task details | `lodestar task show <id>` |
| Claim task | `lodestar task claim <id> --agent <agent-id>` |
| Extend lease | `lodestar task renew <id>` |
| Release task | `lodestar task release <id>` |
| Mark complete | `lodestar task done <id>` |
| Verify complete | `lodestar task verify <id>` |
| Send message | `lodestar msg send --to task:<id> --from <agent-id> --text "..."` |
| Read task thread | `lodestar msg thread <task-id>` |
| Check inbox | `lodestar msg inbox --agent <agent-id>` |

## Rules

1. **Always claim before working** - Prevents duplicate work
2. **Renew leases proactively** - Default is 15 minutes
3. **Leave context when releasing** - Help the next agent
4. **Verify after done** - Unblocks dependent tasks
5. **Don't edit spec.yaml directly** - Use `lodestar task create/update`

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |
"""
