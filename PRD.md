# Lodestar — Agent-Native Repo Orchestration (Greenfield PRD)

## Summary

Lodestar is a lightweight coordination layer for **agentic coding in a single Git repository**. It provides a self-explanatory CLI and MCP surface so **agents (and sub-agents spawned by other agents)** can reliably discover what to do, claim work, respect dependencies, communicate, and report progress—without a human acting as the “scheduler”.

Product name: **Lodestar**  
CLI name: **`lodestar`**  
Primary design principle: **Progressive discovery** (safe defaults, “next actions” guidance, machine-readable outputs)

This is a greenfield project that borrows the best ideas from Klondike (clear spec, session isolation, agent-friendly interfaces), but starts clean with a multi-agent-first architecture.

---

## Problem

Modern coding agents can spawn sub-agents and coordinate among themselves, but repos don’t provide a consistent “coordination contract”. Teams end up with:
- ad-hoc prompts and tribal knowledge
- duplicate work and conflicting edits
- unclear ownership (“who is doing what?”)
- blocked work due to invisible dependencies
- no durable communication channel between agents

Humans become the bottleneck: manually spawning agents, assigning tasks, and resolving confusion.

---

## Goals

1. **Self-explanatory for agents**
   - An agent that enters the repo can run one command and understand how to proceed.
2. **Many agents, one repo**
   - Support dozens of concurrently running agents without corrupting state or creating constant merge conflicts.
3. **Task claiming + dependencies**
   - Agents can claim tasks using leases (auto-expire) and can only claim tasks whose dependencies are satisfied.
4. **Agent identity**
   - Every agent session gets a stable identity and heartbeat.
5. **Tool-mediated communication**
   - Agents can message each other (direct + per-task threads) via the CLI/MCP tools.
6. **Progressive discovery UX**
   - Safe defaults, clear next steps, interactive when TTY, strict machine outputs when not.

---

## Non-goals (v1)

- Full project management suite (no Jira replacement)
- Automatic “merge conflict resolution”
- Mandatory worktree workflow (supported as optional later)
- Long-running daemon requirement (should work as command-invoked tool; optional background mode later)

---

## Primary users

- **Coding agents** (Claude Code, Copilot, Codex CLI, custom agents) including **sub-agents spawned by other agents**
- **Engineers** who want a simple, visible agent coordination layer
- **CI systems** that validate and summarize agent work

---

## Success metrics

- A fresh agent can perform first useful action within **60 seconds** by running `lodestar agent join`.
- Task collisions (two agents implementing the same thing) reduced by **>80%** compared to baseline.
- “Stale claimed tasks” are automatically released via lease expiry (no permanent deadlocks).
- “What should I do next?” is answerable via `lodestar task next` with no extra context.

---

## Product principles

1. **Two-plane state model**
   - **Spec plane** (versioned): tasks, dependencies, acceptance criteria.
   - **Runtime plane** (ephemeral, unversioned): agents, leases, heartbeats, messages, live status.

2. **Everything is tool-friendly**
   - Every command supports `--json` output.
   - Schemas are available via `--schema` and exported as JSON Schema.

3. **Safe-by-default**
   - Read operations are always safe.
   - Writes use atomic updates and concurrency-safe locks.

4. **Progressive discovery**
   - No-args and minimal commands return a “next actions” list.
   - Interactive prompts only when TTY; otherwise require explicit flags.

---

## User stories

### Agent onboarding
- As an agent, I run `lodestar agent join` and receive my identity plus the top next commands.
- As an orchestrator agent, I can request a sub-agent brief for a task.

### Task scheduling
- As an agent, I ask for `lodestar task next` and receive claimable tasks filtered by dependencies.
- As an agent, I claim a task for a limited time (lease) and renew it while working.

### Communication
- As an agent, I send a message to another agent or to a task thread.
- As an agent, I can read my inbox and task threads since a cursor.

### Status & audit
- As a human, I can run `lodestar status` to see agents, claims, blocked tasks.
- As CI, I can export a JSON snapshot of current spec + runtime state.

---

## CLI experience (Typer + progressive discovery)

### Technology
- **Python 3.12+**
- **Typer** for CLI (command tree, help, validation)
- **Rich** for human-readable output (tables, panels); no Rich output in `--json`
- **Pydantic v2** for models + JSON Schema export
- **SQLite** (runtime plane) with WAL enabled for concurrency
- **YAML** (spec plane) stored in repo (committed)

### Core discovery behaviors
1. `lodestar` (no args) prints:
   - repo initialized? yes/no
   - agent registered? yes/no
   - summary counts: tasks ready/blocked/claimed, active agents
   - **Next actions**: 3–5 suggested commands

2. `lodestar agent join` is the canonical entrypoint for agents:
   - registers agent identity (or resumes if already registered)
   - starts heartbeat lease (optional)
   - returns JSON (if `--json`) with `agent_id` and suggested next commands

3. Every command supports:
   - `--json` (strict JSON output)
   - `--schema` (JSON Schema for the JSON output)
   - `--explain` (short, agent-friendly explanation of what the command does)

### Command set (v1)

Top level:
- `lodestar init`
- `lodestar status`
- `lodestar doctor`
- `lodestar export snapshot`

Agent:
- `lodestar agent join`
- `lodestar agent list`
- `lodestar agent heartbeat`
- `lodestar agent brief --task T123 [--format copilot|claude|generic]`

Task:
- `lodestar task list`
- `lodestar task show T123`
- `lodestar task create`
- `lodestar task update T123`
- `lodestar task next`
- `lodestar task claim T123 [--ttl 15m]`
- `lodestar task renew T123`
- `lodestar task release T123`
- `lodestar task done T123`
- `lodestar task verify T123`
- `lodestar task graph` (export DAG as JSON; optional dot)

Messaging:
- `lodestar msg send --to agent:A1|task:T123 --text "..."`
- `lodestar msg inbox [--since CURSOR]`
- `lodestar msg thread T123 [--since CURSOR]`

MCP (optional in v1, but designed in):
- `lodestar mcp serve` (exposes the same operations as tools)

---

## Spec plane design (versioned)

### Location
- `.lodestar/spec.yaml` (committed)
- `.lodestar/README.md` (optional, committed)
- Root `AGENTS.md` (committed, short “agent contract”)

### `spec.yaml` structure (v1)

- `project`: name, default branch, optional conventions
- `tasks`: dictionary keyed by `task_id`
- `features` (optional): group tasks (narrative container)

Task fields:
- `id`: string, e.g. `T123` or `AUTH-001`
- `title`: short string
- `description`: short paragraph
- `acceptance_criteria`: list of bullet strings
- `depends_on`: list of task ids
- `labels`: list of strings (e.g., “frontend”, “tests”)
- `locks` (optional): glob patterns of files/dirs “owned” by this task (soft-lock)
- `priority`: integer (default 100)
- `status`: `todo|ready|blocked|done|verified`  
  (Note: `claimed` is runtime, not spec)
- `created_at`, `updated_at` (ISO date-time)

Rules:
- A task is **claimable** when `status == ready` and all `depends_on` are `verified` (or configured threshold).
- Spec changes are atomic and validated (no cycles in DAG).

---

## Runtime plane design (ephemeral)

### Location
- `.lodestar/runtime.sqlite` (gitignored)
- `.lodestar/runtime.jsonl` (optional audit log, gitignored)

### SQLite (WAL) tables (v1)

`agents`
- `agent_id` (pk)
- `display_name`
- `created_at`
- `last_seen_at`
- `capabilities` (json)
- `session_meta` (json) — tool name, model, etc.

`leases`
- `lease_id` (pk)
- `task_id`
- `agent_id`
- `expires_at`
- `created_at`
- unique constraint: one active lease per task

`messages`
- `message_id` (pk)
- `created_at`
- `from_agent_id`
- `to_type` (`agent` or `task`)
- `to_id` (agent_id or task_id)
- `text`
- `meta` (json)

`events` (optional)
- append-only audit events (claim/release/done/verify/message)

### Lease semantics
- Claim: transaction checks task claimable + no active lease -> inserts lease
- Renew: only current agent can renew; extends `expires_at`
- Expiry: leases treated as inactive after `expires_at` (no background daemon required)
- Commands that read “active claims” filter out expired leases automatically

---

## Key workflows

### Workflow A: New agent arrives
1. Agent runs: `lodestar agent join --json`
2. Lodestar returns:
   - `agent_id`
   - “next actions” (e.g., `task next`, `status`)
3. Agent runs `lodestar task next --json`
4. Agent claims: `lodestar task claim T123 --ttl 15m`

### Workflow B: Orchestrator spawns sub-agent
1. Orchestrator runs: `lodestar agent brief --task T123 --format claude`
2. Lodestar outputs a concise brief:
   - goal
   - acceptance criteria
   - allowed paths/locks
   - exact check commands
   - how to report back via `lodestar msg send`

### Workflow C: Dependencies
- `task next` only returns tasks whose deps are satisfied.
- `task graph` provides DAG for smarter external scheduling.

### Workflow D: Communication
- Agents post progress to the task thread:
  - `lodestar msg send --to task:T123 --text "Implemented X; tests passing."`
- Orchestrator reads thread to decide next action.

---

## Architecture

### Modules (Python package layout)
- `lodestar.cli` — Typer app, command wiring, output formatting
- `lodestar.core` — domain services (task scheduling, claim logic, validation)
- `lodestar.spec` — YAML spec load/validate/save + DAG validation
- `lodestar.runtime` — SQLite access layer + migrations
- `lodestar.models` — Pydantic models + schemas
- `lodestar.mcp` — optional MCP server exposing tools
- `lodestar.util` — locks, time parsing, path globs, JSON output

### Concurrency and locking
- Spec writes guarded by a file lock (e.g., `portalocker`) and atomic replace-write.
- Runtime uses SQLite WAL for concurrent access and transactions for claims.

### Output design
Every command returns a consistent envelope when `--json` is used:

```json
{
  "ok": true,
  "data": { "...": "..." },
  "next": [
    {"intent": "task.next", "cmd": "lodestar task next"},
    {"intent": "status", "cmd": "lodestar status"}
  ],
  "warnings": []
}
```

---

## Smart tech choices

- **SQLite WAL** for concurrency without requiring a daemon.
- **Pydantic** for strict schemas and agent-safe outputs.
- **Typer + Rich** for excellent human UX while preserving machine output.
- **Explicit “two-plane state”** to avoid git conflicts and preserve repo cleanliness.
- **Optional MCP server** for agents that prefer tool calls over shelling out.

---

## Initialization & repo footprint

`lodestar init` creates:
- `.lodestar/spec.yaml`
- `.lodestar/.gitignore` entry for runtime files
- root `AGENTS.md` (short)
- optional GitHub Actions snippet (later milestone)

Minimal `AGENTS.md` content (generated):
- “Run `lodestar agent join` first”
- “Use `lodestar task next` to pick work”
- “Use `lodestar msg` to communicate”
- “Never edit `.lodestar/runtime.sqlite`”

---

## Security & safety

- No network access required.
- All data stored locally in repo directory.
- Commands validate inputs; `--json` mode never emits ANSI.
- “Dangerous” operations (e.g., rewriting spec) require explicit flags when not TTY.

---

## Testing strategy

- Unit tests for:
  - DAG validation (cycles, missing deps)
  - lease claims/renew/expiry behaviors
  - `task next` scheduling rules
  - JSON schema generation stability

- Integration tests:
  - concurrent claims from multiple processes
  - spec write locking and atomicity

- Golden tests:
  - CLI `--json` output snapshots per command

Tooling:
- `pytest`, `ruff`, `mypy` (or pyright), `pre-commit`

---

## Packaging and distribution

- Build system: `hatchling` (or `setuptools` acceptable)
- Recommended dev workflow: `uv` (fast, modern) but not required
- Publish to PyPI as `lodestar-cli`
- Entry point: `lodestar`

---

## Milestones

### M0 — Skeleton (1–2 days)
- Typer app, `init`, `doctor`, `status`
- Spec load/save + validation framework
- Runtime SQLite init with WAL

### M1 — Agent identity + onboarding (2–4 days)
- `agent join`, `agent list`, `agent heartbeat`
- JSON envelopes + schemas
- Progressive discovery “next actions”

### M2 — Tasks + dependencies (4–7 days)
- Task CRUD in spec
- DAG validation + `task graph`
- `task next` scheduling

### M3 — Leases / claiming (3–5 days)
- `claim/renew/release`
- expiry handling
- concurrency tests

### M4 — Messaging (3–5 days)
- `msg send/inbox/thread`
- cursors and pagination

### M5 — MCP server (optional, 5–10 days)
- `mcp serve`
- tools mirror CLI operations
- basic auth model (local only)

---

## Acceptance criteria (Definition of Done)

1. Running `lodestar agent join --json` in a repo initialized with `lodestar init` returns a stable `agent_id` and suggested next actions.
2. `lodestar task next --json` returns only tasks with satisfied dependencies.
3. `lodestar task claim T123` is atomic; two concurrent claim attempts result in only one success.
4. Leases expire without manual intervention and the task becomes claimable again.
5. `lodestar msg send` and `lodestar msg inbox` work reliably with cursor pagination.
6. All commands support `--json`, and schemas can be exported with `--schema`.

---

## Open questions (to resolve early)

- Task ID conventions: allow arbitrary strings vs enforced prefixes.
- Dependency satisfaction: require `verified` vs allow `done`.
- “Locks” enforcement: warn-only vs strict validation at `task done/verify`.
- Whether to ship MCP server in v1 or v1.1.

---

## Appendix: Example `spec.yaml`

```yaml
project:
  name: lodestar-demo
  default_branch: main

tasks:
  T001:
    id: T001
    title: Add CLI onboarding
    description: Implement agent join and next-actions envelope.
    acceptance_criteria:
      - lodestar agent join returns agent_id and next actions
      - --json output is stable and schema-exportable
    depends_on: []
    labels: [cli, onboarding]
    priority: 10
    status: ready

  T002:
    id: T002
    title: Implement lease-based task claims
    description: Add runtime leases table and atomic claim/renew/release commands.
    acceptance_criteria:
      - only one agent can claim at a time
      - claims expire after ttl
    depends_on: [T001]
    labels: [runtime, scheduling]
    priority: 20
    status: blocked
```
