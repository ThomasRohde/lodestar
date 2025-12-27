# Message Commands

Commands for inter-agent messaging.

!!! tip "Quick Start"
    Run `lodestar msg` without a subcommand to see messaging examples and available commands.

## msg send

Send a message to an agent or task thread.

```bash
lodestar msg send [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--to TEXT` | `-t` | Recipient: 'agent:A123' or 'task:T001' (required) |
| `--text TEXT` | `-m` | Message text (required) |
| `--from TEXT` | `-f` | Your agent ID (required) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example: Message to an Agent

```bash
$ lodestar msg send \
    --to agent:A5678EFGH \
    --from A1234ABCD \
    --text "F002 is ready for review"
Sent message M1234567
```

### Example: Message to a Task Thread

```bash
$ lodestar msg send \
    --to task:F002 \
    --from A1234ABCD \
    --text "Started work on password reset flow"
Sent message M1234568
```

Task threads are useful for leaving context about your work for other agents who may pick up the task later.

---

## msg inbox

Read messages from your inbox.

```bash
lodestar msg inbox [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent TEXT` | `-a` | Your agent ID (required) |
| `--since TEXT` | `-s` | Cursor (ISO timestamp) to fetch messages after |
| `--limit INTEGER` | `-n` | Maximum messages to return (default: 50) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar msg inbox --agent A1234ABCD
Messages (2)

  From: A5678EFGH  2m ago
  Need help with F003 dependencies

  From: A9999WXYZ  1h ago
  F001 is now verified
```

### Pagination

Use `--since` to fetch messages after a certain point (useful for polling):

```bash
$ lodestar msg inbox --agent A1234ABCD --since 2024-01-15T10:00:00Z
```

---

## msg thread

Read messages in a task thread.

```bash
lodestar msg thread TASK_ID [OPTIONS]
```

View the conversation history for a specific task. Useful for understanding context and previous work.

### Arguments

| Argument | Description |
|----------|-------------|
| `TASK_ID` | Task ID to view thread for (required) |

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--since TEXT` | `-s` | Cursor (ISO timestamp) to fetch messages after |
| `--limit INTEGER` | `-n` | Maximum messages to return (default: 50) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar msg thread F002
Thread for F002 (3 messages)

  A1234ABCD  10m ago
  Starting work on password reset

  A5678EFGH  5m ago
  Auth tokens are in src/auth/tokens.py

  A1234ABCD  2m ago
  Thanks, found it. Implementation complete.
```

## Messaging Patterns

### Handoff Messages

When releasing a task, leave context for the next agent:

```bash
# Release the task
lodestar task release F002

# Leave context in the thread
lodestar msg send \
    --to task:F002 \
    --from A1234ABCD \
    --text "Blocked on API credentials. Need access to email service."
```

### Status Updates

Keep other agents informed of progress:

```bash
lodestar msg send \
    --to task:F002 \
    --from A1234ABCD \
    --text "50% complete. Token generation done, working on email templates."
```

### Direct Questions

Ask specific agents for help:

```bash
lodestar msg send \
    --to agent:A5678EFGH \
    --from A1234ABCD \
    --text "What email library should I use for F002?"
```
