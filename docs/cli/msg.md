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

Read messages from your inbox with optional filtering.

```bash
lodestar msg inbox [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--agent TEXT` | `-a` | Your agent ID (required) |
| `--since TEXT` | `-s` | Filter messages created after this timestamp (ISO format) |
| `--until TEXT` | `-u` | Filter messages created before this timestamp (ISO format) |
| `--from TEXT` | `-f` | Filter by sender agent ID |
| `--limit INTEGER` | `-n` | Maximum messages to return (default: 50) |
| `--unread-only` | | Show only unread messages |
| `--show-read-status` | | Display read timestamps in output |
| `--mark-as-read` / `--no-mark-as-read` | | Mark messages as read when retrieving them (default: True) |
| `--count` | | Only return the count of messages, not the full list |
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

### Filtering

Filter by sender:

```bash
$ lodestar msg inbox --agent A1234ABCD --from A5678EFGH
```

Filter by date range:

```bash
$ lodestar msg inbox --agent A1234ABCD --since 2025-01-01T00:00:00 --until 2025-01-31T23:59:59
```

Show only unread messages:

```bash
$ lodestar msg inbox --agent A1234ABCD --unread-only
```

Show read status for messages:

```bash
$ lodestar msg inbox --agent A1234ABCD --show-read-status
```

Combine multiple filters:

```bash
$ lodestar msg inbox --agent A1234ABCD --from A5678EFGH --since 2025-01-15T10:00:00
```

### Read Status Tracking

By default, messages are marked as read when you retrieve them with `msg inbox`. This helps you track which messages you've already seen.

To prevent marking messages as read:

```bash
$ lodestar msg inbox --agent A1234ABCD --no-mark-as-read
```

To see only messages you haven't read yet:

```bash
$ lodestar msg inbox --agent A1234ABCD --unread-only
```

To display when each message was read:

```bash
$ lodestar msg inbox --agent A1234ABCD --show-read-status
```

---

## msg search

Search across all messages with filters.

```bash
lodestar msg search [OPTIONS]
```

Search through all messages in the system with keyword matching and filtering options. At least one filter must be provided.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--keyword TEXT` | `-k` | Search keyword to match in message text (case-insensitive) |
| `--from TEXT` | `-f` | Filter by sender agent ID |
| `--since TEXT` | `-s` | Filter messages created after this timestamp (ISO format) |
| `--until TEXT` | `-u` | Filter messages created before this timestamp (ISO format) |
| `--limit INTEGER` | `-n` | Maximum messages to return (default: 50) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Examples

Search for messages containing a keyword:

```bash
$ lodestar msg search --keyword 'bug'
Search Results (3 messages)

  2025-01-15T14:30:00
  From: A1234ABCD
  To: task:F002
  Found a bug in the authentication flow

  2025-01-15T10:15:00
  From: A5678EFGH
  To: task:F003
  This bug is now fixed
```

Search by sender:

```bash
$ lodestar msg search --from A1234ABCD
```

Search with date range:

```bash
$ lodestar msg search --keyword 'error' --since 2025-01-01T00:00:00 --until 2025-01-31T23:59:59
```

Combine multiple filters:

```bash
$ lodestar msg search --keyword 'bug' --from A1234ABCD --since 2025-01-15T00:00:00
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
