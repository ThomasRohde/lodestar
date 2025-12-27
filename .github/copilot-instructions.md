# Lodestar — Agent Instructions

Lodestar is a **Python CLI tool for multi-agent coordination in Git repositories**. It provides agents with task claiming, dependency tracking, and messaging—without human scheduling.

## Architecture Overview

### Two-Plane State Model
- **Spec plane** (versioned): `.lodestar/spec.yaml` — tasks, dependencies, acceptance criteria (committed)
- **Runtime plane** (ephemeral): `.lodestar/runtime.sqlite` — agents, leases, messages (gitignored)

### Package Layout
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

## Tech Stack

| Component | Choice | Notes |
|-----------|--------|-------|
| Python | 3.12+ | Use `uv` for dev workflow |
| CLI | Typer | `--json`, `--schema`, `--explain` on every command |
| Output | Rich | Tables/panels for TTY; no ANSI in `--json` mode |
| Models | Pydantic v2 | Strict schemas, auto JSON Schema export |
| Runtime DB | SQLite WAL | `portalocker` for spec writes |
| Spec format | YAML | `.lodestar/spec.yaml` |

## Critical Patterns

### JSON Envelope (all `--json` output)
```json
{
  "ok": true,
  "data": { ... },
  "next": [{"intent": "task.next", "cmd": "lodestar task next"}],
  "warnings": []
}
```

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

## Developer Workflow

```bash
# Setup
uv sync                          # Install deps
uv run pytest                    # Run tests
uv run ruff check src tests      # Lint
uv run ruff format src tests     # Format

# CLI development
uv run lodestar --help           # Test CLI entrypoint
uv run pytest -k "test_name"     # Run specific test
```

## Key References

- [PRD.md](../PRD.md) — Full product requirements with command specs
- `.lodestar/spec.yaml` — Task definitions (versioned)
- `.lodestar/runtime.sqlite` — Agent state (gitignored)
- `AGENTS.md` — Generated contract for agents entering repos using Lodestar

## Bootstrapping Strategy

**Lodestar is built using klondike, then will dogfood itself.**

1. **Phase 1 (now)**: Use `klondike` CLI for session/feature tracking during development
2. **Phase 2**: Once core Lodestar features work, migrate to `lodestar` for self-coordination
3. **Phase 3**: Deprecate klondike dependency

### Current: Session Management (via klondike)
```bash
klondike status                  # Project overview
klondike feature list            # See features to implement
klondike session start --focus "description"
klondike session end --summary "..." --next "..."
```

## Testing Strategy

- **Unit tests**: DAG validation, lease behaviors, scheduling rules, schema stability
- **Integration tests**: Concurrent claims from multiple processes, spec locking
- **Golden tests**: CLI `--json` output snapshots
- Test CLI end-to-end: `uv run lodestar <cmd>` with assertions on output
