"""lodestar init command - Initialize a Lodestar repository."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import typer

from lodestar.cli.templates import render_agents_md_cli, render_agents_md_mcp
from lodestar.models.envelope import (
    NEXT_ACTION_AGENT_JOIN,
    NEXT_ACTION_STATUS,
    Envelope,
    NextAction,
)
from lodestar.spec.loader import create_default_spec, save_spec
from lodestar.util.output import console, print_json, print_rich
from lodestar.util.paths import LODESTAR_DIR, find_lodestar_root


def init_command(
    path: Path | None = typer.Argument(
        None,
        help="Path to initialize. Defaults to current directory.",
    ),
    project_name: str | None = typer.Option(
        None,
        "--name",
        "-n",
        help="Project name. Defaults to directory name.",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    force: bool = typer.Option(
        False,
        "--force",
        "-f",
        help="Overwrite existing .lodestar directory.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
    mcp: bool = typer.Option(
        False,
        "--mcp",
        help="Create MCP configuration files for IDE/agent integration.",
    ),
) -> None:
    """Initialize a new Lodestar repository.

    Creates the .lodestar directory with spec.yaml and runtime database.
    """
    if explain:
        _show_explain(json_output)
        return

    # Resolve path
    root = (path or Path.cwd()).resolve()

    # Check if already initialized
    existing = find_lodestar_root(root)
    if existing and not force:
        if json_output:
            print_json(
                Envelope.error(
                    f"Already initialized at {existing}. Use --force to reinitialize.",
                    next_actions=[NEXT_ACTION_STATUS],
                ).model_dump()
            )
        else:
            print_rich(
                f"[error]Already initialized at {existing}[/error]",
                style="error",
            )
            print_rich("Use --force to reinitialize.", style="muted")
        raise typer.Exit(1)

    # Determine project name
    name = project_name or root.name

    # Create .lodestar directory
    lodestar_dir = root / LODESTAR_DIR
    lodestar_dir.mkdir(exist_ok=True)

    # Create .gitignore for runtime files
    gitignore_path = lodestar_dir / ".gitignore"
    gitignore_path.write_text(
        "# Runtime files (ephemeral, not versioned)\n"
        "runtime.sqlite\n"
        "runtime.sqlite-wal\n"
        "runtime.sqlite-shm\n"
        "runtime.jsonl\n"
        "*.lock\n"
    )

    # Create default spec
    spec = create_default_spec(name)
    save_spec(spec, root)

    # Create MCP config files if requested
    mcp_files: list[str] = []
    if mcp:
        mcp_paths = _create_mcp_configs(root, force=force)
        mcp_files = [str(p) for p in mcp_paths]

    # Create AGENTS.md (use MCP version if --mcp)
    agents_md = root / "AGENTS.md"
    if not agents_md.exists() or force:
        content = render_agents_md_mcp(name) if mcp else render_agents_md_cli(name)
        agents_md.write_text(content)

    # Build response
    result = {
        "initialized": True,
        "path": str(root),
        "project_name": name,
        "mcp_enabled": mcp,
        "files_created": [
            str(lodestar_dir / "spec.yaml"),
            str(gitignore_path),
            str(agents_md),
            *mcp_files,
        ],
    }

    next_actions = [
        NEXT_ACTION_AGENT_JOIN,
        NextAction(
            intent="task.create",
            cmd="lodestar task create",
            description="Create your first task",
        ),
        NEXT_ACTION_STATUS,
    ]

    if json_output:
        print_json(Envelope.success(result, next_actions=next_actions).model_dump())
    else:
        console.print()
        console.print(f"[success]Initialized Lodestar in {root}[/success]")
        console.print()
        console.print("[muted]Created:[/muted]")
        console.print(f"  {LODESTAR_DIR}/spec.yaml")
        console.print(f"  {LODESTAR_DIR}/.gitignore")
        console.print("  AGENTS.md")
        if mcp:
            console.print("  .vscode/mcp.json")
            console.print("  .mcp.json")
        console.print()
        console.print("[info]Next steps:[/info]")
        console.print("  1. Run [command]lodestar agent join[/command] to register")
        console.print("  2. Run [command]lodestar task create[/command] to add tasks")
        console.print("  3. Run [command]lodestar status[/command] to see overview")
        console.print()


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation: dict[str, Any] = {
        "command": "lodestar init",
        "purpose": "Initialize a new Lodestar repository for multi-agent coordination.",
        "creates": [
            ".lodestar/spec.yaml - Task definitions and dependencies (versioned)",
            ".lodestar/.gitignore - Excludes runtime files from git",
            "AGENTS.md - Quick reference for agents entering the repo",
        ],
        "options": {
            "--mcp": "Create MCP configuration files (.vscode/mcp.json, .mcp.json)",
            "--force": "Overwrite existing .lodestar directory",
            "--name": "Set project name (defaults to directory name)",
        },
        "notes": [
            "Run this once per repository",
            "The spec.yaml should be committed to git",
            "Runtime files (SQLite) are auto-generated and gitignored",
            "Use --mcp to enable MCP integration for IDE/agent tools",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar init[/info]")
        console.print()
        console.print("Initialize a new Lodestar repository for multi-agent coordination.")
        console.print()
        console.print("[muted]Creates:[/muted]")
        for item in explanation["creates"]:
            console.print(f"  - {item}")
        console.print()
        console.print("[muted]Options:[/muted]")
        for opt, desc in explanation["options"].items():
            console.print(f"  {opt}: {desc}")
        console.print()


def _create_mcp_configs(root: Path, force: bool = False) -> list[Path]:
    """Create MCP configuration files. Returns list of created file paths."""
    created = []

    # VS Code / Copilot config
    vscode_dir = root / ".vscode"
    vscode_dir.mkdir(exist_ok=True)
    vscode_mcp = vscode_dir / "mcp.json"
    if not vscode_mcp.exists() or force:
        vscode_mcp.write_text(
            json.dumps(
                {
                    "servers": {
                        "Lodestar": {
                            "type": "stdio",
                            "command": "lodestar",
                            "args": ["mcp", "serve", "--repo", "."],
                        }
                    },
                    "inputs": [],
                },
                indent=2,
            )
            + "\n"
        )
        created.append(vscode_mcp)

    # Claude Code project-scoped config
    claude_mcp = root / ".mcp.json"
    if not claude_mcp.exists() or force:
        claude_mcp.write_text(
            json.dumps(
                {
                    "mcpServers": {
                        "Lodestar": {
                            "type": "stdio",
                            "command": "lodestar",
                            "args": ["mcp", "serve", "--repo", "."],
                        }
                    }
                },
                indent=2,
            )
            + "\n"
        )
        created.append(claude_mcp)

    return created
