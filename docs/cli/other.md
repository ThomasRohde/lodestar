# Other Commands

Repository management and utility commands.

## init

Initialize Lodestar in a repository.

```bash
lodestar init [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--force` | Overwrite existing configuration |

### Example

```bash
$ lodestar init
Initialized Lodestar in /path/to/repo

Created:
  .lodestar/spec.yaml    - Task definitions
  .lodestar/.gitignore   - Ignore runtime files
```

---

## status

Show repository status and next actions.

```bash
lodestar status [OPTIONS]
```

### Example

```bash
$ lodestar status
┌──────────────────────────────────────────────────────┐
│ lodestar                                             │
└────────────────────────── Branch: main ──────────────┘

Tasks
  Status    Count
  ready         5
  done          2
  verified     10

Runtime
  Agents registered: 2
  Active claims: 1

Next Actions
  lodestar task next - Get next claimable task
  lodestar task list - See all tasks
```

---

## doctor

Run health checks on the repository.

```bash
lodestar doctor [OPTIONS]
```

### Example

```bash
$ lodestar doctor
Health Check

  ✓ repository: Repository found
  ✓ spec.yaml: Valid spec with 15 tasks
  ✓ dependencies: No cycles or missing dependencies
  ✓ runtime.sqlite: Database is healthy
  ✓ .gitignore: Runtime files are gitignored

All checks passed!
```

---

## export snapshot

Export the full repository state.

```bash
lodestar export snapshot [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--output TEXT` | Output file path |
| `--format TEXT` | Format (json, yaml) |

### Example

```bash
$ lodestar export snapshot --format json
{
  "spec": {
    "tasks": [...]
  },
  "runtime": {
    "agents": [...],
    "leases": [...],
    "messages": [...]
  }
}
```
