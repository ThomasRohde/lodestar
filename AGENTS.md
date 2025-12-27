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

# 3. Complete
uv run lodestar task done <id>
uv run lodestar task verify <id>
```

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
