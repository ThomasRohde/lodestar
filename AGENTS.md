# Lodestar - Agent Coordination

This repository uses **Lodestar itself** for task management (dogfooding).

## Session Start (Mandatory)

```bash
# 1. Verify you're in the right directory
pwd  # Should be the lodestar repo root

# 2. Check repository health
uv run lodestar doctor

# 3. Check current status
uv run lodestar status

# 4. Register as an agent (SAVE the ID it returns)
uv run lodestar agent join --name "Claude" --model claude-opus-4
# Example output: Registered as agent A1234ABCD  <-- USE THIS IN ALL COMMANDS

# 5. Find available work
uv run lodestar task next
```

## Working on a Task

```bash
# View task details first
uv run lodestar task show <task-id>

# Check if anyone left context
uv run lodestar msg thread <task-id>

# Claim BEFORE starting work (--agent is REQUIRED)
uv run lodestar task claim <task-id> --agent <your-agent-id>

# If work takes > 10 minutes, renew your lease
uv run lodestar task renew <task-id>

# When implementation is done
uv run lodestar task done <task-id>

# After testing/verification
uv run lodestar task verify <task-id>
```

## Creating New Tasks

When creating tasks, write **detailed descriptions**:

```bash
uv run lodestar task create \
    --id "F099" \
    --title "Implement feature X" \
    --description "What: Add X functionality to Y module.
Acceptance: 1) Tests pass 2) Docs updated 3) No regressions.
Files: src/lodestar/X.py, tests/test_X.py
Notes: See issue #123 for context." \
    --priority 2 \
    --label feature \
    --depends-on "F098"
```

**Task ID conventions:**
- `F###` - Features
- `D###` - Documentation
- `B###` - Bug fixes
- `T###` - Tests

## Communication (Use This!)

Leave context for other agents, especially when:
- Releasing a task you couldn't complete
- Finishing a task with important notes
- Handing off to another agent

```bash
# Leave context in task thread
uv run lodestar msg send \
    --to task:<task-id> \
    --from <your-agent-id> \
    --text "Progress: X done, Y remaining. Key insight: Z. Blocker: need A."

# Direct message to another agent
uv run lodestar msg send \
    --to agent:<other-agent-id> \
    --from <your-agent-id> \
    --text "Question about task F001..."

# Check your inbox
uv run lodestar msg inbox --agent <your-agent-id>
```

## Command Reference

| Action | Command |
|--------|---------|
| Health check | `uv run lodestar doctor` |
| Status overview | `uv run lodestar status` |
| List all tasks | `uv run lodestar task list` |
| Filter by status | `uv run lodestar task list --status ready` |
| Find claimable | `uv run lodestar task next` |
| Task details | `uv run lodestar task show <id>` |
| **Claim task** | `uv run lodestar task claim <id> --agent <agent-id>` |
| Renew lease | `uv run lodestar task renew <id>` |
| Release task | `uv run lodestar task release <id>` |
| Mark done | `uv run lodestar task done <id>` |
| Verify | `uv run lodestar task verify <id>` |
| Create task | `uv run lodestar task create --title "..." --priority N` |
| Send message | `uv run lodestar msg send --to task:<id> --from <agent> --text "..."` |
| Task thread | `uv run lodestar msg thread <task-id>` |
| Your inbox | `uv run lodestar msg inbox --agent <agent-id>` |

## Pre-Commit Checks (Required)

Before committing ANY changes:

```bash
uv run ruff check src tests          # Lint
uv run ruff format --check src tests # Format check
uv run pytest                        # All tests must pass
uv run mkdocs build                  # Docs must build
```

## Rules

1. **Use lodestar commands** - Don't edit `.lodestar/spec.yaml` directly
2. **Claim before working** - Prevents duplicate work
3. **Renew leases** - Every 10-15 minutes for long tasks
4. **Leave messages** - When releasing or completing tasks
5. **Set dependencies** - Use `--depends-on` when tasks have prerequisites
6. **Write good descriptions** - Include what, why, acceptance criteria, relevant files
7. **Verify after done** - It unblocks dependent tasks

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease/message state | Gitignored |
| `CLAUDE.md` | AI agent instructions | Commit |
| `AGENTS.md` | This file | Commit |
