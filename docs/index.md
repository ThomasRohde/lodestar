# Lodestar

**Agent-native repo orchestration for multi-agent coordination in Git repositories.**

Lodestar is a Python CLI tool that provides agents with task claiming (via leases), dependency tracking, and messaging—without requiring human scheduling.

## Features

- **Two-Plane State Model**: Separate spec (tasks, dependencies) from runtime (agents, leases)
- **Lease-Based Task Claims**: Atomic claiming with TTL-based expiry
- **Dependency Tracking**: DAG-based task scheduling with automatic readiness detection
- **PRD Context Delivery**: Tasks carry product intent with frozen excerpts and drift detection
- **Agent Messaging**: Inter-agent communication for handoffs and coordination
- **JSON-First Output**: All commands support `--json` for programmatic access

## Quick Start

```bash
# Install
uv add lodestar-cli

# Initialize a repository
lodestar init

# Join as an agent
lodestar agent join

# Find available work
lodestar task next

# Claim and work on a task
lodestar task claim <task-id>
lodestar task done <task-id>
```

## Documentation

- [Getting Started](getting-started.md) - Installation and first steps
- [Concepts](concepts/index.md) - Architecture and core concepts
- [CLI Reference](cli/index.md) - Complete command documentation
- [Guides](guides/index.md) - How-to guides for common workflows
- [Reference](reference/index.md) - Schema and API reference
