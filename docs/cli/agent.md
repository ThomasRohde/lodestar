# Agent Commands

Commands for managing agent registration and identity.

!!! tip "Quick Start"
    Run `lodestar agent` without a subcommand to see the typical workflow and available commands.

## Agent Availability Status

Agents are automatically assigned an availability status based on their last activity (heartbeat):

| Status | Color | Description |
|--------|-------|-------------|
| `active` | Green | Agent was active within the idle threshold (default: 15 minutes) |
| `idle` | Yellow | Agent has been inactive beyond the idle threshold but within the offline threshold |
| `offline` | Gray | Agent has been inactive beyond the offline threshold (default: 60 minutes) |

### Configuring Thresholds

You can customize the status thresholds via environment variables:

```bash
# Set idle threshold to 30 minutes (default: 15)
export LODESTAR_AGENT_IDLE_THRESHOLD_MINUTES=30

# Set offline threshold to 2 hours (default: 60)
export LODESTAR_AGENT_OFFLINE_THRESHOLD_MINUTES=120
```

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

  A1234ABCD (Dev Agent) active
    Role: backend
    Capabilities: python, testing
    Last seen: 2024-01-15T10:30:00
  A5678EFGH (Review Agent) offline
    Role: code-review
    Capabilities: security, performance
    Last seen: 2024-01-15T09:00:00
```

### JSON Output

```bash
$ lodestar agent list --json
{
  "ok": true,
  "data": {
    "agents": [
      {
        "agent_id": "A1234ABCD",
        "display_name": "Dev Agent",
        "role": "backend",
        "status": "active",
        "capabilities": ["python", "testing"],
        "last_seen_at": "2024-01-15T10:30:00",
        "session_meta": {}
      },
      {
        "agent_id": "A5678EFGH",
        "display_name": "Review Agent",
        "role": "code-review",
        "status": "offline",
        "capabilities": ["security", "performance"],
        "last_seen_at": "2024-01-15T09:00:00",
        "session_meta": {}
      }
    ],
    "count": 2
  },
  "next": [],
  "warnings": []
}
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

  A1234ABCD (Dev Agent) active
    Role: backend
    Capabilities: python, testing
    Last seen: 2024-01-15T10:30:00
  A9999WXYZ (Full Stack Dev) idle
    Role: fullstack
    Capabilities: python, javascript, sql
    Last seen: 2024-01-15T10:25:00

# Find agents that do code review
$ lodestar agent find --role code-review
Agents with role 'code-review' (1)

  A5678EFGH (Review Agent) offline
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
        "status": "active",
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

This is useful when you need to hand off a task to another agent with all the context they need to get started. The output format is optimized for different agent types.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--task TEXT` | `-t` | Task ID to get brief for (required) |
| `--format TEXT` | `-f` | Brief format: claude, copilot, generic (default: generic) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Format Options

The `--format` flag controls the output style:

| Format | Description | Best For |
|--------|-------------|----------|
| `generic` | Plain labeled sections (TASK, CONTEXT, COMMANDS) | General purpose, scripts |
| `claude` | XML-style tags optimized for Claude's structured prompts | Claude agents |
| `copilot` | GitHub-flavored markdown with headers and code fences | GitHub Copilot |

### Example: Generic Format (default)

```bash
$ lodestar agent brief --task F002 --format generic
TASK: F002 - Implement password reset

CONTEXT:
  Implement email-based password reset flow with secure token generation.
  Labels: feature, security

COMMANDS:
  Claim:    lodestar task claim F002 --agent YOUR_AGENT_ID
  Progress: lodestar msg send --task F002 --from YOUR_AGENT_ID --text 'Update'
  Done:     lodestar task done F002
```

### Example: Claude Format

```bash
$ lodestar agent brief --task F002 --format claude
<task>
  <id>F002</id>
  <title>Implement password reset</title>
</task>

<context>
  Implement email-based password reset flow with secure token generation.
  <labels>feature, security</labels>
</context>

<instructions>
  1. Claim task: lodestar task claim F002 --agent YOUR_AGENT_ID
  2. Report progress: lodestar msg send --task F002 --from YOUR_AGENT_ID --text 'Update'
  3. Mark complete: lodestar task done F002
</instructions>
```

### Example: Copilot Format

```bash
$ lodestar agent brief --task F002 --format copilot
## Task: F002

**Implement password reset**

### Goal

Implement email-based password reset flow with secure token generation.

**Labels:** feature, security

### Commands

\`\`\`bash
# Claim this task
lodestar task claim F002 --agent YOUR_AGENT_ID

# Report progress
lodestar msg send --task F002 --from YOUR_AGENT_ID --text 'Progress update'

# Mark complete
lodestar task done F002
\`\`\`
```

### JSON Output

```bash
$ lodestar agent brief --task F002 --json
{
  "ok": true,
  "data": {
    "task_id": "F002",
    "title": "Implement password reset",
    "description": "Implement email-based password reset flow...",
    "labels": ["feature", "security"],
    "depends_on": ["F001"],
    "priority": 1,
    "format": "generic",
    "brief": "TASK: F002 - Implement password reset\\n\\nCONTEXT:..."
  },
  "next": [],
  "warnings": []
}
```
