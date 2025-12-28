"""Brief formatters for agent task briefings.

Provides multiple output formats for task briefs used when spawning sub-agents.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum


class BriefFormat(str, Enum):
    """Supported brief output formats."""

    CLAUDE = "claude"
    COPILOT = "copilot"
    GENERIC = "generic"


@dataclass
class TaskBrief:
    """Data for a task brief."""

    task_id: str
    title: str
    description: str
    acceptance_criteria: list[str]
    locks: list[str]
    labels: list[str]


class BriefFormatter(ABC):
    """Base class for brief formatters."""

    @abstractmethod
    def format(self, brief: TaskBrief) -> str:
        """Format the brief as a string."""
        pass


class ClaudeBriefFormatter(BriefFormatter):
    """Format brief in Claude XML style with system prompt structure."""

    def format(self, brief: TaskBrief) -> str:
        lines = []
        lines.append("<task>")
        lines.append(f"  <id>{brief.task_id}</id>")
        lines.append(f"  <title>{brief.title}</title>")
        lines.append("</task>")
        lines.append("")
        lines.append("<context>")
        lines.append(f"  {brief.description or brief.title}")
        if brief.labels:
            lines.append(f"  <labels>{', '.join(brief.labels)}</labels>")
        if brief.locks:
            lines.append("  <allowed_paths>")
            for lock in brief.locks:
                lines.append(f"    <path>{lock}</path>")
            lines.append("  </allowed_paths>")
        lines.append("</context>")
        lines.append("")
        if brief.acceptance_criteria:
            lines.append("<acceptance_criteria>")
            for criterion in brief.acceptance_criteria:
                lines.append(f"  <criterion>{criterion}</criterion>")
            lines.append("</acceptance_criteria>")
            lines.append("")
        lines.append("<instructions>")
        lines.append(f"  1. Claim task: lodestar task claim {brief.task_id} --agent YOUR_AGENT_ID")
        lines.append(
            f"  2. Report progress: lodestar msg send --to task:{brief.task_id} "
            "--from YOUR_AGENT_ID --text 'Update'"
        )
        lines.append(f"  3. Mark complete: lodestar task done {brief.task_id}")
        lines.append("</instructions>")
        return "\n".join(lines)


class CopilotBriefFormatter(BriefFormatter):
    """Format brief in GitHub Copilot style with markdown headers."""

    def format(self, brief: TaskBrief) -> str:
        lines = []
        lines.append(f"## Task: {brief.task_id}")
        lines.append("")
        lines.append(f"**{brief.title}**")
        lines.append("")
        lines.append("### Goal")
        lines.append("")
        lines.append(brief.description or brief.title)
        lines.append("")
        if brief.labels:
            lines.append(f"**Labels:** {', '.join(brief.labels)}")
            lines.append("")
        if brief.acceptance_criteria:
            lines.append("### Acceptance Criteria")
            lines.append("")
            for criterion in brief.acceptance_criteria:
                lines.append(f"- [ ] {criterion}")
            lines.append("")
        if brief.locks:
            lines.append("### Allowed Paths")
            lines.append("")
            lines.append("```")
            for lock in brief.locks:
                lines.append(lock)
            lines.append("```")
            lines.append("")
        lines.append("### Commands")
        lines.append("")
        lines.append("```bash")
        lines.append("# Claim this task")
        lines.append(f"lodestar task claim {brief.task_id} --agent YOUR_AGENT_ID")
        lines.append("")
        lines.append("# Report progress")
        lines.append(
            f"lodestar msg send --to task:{brief.task_id} "
            "--from YOUR_AGENT_ID --text 'Progress update'"
        )
        lines.append("")
        lines.append("# Mark complete")
        lines.append(f"lodestar task done {brief.task_id}")
        lines.append("```")
        return "\n".join(lines)


class GenericBriefFormatter(BriefFormatter):
    """Format brief in plain text with labeled sections."""

    def format(self, brief: TaskBrief) -> str:
        lines = []
        lines.append(f"TASK: {brief.task_id} - {brief.title}")
        lines.append("")
        lines.append("CONTEXT:")
        lines.append(f"  {brief.description or brief.title}")
        if brief.labels:
            lines.append(f"  Labels: {', '.join(brief.labels)}")
        lines.append("")
        if brief.acceptance_criteria:
            lines.append("CRITERIA:")
            for i, criterion in enumerate(brief.acceptance_criteria, 1):
                lines.append(f"  {i}. {criterion}")
            lines.append("")
        if brief.locks:
            lines.append("PATHS:")
            for lock in brief.locks:
                lines.append(f"  - {lock}")
            lines.append("")
        lines.append("COMMANDS:")
        lines.append(f"  Claim:    lodestar task claim {brief.task_id} --agent YOUR_AGENT_ID")
        lines.append(
            f"  Progress: lodestar msg send --to task:{brief.task_id} "
            "--from YOUR_AGENT_ID --text 'Update'"
        )
        lines.append(f"  Done:     lodestar task done {brief.task_id}")
        return "\n".join(lines)


# Formatter registry
_FORMATTERS: dict[BriefFormat, type[BriefFormatter]] = {
    BriefFormat.CLAUDE: ClaudeBriefFormatter,
    BriefFormat.COPILOT: CopilotBriefFormatter,
    BriefFormat.GENERIC: GenericBriefFormatter,
}


def get_formatter(format_type: str | BriefFormat) -> BriefFormatter:
    """Get a formatter instance by format type.

    Args:
        format_type: Format name or BriefFormat enum.

    Returns:
        Formatter instance.

    Raises:
        ValueError: If format type is not recognized.
    """
    if isinstance(format_type, str):
        try:
            format_type = BriefFormat(format_type.lower())
        except ValueError:
            valid = ", ".join(f.value for f in BriefFormat)
            raise ValueError(f"Unknown format '{format_type}'. Valid formats: {valid}") from None

    formatter_class = _FORMATTERS.get(format_type)
    if formatter_class is None:
        raise ValueError(f"No formatter registered for {format_type}")

    return formatter_class()


def format_task_brief(
    task_id: str,
    title: str,
    description: str,
    acceptance_criteria: list[str],
    locks: list[str],
    labels: list[str],
    format_type: str = "generic",
) -> str:
    """Format a task brief in the specified format.

    Convenience function that creates a TaskBrief and formats it.

    Args:
        task_id: Task identifier.
        title: Task title.
        description: Task description.
        acceptance_criteria: List of acceptance criteria.
        locks: List of lock patterns.
        labels: List of labels.
        format_type: Output format (claude, copilot, generic).

    Returns:
        Formatted brief string.
    """
    brief = TaskBrief(
        task_id=task_id,
        title=title,
        description=description,
        acceptance_criteria=acceptance_criteria,
        locks=locks,
        labels=labels,
    )
    formatter = get_formatter(format_type)
    return formatter.format(brief)
