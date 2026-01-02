# Other Commands

Repository management and utility commands.

## init

Initialize a new Lodestar repository.

```bash
lodestar init [PATH] [OPTIONS]
```

Creates the `.lodestar` directory with spec.yaml and runtime database configuration.

### Arguments

| Argument | Description |
|----------|-------------|
| `PATH` | Path to initialize (default: current directory) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--name TEXT` | `-n` | Project name (default: directory name) |
| `--force` | `-f` | Overwrite existing .lodestar directory |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar init
Initialized Lodestar repository

Created:
  .lodestar/spec.yaml - Task definitions (commit this)
  .lodestar/.gitignore - Ignores runtime files
```

### Initialize with Custom Name

```bash
$ lodestar init --name "My Project"
Initialized Lodestar repository: My Project
```

### Initialize a Different Directory

```bash
$ lodestar init /path/to/project
```

---

## status

Show repository status and suggested next actions.

```bash
lodestar status [OPTIONS]
```

This is the progressive discovery entry point. Run with no args to see what to do next.

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar status
┌─────────────────────────────────────────────────────────────────────────────┐
│ lodestar                                                                    │
└─────────────────────────────── Branch: main ────────────────────────────────┘

Tasks
 Status    Count
 ready         5
 done          2
 verified     10

Runtime
  Agents registered: 2
  Active claims: 1

Next Actions
  lodestar task next - Get next claimable task (5 available)
  lodestar task list - See all tasks
```

### JSON Output

```bash
$ lodestar status --json
{
  "ok": true,
  "data": {
    "branch": "main",
    "tasks": {
      "ready": 5,
      "done": 2,
      "verified": 10
    },
    "runtime": {
      "agents_count": 2,
      "active_claims": 1
    }
  },
  "next": [
    {"intent": "task.next", "cmd": "lodestar task next"},
    {"intent": "task.list", "cmd": "lodestar task list"}
  ],
  "warnings": []
}
```

---

## reset

Reset .lodestar to clean state.

```bash
lodestar reset [OPTIONS]
```

Clears runtime data (agents, leases, messages) and optionally tasks to enable starting fresh. Only modifies files inside `.lodestar` directory—does not touch repository code or git history.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--force` | `-f` | Skip confirmation prompt (required for non-interactive use) |
| `--hard` | | Also delete all tasks from spec.yaml (keeps project metadata) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Reset Modes

#### Soft Reset (Default)

Deletes runtime data only. Tasks are preserved.

```bash
$ lodestar reset
⚠ Reset .lodestar to clean state

Reset type: SOFT

Will delete:
  • Runtime data: 2 agents, 1 leases, 5 messages
  • Tasks: None (spec.yaml preserved)

Continue? [y/N]: y

✓ Reset complete

Deleted:
  • Runtime data: 2 agents, 1 leases, 5 messages

Next steps:
  1. lodestar agent join - Register as agent
  3. lodestar status - See overview
```

**Use when:** You want to clear agents and leases but keep task definitions.

#### Hard Reset

Deletes runtime data AND all tasks from spec.yaml. Project metadata is preserved.

```bash
$ lodestar reset --hard --force
✓ Reset complete

Deleted:
  • Runtime data: 2 agents, 1 leases, 5 messages
  • Tasks: 15 tasks from spec.yaml

Next steps:
  1. lodestar agent join - Register as agent
  2. lodestar task create - Add tasks
  3. lodestar status - See overview
```

**Use when:** Starting completely fresh with no tasks.

### Non-Interactive Mode

Use `--force` to skip confirmation (required for automation/CI/agents):

```bash
$ lodestar reset --force
✓ Reset complete
```

In JSON mode, `--force` is always required:

```bash
$ lodestar reset --json
{
  "ok": false,
  "error": "Confirmation required. Use --force to proceed without prompt.",
  "data": {
    "reset_type": "soft",
    "tasks_to_delete": 0,
    "agents_to_clear": 2,
    "leases_to_clear": 1,
    "messages_to_clear": 5
  },
  "next": [],
  "warnings": []
}
```

### JSON Output

```bash
$ lodestar reset --force --json
{
  "ok": true,
  "data": {
    "reset_type": "soft",
    "runtime_deleted": true,
    "tasks_deleted": 0,
    "agents_cleared": 2,
    "leases_cleared": 1,
    "messages_cleared": 5
  },
  "next": [
    {"intent": "agent.join", "cmd": "lodestar agent join"},
    {"intent": "status", "cmd": "lodestar status"}
  ],
  "warnings": []
}
```

### Hard Reset JSON

```bash
$ lodestar reset --hard --force --json
{
  "ok": true,
  "data": {
    "reset_type": "hard",
    "runtime_deleted": true,
    "tasks_deleted": 15,
    "agents_cleared": 2,
    "leases_cleared": 1,
    "messages_cleared": 5
  },
  "next": [
    {"intent": "agent.join", "cmd": "lodestar agent join"},
    {"intent": "status", "cmd": "lodestar status"}
  ],
  "warnings": []
}
```

### Safety

- **Confirmation required:** Interactive prompt unless `--force` is used
- **Scope limited:** Only modifies `.lodestar/` directory
- **Git safe:** Does not affect repository code or git history
- **Project preserved:** Hard reset keeps project name and metadata

### Files Deleted

#### Soft Reset
- `runtime.sqlite` (agents, leases, messages)
- `runtime.sqlite-wal` (write-ahead log)
- `runtime.sqlite-shm` (shared memory)

#### Hard Reset
- All runtime files (above)
- Tasks cleared from `spec.yaml` (project metadata preserved)

---

## doctor

Check repository health and diagnose issues.

```bash
lodestar doctor [OPTIONS]
```

Validates spec.yaml, checks for dependency cycles, and verifies runtime database integrity.

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example: Healthy Repository

```bash
$ lodestar doctor
Health Check

  ✓ repository: Repository found at /path/to/project
  ✓ spec.yaml: Valid spec with 15 tasks
  ✓ dependencies: No cycles or missing dependencies
  ✓ runtime.sqlite: Database is healthy
  ✓ .gitignore: Runtime files are gitignored

All checks passed!
```

### Example: Issues Found

```bash
$ lodestar doctor
Health Check

  ✓ repository: Repository found at /path/to/project
  ✓ spec.yaml: Valid spec with 15 tasks
  ✗ dependencies: Cycle detected: F001 -> F002 -> F003 -> F001
  ! dependencies: Task F010 has no dependents and is not verified
  ✓ .gitignore: Runtime files are gitignored

Issues found. Run lodestar doctor --explain for details.
```

### Diagnostic Symbols

| Symbol | Meaning |
|--------|---------|
| ✓ | Check passed |
| ✗ | Error (must be fixed) |
| ! | Warning (review recommended) |
| i | Info |

---

## export snapshot

Export a complete snapshot of spec and runtime state.

```bash
lodestar export snapshot [OPTIONS]
```

Useful for CI validation, debugging, and auditing.

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--include-messages` | Include messages in the snapshot |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar export snapshot --json
{
  "ok": true,
  "data": {
    "spec": {
      "name": "my-project",
      "tasks": [
        {
          "id": "F001",
          "title": "Implement auth",
          "status": "verified",
          "priority": 1,
          "labels": ["feature"],
          "depends_on": []
        }
      ]
    },
    "runtime": {
      "agents": [
        {
          "id": "A1234ABCD",
          "name": "Dev Agent",
          "last_heartbeat": "2024-01-15T10:30:00Z"
        }
      ],
      "leases": [],
      "task_statuses": {
        "F001": "verified"
      }
    }
  },
  "next": [],
  "warnings": []
}
```

### Include Messages

```bash
$ lodestar export snapshot --json --include-messages
# Adds "messages" array to the runtime section
```

## Global Options

These options are available on all commands:

| Option | Short | Description |
|--------|-------|-------------|
| `--version` | `-v` | Show version and exit |
| `--json` | | Output in JSON format |
| `--help` | | Show help message |

### Version

```bash
$ lodestar --version
lodestar 0.1.0
```

### JSON Envelope

All `--json` output follows this structure:

```json
{
  "ok": true,
  "data": { },
  "next": [
    {"intent": "action.name", "cmd": "lodestar command"}
  ],
  "warnings": []
}
```

- `ok`: Whether the command succeeded
- `data`: Command-specific output
- `next`: Suggested next actions
- `warnings`: Non-fatal issues
