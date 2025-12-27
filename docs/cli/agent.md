# Agent Commands

Commands for managing agent registration and status.

## agent join

Register as a new agent.

```bash
lodestar agent join [OPTIONS]
```

### Options

| Option | Description |
|--------|-------------|
| `--name TEXT` | Agent name (default: auto-generated) |

### Example

```bash
$ lodestar agent join
Registered as agent A1234ABCD

Next steps:
  lodestar task next - Get next task
  lodestar task list - See all tasks
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
| `--active` | Show only agents with recent heartbeats |

### Example

```bash
$ lodestar agent list
Agents (2)
  A1234ABCD  online   Last seen: 2m ago
  A5678EFGH  offline  Last seen: 1h ago
```

---

## agent heartbeat

Update agent heartbeat to indicate liveness.

```bash
lodestar agent heartbeat AGENT_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `AGENT_ID` | Agent ID to update |

### Example

```bash
$ lodestar agent heartbeat A1234ABCD
Heartbeat updated for A1234ABCD
```

---

## agent brief

Get a brief status for an agent.

```bash
lodestar agent brief AGENT_ID [OPTIONS]
```

### Arguments

| Argument | Description |
|----------|-------------|
| `AGENT_ID` | Agent ID to query |

### Example

```bash
$ lodestar agent brief A1234ABCD
Agent A1234ABCD
  Status: online
  Active claims: 1
  Last heartbeat: 30s ago
```
