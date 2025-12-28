# Task Commands

Commands for creating, claiming, and completing tasks.

!!! tip "Quick Start"
    Run `lodestar task` without a subcommand to see the typical workflow and available commands.

## task list

List all tasks with optional filtering.

```bash
lodestar task list [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--status TEXT` | `-s` | Filter by status (todo, ready, blocked, done, verified, deleted) |
| `--label TEXT` | `-l` | Filter by label |
| `--include-deleted` | | Include deleted tasks in the list |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar task list
Tasks (15)

  F001 verified P1  Implement user authentication
  F002 ready    P1  Add password reset
  F003 done     P2  Update documentation
```

### Filtering

```bash
# Show only ready tasks
$ lodestar task list --status ready

# Show tasks with a specific label
$ lodestar task list --label feature
```

---

## task show

Show detailed information about a task.

```bash
lodestar task show TASK_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to show (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar task show F002
F002 - Add password reset

Status: ready
Priority: 1
Labels: feature, security
Depends on: F001 (verified)

Description:
  Email-based password reset flow with secure token generation.

Claimable - run lodestar task claim F002 to claim
```

---

## task context

Get PRD context for a task.

```bash
lodestar task context TASK_ID [OPTIONS]
```

Returns the task's PRD references, frozen excerpt, and live PRD sections. Respects a character budget for context window management.

!!! tip "PRD Context Feature"
    This command surfaces intent from the PRD without requiring agents to re-read
    the entire document. It's the "just enough context" delivery mechanism.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to get context for (required) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--max-chars INTEGER` | `-m` | Maximum characters for context output (default: 1000) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### What It Returns

- **Task description** from the spec
- **PRD source** file path (if linked)
- **PRD references** (section anchors)
- **Frozen excerpt** (snapshot from task creation)
- **Live PRD sections** (extracted from current PRD)
- **Drift warnings** if the PRD has changed since task creation

### Example

```bash
$ lodestar task context F002
Context for F002

PRD Source: PRD.md
References: #password-reset, #security-requirements

Content:
  Implement email-based password reset with secure token generation.
  Tokens must expire after 15 minutes and be single-use.
  ...
```

### JSON Output

```bash
$ lodestar task context F002 --json
{
  "ok": true,
  "data": {
    "task_id": "F002",
    "title": "Add password reset",
    "description": "Email-based password reset flow...",
    "prd_source": "PRD.md",
    "prd_refs": [
      {"anchor": "#password-reset", "lines": null}
    ],
    "prd_excerpt": "Tokens must expire after 15 minutes...",
    "prd_sections": [
      {"anchor": "#password-reset", "content": "..."}
    ],
    "content": "...",
    "truncated": false
  },
  "warnings": []
}
```

### Drift Detection

If the PRD file has changed since the task was created (based on stored hash), you'll see a warning:

```bash
$ lodestar task context F002
Context for F002

⚠ PRD has changed since task creation. Review PRD.md for updates.

...
```

This helps agents know when task context may be stale.

---

## task create

Create a new task.

```bash
lodestar task create [OPTIONS]
```

!!! important "Write Detailed Descriptions"
    For the planning→executing agent workflow (e.g., Opus creates, Sonnet executes),
    include enough context for executing agents to work independently.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--title TEXT` | `-t` | Task title (required) |
| `--id TEXT` | | Task ID (auto-generated if not provided) |
| `--description TEXT` | `-d` | Detailed description (see below) |
| `--priority INTEGER` | `-p` | Priority, lower = higher (default: 100) |
| `--status TEXT` | `-s` | Initial status (default: ready) |
| `--depends-on TEXT` | | Task IDs this depends on (repeatable) |
| `--label TEXT` | `-l` | Labels for the task (repeatable) |
| `--prd-source TEXT` | | Path to PRD file (e.g., PRD.md) |
| `--prd-ref TEXT` | | PRD section anchors (e.g., #task-claiming). Repeatable |
| `--prd-excerpt TEXT` | | Frozen PRD excerpt to attach to task |
| `--json` | | Output in JSON format |

### Writing Good Descriptions

Include these elements so executing agents have full context:

- **WHAT**: Clear goal and scope
- **WHERE**: Relevant files and directories
- **WHY**: Business context or motivation
- **ACCEPT**: Measurable acceptance criteria
- **CONTEXT**: Pointers to related code, patterns to follow

### Example

```bash
$ lodestar task create \
    --id F010 \
    --title "Add email notifications" \
    --description "WHAT: Send email when tasks complete.
WHERE: src/notifications/, templates/email/
WHY: Users requested completion alerts.
ACCEPT: 1) Email on task.done 2) Configurable template 3) Tests pass
CONTEXT: See notify() in src/alerts.py for pattern" \
    --priority 2 \
    --label feature \
    --depends-on F001
Created task F010
```

### Creating Tasks with PRD Context

Link tasks to PRD sections so executing agents receive context automatically:

```bash
$ lodestar task create \
    --id F011 \
    --title "Implement lease expiry" \
    --description "Add automatic lease expiration handling." \
    --prd-source PRD.md \
    --prd-ref "#lease-semantics" \
    --prd-ref "#task-claiming" \
    --prd-excerpt "Leases auto-expire without manual intervention. Commands that read active claims filter out expired leases automatically." \
    --label feature
Created task F011
```

The PRD hash is automatically computed and stored for drift detection.

When other agents claim this task, they receive:

- The frozen excerpt (stable context even if PRD changes)
- Links to live PRD sections (can be re-extracted)
- Warnings if the PRD has drifted since task creation

---

## task update

Update an existing task's properties.

```bash
lodestar task update TASK_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to update (required) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--title TEXT` | `-t` | New task title |
| `--description TEXT` | `-d` | New description |
| `--priority INTEGER` | `-p` | New priority |
| `--status TEXT` | `-s` | New status |
| `--add-label TEXT` | | Add a label |
| `--remove-label TEXT` | | Remove a label |
| `--json` | | Output in JSON format |

### Example

```bash
$ lodestar task update F010 --priority 1 --add-label urgent
Updated task F010
```

---

## task next

Get the next claimable task(s).

```bash
lodestar task next [OPTIONS]
```

Returns tasks that are ready and have all dependencies satisfied. Tasks are sorted by priority (lower = higher priority).

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--count INTEGER` | `-n` | Number of tasks to return (default: 1) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar task next
Next Claimable Tasks (3 available)

  F002 P1  Add password reset
  F005 P2  Implement search

Run lodestar task claim F002 to claim
```

```bash
$ lodestar task next --count 5
# Shows up to 5 claimable tasks
```

---

## task claim

Claim a task with a lease.

```bash
lodestar task claim TASK_ID [OPTIONS]
```

Claims are time-limited and auto-expire. Renew with `task renew` if you need more time.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to claim (required) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent TEXT` | `-a` | Your agent ID (required) |
| `--ttl TEXT` | `-t` | Lease duration, e.g., 15m, 1h (default: 15m) |
| `--no-context` | | Don't include PRD context in output |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
  Lease: L5678EFGH
  Expires in: 15m

Task Context:
  Add password reset
  Email-based password reset flow with secure token generation...
  PRD: PRD.md

Remember to:
  - Renew with lodestar task renew F002 before expiry
  - Mark done with lodestar task done F002 when complete
```

### Context Bundle

By default, `task claim` includes a context bundle with the task description and PRD context. This ensures agents receive "just enough" product intent without needing to read the full PRD.

The context bundle includes:

- Task title and description
- PRD source file path
- Frozen PRD excerpt (if attached to task)
- Drift warnings if the PRD has changed since task creation

Use `--no-context` to skip the context bundle (useful for scripts).

### JSON Output with Context

```bash
$ lodestar task claim F002 --agent A1234ABCD --json
{
  "ok": true,
  "data": {
    "lease_id": "L5678EFGH",
    "task_id": "F002",
    "agent_id": "A1234ABCD",
    "expires_at": "2025-01-15T10:30:00Z",
    "ttl_seconds": 900,
    "context": {
      "title": "Add password reset",
      "description": "Email-based password reset flow...",
      "prd_source": "PRD.md",
      "prd_excerpt": "Tokens must expire after 15 minutes..."
    }
  },
  "warnings": ["PRD has changed since task creation. Review PRD.md for updates."],
  "next": [...]
}
```

### Drift Detection Warnings

If the PRD file has changed since the task was created, `task claim` will emit a warning:

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
  ...

⚠ PRD has changed since task creation. Review PRD.md for updates.
```

This helps agents notice when the original intent may have evolved. Use `lodestar task context F002` for the full context with live PRD sections.

### Custom TTL

```bash
$ lodestar task claim F002 --agent A1234ABCD --ttl 1h
Claimed task F002
  Lease: L5678EFGH
  Expires in: 1h
```

---

## task renew

Renew your claim on a task.

```bash
lodestar task renew TASK_ID [OPTIONS]
```

Extends the lease expiration time. Only the agent holding the lease can renew it.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to renew (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar task renew F002
Renewed lease for F002
  Expires in: 15m
```

---

## task release

Release your claim on a task.

```bash
lodestar task release TASK_ID [OPTIONS]
```

Frees the task so other agents can claim it. Use this when you're blocked or can't complete the task.

!!! note "Auto-release on completion"
    You don't need to manually release after `task done` or `task verify` - those commands auto-release the lease.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to release (required) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent TEXT` | `-a` | Your agent ID (optional, infers from active lease) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar task release F002
Released task F002
```

---

## task done

Mark a task as done.

```bash
lodestar task done TASK_ID [OPTIONS]
```

Changes the task status to `done`. The task should then be verified by the same or a different agent.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to mark done (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar task done F002
Marked F002 as done
Run lodestar task verify F002 after review
```

---

## task verify

Mark a task as verified (unblocks dependents).

```bash
lodestar task verify TASK_ID [OPTIONS]
```

Changes the task status to `verified`. Any tasks that depend on this task will become claimable.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to verify (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar task verify F002
Verified F002
Unblocked tasks: F005, F006
```

---

## task delete

Soft-delete a task.

```bash
lodestar task delete TASK_ID [OPTIONS]
```

Tasks are soft-deleted (status set to `deleted`), not physically removed from the spec. Deleted tasks are hidden from `task list` by default.

!!! warning "Dependency Protection"
    If a task has dependents (other tasks depend on it), you must use `--cascade` to delete it along with all its dependents.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to delete (required) |

### Options

| Option | Description |
|--------|-------------|
| `--cascade` | Delete this task and all tasks that depend on it |
| `--json` | Output in JSON format |

### Soft-Delete Semantics

- Deleted tasks have `status = deleted` in spec.yaml
- `task list` hides deleted tasks by default
- Use `task list --include-deleted` to see deleted tasks
- Use `task list --status deleted` to see only deleted tasks
- `task show` indicates if a task is deleted
- Deleted tasks don't appear in `task next` (not claimable)

### Example (Simple Delete)

```bash
$ lodestar task delete F010
Deleted 1 task(s)
  - F010: Add email notifications
```

### Example (Delete with Dependents - Error)

```bash
$ lodestar task delete F001
Cannot delete F001
  2 task(s) depend on this task:
    - F002: Add password reset
    - F003: Update documentation

  Use --cascade to delete this task and all dependents
```

### Example (Cascade Delete)

```bash
$ lodestar task delete F001 --cascade
Deleted 3 task(s)
  - F001: User authentication
  - F002: Add password reset
  - F003: Update documentation

Tip: Use 'lodestar task list --include-deleted' to see deleted tasks
```

### Viewing Deleted Tasks

```bash
# Show all tasks including deleted
$ lodestar task list --include-deleted

# Show only deleted tasks
$ lodestar task list --status deleted

# View details of a deleted task
$ lodestar task show F010
F010 - Add email notifications

Status: deleted (soft-deleted)
Priority: 2
...
```

### Common Use Cases

**Removing obsolete tasks:**
```bash
lodestar task delete F099  # No dependents
```

**Removing a feature branch:**
```bash
# Delete root task and entire feature tree
lodestar task delete AUTH-001 --cascade
```

**Cleaning up mistakes:**
```bash
# Delete accidentally created task
lodestar task delete T042
```

---

## task graph

Export the task dependency graph.

```bash
lodestar task graph [OPTIONS]
```

Exports the task DAG in various formats for visualization or analysis.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--format TEXT` | `-f` | Output format: json, dot (default: json) |
| `--json` | | Output in JSON format |

### Example (DOT format)

```bash
$ lodestar task graph --format dot
digraph tasks {
    "F001" -> "F002"
    "F001" -> "F003"
    "F002" -> "F004"
}
```

### Example (JSON format)

```bash
$ lodestar task graph --format json
{
  "nodes": ["F001", "F002", "F003", "F004"],
  "edges": [
    {"from": "F001", "to": "F002"},
    {"from": "F001", "to": "F003"},
    {"from": "F002", "to": "F004"}
  ]
}
```

You can visualize DOT output with tools like Graphviz:

```bash
lodestar task graph --format dot | dot -Tpng -o tasks.png
```
