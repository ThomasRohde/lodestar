# Getting Started

This guide will help you install Lodestar and set up your first multi-agent project.

## Installation

Lodestar is available on PyPI. Install it using your preferred Python package manager:

=== "uv"

    ```bash
    uv add lodestar-cli
    ```

=== "pip"

    ```bash
    pip install lodestar-cli
    ```

## Initialize a Repository

Navigate to your Git repository and initialize Lodestar:

```bash
lodestar init
```

This creates:

- `.lodestar/spec.yaml` - Task definitions (committed to git)
- `.lodestar/runtime.sqlite` - Agent state (gitignored)

## Join as an Agent

Register yourself as an agent to start claiming tasks:

```bash
lodestar agent join
```

You'll receive an agent ID that you'll use for all subsequent operations.

## Find Available Work

See what tasks are available to work on:

```bash
lodestar task next
```

This shows tasks that are:

- In `ready` status
- Have all dependencies verified
- Not currently claimed by another agent

## Claim a Task

When you find a task to work on, claim it:

```bash
lodestar task claim <task-id>
```

This creates a lease that reserves the task for you (default: 15 minutes).

## Complete a Task

When you're done:

```bash
lodestar task done <task-id>
```

Then verify it:

```bash
lodestar task verify <task-id>
```

## Next Steps

- Learn about the [Two-Plane Model](concepts/two-plane-model.md)
- Explore the [CLI Reference](cli/index.md)
- Read the [Agent Workflow Guide](guides/agent-workflow.md)
