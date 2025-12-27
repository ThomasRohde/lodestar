# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Lodestar** is a Python CLI tool for multi-agent coordination in Git repositories. It provides agents with task claiming (via leases), dependency tracking, and messaging—without requiring human scheduling.

- **CLI name**: `lodestar`
- **Package**: `lodestar-cli` (PyPI)
- **Python**: 3.12+
- **Full spec**: See [PRD.md](PRD.md) for complete product requirements

### Two-Plane State Model (Core Concept)

| Plane | Purpose | Location | Git Status |
|-------|---------|----------|------------|
| **Spec** | Tasks, dependencies, acceptance criteria | `.lodestar/spec.yaml` | Committed |
| **Runtime** | Agents, leases, heartbeats, messages | `.lodestar/runtime.sqlite` | Gitignored |

### Package Structure

```
src/lodestar/
├── cli/        # Typer commands, output formatting
├── core/       # Domain services (scheduling, claims, validation)
├── spec/       # YAML spec load/validate/save, DAG validation
├── runtime/    # SQLite access layer + migrations
├── models/     # Pydantic v2 models + JSON Schema export
├── mcp/        # Optional MCP server (exposes tools)
└── util/       # Locks, time parsing, path globs
```

## Development Commands

```bash
# Environment
uv sync                              # Install dependencies

# Testing
uv run pytest                        # Run all tests
uv run pytest -k "test_name"         # Run specific test
uv run pytest tests/test_cli.py      # Run test file

# Linting & Formatting
uv run ruff check src tests          # Lint
uv run ruff format src tests         # Format
uv run ruff format --check src tests # Format check (CI)

# CLI
uv run lodestar --help               # Test CLI
uv run lodestar init                 # Initialize repo
```

## Critical Patterns

### JSON Envelope (all `--json` output must follow this)

```json
{
  "ok": true,
  "data": { ... },
  "next": [{"intent": "task.next", "cmd": "lodestar task next"}],
  "warnings": []
}
```

Every command must support `--json`, `--schema`, and `--explain` flags.

### Lease-Based Task Claims

- Claims have TTL (default 15m); auto-expire without daemon
- One active lease per task (atomic via SQLite transaction)
- "Active claims" = filter out expired leases at read time

### Task Scheduling Rules

- Task is **claimable** when: `status == ready` AND all `depends_on` are `verified`
- `lodestar task next` returns only claimable tasks, sorted by priority

### Progressive Discovery

- No-args commands return "next actions" suggestions
- Interactive prompts only when TTY; require explicit flags otherwise

## Tech Stack

| Component | Choice |
|-----------|--------|
| CLI | Typer |
| Output | Rich (no ANSI in --json mode) |
| Models | Pydantic v2 |
| Runtime DB | SQLite with WAL |
| Spec locking | portalocker |
| Spec format | YAML |

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
lodestar task claim <id>         # Claim a task (lease)
lodestar task renew <id>         # Renew lease
lodestar task release <id>       # Release lease
lodestar task done <id>          # Mark done
lodestar task verify <id>        # Mark verified
lodestar task block <id>         # Mark blocked
lodestar task add                # Add new task
lodestar task edit <id>          # Edit task
lodestar task deps <id>          # Show dependencies
lodestar task validate           # Validate DAG

# Messaging
lodestar msg send <to>           # Send message
lodestar msg list                # List threads
lodestar msg thread <id>         # Show thread

# Export
lodestar export snapshot         # Export full state
```

All commands support `--json`, `--schema`, and `--explain` flags.

---

## Dogfooding: This Repo Uses Lodestar

This project uses **lodestar itself** for task management. Tasks are defined in `.lodestar/spec.yaml`.

### Agent Workflow

#### Starting a Session

1. Run `pwd` / `Get-Location` to confirm working directory
2. Run `uv run lodestar status` to see project status and task counts
3. Run `uv run lodestar doctor` to verify repository health
4. Check `git log --oneline -10` for recent commits
5. Run `uv run lodestar agent join` to register as an agent
6. Run `uv run lodestar task next` to find available work

#### During a Session

- Work on **ONE task at a time**
- Claim before working: `uv run lodestar task claim <id> --agent <your-id>`
- Renew lease if task takes longer: `uv run lodestar task renew <id>`
- Make atomic, reviewable commits with descriptive messages
- Test incrementally - don't batch testing to the end

#### Completing a Task

1. Ensure code passes linting and tests
2. Commit all changes
3. Mark task done: `uv run lodestar task done <id>`
4. Verify the task: `uv run lodestar task verify <id>`

### Lodestar Quick Reference

```bash
# Status
uv run lodestar status           # Project overview
uv run lodestar doctor           # Health check

# Task management
uv run lodestar task list        # List all tasks
uv run lodestar task next        # Find claimable tasks
uv run lodestar task show <id>   # Show task details
uv run lodestar task claim <id>  # Claim a task
uv run lodestar task done <id>   # Mark task done
uv run lodestar task verify <id> # Mark task verified

# Agent management
uv run lodestar agent join       # Register as agent
uv run lodestar agent list       # List agents
```

## Prohibited Behaviors

- Leaving code in broken/half-implemented state
- Making changes without committing and documenting
- Marking tasks as verified without end-to-end testing
- **Committing without running build checks first**
- **Committing without running tests first**
- **Leaving the repository with failing builds or tests**

## Testing Standards

- Always verify features as a user would (end-to-end)
- For CLI tools: run actual commands, check output
- Document any testing limitations in commit messages

## Git Hygiene

- Commit early, commit often
- Use conventional commit messages
- Tag stable checkpoints
- Use `git revert` to recover from bad changes
- Never force push without documenting why

## Pre-Commit Verification (MANDATORY)

Before committing, run:

```bash
uv run ruff check src tests          # Lint
uv run ruff format --check src tests # Format check
uv run pytest                        # Tests
```

**Record results:**

```markdown
#### Pre-Commit Verification
| Command | Exit Code | Notes |
|---------|-----------|-------|
| ruff check | 0 | All passed |
| ruff format --check | 0 | All formatted |
| pytest | 0 | 84 tests passed |
```

Only commit if all checks pass.
