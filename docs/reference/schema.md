# Schema Reference

This document provides complete schema definitions for developers building tools on top of Lodestar. Lodestar uses a two-plane architecture:

- **Spec plane** (`.lodestar/spec.yaml`) — Version-controlled task definitions
- **Runtime plane** (`.lodestar/runtime.sqlite`) — Ephemeral agent state (gitignored)

---

## Spec Plane: spec.yaml

The spec file is a YAML document containing project configuration and task definitions. It's designed to be committed to version control.

### File Location

```
<repo-root>/.lodestar/spec.yaml
```

### Top-Level Structure

```yaml
project:
  name: string                    # Required: Project name
  default_branch: string          # Default: "main"
  conventions: object             # Optional: Project-specific conventions

tasks:
  <task_id>:                      # Task ID is the key (e.g., "F001", "AUTH-001")
    title: string
    description: string
    # ... task fields
    
features:                         # Optional: Feature groupings
  <feature_id>: [task_id, ...]
```

### Project Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `name` | string | Yes | - | Project name |
| `default_branch` | string | No | `"main"` | Default git branch |
| `conventions` | object | No | `{}` | Project-specific conventions (freeform) |

### Task Schema

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `id` | string | Yes | - | Unique task identifier (matches the key) |
| `title` | string | Yes | - | Short task title |
| `description` | string | No | `""` | Detailed task description |
| `acceptance_criteria` | list[string] | No | `[]` | List of acceptance criteria |
| `depends_on` | list[string] | No | `[]` | Task IDs this task depends on |
| `labels` | list[string] | No | `[]` | Tags/labels for categorization |
| `locks` | list[string] | No | `[]` | Glob patterns of files/dirs owned by this task |
| `priority` | integer | No | `100` | Priority (lower = higher priority) |
| `status` | string | No | `"todo"` | Current status (see TaskStatus enum) |
| `created_at` | datetime | Auto | Now | When the task was created (ISO 8601) |
| `updated_at` | datetime | Auto | Now | When the task was last updated (ISO 8601) |
| `completed_by` | string | No | `null` | Agent ID who marked the task as done |
| `completed_at` | datetime | No | `null` | When the task was marked as done |
| `verified_by` | string | No | `null` | Agent ID who verified the task |
| `verified_at` | datetime | No | `null` | When the task was verified |
| `prd` | PrdContext | No | `null` | Optional PRD context (see below) |

### TaskStatus Enum

| Value | Description |
|-------|-------------|
| `todo` | Task not yet ready (may have unmet dependencies) |
| `ready` | Task is ready to be claimed |
| `blocked` | Task is explicitly blocked |
| `done` | Task marked complete, pending verification |
| `verified` | Task verified and complete |
| `deleted` | Task soft-deleted |

!!! note "Claimability"
    A task is **claimable** when `status == "ready"` AND all tasks in `depends_on` have `status == "verified"`.

### PRD Context Schema

Tasks can include PRD context for delivering product requirements to agents:

#### PrdContext

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `source` | string | Yes | Path to PRD file (e.g., `PRD.md`) |
| `refs` | list[PrdRef] | No | Section references with anchors |
| `excerpt` | string | No | Frozen snapshot from task creation |
| `prd_hash` | string | No | SHA256 hash for drift detection |

#### PrdRef

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `anchor` | string | Yes | Section anchor (e.g., `#task-claiming`) |
| `lines` | list[int] | No | Optional `[start, end]` line range |

### Complete Example

```yaml
project:
  name: my-project
  default_branch: main
  conventions:
    commit_style: conventional
    test_framework: pytest

tasks:
  AUTH-001:
    title: Implement user authentication
    description: |
      Add OAuth2 authentication flow with support for
      GitHub and Google providers.
    acceptance_criteria:
      - OAuth2 flow completes successfully
      - Tokens stored securely
      - Session management works
    depends_on: []
    labels:
      - auth
      - security
    locks:
      - src/auth/**
      - tests/test_auth.py
    priority: 1
    status: ready
    created_at: '2025-01-15T10:00:00+00:00'
    updated_at: '2025-01-15T10:00:00+00:00'
    prd:
      source: PRD.md
      refs:
        - anchor: "#authentication"
          lines: [50, 100]
      excerpt: |
        Users must authenticate via OAuth2 before accessing
        protected resources...
      prd_hash: "sha256:abc123..."

  AUTH-002:
    title: Add role-based access control
    description: Implement RBAC on top of authentication.
    depends_on:
      - AUTH-001
    labels:
      - auth
      - security
    priority: 2
    status: todo
    created_at: '2025-01-15T10:00:00+00:00'
    updated_at: '2025-01-15T10:00:00+00:00'

features:
  authentication:
    - AUTH-001
    - AUTH-002
```

---

## Runtime Plane: runtime.sqlite

The runtime database is an SQLite database using WAL (Write-Ahead Logging) mode for concurrent access. It stores ephemeral state that should not be version controlled.

### File Location

```
<repo-root>/.lodestar/runtime.sqlite
<repo-root>/.lodestar/runtime.sqlite-wal   # WAL file
<repo-root>/.lodestar/runtime.sqlite-shm   # Shared memory file
```

### Database Configuration

- **SQLite version**: 3.x (standard library)
- **Journal mode**: WAL (Write-Ahead Logging)
- **Encoding**: UTF-8
- **Datetime format**: ISO 8601 strings

---

### Table: `schema_version`

Tracks database schema version for migrations.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `version` | INTEGER | PRIMARY KEY | Schema version number |

---

### Table: `agents`

Registered agents with their metadata and capabilities.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `agent_id` | TEXT | PRIMARY KEY | Unique agent ID (format: `A` + 8 hex chars) |
| `display_name` | TEXT | DEFAULT `""` | Human-readable name |
| `role` | TEXT | DEFAULT `""` | Agent role (e.g., "code-review") |
| `created_at` | TEXT | NOT NULL | Registration time (ISO 8601) |
| `last_seen_at` | TEXT | NOT NULL | Last heartbeat time (ISO 8601) |
| `capabilities` | TEXT | DEFAULT `[]` | JSON array of capability strings |
| `session_meta` | TEXT | DEFAULT `{}` | JSON object with session metadata |

#### Agent ID Format

Agent IDs follow the pattern `A{8-hex-chars}`, e.g., `A1B2C3D4E`.

#### Agent Status Calculation

Agent status is derived from `last_seen_at`:

| Status | Condition |
|--------|-----------|
| `active` | `last_seen_at` within 15 minutes |
| `idle` | `last_seen_at` between 15-60 minutes ago |
| `offline` | `last_seen_at` more than 60 minutes ago |

Thresholds are configurable via environment variables:

- `LODESTAR_AGENT_IDLE_THRESHOLD_MINUTES` (default: 15)
- `LODESTAR_AGENT_OFFLINE_THRESHOLD_MINUTES` (default: 60)

#### Example Row

```sql
INSERT INTO agents VALUES (
  'A1B2C3D4E',
  'Claude Agent',
  'code-review',
  '2025-01-15T10:00:00+00:00',
  '2025-01-15T10:30:00+00:00',
  '["python", "testing"]',
  '{"client": "vscode", "model": "claude-sonnet"}'
);
```

---

### Table: `leases`

Active task claims with time-based expiration.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `lease_id` | TEXT | PRIMARY KEY | Unique lease ID (format: `L` + 8 hex chars) |
| `task_id` | TEXT | NOT NULL, INDEX | Task being claimed |
| `agent_id` | TEXT | NOT NULL, FK → agents.agent_id | Claiming agent |
| `created_at` | TEXT | NOT NULL | When lease was created (ISO 8601) |
| `expires_at` | TEXT | NOT NULL, INDEX | When lease expires (ISO 8601) |

#### Indexes

- `idx_leases_agent_id` on `agent_id`
- Index on `task_id`
- Index on `expires_at`

#### Lease Semantics

- A lease is **active** if `expires_at > current_time`
- Only one active lease per task is allowed
- Leases auto-expire; no background cleanup needed
- Default TTL: 15 minutes (configurable via `LODESTAR_LEASE_TTL`)

#### Lease ID Format

Lease IDs follow the pattern `L{8-hex-chars}`, e.g., `L9F8E7D6C`.

#### Example Row

```sql
INSERT INTO leases VALUES (
  'L9F8E7D6C',
  'AUTH-001',
  'A1B2C3D4E',
  '2025-01-15T10:00:00+00:00',
  '2025-01-15T10:15:00+00:00'
);
```

---

### Table: `messages`

Agent-to-agent and task-thread messaging.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `message_id` | TEXT | PRIMARY KEY | Unique message ID (format: `M` + 12 hex chars) |
| `created_at` | TEXT | NOT NULL, INDEX | When message was sent (ISO 8601) |
| `from_agent_id` | TEXT | NOT NULL, FK → agents.agent_id | Sender agent ID |
| `to_type` | TEXT | NOT NULL | Recipient type: `"agent"` or `"task"` |
| `to_id` | TEXT | NOT NULL | Recipient ID (agent_id or task_id) |
| `text` | TEXT | NOT NULL | Message content |
| `meta` | TEXT | DEFAULT `{}` | JSON object with additional metadata |
| `read_at` | TEXT | NULL | When message was read (ISO 8601, NULL if unread) |

#### Indexes

- `idx_messages_to` on `(to_type, to_id)`
- `idx_messages_from` on `from_agent_id`
- `idx_messages_created` on `created_at`

#### Message Types

| `to_type` | Description |
|-----------|-------------|
| `agent` | Direct message to a specific agent |
| `task` | Message in a task thread (visible to all) |

#### Message Metadata

The `meta` field can contain:

```json
{
  "subject": "Optional subject line",
  "severity": "info|warning|handoff|blocker"
}
```

#### Message ID Format

Message IDs follow the pattern `M{12-hex-chars}`, e.g., `M1A2B3C4D5E6F`.

#### Example Rows

```sql
-- Direct message to agent
INSERT INTO messages VALUES (
  'M1A2B3C4D5E6F',
  '2025-01-15T10:00:00+00:00',
  'A1B2C3D4E',
  'agent',
  'A9F8E7D6C',
  'Need help with authentication flow',
  '{"subject": "Help needed", "severity": "info"}',
  NULL
);

-- Task thread message
INSERT INTO messages VALUES (
  'M2B3C4D5E6F7A',
  '2025-01-15T10:05:00+00:00',
  'A1B2C3D4E',
  'task',
  'AUTH-001',
  'Started working on OAuth2 integration',
  '{}',
  NULL
);
```

---

### Table: `events`

Audit log for all significant actions.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `event_id` | INTEGER | PRIMARY KEY AUTOINCREMENT | Unique event ID |
| `created_at` | TEXT | NOT NULL, INDEX | When event occurred (ISO 8601) |
| `event_type` | TEXT | NOT NULL, INDEX | Event type (see below) |
| `agent_id` | TEXT | NULL | Acting agent ID |
| `task_id` | TEXT | NULL | Related task ID |
| `target_agent_id` | TEXT | NULL | Target agent (for messaging) |
| `correlation_id` | TEXT | NULL, INDEX | For correlating related events |
| `data` | TEXT | DEFAULT `{}` | JSON object with event-specific data |

#### Indexes

- `idx_events_created` on `created_at`
- `idx_events_type` on `event_type`
- `idx_events_correlation` on `correlation_id`

#### Event Types

| Event Type | Description |
|------------|-------------|
| `agent.join` | Agent registered |
| `agent.heartbeat` | Agent heartbeat updated |
| `agent.leave` | Agent marked offline |
| `task.claim` | Task lease created |
| `task.renew` | Lease renewed |
| `task.release` | Lease released |
| `lease.expired` | Lease expired (detected) |
| `task.done` | Task marked as done |
| `task.verified` | Task verified |
| `message.sent` | Message sent |
| `message.read` | Message read |

#### Example Row

```sql
INSERT INTO events (created_at, event_type, agent_id, task_id, data) VALUES (
  '2025-01-15T10:00:00+00:00',
  'task.claim',
  'A1B2C3D4E',
  'AUTH-001',
  '{"lease_id": "L9F8E7D6C", "ttl_seconds": 900}'
);
```

---

## Working with Schemas

### Reading the Spec File

```python
import yaml
from pathlib import Path

spec_path = Path(".lodestar/spec.yaml")
with open(spec_path) as f:
    spec = yaml.safe_load(f)

# Access project info
print(spec["project"]["name"])

# Iterate tasks
for task_id, task in spec.get("tasks", {}).items():
    print(f"{task_id}: {task['title']} ({task['status']})")
```

### Connecting to Runtime Database

```python
import sqlite3
from pathlib import Path

db_path = Path(".lodestar/runtime.sqlite")
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row

# Query active agents
cursor = conn.execute("""
    SELECT agent_id, display_name, last_seen_at
    FROM agents
    ORDER BY last_seen_at DESC
""")

for row in cursor:
    print(f"{row['agent_id']}: {row['display_name']}")
```

### Querying Active Leases

```python
from datetime import datetime, UTC

now = datetime.now(UTC).isoformat()

cursor = conn.execute("""
    SELECT l.task_id, l.agent_id, l.expires_at, a.display_name
    FROM leases l
    JOIN agents a ON l.agent_id = a.agent_id
    WHERE l.expires_at > ?
    ORDER BY l.expires_at
""", (now,))

for row in cursor:
    print(f"Task {row['task_id']} claimed by {row['display_name']}")
```

### Finding Claimable Tasks

```python
# Get verified task IDs from spec
verified = {
    task_id for task_id, task in spec.get("tasks", {}).items()
    if task.get("status") == "verified"
}

# Find claimable tasks
claimable = []
for task_id, task in spec.get("tasks", {}).items():
    if task.get("status") != "ready":
        continue
    deps = task.get("depends_on", [])
    if all(dep in verified for dep in deps):
        claimable.append(task_id)

print(f"Claimable tasks: {claimable}")
```

---

## JSON Schema Export

Export JSON Schema for validation:

```bash
# Export task context schema
lodestar task context --schema > task-context.schema.json

# Export status schema  
lodestar status --schema > status.schema.json
```

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `LODESTAR_LEASE_TTL` | `15m` | Default lease duration |
| `LODESTAR_NO_COLOR` | unset | Disable colored output |
| `LODESTAR_AGENT_IDLE_THRESHOLD_MINUTES` | `15` | Minutes until agent is "idle" |
| `LODESTAR_AGENT_OFFLINE_THRESHOLD_MINUTES` | `60` | Minutes until agent is "offline" |

---

## Best Practices for Tool Developers

1. **Always check lease expiration** — Filter by `expires_at > now` when querying leases
2. **Use transactions** — SQLite supports transactions; use them for atomic updates
3. **Handle concurrent access** — The database uses WAL mode for safe concurrent reads
4. **Validate against schema** — Use the Pydantic models or JSON Schema for validation
5. **Respect the two-plane model** — Spec changes should be committed; runtime is ephemeral
6. **Use ISO 8601 datetimes** — All timestamps should be timezone-aware UTC
