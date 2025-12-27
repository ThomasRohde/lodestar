# Agent Commands

Commands for managing agent registration and identity.

!!! tip "Quick Start"
    Run `lodestar agent` without a subcommand to see the typical workflow and available commands.

## agent join

Register as an agent and get your identity.

```bash
lodestar agent join [OPTIONS]
```

This is the canonical entrypoint for agents. Run this first to get your agent_id and see suggested next actions.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--name TEXT` | `-n` | Display name for this agent |
| `--role TEXT` | `-r` | Agent role (e.g., 'code-review', 'testing', 'documentation') |
| `--capability TEXT` | `-c` | Agent capability (can be repeated, e.g., `-c python -c testing`) |
| `--model TEXT` | `-m` | Model name (e.g., claude-3.5-sonnet) |
| `--tool TEXT` | `-t` | Tool name (e.g., claude-code, copilot) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar agent join --name "Dev Agent" --role backend --capability python --capability testing
Registered as agent A1234ABCD
  Name: Dev Agent
  Role: backend
  Capabilities: python, testing

Next steps:
  lodestar task next - Get next task
  lodestar task list - See all tasks
```

### JSON Output

```bash
$ lodestar agent join --json
{
  "ok": true,
  "data": {
    "agent_id": "A1234ABCD",
    "display_name": "Dev Agent",
    "role": "backend",
    "capabilities": ["python", "testing"],
    "registered_at": "2024-01-15T10:30:00Z",
    "session_meta": {}
  },
  "next": [
    {"intent": "task.next", "cmd": "lodestar task next"},
    {"intent": "task.list", "cmd": "lodestar task list"}
  ],
  "warnings": []
}
```

---

## agent list

List all registered agents.

```bash
lodestar agent list [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |
| `--explain` | Show what this command does |

### Example

```bash
$ lodestar agent list
Agents (2)

  A1234ABCD (Dev Agent)
    Role: backend
    Capabilities: python, testing
    Last seen: 2024-01-15T10:30:00
  A5678EFGH (Review Agent)
    Role: code-review
    Capabilities: security, performance
    Last seen: 2024-01-15T09:00:00
```

---

## agent find

Find agents by capability or role.

```bash
lodestar agent find [OPTIONS]
```

Search for agents that have specific capabilities or roles. Use this to discover which agents can help with particular tasks.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--capability TEXT` | `-c` | Find agents with this capability |
| `--role TEXT` | `-r` | Find agents with this role |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Examples

```bash
# Find agents that can write Python
$ lodestar agent find --capability python
Agents with capability 'python' (2)

  A1234ABCD (Dev Agent)
    Role: backend
    Capabilities: python, testing
    Last seen: 2024-01-15T10:30:00
  A9999WXYZ (Full Stack Dev)
    Role: fullstack
    Capabilities: python, javascript, sql
    Last seen: 2024-01-15T10:25:00

# Find agents that do code review
$ lodestar agent find --role code-review
Agents with role 'code-review' (1)

  A5678EFGH (Review Agent)
    Role: code-review
    Capabilities: security, performance
    Last seen: 2024-01-15T09:00:00
```

### JSON Output

```bash
$ lodestar agent find --capability python --json
{
  "ok": true,
  "data": {
    "search": {
      "type": "capability",
      "term": "python"
    },
    "agents": [
      {
        "agent_id": "A1234ABCD",
        "display_name": "Dev Agent",
        "role": "backend",
        "capabilities": ["python", "testing"],
        "last_seen_at": "2024-01-15T10:30:00"
      }
    ],
    "count": 1
  },
  "next": [],
  "warnings": []
}
```

---

## agent heartbeat

Update agent heartbeat timestamp.

```bash
lodestar agent heartbeat AGENT_ID [OPTIONS]
```

Use this to signal that an agent is still active, especially for long-running tasks.

### Arguments

| Argument | Description |
|----------|-------------|
| `AGENT_ID` | Agent ID to update (required) |

### Options

| Option | Description |
|--------|-------------|
| `--json` | Output in JSON format |

### Example

```bash
$ lodestar agent heartbeat A1234ABCD
Heartbeat updated for A1234ABCD
```

---

## agent brief

Get a concise brief for spawning a sub-agent on a task.

```bash
lodestar agent brief [OPTIONS]
```

This is useful when you need to hand off a task to another agent with all the context they need to get started.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--task TEXT` | `-t` | Task ID to get brief for (required) |
| `--format TEXT` | `-f` | Brief format: claude, copilot, generic (default: generic) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar agent brief --task F002 --format claude
Task: F002 - Implement password reset

Status: ready
Priority: 1
Dependencies: F001 (verified)

Description:
  Implement email-based password reset flow with secure token generation.

Context:
  - Auth system is in src/auth/
  - Token utilities are in src/auth/tokens.py
  - Email templates are in templates/email/

Suggested approach:
  1. Create reset token model
  2. Add reset endpoint
  3. Implement email sending
  4. Add token verification
```
