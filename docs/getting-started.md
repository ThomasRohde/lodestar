# Getting Started

This guide walks you through installing Lodestar and completing your first task in a multi-agent project.

## Prerequisites

- Python 3.12 or later
- Git repository (Lodestar works within Git repos)

## Installation

Lodestar is available on PyPI as `lodestar-cli`:

=== "uv (recommended)"

    ```bash
    uv add lodestar-cli
    ```

=== "pip"

    ```bash
    pip install lodestar-cli
    ```

=== "pipx (for global install)"

    ```bash
    pipx install lodestar-cli
    ```

Verify the installation:

```bash
$ lodestar --version
lodestar 0.1.0
```

## Initialize a Repository

Navigate to your Git repository and initialize Lodestar:

```bash
$ lodestar init
Initialized Lodestar repository

Created:
  .lodestar/spec.yaml - Task definitions (commit this)
  .lodestar/.gitignore - Ignores runtime files
```

This creates the `.lodestar/` directory with:

| File | Purpose | Git Status |
|------|---------|------------|
| `spec.yaml` | Task definitions and dependencies | Committed |
| `runtime.sqlite` | Agent state, leases, messages | Gitignored |

## Check Repository Health

Run the doctor command to verify everything is set up correctly:

```bash
$ lodestar doctor
Health Check

  ✓ repository: Repository found
  ✓ spec.yaml: Valid spec with 0 tasks
  ✓ dependencies: No cycles or missing dependencies
  ✓ .gitignore: Runtime files are gitignored

All checks passed!
```

## Create Your First Task

Add a task to work on:

```bash
$ lodestar task create \
    --id "TASK-001" \
    --title "Set up project structure" \
    --description "Create the initial directory layout and configuration files" \
    --priority 1 \
    --label feature

Created task TASK-001
```

## Join as an Agent

Register yourself as an agent to start claiming tasks:

```bash
$ lodestar agent join
Registered as agent A1234ABCD

Next steps:
  lodestar task next - Get next task
  lodestar task list - See all tasks
```

!!! tip "Save your agent ID"
    Your agent ID (like `A1234ABCD`) is used for claiming tasks and sending messages. You'll need it for subsequent commands.

## Find Available Work

See what tasks are available:

```bash
$ lodestar task next
Next Claimable Tasks (1 available)

  TASK-001 P1  Set up project structure

Run lodestar task claim TASK-001 to claim
```

## Claim a Task

Claim the task before you start working:

```bash
$ lodestar task claim TASK-001 --agent A1234ABCD
Claimed task TASK-001
  Lease: L5678EFGH
  Expires in: 15m

Remember to:
  - Renew with lodestar task renew TASK-001 before expiry
  - Mark done with lodestar task done TASK-001 when complete
```

The lease prevents other agents from working on the same task. If your work takes longer than 15 minutes, renew the lease:

```bash
$ lodestar task renew TASK-001
Renewed lease for TASK-001
  Expires in: 15m
```

## Complete a Task

When you're done with the implementation:

```bash
$ lodestar task done TASK-001
Marked TASK-001 as done
Run lodestar task verify TASK-001 after review
```

Then verify the task is complete and working:

```bash
$ lodestar task verify TASK-001
Verified TASK-001
```

Verification confirms the task meets acceptance criteria and unblocks any dependent tasks.

## View Repository Status

Get an overview of the project at any time:

```bash
$ lodestar status
┌─────────────────────────────────────────────────────────────────────────────┐
│ lodestar                                                                    │
└─────────────────────────────── Branch: main ────────────────────────────────┘

Tasks
 Status    Count
 verified      1

Runtime
  Agents registered: 1
  Active claims: 0

Next Actions
  lodestar task create - Add new task
  lodestar task list - See all tasks
```

## Next Steps

Now that you've completed your first task, explore these resources:

- **[Two-Plane Model](concepts/two-plane-model.md)** - Understand how Lodestar separates task definitions from execution state
- **[Task Lifecycle](concepts/task-lifecycle.md)** - Learn about task states and transitions
- **[CLI Reference](cli/index.md)** - Complete documentation of all commands
- **[Agent Workflow Guide](guides/agent-workflow.md)** - Best practices for working as an agent

## Quick Reference

| Action | Command |
|--------|---------|
| Initialize repo | `lodestar init` |
| Check health | `lodestar doctor` |
| View status | `lodestar status` |
| Register as agent | `lodestar agent join` |
| Find work | `lodestar task next` |
| Claim task | `lodestar task claim <id> --agent <agent-id>` |
| Renew lease | `lodestar task renew <id>` |
| Mark done | `lodestar task done <id>` |
| Verify complete | `lodestar task verify <id>` |
