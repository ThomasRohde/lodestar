# CLI Reference

Lodestar provides a comprehensive CLI for managing multi-agent coordination.

## Progressive Discovery

The CLI is self-documenting. Run any command group without a subcommand to see available workflows:

```bash
lodestar agent    # Shows agent registration workflow
lodestar task     # Shows task management workflow
lodestar msg      # Shows messaging workflow
```

Each command also supports `--help` for detailed usage and `--explain` for context about what it does.

## Global Flags

All commands support these flags:

| Flag | Description |
|------|-------------|
| `--json` | Output in JSON format (for programmatic use) |
| `--explain` | Show detailed explanation of what command does |
| `--help` | Show help message |

## Command Groups

### [Agent Commands](agent.md)

Manage agent registration and identity.

| Command | Description |
|---------|-------------|
| `agent join` | Register as an agent and get your identity |
| `agent list` | List all registered agents |
| `agent find` | Find agents by capability or role |
| `agent heartbeat` | Update agent heartbeat timestamp |
| `agent brief` | Get a concise brief for spawning a sub-agent |

### [Task Commands](task.md)

Create, claim, and complete tasks.

| Command | Description |
|---------|-------------|
| `task list` | List all tasks with optional filtering |
| `task show` | Show detailed information about a task |
| `task context` | Get PRD context for a task |
| `task create` | Create a new task |
| `task update` | Update an existing task's properties |
| `task next` | Get the next claimable task(s) |
| `task claim` | Claim a task with a lease |
| `task renew` | Renew your claim on a task |
| `task release` | Release your claim on a task |
| `task done` | Mark a task as done |
| `task verify` | Mark a task as verified |
| `task delete` | Soft-delete a task |
| `task graph` | Export the task dependency graph |

### [Message Commands](msg.md)

Inter-agent messaging.

| Command | Description |
|---------|-------------|
| `msg send` | Send a message to an agent or task thread |
| `msg inbox` | Read messages from your inbox |
| `msg wait` | Block until a new message arrives |
| `msg search` | Search messages with filters |
| `msg thread` | Read messages in a task thread |

### [Other Commands](other.md)

Repository management and utilities.

| Command | Description |
|---------|-------------|
| `init` | Initialize a new Lodestar repository |
| `status` | Show repository status and suggested next actions |
| `doctor` | Check repository health and diagnose issues |
| `export snapshot` | Export a complete snapshot of spec and runtime state |

## JSON Output

All commands support `--json` for programmatic access. Output follows this envelope:

```json
{
  "ok": true,
  "data": { },
  "next": [
    {"intent": "task.next", "cmd": "lodestar task next"}
  ],
  "warnings": []
}
```

| Field | Description |
|-------|-------------|
| `ok` | Whether the command succeeded |
| `data` | Command-specific output data |
| `next` | Suggested next actions with commands |
| `warnings` | Non-fatal issues or notices |

## Quick Reference

```bash
# Repository setup
lodestar init                       # Initialize repository
lodestar status                     # View status and next actions
lodestar doctor                     # Check health

# Agent registration
lodestar agent join                 # Register as agent
lodestar agent list                 # List all agents
lodestar agent find -c <capability> # Find agents by capability
lodestar agent brief -t <task>      # Get sub-agent brief

# Finding work
lodestar task list                  # List all tasks
lodestar task next                  # Find claimable tasks
lodestar task show <id>             # View task details
lodestar task context <id>          # Get PRD context for task

# Working on tasks
lodestar task claim <id> -a <agent> # Claim a task
lodestar task renew <id>            # Extend lease
lodestar task release <id>          # Release without completing

# Completing tasks
lodestar task done <id>             # Mark as done
lodestar task verify <id>           # Mark as verified
lodestar task delete <id>           # Soft-delete task

# Messaging
lodestar msg send -t <to> -f <from> -m "text"  # Send message
lodestar msg inbox -a <agent>                   # Check inbox
lodestar msg wait -a <agent>                    # Wait for new messages
lodestar msg search -k <keyword>                # Search messages
lodestar msg thread <task-id>                   # View task thread
```
