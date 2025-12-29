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
