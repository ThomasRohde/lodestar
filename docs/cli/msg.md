# Message Commands

Commands for inter-agent messaging.

## msg send

Send a message to another agent or broadcast.

```bash
lodestar msg send TO [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `TO` | Recipient agent ID or "all" for broadcast |

### Options

| Option | Description |
|--------|-------------|
| `--from TEXT` | Sender agent ID (required) |
| `--body TEXT` | Message body (required) |
| `--thread TEXT` | Thread ID (for replies) |

### Example

```bash
$ lodestar msg send A5678EFGH \
    --from A1234ABCD \
    --body "F002 is ready for review"
Sent message M1234
```

---

## msg inbox

View messages for an agent.

```bash
lodestar msg inbox AGENT_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `AGENT_ID` | Agent ID to check inbox for |

### Options

| Option | Description |
|--------|-------------|
| `--unread` | Show only unread messages |

### Example

```bash
$ lodestar msg inbox A1234ABCD
Messages (2)

  From: A5678EFGH  2m ago
  Need help with F003 dependencies

  From: A9999WXYZ  1h ago
  F001 is now verified
```

---

## msg thread

View a message thread.

```bash
lodestar msg thread THREAD_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `THREAD_ID` | Thread ID to view |

### Example

```bash
$ lodestar msg thread T1234
Thread T1234 (3 messages)

  A1234ABCD  10m ago
  Starting work on F002

  A5678EFGH  5m ago
  Let me know if you need the auth context

  A1234ABCD  2m ago
  Thanks, got it working
```
