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
| `--status TEXT` | `-s` | Filter by status (todo, ready, blocked, done, verified) |
| `--label TEXT` | `-l` | Filter by label |
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

## task create

Create a new task.

```bash
lodestar task create [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--title TEXT` | `-t` | Task title (required) |
| `--id TEXT` | | Task ID (auto-generated if not provided) |
| `--description TEXT` | `-d` | Task description |
| `--priority INTEGER` | `-p` | Priority, lower = higher (default: 100) |
| `--status TEXT` | `-s` | Initial status (default: ready) |
| `--depends-on TEXT` | | Task IDs this depends on (repeatable) |
| `--label TEXT` | `-l` | Labels for the task (repeatable) |
| `--json` | | Output in JSON format |

### Example

```bash
$ lodestar task create \
    --id F010 \
    --title "Add email notifications" \
    --description "Send email on important events" \
    --priority 2 \
    --label feature \
    --label notifications \
    --depends-on F001
Created task F010
```

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
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
  Lease: L5678EFGH
  Expires in: 15m

Remember to:
  - Renew with lodestar task renew F002 before expiry
  - Mark done with lodestar task done F002 when complete
```

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

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to release (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

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
