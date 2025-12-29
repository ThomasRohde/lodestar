# Lodestar

[![PyPI version](https://img.shields.io/pypi/v/lodestar-cli.svg)](https://pypi.org/project/lodestar-cli/)
[![CI Status](https://github.com/lodestar-cli/lodestar/actions/workflows/ci.yml/badge.svg)](https://github.com/lodestar-cli/lodestar/actions/workflows/ci.yml)
[![Documentation](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://github.com/lodestar-cli/lodestar/tree/master/docs)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Agent-native repo orchestration for multi-agent coordination in Git repositories.**

Lodestar is a Python CLI tool that enables multiple AI agents (or humans) to work together on tasks in a Git repository without stepping on each other's toes. It provides atomic task claiming with leases, dependency tracking, and inter-agent messaging—all without requiring a central coordinator or human scheduler.

## Why Lodestar?

When multiple agents work in the same repository, chaos ensues: duplicate work, merge conflicts, and broken dependencies. Lodestar solves this by providing:

- **Task claiming with leases**: Agents atomically claim tasks with TTL-based expiration (no daemons required)
- **Dependency-aware scheduling**: Tasks automatically become available when their dependencies are verified
- **Clean Git history**: Task definitions live in `.lodestar/spec.yaml` (committed), while execution state lives in `runtime.sqlite` (gitignored)
- **No central server**: Everything runs locally using SQLite for race-free coordination

## Key Features

- **Multi-Agent Coordination**: Multiple agents can work simultaneously without conflicts through atomic task claims
- **Lease-Based Claims**: Tasks are claimed with time-limited leases that auto-expire, preventing stuck locks
- **Two-Plane State Model**: Clean separation between task definitions (spec) and execution state (runtime)
- **Dependency Tracking**: DAG-based task scheduling with automatic readiness detection
- **PRD Context Delivery**: Tasks carry just-enough product intent from PRDs—frozen excerpts, section refs, and drift detection
- **Self-Documenting CLI**: Every command supports `--json`, `--schema`, and `--explain` flags for programmatic access
- **Progressive Discovery**: No-args commands suggest next actions to guide workflows
- **Agent Messaging**: Built-in inter-agent communication for handoffs and coordination
- **MCP Server Integration**: Expose Lodestar as an MCP server for seamless integration with AI assistants like Claude Desktop

## Installation

### Using uv (recommended)

```bash
uv add lodestar-cli
```

### Using pip

```bash
pip install lodestar-cli
```

### Using pipx (for global install)

```bash
pipx install lodestar-cli
```

Verify the installation:

```bash
lodestar --version
```

## Quick Start

Initialize a repository and complete your first task:

```bash
# Initialize Lodestar in your Git repository
lodestar init

# Check repository health
lodestar doctor

# Create a task
lodestar task create \
  --id "TASK-001" \
  --title "Set up project structure" \
  --description "Create initial directory layout" \
  --priority 1 \
  --label feature

# Join as an agent
lodestar agent join
# Output: Registered as agent A1234ABCD

# Find available work
lodestar task next

# Claim a task (prevents other agents from taking it)
lodestar task claim TASK-001 --agent A1234ABCD

# Do your work...
# git add, git commit, etc.

# Mark task as done
lodestar task done TASK-001

# Verify completion (unblocks dependent tasks)
lodestar task verify TASK-001

# Delete a task (soft-delete, preserves in spec.yaml)
lodestar task delete TASK-002

# Check status
lodestar status
```

For development/testing, use `uv run lodestar` instead of `lodestar` to run from source.

## MCP Server Integration

Lodestar can be exposed as an MCP (Model Context Protocol) server, allowing AI assistants like Claude Desktop to interact with your Lodestar repository through standardized tools.

### Installing MCP Dependencies

The MCP server functionality requires additional dependencies. Install them using:

```bash
# Using uv tool (recommended for global installation)
uv tool install 'lodestar-cli[mcp]'

# Or upgrade if already installed
uv tool upgrade 'lodestar-cli[mcp]'

# Using uv in a project
uv add 'lodestar-cli[mcp]'

# Using pip
pip install 'lodestar-cli[mcp]'

# Using pipx (alternative global installation)
pipx install 'lodestar-cli[mcp]'

# For development
uv sync --extra mcp
```

### Starting the MCP Server

Run the MCP server from within a Lodestar repository:

```bash
# Auto-discover repository from current directory
lodestar mcp serve

# Specify repository path explicitly
lodestar mcp serve --repo /path/to/repository

# Enable logging to file
lodestar mcp serve --log-file mcp.log

# Use JSON-formatted logs
lodestar mcp serve --log-file mcp.log --json-logs
```

The server uses stdio transport by default, making it compatible with MCP clients like Claude Desktop.

### Configuring with Claude Desktop

Add Lodestar as an MCP server in Claude Desktop's configuration file:

**macOS/Linux:** `~/Library/Application Support/Claude/claude_desktop_config.json`
**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`

```json
{
  "mcpServers": {
    "lodestar": {
      "command": "lodestar",
      "args": ["mcp", "serve", "--repo", "/absolute/path/to/your/repository"],
      "env": {}
    }
  }
}
```

If you installed Lodestar with `uv` in a project, use:

```json
{
  "mcpServers": {
    "lodestar": {
      "command": "uv",
      "args": ["run", "lodestar", "mcp", "serve", "--repo", "/absolute/path/to/your/repository"],
      "env": {}
    }
  }
}
```

After updating the configuration, restart Claude Desktop. The Lodestar tools will be available for Claude to use when working with your repository.

### Available MCP Tools

When connected, Claude can use Lodestar tools to:
- List and query tasks
- Create and update tasks
- Claim and release tasks
- Mark tasks as done or verified
- Send messages between agents
- View dependency graphs
- And more...

All Lodestar CLI functionality is exposed through the MCP interface.

## Architecture Overview

Lodestar uses a **two-plane state model** that separates concerns:

| Plane | Purpose | Location | Git Status |
|-------|---------|----------|------------|
| **Spec Plane** | Task definitions, dependencies, acceptance criteria | `.lodestar/spec.yaml` | Committed |
| **Runtime Plane** | Agent state, leases, heartbeats, messages | `.lodestar/runtime.sqlite` | Gitignored |

This separation provides:

- **Clean Git history**: No noise from lease claims or heartbeats in version control
- **Easy resets**: Delete `runtime.sqlite` to start fresh without losing task definitions
- **Reproducibility**: Same spec produces same task graph on any machine
- **Multi-machine support**: Each machine has its own runtime state but shares the task definitions

### How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                     Git Repository                          │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ .lodestar/spec.yaml (committed)                     │    │
│  │  - Task definitions                                 │    │
│  │  - Dependencies (DAG)                               │    │
│  │  - Priorities & labels                              │    │
│  └─────────────────────────────────────────────────────┘    │
│                                                              │
│  ┌─────────────────────────────────────────────────────┐    │
│  │ .lodestar/runtime.sqlite (gitignored)               │    │
│  │  - Registered agents                                │    │
│  │  - Active leases (task claims)                      │    │
│  │  - Task status (ready/done/verified)                │    │
│  │  - Inter-agent messages                             │    │
│  └─────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────┘
```

Tasks flow through states: `ready` → `done` → `verified`. A task becomes claimable when it's `ready` and all its dependencies are `verified`. Tasks can also be soft-deleted (status set to `deleted`) to hide them from normal views while preserving history.

### PRD Context Delivery

Tasks can carry product intent from a PRD, so executing agents don't need to re-read the full document:

```bash
# Get PRD context for a task
lodestar task context TASK-001

# Create a task with PRD context attached
lodestar task create \
    --id "TASK-002" \
    --title "Implement password reset" \
    --prd-source PRD.md \
    --prd-ref "#password-reset" \
    --prd-excerpt "Reset tokens must expire after 15 minutes..."
```

When claiming a task, context is delivered automatically. If the PRD has changed since task creation, you'll get a drift warning.

## Documentation

Full documentation is available in the [`docs/`](docs/) directory:

- **[Getting Started](docs/getting-started.md)** - Installation and first steps
- **[Concepts](docs/concepts/)** - Architecture and core concepts
  - [Two-Plane Model](docs/concepts/two-plane-model.md)
  - [Task Lifecycle](docs/concepts/task-lifecycle.md)
  - [Lease Mechanics](docs/concepts/lease-mechanics.md)
  - [PRD Context Delivery](docs/concepts/prd-context.md)
- **[CLI Reference](docs/cli/)** - Complete command documentation
- **[Guides](docs/guides/)** - How-to guides for common workflows
  - [Agent Workflow](docs/guides/agent-workflow.md)
  - [CI Integration](docs/guides/ci-integration.md)

You can also browse the docs locally:

```bash
uv run mkdocs serve
```

## Contributing

Contributions are welcome! This project uses Lodestar for its own task management (dogfooding).

### Development Setup

```bash
# Clone the repository
git clone https://github.com/lodestar-cli/lodestar.git
cd lodestar

# Install dependencies
uv sync

# Run tests
uv run pytest

# Run linting
uv run ruff check src tests
uv run ruff format src tests

# Serve documentation locally
uv run mkdocs serve
```

### Using Lodestar to Contribute

This repository uses Lodestar for task management. To contribute:

1. Run `uv run lodestar status` to see available work
2. Find tasks with `uv run lodestar task next`
3. Claim a task before working: `uv run lodestar task claim <id> --agent <your-agent-id>`
4. Make your changes and commit
5. Mark complete: `uv run lodestar task done <id>`
6. Verify: `uv run lodestar task verify <id>`

See [`CLAUDE.md`](CLAUDE.md) for detailed development guidelines.

### Testing Standards

Before committing, ensure all checks pass:

```bash
uv run ruff check src tests          # Linting
uv run ruff format --check src tests # Format check
uv run pytest                        # Tests
uv run mkdocs build                  # Docs build
```

## License

This project is licensed under the MIT License. See the [LICENSE](LICENSE) file for details.

## Links

- **PyPI**: [lodestar-cli](https://pypi.org/project/lodestar-cli/)
- **Repository**: [github.com/lodestar-cli/lodestar](https://github.com/lodestar-cli/lodestar)
- **Issues**: [github.com/lodestar-cli/lodestar/issues](https://github.com/lodestar-cli/lodestar/issues)
- **Documentation**: [docs/](docs/)
