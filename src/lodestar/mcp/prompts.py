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
lodestar.agent.join(role="ai-agent", capabilities=["python", "testing"])
# Save the returned agent_id for subsequent commands
```

## 2. Find Available Work

Get the next claimable task:

```bash
lodestar.task.next()
# Returns tasks that are ready and have all dependencies verified
```

Or list all tasks to find specific work:

```bash
lodestar.task.list(status="ready")
```

## 3. Claim the Task

Before starting work, claim the task to prevent duplicate effort:

```bash
lodestar.task.claim(task_id="T001", agent_id="YOUR_AGENT_ID")
# You now have a 15-minute lease (renewable)
```

## 4. Get Task Context

Retrieve full task details including PRD context:

```bash
lodestar.task.get(task_id="T001")
# Or for even more context:
lodestar.task.context(task_id="T001")
```

This provides:
- Task description and acceptance criteria
- PRD context (frozen excerpts from requirements)
- Dependencies and dependent tasks
- Any drift warnings if PRD has changed

## 5. Do the Work

Implement the task following the acceptance criteria. Make sure to:
- Run tests frequently
- Commit your changes incrementally
- Renew your lease if needed: `lodestar.task.renew(task_id="T001")`

## 6. Mark as Done

When implementation is complete and tests pass:

```bash
lodestar.task.done(task_id="T001", agent_id="YOUR_AGENT_ID")
```

## 7. Verify the Task

After reviewing that all acceptance criteria are met:

```bash
lodestar.task.verify(task_id="T001", agent_id="YOUR_AGENT_ID")
```

Verification unblocks any dependent tasks.

## 8. Handoff (if needed)

If you're blocked or ending your session before completion:

```bash
# Release the task
lodestar.task.release(task_id="T001", agent_id="YOUR_AGENT_ID")

# Leave context for the next agent
lodestar.message.send(
    to_agent_id="task:T001",
    from_agent_id="YOUR_AGENT_ID",
    content="Progress: 60% complete. Token generation works. Blocked on email template approval."
)
```

## Best Practices

- **One task at a time**: Focus on completion before claiming another
- **Claim before working**: Don't work on unclaimed tasks
- **Renew proactively**: Don't let your lease expire
- **Verify thoroughly**: Ensure all acceptance criteria are met
- **Leave context**: Help the next agent with handoff messages
- **Check drift warnings**: Review PRD if context has changed

## Quick Command Reference

```
lodestar.agent.join()          # Register as agent
lodestar.task.next()           # Find claimable tasks
lodestar.task.claim()          # Claim a task
lodestar.task.context()        # Get full context
lodestar.task.renew()          # Extend lease
lodestar.task.done()           # Mark complete
lodestar.task.verify()         # Mark verified
lodestar.task.release()        # Release if blocked
lodestar.message.send()        # Leave handoff context
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
lodestar.task.context(task_id="YOUR_TASK_ID")
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
5. **Renew your lease** if needed: `lodestar.task.renew(task_id="T001")`

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
lodestar.task.done(task_id="YOUR_TASK_ID", agent_id="YOUR_AGENT_ID")
```

## 7. Verify Thoroughly

The verification step is crucial - it unblocks dependent tasks:

```bash
lodestar.task.verify(task_id="YOUR_TASK_ID", agent_id="YOUR_AGENT_ID")
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
task_context = lodestar.task.context(task_id="T042")

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
lodestar.task.done(task_id="T042", agent_id="A123")

# 6. Verify thoroughly
lodestar.task.verify(task_id="T042", agent_id="A123")
```

Remember: **Quality over speed**. A properly completed task is better than rushing to "done" with incomplete work.
"""

        return [
            {
                "role": "user",
                "content": execute_content,
            }
        ]
