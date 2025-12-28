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

# Documentation
uv run mkdocs serve                  # Local docs preview
uv run mkdocs build                  # Build static docs
```

## Documentation

This project uses **mkdocs** with the Material theme for documentation. Docs are in the `docs/` directory.

### When to Update Documentation

Update docs whenever you:
- Add, modify, or remove CLI commands
- Change command flags or output formats
- Modify core concepts (spec/runtime planes, leases, scheduling)
- Add new features or workflows
- Fix bugs that affect documented behavior

### Documentation Structure

```
docs/
├── index.md              # Landing page / overview
├── getting-started.md    # Installation and quickstart
├── concepts/             # Architecture and core concepts
│   ├── two-plane-model.md
│   ├── task-lifecycle.md
│   └── lease-mechanics.md
├── cli/                  # CLI command reference
│   ├── index.md
│   ├── agent.md
│   ├── task.md
│   └── msg.md
├── guides/               # How-to guides
│   ├── agent-workflow.md
│   └── ci-integration.md
└── reference/            # API and schema reference
```

### Documentation Standards

- Keep CLI examples up-to-date with actual command output
- Use `--json` output examples for programmatic usage
- Include both human and AI agent perspectives in guides
- Cross-reference related sections
- Test all code examples before committing

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

### Soft-Delete Semantics

- Tasks are soft-deleted (status set to `deleted`), not physically removed
- Deleted tasks are hidden from `task list` by default
- Use `task list --include-deleted` or `task list --status deleted` to view deleted tasks
- Deleting a task with dependents requires `--cascade` flag
- Cascade delete recursively deletes all downstream dependent tasks

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
lodestar agent join              # Register as agent (--role, --capability for metadata)
lodestar agent list              # List all agents (shows role/capabilities)
lodestar agent find              # Find agents by --capability or --role
lodestar agent show <id>         # Show agent details
lodestar agent heartbeat <id>    # Update heartbeat

# Task operations
lodestar task list               # List all tasks
lodestar task show <id>          # Show task details
lodestar task next               # Find claimable tasks
lodestar task create             # Create new task
lodestar task update <id>        # Update task
lodestar task claim <id>         # Claim a task (lease, --force bypasses lock warnings)
lodestar task renew <id>         # Renew lease
lodestar task release <id>       # Release lease
lodestar task done <id>          # Mark done
lodestar task verify <id>        # Mark verified
lodestar task delete <id>        # Soft-delete task (--cascade for dependents)
lodestar task graph              # Export dependency graph

# Messaging
lodestar msg send <to>           # Send message
lodestar msg list                # List threads
lodestar msg thread <id>         # Show thread

# Export
lodestar export snapshot         # Export full state
```

All commands support `--json`, `--schema`, and `--explain` flags.

---

## Dogfooding: This Repo Uses Lodestar (MANDATORY)

This project uses **lodestar itself** for task management. **You MUST use lodestar commands** to create, fetch, and manage tasks—do not edit `.lodestar/spec.yaml` directly.

### Task Management Requirements

**Finding Work:**
- Run `uv run lodestar task next` to find available tasks
- Run `uv run lodestar task list` to see all tasks
- Run `uv run lodestar task show <id>` to see task details

**Creating Tasks:**
- Use `uv run lodestar task create` to add new tasks
- Always include `--title`, `--description`, and appropriate `--label`
- Set `--depends-on` when tasks have prerequisites
- Set `--priority` (lower = higher priority)

```bash
# Example: Create a new feature task
uv run lodestar task create \
  --id "F099" \
  --title "Implement new feature" \
  --description "Description of what needs to be done" \
  --priority 2 \
  --label feature \
  --depends-on "F001"
```

**Working on Tasks:**
- Claim before starting: `uv run lodestar task claim <id>`
- Renew if needed: `uv run lodestar task renew <id>`
- Release if blocked: `uv run lodestar task release <id>`

**Completing Tasks:**
- Mark done: `uv run lodestar task done <id>`
- Verify: `uv run lodestar task verify <id>`

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

# Finding tasks
uv run lodestar task next        # Find claimable tasks
uv run lodestar task list        # List all tasks
uv run lodestar task show <id>   # Show task details

# Creating tasks
uv run lodestar task create --title "..." --priority 1 --label feature

# Working on tasks
uv run lodestar task claim <id>  # Claim a task
uv run lodestar task renew <id>  # Extend lease
uv run lodestar task release <id> # Release without completing

# Completing tasks
uv run lodestar task done <id>   # Mark task done
uv run lodestar task verify <id> # Mark task verified

# Deleting tasks
uv run lodestar task delete <id>         # Soft-delete (hides from list)
uv run lodestar task delete <id> --cascade # Delete with all dependents
uv run lodestar task list --include-deleted # Show deleted tasks

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
- **Changing CLI commands without updating documentation**
- **Editing `.lodestar/spec.yaml` directly** — use `lodestar task create/update` commands
- **Working on tasks without claiming them first** — use `lodestar task claim`

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
uv run mkdocs build                  # Docs build (if docs exist)
```

**Record results:**

```markdown
#### Pre-Commit Verification
| Command | Exit Code | Notes |
|---------|-----------|-------|
| ruff check | 0 | All passed |
| ruff format --check | 0 | All formatted |
| pytest | 0 | 84 tests passed |
| mkdocs build | 0 | Docs built |
```

Only commit if all checks pass.
