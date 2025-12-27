# Task Commands

Commands for creating, claiming, and completing tasks.

## task list

List all tasks.

```bash
lodestar task list [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--status TEXT` | Filter by status (ready, done, verified) |
| `--label TEXT` | Filter by label |

### Example

```bash
$ lodestar task list
Tasks (15)
  F001 verified P1  Implement user authentication
  F002 ready    P1  Add password reset
  F003 done     P2  Update documentation
```

---

## task show

Show detailed task information.

```bash
lodestar task show TASK_ID [OPTIONS]
```

### Example

```bash
$ lodestar task show F002
F002 - Add password reset

Status: ready
Priority: 1
Labels: feature
Depends on: F001 (verified)

Description:
  Email-based password reset flow with secure token generation.
```

---

## task create

Create a new task.

```bash
lodestar task create [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--id TEXT` | Task ID (required) |
| `--title TEXT` | Task title (required) |
| `--description TEXT` | Task description |
| `--priority INT` | Priority (lower = higher priority) |
| `--label TEXT` | Labels (can be repeated) |
| `--depends-on TEXT` | Dependencies (can be repeated) |

### Example

```bash
$ lodestar task create \
    --id F010 \
    --title "Add email notifications" \
    --description "Send email on important events" \
    --priority 2 \
    --label feature \
    --depends-on F001
Created task F010
```

---

## task update

Update an existing task.

```bash
lodestar task update TASK_ID [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--title TEXT` | New title |
| `--description TEXT` | New description |
| `--priority INT` | New priority |

---

## task next

Find the next claimable tasks.

```bash
lodestar task next [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--limit INT` | Maximum tasks to show (default: 5) |

### Example

```bash
$ lodestar task next
Next Claimable Tasks (3 available)

  F002 P1  Add password reset
  F005 P2  Implement search

Run lodestar task claim F002 to claim
```

---

## task claim

Claim a task with a lease.

```bash
lodestar task claim TASK_ID [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--agent TEXT` | Agent ID (required) |
| `--ttl TEXT` | Lease duration (default: 15m) |

### Example

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
  Lease: L5678EFGH
  Expires in: 15m
```

---

## task renew

Renew an existing lease.

```bash
lodestar task renew TASK_ID [OPTIONS]
```

### Example

```bash
$ lodestar task renew F002
Renewed lease for F002
  Expires in: 15m
```

---

## task release

Release a lease without completing the task.

```bash
lodestar task release TASK_ID [OPTIONS]
```

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

### Example

```bash
$ lodestar task done F002
Marked F002 as done
```

---

## task verify

Mark a task as verified.

```bash
lodestar task verify TASK_ID [OPTIONS]
```

### Example

```bash
$ lodestar task verify F002
Marked F002 as verified
```

---

## task graph

Export the task dependency graph.

```bash
lodestar task graph [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--format TEXT` | Output format (dot, mermaid) |

### Example

```bash
$ lodestar task graph --format mermaid
graph TD
    F001 --> F002
    F001 --> F003
    F002 --> F004
```
