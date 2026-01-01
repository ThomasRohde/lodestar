"""AGENTS.md templates for lodestar init command.

These templates are generated when initializing a new Lodestar repository.
They provide guidance to agents (human or AI) on how to use the repository.
"""

from __future__ import annotations

# CLI-only AGENTS.md template (no MCP)
AGENTS_MD_CLI_TEMPLATE = """# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

The CLI is self-documenting. Run these commands to see workflows:

```bash
lodestar agent     # Agent registration workflow
lodestar task      # Task management workflow
lodestar msg       # Messaging workflow
```

## Quick Start

```bash
lodestar doctor                        # Check repository health
lodestar agent join --name "Your Name" # Register, SAVE the agent ID
lodestar task next                     # Find available work
```

## Finding Work

```bash
# Get next claimable task (status=ready, all deps verified, no active lease)
lodestar task next

# Get multiple options to choose from
lodestar task next --count 5

# Browse all tasks
lodestar task list

# Filter by status or label
lodestar task list --status ready
lodestar task list --label feature
lodestar task list --status done

# View deleted tasks
lodestar task list --include-deleted
lodestar task list --status deleted

# Get full task details
lodestar task show F001
lodestar task show F001 --json    # For programmatic access
```

## Complete Workflow Example

```bash
# 1. Register as an agent (save your ID!)
lodestar agent join --name "Agent-1"
# Output: Registered agent A1234ABCD

# 2. Find available work
lodestar task next --count 3

# 3. Claim before working (creates 15-min lease)
lodestar task claim F001 --agent A1234ABCD

# 4. Do the work...
#    If it takes longer than 10 min, renew the lease:
lodestar task renew F001 --agent A1234ABCD

# 5. Complete the task
lodestar task done F001
lodestar task verify F001

# Alternative: Release if you can't complete
lodestar task release F001
```

## Creating Tasks

Write **detailed descriptions** so executing agents have full context.

### Basic Task

```bash
lodestar task create --title "Fix login bug" --label bug --priority 1
```

### Full Task with Dependencies

```bash
lodestar task create \\
    --id "F001" \\
    --title "Add user authentication" \\
    --description "WHAT: Implement OAuth2 login. WHERE: src/auth/. WHY: Users need SSO. ACCEPT: Tests pass, login works." \\
    --depends-on "F000" \\
    --label feature \\
    --priority 2
```

### Task with PRD References

```bash
# Reference sections in a PRD file
lodestar task create \\
    --title "Implement caching layer" \\
    --prd-source "PRD.md" \\
    --prd-ref "#caching-requirements" \\
    --prd-ref "#performance-targets"

# Or embed a frozen excerpt directly
lodestar task create \\
    --title "Add rate limiting" \\
    --prd-excerpt "Rate limit: 100 req/min per user. Use Redis for distributed counting."
```

### Task Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--id` | | Task ID (auto-generated if omitted) |
| `--title` | `-t` | Task title (required) |
| `--description` | `-d` | WHAT/WHERE/WHY/ACCEPT format recommended |
| `--priority` | `-p` | Lower number = higher priority (default: 100) |
| `--status` | `-s` | Initial status (default: ready) |
| `--depends-on` | | Task IDs this depends on (repeatable) |
| `--label` | `-l` | Labels for categorization (repeatable) |
| `--prd-source` | | Path to PRD file |
| `--prd-ref` | | PRD section anchors (repeatable) |
| `--prd-excerpt` | | Frozen PRD text to embed |

## Multi-Agent File Coordination

When multiple agents work concurrently, use the `locks` field to declare file ownership:

```yaml
# In spec.yaml
F001:
  title: Implement auth
  locks:
    - src/auth/**
    - tests/auth/**
```

When claiming a task, you'll see warnings if locks overlap with other claimed tasks:

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
WARNING: Lock 'src/auth/**' overlaps with 'src/**' (task F001, claimed by A9876WXYZ)

Use --force to bypass lock conflict warnings
```

Use `--force` when you intentionally coordinate with another agent.

## CLI Quick Reference

| Command | Key Options |
|---------|-------------|
| `task list` | `--status`, `--label`, `--include-deleted` |
| `task next` | `--count` |
| `task show <id>` | `--json` |
| `task create` | `--title`, `--description`, `--priority`, `--depends-on`, `--label`, `--prd-source`, `--prd-ref`, `--prd-excerpt` |
| `task claim <id>` | `--agent`, `--force` |
| `task renew <id>` | `--agent` |
| `task done <id>` | |
| `task verify <id>` | |
| `task delete <id>` | `--cascade` |

## Get Help

```bash
lodestar <command> --help    # See all options
lodestar <command> --explain # Understand what it does
```

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |
"""

# MCP-enabled AGENTS.md template
AGENTS_MD_MCP_TEMPLATE = """# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## MCP Tools (Preferred)

When connected via MCP, use the `lodestar_*` tools directly. MCP is the preferred method for agents.

### Quick Start

```
lodestar_agent_join(name="Your Name")     # Register, SAVE the agentId
lodestar_task_next()                       # Find available work
lodestar_task_claim(task_id="F001", agent_id="YOUR_ID")
```

### Agent Workflow

```
1. JOIN      lodestar_agent_join()         -> Get your agentId
2. FIND      lodestar_task_next()          -> Get claimable tasks
3. CLAIM     lodestar_task_claim()         -> Create 15-min lease
4. CONTEXT   lodestar_task_context()       -> Get PRD context
5. WORK      (implement the task)
6. DONE      lodestar_task_done()          -> Mark complete
7. VERIFY    lodestar_task_verify()        -> Unblock dependents
```

### MCP Tool Reference

| Category | Tool | Purpose |
|----------|------|---------|
| **Repo** | `lodestar_repo_status` | Get project status, task counts, next actions |
| **Agent** | `lodestar_agent_join` | Register as agent (returns agentId) |
| | `lodestar_agent_heartbeat` | Update presence (call every 5 min) |
| | `lodestar_agent_leave` | Mark offline gracefully |
| | `lodestar_agent_list` | List all registered agents |
| **Task Query** | `lodestar_task_next` | Get claimable tasks (dependency-aware) |
| | `lodestar_task_list` | List tasks with filtering |
| | `lodestar_task_get` | Get full task details |
| | `lodestar_task_context` | Get PRD context for a task |
| **Task Mutation** | `lodestar_task_claim` | Claim task (15-min lease) |
| | `lodestar_task_release` | Release claim (if blocked) |
| | `lodestar_task_done` | Mark task complete |
| | `lodestar_task_verify` | Verify task (unblocks deps) |
| **Message** | `lodestar_message_send` | Send to agent or task thread |
| | `lodestar_message_list` | Get inbox messages |
| | `lodestar_message_ack` | Mark messages as read |
| **Events** | `lodestar_events_pull` | Pull event stream |

### Handoff Pattern

When blocked or ending session before completion:

```
lodestar_task_release(task_id="F001", agent_id="YOUR_ID", reason="Blocked on API approval")
lodestar_message_send(task_id="F001", from_agent_id="YOUR_ID", body="Progress: 60% complete. Tests passing.")
```

## CLI Commands (No MCP Equivalent)

These operations require CLI:

| Command | Purpose |
|---------|---------|
| `lodestar init` | Initialize repository |
| `lodestar doctor` | Health check |
| `lodestar task create` | Create new tasks |
| `lodestar task update` | Update task fields |
| `lodestar task delete` | Delete tasks (--cascade for deps) |
| `lodestar task renew` | Extend lease duration |
| `lodestar task graph` | Export dependency graph |
| `lodestar export snapshot` | Export full state |

### Creating Tasks (CLI Only)

```bash
lodestar task create \\
    --id "F001" \\
    --title "Add authentication" \\
    --description "WHAT: Implement OAuth2. WHERE: src/auth/. ACCEPT: Tests pass." \\
    --depends-on "F000" \\
    --label feature \\
    --priority 2
```

### Task with PRD References (CLI Only)

```bash
lodestar task create \\
    --title "Implement caching" \\
    --prd-source "PRD.md" \\
    --prd-ref "#caching-requirements"
```

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |

## Help

```bash
lodestar <command> --help     # CLI options
lodestar <command> --explain  # What it does
```
"""


def render_agents_md_cli(project_name: str) -> str:
    """Render CLI-only AGENTS.md template."""
    return AGENTS_MD_CLI_TEMPLATE.format(project_name=project_name)


def render_agents_md_mcp(project_name: str) -> str:
    """Render MCP-enabled AGENTS.md template."""
    return AGENTS_MD_MCP_TEMPLATE.format(project_name=project_name)
