# Lodestar — Agent Instructions

Lodestar is a **Python CLI tool for multi-agent coordination in Git repositories**. It provides agents with task claiming, dependency tracking, and messaging—without human scheduling.

## Architecture Overview

### Two-Plane State Model
- **Spec plane** (versioned): `.lodestar/spec.yaml` — tasks, dependencies, acceptance criteria (committed)
- **Runtime plane** (ephemeral): `.lodestar/runtime.sqlite` — agents, leases, messages (gitignored)

### Package Layout
```
src/lodestar/
├── cli/           # Typer app + commands/ subdir for each command group
├── core/          # Domain services (scheduling, claims, validation)
├── spec/          # loader.py (YAML + portalocker), dag.py (cycle detection)
├── runtime/       # database.py (SQLite WAL, CRUD for agents/leases/messages)
├── models/        # Pydantic v2: envelope.py, spec.py, runtime.py
├── mcp/           # Optional MCP server (exposes tools)
└── util/          # paths.py, output.py (Rich + JSON), time.py
```

## Tech Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Python | 3.12+ | Use `uv` for dev workflow |
| CLI | Typer | `--json`, `--schema`, `--explain` on every command |
| Output | Rich | Custom theme in `util/output.py`; no ANSI in `--json` mode |
| Models | Pydantic v2 | Strict schemas, auto JSON Schema export |
| Runtime DB | SQLite WAL | `runtime/database.py` handles all CRUD |
| Spec format | YAML | `spec/loader.py` with `portalocker` for atomic writes |

## Critical Patterns

### JSON Envelope (all `--json` output)
Every command wraps output in `models/envelope.py`:
```python
Envelope.success(data, next_actions=[NEXT_ACTION_TASK_NEXT])
```
Returns: `{"ok": true, "data": {...}, "next": [...], "warnings": []}`

### CLI Command Structure
Commands live in `cli/commands/<name>.py`. Each command:
1. Accepts `--json`, `--explain` options
2. Uses `print_json()` for JSON mode, `console.print()` for Rich
3. Returns `Envelope` for consistent output
4. See [status.py](src/lodestar/cli/commands/status.py#L1) as the canonical example

### Lease-Based Task Claims
- `RuntimeDatabase.create_lease()` is atomic (SQLite transaction)
- Leases auto-expire; `is_expired()` checks `expires_at > now`
- No daemon needed—expiry checked at read time

### Task Scheduling
- Task is **claimable** when: `status == ready` AND all `depends_on` are `verified`
- `Spec.get_claimable_tasks()` returns sorted by priority
- DAG validation in `spec/dag.py`: cycles, missing deps, orphans

### Path Discovery
- `util/paths.py`: `find_lodestar_root()` walks up to find `.lodestar/`
- All commands work from any subdirectory

## Developer Workflow

```bash
# Setup
uv sync                          # Install deps
uv run pytest                    # Run tests
uv run ruff check src tests      # Lint
uv run ruff format src tests     # Format

# CLI development
uv run lodestar --help           # Test CLI entrypoint
uv run lodestar status --json    # Test JSON output
uv run pytest -k "test_name"     # Run specific test
```

## Key References

- [PRD.md](../PRD.md) — Full product requirements with command specs
- [src/lodestar/models/](../src/lodestar/models/) — All Pydantic models
- [src/lodestar/cli/commands/status.py](../src/lodestar/cli/commands/status.py) — Canonical command pattern

## CLI Command Reference

```bash
# Top-level commands
lodestar init                    # Initialize repository
lodestar status                  # Show status + next actions
lodestar doctor                  # Health check

# Agent management
lodestar agent join              # Register as agent
lodestar agent list              # List all agents
lodestar agent show <id>         # Show agent details
lodestar agent heartbeat <id>    # Update heartbeat

# Task operations
lodestar task list               # List all tasks
lodestar task show <id>          # Show task details
lodestar task next               # Find claimable tasks
lodestar task create             # Create new task
lodestar task update <id>        # Update task
lodestar task claim <id>         # Claim a task (lease)
lodestar task renew <id>         # Renew lease
lodestar task release <id>       # Release lease
lodestar task done <id>          # Mark done
lodestar task verify <id>        # Mark verified
lodestar task graph              # Export dependency graph

# Messaging
lodestar msg send <to>           # Send message
lodestar msg list                # List threads
lodestar msg thread <id>         # Show thread

# Export
lodestar export snapshot         # Export full state
```

All commands support `--json`, `--schema`, and `--explain` flags.

## Dogfooding: This Repo Uses Lodestar

This project uses **lodestar itself** for task management. Tasks are defined in `.lodestar/spec.yaml`.

### Task Creation
```bash
# Create a task
lodestar task create --title "My task" --priority 1 --label "feature"

# With dependencies
lodestar task create --title "Step 2" --depends-on "STEP-001"
```

### Agent Workflow
```bash
lodestar status                  # Project overview
lodestar agent join              # Register as agent
lodestar task next               # Find available work
lodestar task claim <id>         # Claim a task
lodestar task done <id>          # Mark task complete
lodestar task verify <id>        # Verify task
```

## Testing Strategy

- **Unit tests**: `tests/test_models.py`, `test_spec.py`, `test_runtime.py`
- **Integration tests**: Concurrent claims, spec locking
- **Golden tests**: CLI `--json` output snapshots
- Test CLI end-to-end: `uv run lodestar <cmd>` with assertions on output
