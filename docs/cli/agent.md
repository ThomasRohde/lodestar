# Agent Commands

Commands for managing agent registration and identity.

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
| `--model TEXT` | `-m` | Model name (e.g., claude-3.5-sonnet) |
| `--tool TEXT` | `-t` | Tool name (e.g., claude-code, copilot) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar agent join --name "Dev Agent" --model claude-3.5-sonnet
Registered as agent A1234ABCD

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
    "name": "Dev Agent",
    "created_at": "2024-01-15T10:30:00Z"
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

  A1234ABCD  Dev Agent       claude-3.5-sonnet  Last seen: 2m ago
  A5678EFGH  Review Agent    gpt-4              Last seen: 1h ago
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
