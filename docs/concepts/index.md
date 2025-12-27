# Concepts

Understanding Lodestar's core concepts will help you work effectively with the tool.

## Core Architecture

Lodestar uses a **two-plane state model** to separate what needs to be done (spec) from who is doing it (runtime):

| Plane | Purpose | Location | Git Status |
|-------|---------|----------|------------|
| **Spec** | Tasks, dependencies, acceptance criteria | `.lodestar/spec.yaml` | Committed |
| **Runtime** | Agents, leases, heartbeats, messages | `.lodestar/runtime.sqlite` | Gitignored |

## Key Concepts

### [Two-Plane Model](two-plane-model.md)

How Lodestar separates task definitions from execution state.

### [Task Lifecycle](task-lifecycle.md)

The states a task moves through from creation to verification.

### [Lease Mechanics](lease-mechanics.md)

How task claiming works with time-limited leases.

## Design Principles

1. **No Daemon Required**: Lease expiry is checked at read time, not by a background process
2. **Git-Native**: Spec plane is version controlled; runtime is ephemeral
3. **Agent-Agnostic**: Works the same for human developers and AI agents
4. **Progressive Discovery**: Commands suggest next actions; help is contextual
