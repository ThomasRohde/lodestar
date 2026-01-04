"""MCP prompt templates for Lodestar workflows."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from mcp.server.fastmcp import FastMCP

from lodestar.mcp.server import LodestarContext


def register_prompts(mcp: FastMCP, context: LodestarContext) -> None:
    """
    Register MCP prompts with the server.

    Args:
        mcp: FastMCP server instance.
        context: Lodestar server context with DB and spec access.
    """

    @mcp.prompt(
        name="lodestar_agent_workflow",
        title="Lodestar Agent Workflow",
        description="Step-by-step guide for working with Lodestar tasks from join to verify",
    )
    def agent_workflow() -> list[dict[str, str]]:
        """
        Provides a concise workflow recipe for AI agents working with Lodestar.

        This prompt guides agents through the standard task lifecycle:
        join -> next -> claim -> context -> done -> verify -> message handoff

        Returns:
            List of message dicts with role and content.
        """
        workflow_content = """# Lodestar Agent Workflow

Follow this workflow when working with Lodestar tasks:

## 1. Join as an Agent

Register yourself in the repository:

```bash
lodestar_agent_join(role="ai-agent", capabilities=["python", "testing"])
# Save the returned agent_id for subsequent commands
```

## 2. Find Available Work

Get the next claimable task:

```bash
lodestar_task_next()
# Returns tasks that are ready and have all dependencies verified
```

Or list all tasks to find specific work:

```bash
lodestar_task_list(status="ready")
```

## 3. Check Upstream Messages

**IMPORTANT**: Before claiming, check for messages from upstream (dependency) tasks:

```bash
# Get task details to see dependencies
task = lodestar_task_get(task_id="T001")

# Check each dependency for messages with context or warnings
for dep_id in task["dependsOn"]:
    messages = lodestar_message_list(task_id=dep_id, unread_by="YOUR_AGENT_ID")
    # Review messages for important context, warnings, or issues
```

Upstream messages may contain:
- Important context about implementation decisions
- Warnings about edge cases or limitations
- API changes or constraints
- Known issues or workarounds

## 4. Claim the Task

Before starting work, claim the task to prevent duplicate effort:

```bash
lodestar_task_claim(task_id="T001", agent_id="YOUR_AGENT_ID")
# You now have a 15-minute lease (renewable)
```

## 5. Get Task Context

Retrieve full task details including PRD context:

```bash
lodestar_task_get(task_id="T001")
# Or for even more context:
lodestar_task_context(task_id="T001")
```

This provides:
- Task description and acceptance criteria
- PRD context (frozen excerpts from requirements)
- Dependencies and dependent tasks
- Any drift warnings if PRD has changed

## 6. Do the Work

Implement the task following the acceptance criteria. Make sure to:
- Run tests frequently
- Commit your changes incrementally
- Renew your lease if needed: `lodestar_task_renew(task_id="T001")`

## 7. Mark as Done

When implementation is complete and tests pass:

```bash
lodestar_task_done(task_id="T001", agent_id="YOUR_AGENT_ID")
```

## 8. Verify the Task

After reviewing that all acceptance criteria are met:

```bash
lodestar_task_verify(task_id="T001", agent_id="YOUR_AGENT_ID")
```

Verification unblocks any dependent tasks.

## 9. Message Downstream Tasks

**IMPORTANT**: After verifying, check for dependent tasks and message them if needed:

```bash
# Get task details to see dependents
task = lodestar_task_get(task_id="T001")

# If there are important warnings, context, or remaining issues:
for dependent_id in task["dependents"]:
    lodestar_message_send(
        task_id=dependent_id,
        from_agent_id="YOUR_AGENT_ID",
        body="Important: API rate limit of 100 req/min applies to all /users endpoints. Use caching for list operations.",
        severity="warning"
    )
```

Message downstream tasks when:
- There are important constraints or limitations they should know
- You made implementation decisions that affect downstream work
- There are edge cases or gotchas to be aware of
- You identified issues that couldn't be fixed in this task's scope
- There's useful context that will help them complete their work

## 10. Handoff (if blocked or incomplete)

If you're blocked or ending your session before completion:

```bash
# Release the task
lodestar_task_release(task_id="T001", agent_id="YOUR_AGENT_ID")

# Leave context for the next agent on THIS task
lodestar_message_send(
    task_id="T001",
    from_agent_id="YOUR_AGENT_ID",
    body="Progress: 60% complete. Token generation works in src/auth/token.py. Blocked on email template approval from design team. Next: implement template rendering in src/email/render.py",
    severity="handoff"
)
```

## Best Practices

- **Check upstream first**: Always check messages from dependency tasks before claiming
- **One task at a time**: Focus on completion before claiming another
- **Claim before working**: Don't work on unclaimed tasks
- **Renew proactively**: Don't let your lease expire
- **Verify thoroughly**: Ensure all acceptance criteria are met
- **Message downstream**: Alert dependent tasks of important context, warnings, or issues
- **Leave handoff context**: Help the next agent if you need to release
- **Check drift warnings**: Review PRD if context has changed

## Quick Command Reference

```
lodestar_agent_join()          # Register as agent
lodestar_task_next()           # Find claimable tasks
lodestar_message_list()        # Check upstream messages
lodestar_task_claim()          # Claim a task
lodestar_task_context()        # Get full context
lodestar_task_renew()          # Extend lease
lodestar_task_done()           # Mark complete
lodestar_task_verify()         # Mark verified
lodestar_message_send()        # Message downstream or handoff
lodestar_message_ack()         # Mark messages as read
lodestar_task_release()        # Release if blocked
```
"""

        return [
            {
                "role": "user",
                "content": workflow_content,
            }
        ]

    @mcp.prompt(
        name="lodestar_task_execute",
        title="Lodestar Task Execution Guide",
        description="Guide for executing a task following acceptance criteria and producing verification checklist",
    )
    def task_execute() -> list[dict[str, str]]:
        """
        Provides execution guidance for implementing and verifying Lodestar tasks.

        This prompt helps agents:
        - Follow acceptance criteria systematically
        - Create comprehensive verification checklists
        - Ensure quality and completeness before marking tasks done

        Returns:
            List of message dicts with role and content.
        """
        execute_content = """# Lodestar Task Execution Guide

When executing a claimed task, follow this systematic approach:

## 1. Review Task Context

Before writing any code, thoroughly review:

```bash
lodestar_task_context(task_id="YOUR_TASK_ID")
```

This provides:
- **Description**: What needs to be done
- **Acceptance Criteria**: Specific requirements that must be met
- **PRD Context**: Relevant product requirements
- **Dependencies**: What this task builds upon
- **Dependents**: What's blocked waiting for this

## 2. Create Your Verification Checklist

Based on the acceptance criteria, create a checklist BEFORE starting implementation:

**Example:**
```markdown
## Verification Checklist for [TASK_ID]

### Acceptance Criteria
- [ ] Criterion 1: [Specific requirement from task]
- [ ] Criterion 2: [Another requirement]
- [ ] Criterion 3: [etc.]

### Code Quality
- [ ] Code follows project style guide
- [ ] All linting checks pass (ruff check)
- [ ] Code is formatted correctly (ruff format)
- [ ] No type errors or warnings

### Testing
- [ ] Unit tests written for new functionality
- [ ] All tests pass (pytest)
- [ ] Edge cases covered
- [ ] Integration tests if needed

### Documentation
- [ ] Docstrings added for new functions/classes
- [ ] CLI documentation updated if commands changed
- [ ] README or guides updated if needed

### Git Hygiene
- [ ] Changes committed with descriptive message
- [ ] No debug code or commented-out code left behind
- [ ] No unintended files in commit
```

## 3. Implement Incrementally

Follow test-driven development:

1. **Read the existing code** to understand patterns and architecture
2. **Write tests first** for new functionality
3. **Implement in small steps**, running tests after each change
4. **Commit frequently** with clear messages
5. **Renew your lease** if needed: `lodestar_task_renew(task_id="T001")`

## 4. Verify Against Checklist

Before marking the task as done, go through your checklist:

```bash
# Run all quality checks
ruff check src tests
ruff format --check src tests
pytest
```

Document results in your verification checklist.

## 5. Pre-Completion Review

Ask yourself:
- ✅ Are ALL acceptance criteria met?
- ✅ Do all tests pass?
- ✅ Is the code production-ready?
- ✅ Would this pass code review?
- ✅ Is documentation up-to-date?

**If any answer is "no", do NOT mark as done yet.**

## 6. Mark as Done

Only when all checks pass:

```bash
lodestar_task_done(task_id="YOUR_TASK_ID", agent_id="YOUR_AGENT_ID")
```

## 7. Verify Thoroughly

The verification step is crucial - it unblocks dependent tasks:

```bash
lodestar_task_verify(task_id="YOUR_TASK_ID", agent_id="YOUR_AGENT_ID")
```

**Before verifying:**
- Run end-to-end tests
- Test as a user would
- Check all acceptance criteria one final time
- Review your verification checklist

## Common Pitfalls to Avoid

❌ **Don't**: Mark tasks done with failing tests
❌ **Don't**: Skip acceptance criteria review
❌ **Don't**: Verify without thorough testing
❌ **Don't**: Leave TODOs or commented code
❌ **Don't**: Forget to update documentation

✅ **Do**: Follow acceptance criteria exactly
✅ **Do**: Test incrementally and thoroughly
✅ **Do**: Commit early and often
✅ **Do**: Update docs when changing CLI commands
✅ **Do**: Use the verification checklist

## Quality Standards

Every task completion should meet these standards:

1. **Correctness**: Implements all acceptance criteria exactly
2. **Completeness**: No partial implementations or TODOs
3. **Quality**: Passes all linting and formatting checks
4. **Tested**: All tests pass, edge cases covered
5. **Documented**: Code and user-facing docs updated
6. **Clean**: No debug code, proper git hygiene

## Example Workflow

```bash
# 1. Get context
task_context = lodestar_task_context(task_id="T042")

# 2. Create verification checklist (in your editor/notes)

# 3. Implement incrementally
# - Write tests
# - Implement feature
# - Run tests
# - Commit changes

# 4. Run quality checks
ruff check src tests
ruff format --check src tests
pytest

# 5. Mark as done
lodestar_task_done(task_id="T042", agent_id="A123")

# 6. Verify thoroughly
lodestar_task_verify(task_id="T042", agent_id="A123")
```

Remember: **Quality over speed**. A properly completed task is better than rushing to "done" with incomplete work.
"""

        return [
            {
                "role": "user",
                "content": execute_content,
            }
        ]

    @mcp.prompt(
        name="lodestar_task_communication",
        title="Lodestar Task Communication Patterns",
        description="Guide for using task-focused messaging to coordinate with upstream and downstream tasks",
    )
    def task_communication() -> list[dict[str, str]]:
        """
        Provides guidance on using task-focused messaging for coordination.

        This prompt helps agents:
        - Check messages from upstream (dependency) tasks for context
        - Leave messages for downstream (dependent) tasks about issues/constraints
        - Use proper handoff messaging when blocked or incomplete

        Returns:
            List of message dicts with role and content.
        """
        communication_content = """# Lodestar Task Communication Patterns

Lodestar uses **task-focused messaging** to coordinate work across dependency chains. Messages are attached to tasks, not sent between agents directly.

## Why Task-Focused Messaging?

- **Persistent context**: Messages stay with the task across agent handoffs
- **Dependency awareness**: Messages flow naturally through task dependencies
- **No agent routing**: No need to know which agent will work on a task
- **Threaded history**: All communication about a task in one place

## Three Communication Patterns

### 1. Check Upstream Messages (Before Starting)

**When**: Before claiming a task, always check messages from dependencies.

**Why**: Upstream tasks may have left important context, warnings, or constraints.

```python
# Get task details to see dependencies
task = lodestar_task_get(task_id="F002")

# Check each dependency for unread messages
for dep_id in task.get("dependsOn", []):
    messages = lodestar_message_list(
        task_id=dep_id,
        unread_by="YOUR_AGENT_ID"
    )

    # Review each message
    for msg in messages["messages"]:
        print(f"From task {dep_id}:")
        print(f"  [{msg['meta'].get('severity', 'info')}] {msg['text']}")

    # Mark as read after reviewing
    if messages["count"] > 0:
        lodestar_message_ack(
            task_id=dep_id,
            agent_id="YOUR_AGENT_ID"
        )
```

**What to look for in upstream messages:**
- ⚠️ **Warnings**: Constraints, limitations, gotchas
- 📋 **Context**: Implementation decisions that affect downstream work
- 🐛 **Known issues**: Problems that couldn't be fixed in scope
- 🔧 **API changes**: Interface modifications to be aware of
- 📝 **Documentation**: Where to find relevant code/patterns

### 2. Message Downstream Tasks (After Completing)

**When**: After verifying a task, if there's important context for dependent tasks.

**Why**: Help downstream agents avoid issues and understand constraints.

```python
# After verifying, get task details to see dependents
task = lodestar_task_get(task_id="F001")

# Send messages to downstream tasks if needed
for dependent_id in task.get("dependents", []):
    lodestar_message_send(
        task_id=dependent_id,
        from_agent_id="YOUR_AGENT_ID",
        body="Important: The /users endpoint now has rate limiting (100 req/min). Use the caching layer in src/cache/user_cache.py for list operations to avoid hitting limits.",
        severity="warning"
    )
```

**When to message downstream:**
- ⚠️ Made a constraint that affects downstream work
- 📋 Made an implementation choice they should follow
- 🐛 Discovered edge cases they should handle
- 🔧 Changed an interface or API contract
- ❌ Identified work that's out of scope but needed

**Severity levels:**
- `info`: General context or helpful information
- `warning`: Important constraints or limitations to be aware of
- `handoff`: Progress update for next agent on same task
- `blocker`: Critical issue that prevents downstream work

### 3. Handoff Messages (When Blocked or Incomplete)

**When**: You need to release a task before completion.

**Why**: Help the next agent pick up where you left off.

```python
# Release the claim
lodestar_task_release(
    task_id="F001",
    agent_id="YOUR_AGENT_ID",
    reason="Blocked on API key approval from DevOps"
)

# Leave handoff message on the SAME task
lodestar_message_send(
    task_id="F001",  # Same task you're releasing
    from_agent_id="YOUR_AGENT_ID",
    body=\"\"\"Progress: 60% complete.

DONE:
- Token generation working (src/auth/token.py)
- Unit tests passing (tests/auth/test_token.py)
- Database schema updated with new token_meta column

BLOCKED:
- Waiting for SendGrid API key from DevOps (ticket #1234)

NEXT STEPS:
1. Get API key and add to .env
2. Implement email sending in src/email/send.py
3. Add integration test in tests/email/test_send.py
4. Update docs/email-setup.md with configuration steps\"\"\",
    severity="handoff",
    subject="60% complete - blocked on API key"
)
```

## Complete Example Workflow

```python
# 1. Find work
tasks = lodestar_task_next()
task_id = tasks["candidates"][0]["taskId"]

# 2. Check upstream messages BEFORE claiming
task = lodestar_task_get(task_id=task_id)
for dep_id in task.get("dependsOn", []):
    messages = lodestar_message_list(task_id=dep_id, unread_by="MY_AGENT_ID")
    # Review messages...
    if messages["count"] > 0:
        lodestar_message_ack(task_id=dep_id, agent_id="MY_AGENT_ID")

# 3. Claim and work
lodestar_task_claim(task_id=task_id, agent_id="MY_AGENT_ID")
# ... implement task ...

# 4. Complete
lodestar_task_done(task_id=task_id, agent_id="MY_AGENT_ID")
lodestar_task_verify(task_id=task_id, agent_id="MY_AGENT_ID")

# 5. Message downstream if needed
task = lodestar_task_get(task_id=task_id)
if task.get("dependents"):
    for dep_id in task["dependents"]:
        lodestar_message_send(
            task_id=dep_id,
            from_agent_id="MY_AGENT_ID",
            body="Note: Validation now requires both email AND phone. See src/validators.py",
            severity="warning"
        )
```

## Best Practices

✅ **DO:**
- Check upstream messages before claiming
- Mark messages as read after reviewing
- Leave specific, actionable messages for downstream
- Include file paths and code references in messages
- Use appropriate severity levels
- Be concise but complete in handoffs

❌ **DON'T:**
- Claim without checking upstream messages
- Leave vague messages like "some issues exist"
- Message about things already in acceptance criteria
- Forget to mark messages as read
- Over-communicate - only message when it adds value

## Message Severity Guide

| Severity | Use When | Example |
|----------|----------|---------|
| `info` | Helpful context, not critical | "I used lodash for array operations, pattern in utils.js" |
| `warning` | Important constraint or gotcha | "Rate limit: 100 req/min, use caching" |
| `handoff` | Incomplete work, progress update | "60% done, blocked on API key" |
| `blocker` | Critical issue preventing downstream | "Auth endpoint failing in prod, rollback needed" |

## Quick Reference

```python
# Check upstream (before claim)
lodestar_message_list(task_id=upstream_id, unread_by=my_id)

# Mark as read
lodestar_message_ack(task_id=task_id, agent_id=my_id)

# Message downstream (after verify)
lodestar_message_send(
    task_id=downstream_id,
    from_agent_id=my_id,
    body="...",
    severity="warning"  # or info, handoff, blocker
)

# Handoff (before release)
lodestar_message_send(
    task_id=same_task_id,
    from_agent_id=my_id,
    body="Progress: ...",
    severity="handoff"
)
```
"""

        return [
            {
                "role": "user",
                "content": communication_content,
            }
        ]
