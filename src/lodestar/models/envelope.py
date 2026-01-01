"""JSON envelope model for consistent command output."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class NextAction(BaseModel):
    """A suggested next action for progressive discovery."""

    intent: str = Field(description="The intent/purpose of the action")
    cmd: str = Field(description="The full command to run")
    description: str | None = Field(default=None, description="Human-readable description")


class Envelope[T](BaseModel):
    """Standard JSON envelope for all command outputs.

    All --json output follows this structure for consistency.
    """

    ok: bool = Field(description="Whether the operation succeeded")
    data: T = Field(description="The operation result data")
    next: list[NextAction] = Field(
        default_factory=list,
        description="Suggested next actions for progressive discovery",
    )
    warnings: list[str] = Field(
        default_factory=list,
        description="Non-fatal warnings from the operation",
    )

    @classmethod
    def success(
        cls,
        data: T,
        next_actions: list[NextAction] | None = None,
        warnings: list[str] | None = None,
    ) -> Envelope[T]:
        """Create a successful response envelope."""
        return cls(
            ok=True,
            data=data,
            next=next_actions or [],
            warnings=warnings or [],
        )

    @classmethod
    def error(
        cls,
        message: str,
        data: dict[str, Any] | None = None,
        next_actions: list[NextAction] | None = None,
    ) -> Envelope[dict[str, Any]]:
        """Create an error response envelope."""
        return Envelope(
            ok=False,
            data={"error": message, **(data or {})},
            next=next_actions or [],
            warnings=[],
        )


# Common next actions for reuse
NEXT_ACTION_STATUS = NextAction(
    intent="status",
    cmd="lodestar status",
    description="View repository status",
)

NEXT_ACTION_TASK_NEXT = NextAction(
    intent="task.next",
    cmd="lodestar task next",
    description="Get next available task",
)

NEXT_ACTION_AGENT_JOIN = NextAction(
    intent="agent.join",
    cmd="lodestar agent join",
    description="Register as an agent",
)

NEXT_ACTION_TASK_LIST = NextAction(
    intent="task.list",
    cmd="lodestar task list",
    description="List all tasks",
)

NEXT_ACTION_HELP = NextAction(
    intent="help",
    cmd="lodestar --help",
    description="Show available commands",
)
