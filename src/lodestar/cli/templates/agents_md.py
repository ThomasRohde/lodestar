"""AGENTS.md templates for lodestar init command.

These templates are generated when initializing a new Lodestar repository.
They provide guidance to agents (human or AI) on how to use the repository.
"""

from __future__ import annotations

# CLI-only AGENTS.md template (no MCP)
AGENTS_MD_CLI_TEMPLATE = """# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## Quick Start

```bash
lodestar doctor                        # Check repository health
lodestar agent join --name "Your Name" # Register, SAVE the agent ID
lodestar task next                     # Find available work
```

---

## Task Design Principles

**Every task must be completable within a 15-minute lease.** This is non-negotiable.

### The INVEST Criteria

Good tasks follow INVEST:

| Criterion | Meaning | Example |
|-----------|---------|---------|
| **I**ndependent | Can be completed without waiting for others | OK: "Add login form" not BAD: "Add login after auth service" |
| **N**egotiable | Details can be refined during execution | Specify WHAT, not HOW |
| **V**aluable | Delivers user or developer value | Clear business reason |
| **E**stimable | Scope is clear enough to estimate | Bounded file changes |
| **S**mall | Fits in 15-minute lease | Split large work |
| **T**estable | Has verifiable acceptance criteria | "Tests pass", "Endpoint returns 200" |

### Mandatory PRD References

If a PRD or spec file exists in this repository, **all tasks MUST reference it**:

```bash
lodestar task create \\
    --title "Implement feature X" \\
    --prd-source "PRD.md" \\
    --prd-ref "#feature-x-requirements"
```

This creates traceability and ensures executing agents have context.

---

## Task Description Format

Use this structured format for task descriptions:

```
WHAT:   [Concise statement of what to build/fix]
WHERE:  [File paths or modules to modify]
WHY:    [Business context - link to PRD section]
SCOPE:  [Explicit boundaries - what NOT to do]
ACCEPT: [Testable acceptance criteria - numbered]
REFS:   [Related tasks, docs, code patterns]
```

### Example: Well-Structured Task

```bash
lodestar task create \\
    --id "F042" \\
    --title "Add email validation to signup form" \\
    --description "WHAT: Add client-side email format validation.
WHERE: src/components/SignupForm.tsx, src/utils/validation.ts
WHY: Users submit invalid emails causing bounce issues (PRD #signup-requirements)
SCOPE: Client-side only. Do NOT add server validation (separate task F043).
ACCEPT: 1) Invalid emails show error message 2) Valid emails pass 3) Tests cover edge cases
REFS: Follow pattern in src/utils/validation.ts, see F041 for form structure" \\
    --prd-source "PRD.md" \\
    --prd-ref "#signup-requirements" \\
    --accept "Invalid emails show inline error" \\
    --accept "Valid emails pass validation" \\
    --accept "Unit tests cover: empty, missing @, missing domain" \\
    --lock "src/components/SignupForm.tsx" \\
    --lock "src/utils/validation.ts" \\
    --depends-on "F041" \\
    --label feature \\
    --priority 2
```

---

## Task Decomposition Patterns

Large work must be split into 15-minute tasks. Use these patterns:

### Vertical Slicing (Preferred)

End-to-end thin features that deliver value:

```
F001: Add /health endpoint (returns 200)
F002: Add /health checks database connection
F003: Add /health checks cache connection
```

### Horizontal Layering

Infrastructure -> Logic -> Interface:

```
F001: Add User model and migration
F002: Add UserService with CRUD operations
F003: Add /users API endpoints
F004: Add user list UI component
```

### Test-First Approach

Write tests, then implementation:

```
F001: Add tests for email validation
F002: Implement email validation to pass tests
```

---

## Acceptance Criteria Best Practices

Acceptance criteria MUST be:

| Quality | Bad Example | Good Example |
|---------|-------------|--------------|
| **Testable** | "Works correctly" | "Returns 200 OK with JSON body" |
| **Specific** | "Handles errors" | "Returns 400 for invalid input with error message" |
| **Independent** | "And also does X" | Separate criterion for each check |
| **Complete** | Only happy path | Include: happy path, edge cases, error cases |

### Using --accept for Structured Criteria

```bash
lodestar task create \\
    --title "Add rate limiting" \\
    --accept "Requests over 100/min return 429" \\
    --accept "Rate limit headers included in response" \\
    --accept "Existing tests still pass" \\
    --accept "New tests cover rate limit scenarios"
```

---

## Multi-Agent File Coordination

Declare file ownership with `--lock` to prevent conflicts:

```bash
lodestar task create \\
    --title "Refactor auth module" \\
    --lock "src/auth/**" \\
    --lock "tests/auth/**"
```

When claiming, you'll see warnings if locks overlap:

```bash
$ lodestar task claim F002 --agent A1234ABCD
Claimed task F002
WARNING: Lock 'src/auth/**' overlaps with 'src/**' (task F001, agent A9876WXYZ)
```

Use `--force` when intentionally coordinating with another agent.

---

## Complete Task Options Reference

| Option | Short | Description |
|--------|-------|-------------|
| `--id` | | Task ID (auto-generated as T001, T002... if omitted) |
| `--title` | `-t` | Task title (required) |
| `--description` | `-d` | Full description (WHAT/WHERE/WHY/SCOPE/ACCEPT/REFS format) |
| `--accept` | `-a` | Acceptance criterion (repeatable) |
| `--priority` | `-p` | Lower = higher priority (default: 100) |
| `--status` | `-s` | Initial status (default: ready) |
| `--depends-on` | | Task IDs this depends on (repeatable) |
| `--label` | `-l` | Labels for categorization (repeatable) |
| `--lock` | | File glob patterns for ownership (repeatable) |
| `--prd-source` | | Path to PRD file (e.g., "PRD.md") |
| `--prd-ref` | | PRD section anchors (repeatable, e.g., "#feature-x") |
| `--prd-excerpt` | | Frozen PRD text to embed directly |
| `--validate-prd` | | Validate PRD exists and anchors resolve (default) |
| `--no-validate-prd` | | Skip PRD validation |

---

## Working on Tasks

```bash
# 1. Register as an agent (save your ID!)
lodestar agent join --name "Agent-1"
# Output: Registered agent A1234ABCD

# 2. Find available work
lodestar task next --count 3

# 3. Check for upstream messages (tasks this depends on)
lodestar task show F001  # See dependencies
lodestar msg list --task F001 --unread-by A1234ABCD
# Read any messages from upstream tasks about context or issues

# 4. Claim before working (creates 15-min lease)
lodestar task claim F001 --agent A1234ABCD

# 5. Do the work...
#    Renew if taking longer than 10 min:
lodestar task renew F001 --agent A1234ABCD

# 6. Complete the task
lodestar task done F001
lodestar task verify F001

# 7. Message downstream tasks if needed
# If there are remaining issues or important context:
lodestar task show F001  # See dependents
lodestar msg send --task F002 --from A1234ABCD \\
  --text "Note: API rate limit applies to /users endpoint" \\
  --severity warning

# Alternative: Release if you can't complete
lodestar task release F001 --agent A1234ABCD --reason "Blocked on API approval"
# Leave message for next agent:
lodestar msg send --task F001 --from A1234ABCD \\
  --text "60% complete. Tests passing. Blocked on API key approval." \\
  --severity handoff
```

---

## CLI Quick Reference

| Command | Purpose |
|---------|---------|
| `lodestar doctor` | Health check |
| `lodestar status` | Overview with next actions |
| `lodestar agent join` | Register as agent |
| `lodestar task next` | Find claimable tasks |
| `lodestar task list` | List all tasks |
| `lodestar task show <id>` | Task details |
| `lodestar task create` | Create task (planning) |
| `lodestar task claim <id>` | Claim with lease |
| `lodestar task done <id>` | Mark complete |
| `lodestar task verify <id>` | Verify (unblocks deps) |

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |
| `PRD.md` (if exists) | Product requirements | Commit |

## Help

```bash
lodestar <command> --help    # All options
lodestar <command> --explain # What it does
```
"""

# MCP-enabled AGENTS.md template
AGENTS_MD_MCP_TEMPLATE = """# {project_name} - Agent Coordination

This repository uses [Lodestar](https://github.com/lodestar-cli/lodestar) for multi-agent coordination.

## MCP Tools (Preferred for Task Execution)

When connected via MCP, use the `lodestar_*` tools directly for **executing** tasks.

### Quick Start

```
lodestar_agent_join(name="Your Name")     # Register, SAVE the agentId
lodestar_task_next()                       # Find available work
lodestar_task_claim(task_id="F001", agent_id="YOUR_ID")
```

### Agent Workflow

```
1. JOIN      lodestar_agent_join()                          -> Get your agentId
2. FIND      lodestar_task_next()                           -> Get claimable tasks
3. CHECK     lodestar_message_list(task_id, unread_by)      -> Check upstream messages
4. CLAIM     lodestar_task_claim()                          -> Create 15-min lease
5. CONTEXT   lodestar_task_context()                        -> Get PRD context
6. WORK      (implement the task)
7. DONE      lodestar_task_done()                           -> Mark complete
8. VERIFY    lodestar_task_verify()                         -> Unblock dependents
9. MESSAGE   lodestar_message_send(task_id=downstream)      -> Alert downstream tasks
```

---

## IMPORTANT: Task Creation Requires CLI

**Task creation is CLI-only.** MCP tools are for task execution, not task planning.

A planning agent (or human) must use CLI to create well-structured tasks.

### Why CLI-Only for Task Creation?

- Task design requires thoughtful INVEST-compliant decomposition
- PRD validation needs file system access
- Lock patterns need careful consideration
- This separation enforces a plan-then-execute workflow

---

## Task Design Principles (For Planning Agents)

**Every task must be completable within a 15-minute lease.**

### The INVEST Criteria

| Criterion | Meaning | Example |
|-----------|---------|---------|
| **I**ndependent | No waiting for others | "Add login form" not "Add login after auth" |
| **N**egotiable | Details refined during execution | Specify WHAT, not HOW |
| **V**aluable | Delivers user/developer value | Clear business reason |
| **E**stimable | Scope is clear | Bounded file changes |
| **S**mall | Fits in 15-minute lease | Split large work |
| **T**estable | Verifiable acceptance criteria | "Tests pass", "Returns 200" |

### Mandatory PRD References

If a PRD exists, **all tasks MUST reference it**:

```bash
lodestar task create \\
    --title "Implement feature X" \\
    --prd-source "PRD.md" \\
    --prd-ref "#feature-x-requirements"
```

### Task Description Format

Use this structured format:

```
WHAT:   [Concise statement of what to build/fix]
WHERE:  [File paths or modules to modify]
WHY:    [Business context - link to PRD section]
SCOPE:  [Explicit boundaries - what NOT to do]
ACCEPT: [Testable acceptance criteria - numbered]
REFS:   [Related tasks, docs, code patterns]
```

### Example: Well-Structured Task

```bash
lodestar task create \\
    --id "F042" \\
    --title "Add email validation to signup form" \\
    --description "WHAT: Add client-side email format validation.
WHERE: src/components/SignupForm.tsx, src/utils/validation.ts
WHY: Users submit invalid emails causing bounce issues (PRD #signup-requirements)
SCOPE: Client-side only. Do NOT add server validation (separate task F043).
ACCEPT: 1) Invalid emails show error 2) Valid emails pass 3) Tests cover edge cases
REFS: Follow pattern in validation.ts, see F041 for form structure" \\
    --prd-source "PRD.md" \\
    --prd-ref "#signup-requirements" \\
    --accept "Invalid emails show inline error" \\
    --accept "Valid emails pass validation" \\
    --accept "Unit tests cover: empty, missing @, missing domain" \\
    --lock "src/components/SignupForm.tsx" \\
    --lock "src/utils/validation.ts" \\
    --depends-on "F041" \\
    --label feature \\
    --priority 2
```

---

## Complete Task Options Reference (CLI)

| Option | Short | Description |
|--------|-------|-------------|
| `--id` | | Task ID (auto-generated if omitted) |
| `--title` | `-t` | Task title (required) |
| `--description` | `-d` | Full description (WHAT/WHERE/WHY/SCOPE/ACCEPT/REFS) |
| `--accept` | `-a` | Acceptance criterion (repeatable) |
| `--priority` | `-p` | Lower = higher priority (default: 100) |
| `--status` | `-s` | Initial status (default: ready) |
| `--depends-on` | | Task IDs this depends on (repeatable) |
| `--label` | `-l` | Labels for categorization (repeatable) |
| `--lock` | | File glob patterns for ownership (repeatable) |
| `--prd-source` | | Path to PRD file |
| `--prd-ref` | | PRD section anchors (repeatable) |
| `--prd-excerpt` | | Frozen PRD text to embed |
| `--validate-prd` | | Validate PRD exists (default) |
| `--no-validate-prd` | | Skip PRD validation |

---

## MCP Tool Reference

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
| **Message** | `lodestar_message_send` | Send to task thread |
| | `lodestar_message_list` | Get task messages |
| | `lodestar_message_ack` | Mark messages as read |
| **Events** | `lodestar_events_pull` | Pull event stream |

---

## Task Communication Patterns

### Check Upstream Messages

Before claiming a task, check for messages from dependencies:

```
# Get task details to see dependencies
task = lodestar_task_get(task_id="F002")
# Check each dependency for messages
for dep_id in task["dependsOn"]:
    messages = lodestar_message_list(task_id=dep_id, unread_by="YOUR_ID")
    # Read any warnings, context, or issues left by upstream
```

### Message Downstream Tasks

After completing a task, leave important context for dependent tasks:

```
# After verify, get list of dependents
task = lodestar_task_get(task_id="F001")

# Send warnings or context to downstream tasks
for dependent_id in task["dependents"]:
    lodestar_message_send(
        task_id=dependent_id,
        from_agent_id="YOUR_ID",
        body="API rate limit: 100 req/min applies to all /users endpoints",
        severity="warning"
    )
```

### Handoff Pattern (Blocked or Incomplete)

When blocked or ending session before completion:

```
lodestar_task_release(task_id="F001", agent_id="YOUR_ID", reason="Blocked on API approval")

# Leave message for next agent on THIS task
lodestar_message_send(
    task_id="F001",
    from_agent_id="YOUR_ID",
    body="Progress: 60% complete. Tests passing. Blocked on API key approval. Next: finish validation logic in src/auth/validate.py",
    severity="handoff"
)
```

---

## CLI Commands (No MCP Equivalent)

| Command | Purpose |
|---------|---------|
| `lodestar init` | Initialize repository |
| `lodestar doctor` | Health check |
| `lodestar task create` | Create new tasks (planning) |
| `lodestar task update` | Update task fields |
| `lodestar task delete` | Delete tasks (--cascade for deps) |
| `lodestar task renew` | Extend lease duration |
| `lodestar task graph` | Export dependency graph |
| `lodestar export snapshot` | Export full state |

---

## Files

| File | Purpose | Git |
|------|---------|-----|
| `.lodestar/spec.yaml` | Task definitions | Commit |
| `.lodestar/runtime.sqlite` | Agent/lease state | Gitignored |
| `PRD.md` (if exists) | Product requirements | Commit |

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
