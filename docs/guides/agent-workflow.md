# Agent Workflow Guide

This guide covers how to work effectively as an agent with Lodestar, whether you're a human developer or an AI agent.

## Starting a Session

### 1. Check Repository Status

```bash
lodestar status
```

This shows:

- Current branch
- Task counts by status
- Number of active agents
- Suggested next actions

### 2. Run Health Checks

```bash
lodestar doctor
```

Verify the repository is in a healthy state before starting work.

### 3. Register as an Agent

```bash
lodestar agent join
```

Save your agent ID for use in subsequent commands.

### 4. Find Available Work

```bash
lodestar task next
```

Shows tasks that are:

- In `ready` status
- Have all dependencies verified
- Not currently claimed

## Working on a Task

### Claim Before Starting

Always claim a task before beginning work:

```bash
lodestar task claim <task-id> --agent <your-agent-id>
```

This prevents duplicate work and signals to others what you're working on.

### Monitor Your Lease

Leases expire after 15 minutes by default. If your work takes longer:

```bash
lodestar task renew <task-id>
```

### If You Get Blocked

If you can't complete the task, release it:

```bash
lodestar task release <task-id>
```

Optionally send a message explaining the blocker:

```bash
lodestar msg send all --from <your-agent-id> --body "Blocked on F002: need API credentials"
```

## Completing a Task

### 1. Finish Implementation

- Make atomic, reviewable commits
- Ensure tests pass
- Update documentation if needed

### 2. Mark as Done

```bash
lodestar task done <task-id>
```

### 3. Verify

```bash
lodestar task verify <task-id>
```

Verification confirms the task meets acceptance criteria and unblocks dependent tasks.

## Handoffs Between Agents

### Sending Context

When handing off to another agent:

```bash
lodestar msg send <agent-id> \
    --from <your-agent-id> \
    --body "F002 context: auth tokens are stored in Redis, see src/auth/tokens.py"
```

### Receiving Handoffs

Check your inbox:

```bash
lodestar msg inbox <your-agent-id>
```

## Best Practices

1. **One task at a time**: Focus on a single task to completion
2. **Renew early**: Don't let leases expire unexpectedly
3. **Communicate blockers**: Use messaging to flag issues
4. **Verify thoroughly**: Don't mark verified until you've tested
5. **Commit often**: Make progress visible in git history
