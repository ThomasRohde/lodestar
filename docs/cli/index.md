# CLI Reference

Lodestar provides a comprehensive CLI for managing multi-agent coordination.

## Global Flags

All commands support these flags:

| Flag | Description |
|------|-------------|
| `--json` | Output in JSON format (for programmatic use) |
| `--schema` | Show JSON schema for command output |
| `--explain` | Show detailed explanation of what command does |
| `--help` | Show help message |

## Command Groups

### [Agent Commands](agent.md)

Manage agent registration and status.

```bash
lodestar agent join       # Register as an agent
lodestar agent list       # List all agents
lodestar agent heartbeat  # Update agent heartbeat
lodestar agent brief      # Get agent status brief
```

### [Task Commands](task.md)

Create, claim, and complete tasks.

```bash
lodestar task list        # List all tasks
lodestar task show        # Show task details
lodestar task create      # Create a new task
lodestar task update      # Update a task
lodestar task next        # Find claimable tasks
lodestar task claim       # Claim a task
lodestar task renew       # Renew a lease
lodestar task release     # Release a lease
lodestar task done        # Mark task done
lodestar task verify      # Mark task verified
lodestar task graph       # Export dependency graph
```

### [Message Commands](msg.md)

Inter-agent messaging.

```bash
lodestar msg send         # Send a message
lodestar msg inbox        # View inbox
lodestar msg thread       # View message thread
```

### [Other Commands](other.md)

Repository management and utilities.

```bash
lodestar init             # Initialize repository
lodestar status           # Show repository status
lodestar doctor           # Run health checks
lodestar export snapshot  # Export full state
```

## JSON Output

All commands support `--json` for programmatic access:

```bash
$ lodestar status --json
{
  "ok": true,
  "data": {
    "branch": "main",
    "tasks": {"ready": 5, "done": 2, "verified": 10},
    "agents": {"count": 2, "active_claims": 1}
  },
  "next": [
    {"intent": "task.next", "cmd": "lodestar task next"}
  ],
  "warnings": []
}
```
