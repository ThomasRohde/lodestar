# Lodestar - Agent Coordination

This repository uses **Lodestar** for task management. The CLI is self-documenting.

## Getting Started

```bash
# See all commands and workflows
uv run lodestar agent     # Agent workflow
uv run lodestar task      # Task workflow
uv run lodestar msg       # Message workflow

# Start here
uv run lodestar doctor    # Check repository health
uv run lodestar agent join --name "Your Name"  # Register, SAVE your agent ID
uv run lodestar task next # Find work
```

## Essential Workflow

```bash
# 1. Claim before working (--agent is required)
uv run lodestar task claim <id> --agent <your-agent-id>

# 2. Renew if work takes > 10 min
uv run lodestar task renew <id> --agent <your-agent-id>

# 3. Complete (auto-releases lease)
uv run lodestar task done <id>
uv run lodestar task verify <id>

# Only if you CAN'T complete - release for others to pick up
uv run lodestar task release <id>
```

## Creating Tasks (Planning Agents)

When creating tasks, write **detailed descriptions** so executing agents have full context:

```bash
uv run lodestar task create \
    --id "F010" \
    --title "Add email notifications" \
    --description "WHAT: Add email notifications when tasks are completed.
WHERE: src/notifications/, templates/email/
WHY: Users requested alerts for task completion.
ACCEPT: 1) Email sent on task.done 2) Template is configurable 3) Tests pass
CONTEXT: Auth is in src/auth/, see notify() pattern in src/alerts.py" \
    --priority 2 \
    --label feature \
    --depends-on "F009"
```

**Good descriptions include:**
- WHAT: Clear goal and scope
- WHERE: Relevant files/directories
- WHY: Business context or motivation
- ACCEPT: Measurable acceptance criteria
- CONTEXT: Pointers to related code, patterns to follow

This is critical for handoffs between planning agents (e.g., Opus) and executing agents (e.g., Sonnet).

## Get Help

```bash
# Any command with --help shows usage
uv run lodestar task claim --help
uv run lodestar msg send --help

# Or use --explain for context
uv run lodestar task claim --explain
```

## Project-Specific Notes

- All commands use `uv run lodestar` prefix
- Pre-commit checks required: `uv run ruff check src tests && uv run pytest`
- Task IDs: F=feature, D=docs, B=bug, T=test
