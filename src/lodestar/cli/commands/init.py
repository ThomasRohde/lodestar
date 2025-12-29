"""lodestar init command - Initialize a Lodestar repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

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
    mcp: bool = typer.Option(
        False,
        "--mcp",
        help="Create MCP configuration files for IDE/agent integration.",
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

    # Create MCP config files if requested
    mcp_files: list[str] = []
    if mcp:
        mcp_paths = _create_mcp_configs(root, force=force)
        mcp_files = [str(p) for p in mcp_paths]

    # Create AGENTS.md (use MCP version if --mcp)
    agents_md = root / "AGENTS.md"
    if not agents_md.exists() or force:
        content = _agents_md_content_mcp(name) if mcp else _agents_md_content(name)
        agents_md.write_text(content)

    # Build response
    result = {
        "initialized": True,
        "path": str(root),
        "project_name": name,
        "mcp_enabled": mcp,
        "files_created": [
            str(lodestar_dir / "spec.yaml"),
            str(gitignore_path),
            str(agents_md),
            *mcp_files,
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
        if mcp:
            console.print("  .vscode/mcp.json")
            console.print("  .mcp.json")
        console.print()
        console.print("[info]Next steps:[/info]")
        console.print("  1. Run [command]lodestar agent join[/command] to register")
        console.print("  2. Run [command]lodestar task create[/command] to add tasks")
        console.print("  3. Run [command]lodestar status[/command] to see overview")
        console.print()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation: dict[str, Any] = {
        "command": "lodestar init",
        "purpose": "Initialize a new Lodestar repository for multi-agent coordination.",
        "creates": [
            ".lodestar/spec.yaml - Task definitions and dependencies (versioned)",
            ".lodestar/.gitignore - Excludes runtime files from git",
            "AGENTS.md - Quick reference for agents entering the repo",
        ],
        "options": {
            "--mcp": "Create MCP configuration files (.vscode/mcp.json, .mcp.json)",
            "--force": "Overwrite existing .lodestar directory",
            "--name": "Set project name (defaults to directory name)",
        },
        "notes": [
            "Run this once per repository",
            "The spec.yaml should be committed to git",
            "Runtime files (SQLite) are auto-generated and gitignored",
            "Use --mcp to enable MCP integration for IDE/agent tools",
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
        console.print("[muted]Options:[/muted]")
        for opt, desc in explanation["options"].items():
            console.print(f"  {opt}: {desc}")
        console.print()


def _agents_md_content(project_name: str) -> str:
    """Generate AGENTS.md content."""
    return f"""# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

The CLI is self-documenting. Run these commands to see workflows:

```bash
lodestar agent     # Agent registration workflow
lodestar task      # Task management workflow
lodestar msg       # Messaging workflow
```

## Quick Start

```bash
lodestar doctor                        # Check repository health
lodestar agent join --name "Your Name" # Register, SAVE the agent ID
lodestar task next                     # Find available work
```

## Finding Work

```bash
# Get next claimable task (status=ready, all deps verified, no active lease)
lodestar task next

# Get multiple options to choose from
lodestar task next --count 5

# Browse all tasks
lodestar task list

# Filter by status or label
lodestar task list --status ready
lodestar task list --label feature
lodestar task list --status done

# View deleted tasks
lodestar task list --include-deleted
lodestar task list --status deleted

# Get full task details
lodestar task show F001
lodestar task show F001 --json    # For programmatic access
```

## Complete Workflow Example

```bash
# 1. Register as an agent (save your ID!)
lodestar agent join --name "Agent-1"
# Output: Registered agent A1234ABCD

# 2. Find available work
lodestar task next --count 3

# 3. Claim before working (creates 15-min lease)
lodestar task claim F001 --agent A1234ABCD

# 4. Do the work...
#    If it takes longer than 10 min, renew the lease:
lodestar task renew F001 --agent A1234ABCD

# 5. Complete the task
lodestar task done F001
lodestar task verify F001

# Alternative: Release if you can't complete
lodestar task release F001
```

## Creating Tasks

Write **detailed descriptions** so executing agents have full context.

### Basic Task

```bash
lodestar task create --title "Fix login bug" --label bug --priority 1
```

### Full Task with Dependencies

```bash
lodestar task create \\
    --id "F001" \\
    --title "Add user authentication" \\
    --description "WHAT: Implement OAuth2 login. WHERE: src/auth/. WHY: Users need SSO. ACCEPT: Tests pass, login works." \\
    --depends-on "F000" \\
    --label feature \\
    --priority 2
```

### Task with PRD References

```bash
# Reference sections in a PRD file
lodestar task create \\
    --title "Implement caching layer" \\
    --prd-source "PRD.md" \\
    --prd-ref "#caching-requirements" \\
    --prd-ref "#performance-targets"

# Or embed a frozen excerpt directly
lodestar task create \\
    --title "Add rate limiting" \\
    --prd-excerpt "Rate limit: 100 req/min per user. Use Redis for distributed counting."
```

### Task Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--id` | | Task ID (auto-generated if omitted) |
| `--title` | `-t` | Task title (required) |
| `--description` | `-d` | WHAT/WHERE/WHY/ACCEPT format recommended |
| `--priority` | `-p` | Lower number = higher priority (default: 100) |
| `--status` | `-s` | Initial status (default: ready) |
| `--depends-on` | | Task IDs this depends on (repeatable) |
| `--label` | `-l` | Labels for categorization (repeatable) |
| `--prd-source` | | Path to PRD file |
| `--prd-ref` | | PRD section anchors (repeatable) |
| `--prd-excerpt` | | Frozen PRD text to embed |

## Multi-Agent File Coordination

When multiple agents work concurrently, use the `locks` field to declare file ownership:

```yaml
# In spec.yaml
F001:
  title: Implement auth
  locks:
    - src/auth/**
    - tests/auth/**
```

When claiming a task, you'll see warnings if locks overlap with other claimed tasks:

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
WARNING: Lock 'src/auth/**' overlaps with 'src/**' (task F001, claimed by A9876WXYZ)

Use --force to bypass lock conflict warnings
```

Use `--force` when you intentionally coordinate with another agent.

## CLI Quick Reference

| Command | Key Options |
|---------|-------------|
| `task list` | `--status`, `--label`, `--include-deleted` |
| `task next` | `--count` |
| `task show <id>` | `--json` |
| `task create` | `--title`, `--description`, `--priority`, `--depends-on`, `--label`, `--prd-source`, `--prd-ref`, `--prd-excerpt` |
| `task claim <id>` | `--agent`, `--force` |
| `task renew <id>` | `--agent` |
| `task done <id>` | |
| `task verify <id>` | |
| `task delete <id>` | `--cascade` |

## Get Help

```bash
lodestar <command> --help    # See all options
lodestar <command> --explain # Understand what it does
```

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |
"""


def _create_mcp_configs(root: Path, force: bool = False) -> list[Path]:
    """Create MCP configuration files. Returns list of created file paths."""
    created = []

    # VS Code / Copilot config
    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    vscode_mcp = vscode_dir / "mcp.json"
    if not vscode_mcp.exists() or force:
        vscode_mcp.write_text(
            json.dumps(
                {
                    "servers": {
                        "Lodestar": {
                            "type": "stdio",
                            "command": "lodestar",
                            "args": ["mcp", "serve", "--repo", "."],
                        }
                    },
                    "inputs": [],
                },
                indent=2,
            )
            + "\n"
        )
        created.append(vscode_mcp)

    # Claude Code project-scoped config
    claude_mcp = root / ".mcp.json"
    if not claude_mcp.exists() or force:
        claude_mcp.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "Lodestar": {
                            "type": "stdio",
                            "command": "lodestar",
                            "args": ["mcp", "serve", "--repo", "."],
                        }
                    }
                },
                indent=2,
            )
            + "\n"
        )
        created.append(claude_mcp)

    return created


def _agents_md_content_mcp(project_name: str) -> str:
    """Generate MCP-optimized AGENTS.md content."""
    return f"""# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## MCP Tools (Preferred)

When connected via MCP, use the `lodestar_*` tools directly. MCP is the preferred method for agents.

### Quick Start

```
lodestar_agent_join(name="Your Name")     # Register, SAVE the agentId
lodestar_task_next()                       # Find available work
lodestar_task_claim(task_id="F001", agent_id="YOUR_ID")
```

### Agent Workflow

```
1. JOIN      lodestar_agent_join()         -> Get your agentId
2. FIND      lodestar_task_next()          -> Get claimable tasks
3. CLAIM     lodestar_task_claim()         -> Create 15-min lease
4. CONTEXT   lodestar_task_context()       -> Get PRD context
5. WORK      (implement the task)
6. DONE      lodestar_task_done()          -> Mark complete
7. VERIFY    lodestar_task_verify()        -> Unblock dependents
```

### MCP Tool Reference

| Category | Tool | Purpose |
|----------|------|---------|
| **Repo** | `lodestar_repo_status` | Get project status, task counts, next actions |
| **Agent** | `lodestar_agent_join` | Register as agent (returns agentId) |
| | `lodestar_agent_heartbeat` | Update presence (call every 5 min) |
| | `lodestar_agent_leave` | Mark offline gracefully |
| | `lodestar_agent_list` | List all registered agents |
| **Task Query** | `lodestar_task_next` | Get claimable tasks (dependency-aware) |
| | `lodestar_task_list` | List tasks with filtering |
| | `lodestar_task_get` | Get full task details |
| | `lodestar_task_context` | Get PRD context for a task |
| **Task Mutation** | `lodestar_task_claim` | Claim task (15-min lease) |
| | `lodestar_task_release` | Release claim (if blocked) |
| | `lodestar_task_done` | Mark task complete |
| | `lodestar_task_verify` | Verify task (unblocks deps) |
| **Message** | `lodestar_message_send` | Send to agent or task thread |
| | `lodestar_message_list` | Get inbox messages |
| | `lodestar_message_ack` | Mark messages as read |
| **Events** | `lodestar_events_pull` | Pull event stream |

### Handoff Pattern

When blocked or ending session before completion:

```
lodestar_task_release(task_id="F001", agent_id="YOUR_ID", reason="Blocked on API approval")
lodestar_message_send(task_id="F001", from_agent_id="YOUR_ID", body="Progress: 60% complete. Tests passing.")
```

## CLI Commands (No MCP Equivalent)

These operations require CLI:

| Command | Purpose |
|---------|---------|
| `lodestar init` | Initialize repository |
| `lodestar doctor` | Health check |
| `lodestar task create` | Create new tasks |
| `lodestar task update` | Update task fields |
| `lodestar task delete` | Delete tasks (--cascade for deps) |
| `lodestar task renew` | Extend lease duration |
| `lodestar task graph` | Export dependency graph |
| `lodestar export snapshot` | Export full state |

### Creating Tasks (CLI Only)

```bash
lodestar task create \\
    --id "F001" \\
    --title "Add authentication" \\
    --description "WHAT: Implement OAuth2. WHERE: src/auth/. ACCEPT: Tests pass." \\
    --depends-on "F000" \\
    --label feature \\
    --priority 2
```

### Task with PRD References (CLI Only)

```bash
lodestar task create \\
    --title "Implement caching" \\
    --prd-source "PRD.md" \\
    --prd-ref "#caching-requirements"
```

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |

## Help

```bash
lodestar <command> --help     # CLI options
lodestar <command> --explain  # What it does
```
"""
