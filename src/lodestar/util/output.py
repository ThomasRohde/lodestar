"""Output formatting utilities for JSON and Rich output."""

from __future__ import annotations

import json
import sys
from typing import Any

from rich.console import Console
from rich.theme import Theme

# Custom theme for Lodestar CLI
LODESTAR_THEME = Theme(
    {
        "info": "cyan",
        "warning": "yellow",
        "error": "red bold",
        "success": "green",
        "muted": "dim",
        "command": "bold cyan",
        "task_id": "bold magenta",
        "agent_id": "bold blue",
    }
)

# Console instances - use separate for stdout/stderr
console = Console(theme=LODESTAR_THEME)
error_console = Console(stderr=True, theme=LODESTAR_THEME)


def format_json(data: Any, pretty: bool = True) -> str:
    """Format data as JSON string."""
    if pretty:
        return json.dumps(data, indent=2, default=str)
    return json.dumps(data, default=str)


def print_json(data: Any, pretty: bool = True) -> None:
    """Print JSON to stdout with no ANSI codes."""
    # Use plain print to avoid any Rich formatting
    print(format_json(data, pretty))


def print_rich(
    *args: Any,
    style: str | None = None,
    stderr: bool = False,
    **kwargs: Any,
) -> None:
    """Print using Rich console with proper styling."""
    target = error_console if stderr else console
    target.print(*args, style=style, **kwargs)


def is_tty() -> bool:
    """Check if stdout is a TTY (for interactive prompts)."""
    return sys.stdout.isatty()
