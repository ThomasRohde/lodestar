# Reference

Technical reference documentation for Lodestar.

## Spec Schema

The `.lodestar/spec.yaml` file follows this schema:

```yaml
tasks:
  - id: string          # Unique task identifier
    title: string       # Short task title
    description: string # Detailed description
    status: string      # ready | done | verified
    priority: integer   # Lower = higher priority
    labels: [string]    # Categorization labels
    depends_on: [string] # Task IDs this depends on
```

## JSON Output Schema

All `--json` output follows this envelope:

```json
{
  "ok": true,
  "data": { },
  "next": [
    {"intent": "string", "cmd": "string"}
  ],
  "warnings": ["string"]
}
```

## Runtime Database

The `.lodestar/runtime.sqlite` database contains:

### agents

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Agent ID |
| name | TEXT | Agent name |
| created_at | TEXT | Registration time |
| last_heartbeat | TEXT | Last heartbeat time |

### leases

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Lease ID |
| task_id | TEXT | Claimed task |
| agent_id | TEXT | Claiming agent |
| created_at | TEXT | Claim time |
| expires_at | TEXT | Expiration time |

### messages

| Column | Type | Description |
|--------|------|-------------|
| id | TEXT | Message ID |
| thread_id | TEXT | Thread ID |
| from_agent | TEXT | Sender agent |
| to_agent | TEXT | Recipient (or "all") |
| body | TEXT | Message content |
| created_at | TEXT | Send time |

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODESTAR_LEASE_TTL` | `15m` | Default lease duration |
| `LODESTAR_NO_COLOR` | unset | Disable colored output |
