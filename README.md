# Lodestar

Agent-native repo orchestration for multi-agent coordination in Git repositories.

## Installation

```bash
pip install lodestar-cli
```

## Quick Start

```bash
# Initialize a repository
lodestar init

# Register as an agent
lodestar agent join

# Find available work
lodestar task next

# Claim a task
lodestar task claim T001 --agent YOUR_AGENT_ID

# Mark task as done
lodestar task done T001
```

## Documentation

See [PRD.md](PRD.md) for the full product requirements document.

## License

MIT
