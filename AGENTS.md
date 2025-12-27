# lodestar - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## Quick Start for Agents

1. **Register**: Run `lodestar agent join` to get your agent ID
2. **Find work**: Run `lodestar task next` to see available tasks
3. **Claim task**: Run `lodestar task claim T123` to claim a task
4. **Communicate**: Run `lodestar msg send --to task:T123 --text "Progress update"`

## Commands

```bash
lodestar status          # Repository overview
lodestar task list       # All tasks
lodestar task next       # Next claimable task
lodestar task show T123  # Task details
lodestar msg inbox       # Your messages
```

## Rules

- Always claim before working on a task
- Renew claims every 15 minutes for long tasks
- Release claims if you can't complete the work
- Post updates to task threads

## Files

- `.lodestar/spec.yaml` - Task definitions (DO commit)
- `.lodestar/runtime.sqlite` - Runtime state (DO NOT commit or edit)
