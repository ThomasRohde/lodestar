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
