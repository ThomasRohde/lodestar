# Message Commands

Commands for task messaging. All messages are task-targeted - there is no agent-to-agent messaging.

!!! tip "Quick Start"
    Run `lodestar msg` without a subcommand to see messaging examples and available commands.

!!! info "Task-Only Messaging"
    Lodestar uses task threads for all communication. Messages are sent to tasks and visible to all agents working on that task. This encourages context sharing and prevents scattered conversations.

## msg send

Send a message to a task thread.

```bash
lodestar msg send [OPTIONS]
```

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--task TEXT` | `-t` | Task ID to send message to (required) |
| `--text TEXT` | `-m` | Message text (required) |
| `--from TEXT` | `-f` | Your agent ID (required) |
| `--subject TEXT` | `-s` | Optional message subject (stored in meta) |
| `--severity TEXT` | | Optional severity level (stored in meta): info, warning, handoff, blocker |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example: Message to a Task Thread

```bash
$ lodestar msg send \
    --task F002 \
    --from A1234ABCD \
    --text "Started work on password reset flow"
Message sent to task F002
  Message ID: M1234568
```

Task threads are useful for leaving context about your work for other agents who may pick up the task later.

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
| `--since TEXT` | `-s` | Filter messages created after this timestamp (ISO format) |
| `--limit INTEGER` | `-n` | Maximum messages to return (default: 50) |
| `--unread` | | Show only unread messages for --agent |
| `--agent TEXT` | `-a` | Agent ID for filtering unread messages |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Example

```bash
$ lodestar msg thread F002
Thread for F002

  2025-01-15T10:15:00
  A1234ABCD: Starting work on password reset

  2025-01-15T10:25:00
  A5678EFGH (read by 2): Auth tokens are in src/auth/tokens.py

  2025-01-15T10:30:00
  A1234ABCD: Thanks, found it. Implementation complete.
```

### Filtering Unread Messages

See only unread messages from your perspective:

```bash
$ lodestar msg thread F002 --unread --agent A1234ABCD
```

---

## msg mark-read

Mark task messages as read.

```bash
lodestar msg mark-read [OPTIONS]
```

Mark specific messages or all messages in a task as read by an agent. This updates the read_by array for the messages.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--task TEXT` | `-t` | Task ID whose messages to mark as read (required) |
| `--agent TEXT` | `-a` | Agent ID marking messages as read (required) |
| `--message-id TEXT` | `-m` | Specific message ID(s) to mark as read (can be used multiple times) |
| `--json` | | Output in JSON format |
| `--explain` | | Show what this command does |

### Examples

Mark all messages in a task as read:

```bash
$ lodestar msg mark-read --task F002 --agent A1234ABCD
Marked 3 message(s) as read in task F002
```

Mark specific messages as read:

```bash
$ lodestar msg mark-read --task F002 --agent A1234ABCD --message-id M001 --message-id M002
Marked 2 message(s) as read in task F002
```

---

## msg search

Search across all task messages with filters.

```bash
lodestar msg search [OPTIONS]
```

Search through all task messages in the system with keyword matching and filtering options. At least one filter must be provided.

### Options

| Option | Short | Description |
|--------|-------|-------------|
| `--keyword TEXT` | `-k` | Search keyword to match in message text (case-insensitive) |
| `--task TEXT` | `-t` | Filter by task ID |
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
  Task: F002
  Found a bug in the authentication flow

  2025-01-15T10:15:00
  From: A5678EFGH
  Task: F003
  This bug is now fixed
```

Search by task:

```bash
$ lodestar msg search --task F002
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
$ lodestar msg search --keyword 'bug' --task F002 --since 2025-01-15T00:00:00
```

---

## Messaging Patterns



### Handoff Messages

When releasing a task, leave context for the next agent:

```bash
# Release the task
lodestar task release F002

# Leave context in the thread
lodestar msg send \
    --task F002 \
    --from A1234ABCD \
    --text "Blocked on API credentials. Need access to email service."
```

### Status Updates

Keep other agents informed of progress:

```bash
lodestar msg send \
    --task F002 \
    --from A1234ABCD \
    --text "50% complete. Token generation done, working on email templates."
```

### Questions and Discussion

Use task threads for questions related to the task:

```bash
lodestar msg send \
    --task F002 \
    --from A1234ABCD \
    --text "What email library should I use? Need to send password reset emails."
```
