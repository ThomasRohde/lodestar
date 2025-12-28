# Reference

Technical reference documentation for Lodestar.

## Spec Schema

The `.lodestar/spec.yaml` file follows this schema:

```yaml
tasks:
  - id: string          # Unique task identifier
    title: string       # Short task title
    description: string # Detailed description
    status: string      # ready | done | verified | deleted
    priority: integer   # Lower = higher priority
    labels: [string]    # Categorization labels
    depends_on: [string] # Task IDs this depends on
    prd:                # Optional PRD context (see below)
      source: string
      refs: [PrdRef]
      excerpt: string
      prd_hash: string
```

## PRD Context Schema

Tasks can include PRD context for delivering product intent:

### PrdContext

| Field | Type | Description |
|-------|------|-------------|
| `source` | string | Path to PRD file (e.g., `PRD.md`) |
| `refs` | list[PrdRef] | Section references with anchors |
| `excerpt` | string | Frozen snapshot from task creation |
| `prd_hash` | string | SHA256 hash for drift detection |

### PrdRef

| Field | Type | Description |
|-------|------|-------------|
| `anchor` | string | Section anchor (e.g., `#task-claiming`) |
| `lines` | list[int] | Optional `[start, end]` line range |

### Example

```yaml
tasks:
  TASK-042:
    id: TASK-042
    title: "Implement lease expiry"
    description: "Add automatic lease expiration handling."
    status: ready
    priority: 1
    prd:
      source: PRD.md
      refs:
        - anchor: "#lease-semantics"
          lines: [280, 335]
        - anchor: "#task-claiming"
      excerpt: |
        Leases auto-expire without manual intervention. Commands that
        read active claims filter out expired leases automatically.
      prd_hash: "sha256:abc123..."
```

### task context JSON Output

```bash
$ lodestar task context TASK-042 --json
```

```json
{
  "ok": true,
  "data": {
    "task_id": "TASK-042",
    "title": "Implement lease expiry",
    "description": "Add automatic lease expiration handling.",
    "prd_source": "PRD.md",
    "prd_refs": [
      {"anchor": "#lease-semantics", "lines": [280, 335]},
      {"anchor": "#task-claiming", "lines": null}
    ],
    "prd_excerpt": "Leases auto-expire without manual intervention...",
    "prd_sections": [
      {"anchor": "#lease-semantics", "content": "...extracted text..."}
    ],
    "content": "...combined context output...",
    "truncated": false,
    "drift_detected": false
  },
  "warnings": [],
  "next": []
}
```

### Schema Export

Export JSON Schema for any command output:

```bash
$ lodestar task context --schema
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
