# Getting Started

This guide walks you through installing Lodestar and completing your first task in a multi-agent project.

## Prerequisites

- Python 3.12 or later
- Git repository (Lodestar works within Git repos)

!!! note "Windows Users"
    Windows file system behavior differs from Linux/macOS in ways that affect Lodestar:
    
    - **File locking**: Windows may briefly lock files during save operations (~20-40% of operations)
    - **Performance**: File operations are typically 2-3x slower than on Linux/macOS
    - **Antivirus**: Windows Defender or other antivirus software may cause additional file locks
    
    Lodestar v0.2.0+ includes automatic retry logic for these transient errors. Most operations succeed within 1-2 retries.

## Installation

Lodestar is available on PyPI as `lodestar-cli`:

**Using uv (recommended):**

```bash
uv add lodestar-cli
```

**Using pip:**

```bash
pip install lodestar-cli
```

**Using pipx (for global install):**

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
- **[PRD Context Delivery](concepts/prd-context.md)** - How tasks carry product intent from PRDs
- **[CLI Reference](cli/index.md)** - Complete documentation of all commands
- **[Agent Workflow Guide](guides/agent-workflow.md)** - Best practices for working as an agent
- **[Error Handling Guide](guides/error-handling.md)** - How to handle errors and retries (important for Windows users)

## Performance Characteristics

Expected operation times for common tasks:

| Operation | Linux/macOS | Windows | Notes |
|-----------|-------------|---------|-------|
| `task claim` | 50-100ms | 100-300ms | Includes spec lock + DB write |
| `task done` | 50-150ms | 150-500ms | Spec save with atomic rename |
| `task verify` | 100-200ms | 200-600ms | Updates spec + checks dependencies |
| `task list` | 10-50ms | 20-100ms | Read-only operation |
| `task create` | 100-200ms | 200-500ms | Spec validation + save |

**Windows Performance Tips:**

- Run from local drive (not network share) for best performance
- Disable real-time antivirus scanning for `.lodestar/` directory if possible
- SSD storage provides significant improvement over HDD
- Concurrent operations may trigger file locks - use retry logic (see [Error Handling Guide](guides/error-handling.md))

**Network File Systems (NFS/SMB):**

Lodestar is designed for local file systems. Network file systems may have:

- Stale lock files
- Higher latency
- Inconsistent file locking behavior

For best results, clone your repository locally rather than working on a network share.

## Advanced: Tasks with PRD Context

For planning→executing agent workflows (e.g., Opus creates tasks, Sonnet executes), you can attach PRD context to tasks:

### Creating Tasks with Context

```bash
$ lodestar task create \
    --id "TASK-002" \
    --title "Implement password reset" \
    --description "Email-based password reset flow" \
    --prd-source PRD.md \
    --prd-ref "#password-reset" \
    --prd-excerpt "Reset tokens must expire after 15 minutes and be single-use."

Created task TASK-002
```

This attaches:

- **PRD source file** — Where the context came from
- **Section references** — Anchors like `#password-reset`
- **Frozen excerpt** — Key paragraphs copied verbatim
- **PRD hash** — For drift detection

### Getting Task Context

Retrieve the context for any task:

```bash
$ lodestar task context TASK-002
Context for TASK-002

PRD Source: PRD.md
References: #password-reset

Content:
  Implement password reset
  Email-based password reset flow

  Reset tokens must expire after 15 minutes and be single-use.
```

### Context on Claim

When you claim a task, context is delivered automatically:

```bash
$ lodestar task claim TASK-002 --agent A1234ABCD
Claimed task TASK-002
  Lease: L5678EFGH
  Expires in: 15m

Task Context:
  Implement password reset
  Email-based password reset flow
  PRD: PRD.md
```

If the PRD has changed since the task was created, you'll see a drift warning.

!!! tip "When to use PRD context"
    PRD context is optional but valuable when:
    
    - Multiple agents work on the same project
    - Planning and executing are done by different agents
    - Tasks need stable product intent that survives PRD edits

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
