# Two-Plane Model

Lodestar separates state into two distinct planes, each with different characteristics and purposes.

## Spec Plane

The spec plane contains the **definition of work**:

- Task definitions with titles, descriptions, and labels
- Dependencies between tasks (DAG structure)
- Priority assignments
- Acceptance criteria

**Location**: `.lodestar/spec.yaml`
**Git Status**: Committed and version controlled

### Example Spec

```yaml
tasks:
  - id: F001
    title: Implement user authentication
    description: Add OAuth2 login flow
    priority: 1
    labels: [feature, security]
    depends_on: []

  - id: F002
    title: Add password reset
    description: Email-based password reset flow
    priority: 2
    labels: [feature]
    depends_on: [F001]
```

## Runtime Plane

The runtime plane contains the **execution state**:

- Registered agents and their heartbeats
- Active leases (task claims)
- Task status (ready, done, verified)
- Inter-agent messages

**Location**: `.lodestar/runtime.sqlite`
**Git Status**: Gitignored

### Why SQLite?

- Atomic transactions for lease claims
- WAL mode for concurrent access
- No external dependencies
- Fast read queries

## Benefits of Separation

1. **Clean History**: Git history shows what changed, not who was working on what
2. **Easy Resets**: Delete runtime.sqlite to reset all execution state
3. **Reproducibility**: Same spec produces same task graph
4. **Multi-Machine**: Runtime is local; spec is shared
