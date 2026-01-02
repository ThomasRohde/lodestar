"""lodestar mcp commands - MCP server management."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import typer

from lodestar.models.envelope import Envelope
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root

app = typer.Typer(
    help="MCP server management commands.",
    no_args_is_help=False,
)


def _setup_logging(
    log_file: Path | None = None,
    json_logs: bool = False,
) -> logging.Logger:
    """
    Setup logging to stderr and optionally to a file.

    Args:
        log_file: Optional file path for logging
        json_logs: Whether to use JSON format for logs
    """
    # Create logger
    logger = logging.getLogger("lodestar.mcp")
    logger.setLevel(logging.INFO)

    # Create formatter
    if json_logs:
        # Simple JSON-like format
        formatter = logging.Formatter(
            '{"time": "%(asctime)s", "level": "%(levelname)s", "message": "%(message)s"}'
        )
    else:
        formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    # Always log to stderr
    stderr_handler = logging.StreamHandler(sys.stderr)
    stderr_handler.setFormatter(formatter)
    logger.addHandler(stderr_handler)

    # Optionally log to file
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


@app.command(name="serve")
def serve_command(
    repo: Path | None = typer.Option(
        None,
        "--repo",
        help="Path to Lodestar repository (default: auto-discover)",
    ),
    transport: str = typer.Option(
        "stdio",
        "--transport",
        "-t",
        help="Transport type: 'stdio' or 'streamable-http'",
    ),
    host: str = typer.Option(
        "127.0.0.1",
        "--host",
        help="HTTP bind address (streamable-http only)",
    ),
    port: int = typer.Option(
        8000,
        "--port",
        help="HTTP port (streamable-http only)",
    ),
    log_file: Path | None = typer.Option(
        None,
        "--log-file",
        help="Optional log file path",
    ),
    json_logs: bool = typer.Option(
        False,
        "--json-logs",
        help="Use JSON format for logs",
    ),
    dev: bool = typer.Option(
        False,
        "--dev",
        help="Development mode",
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
    explain: bool = typer.Option(
        False,
        "--explain",
        help="Show what this command does.",
    ),
) -> None:
    """Start the Lodestar MCP server.

    The MCP server exposes Lodestar functionality to MCP clients
    like Claude Desktop. By default, it uses stdio transport for
    communication and logs to stderr.
    """
    if explain:
        _show_explain(json_output)
        return

    # Check if MCP dependencies are installed
    try:
        from mcp.server.fastmcp import FastMCP  # noqa: F401
    except ImportError:
        error_msg = (
            "MCP dependencies not installed. "
            "Install with: pip install 'lodestar-cli[mcp]' or uv add 'lodestar-cli[mcp]'"
        )
        if json_output:
            print_json(Envelope.error(error_msg).model_dump())
        else:
            console.print(f"[error]{error_msg}[/error]")
        raise typer.Exit(1)

    # Setup logging
    logger = _setup_logging(log_file, json_logs)

    # Determine repository root
    if repo is None:
        repo_root = find_lodestar_root()
        if repo_root is None:
            error_msg = "Not in a Lodestar repository. Use --repo to specify path."
            if json_output:
                print_json(Envelope.error(error_msg).model_dump())
            else:
                console.print(f"[error]{error_msg}[/error]")
            raise typer.Exit(1)
    else:
        repo_root = repo.resolve()
        if not (repo_root / ".lodestar" / "spec.yaml").exists():
            error_msg = f"Not a valid Lodestar repository: {repo_root}"
            if json_output:
                print_json(Envelope.error(error_msg).model_dump())
            else:
                console.print(f"[error]{error_msg}[/error]")
            raise typer.Exit(1)

    # Validate transport option
    valid_transports = ("stdio", "streamable-http")
    if transport not in valid_transports:
        error_msg = (
            f"Invalid transport '{transport}'. Must be one of: {', '.join(valid_transports)}"
        )
        if json_output:
            print_json(Envelope.error(error_msg).model_dump())
        else:
            console.print(f"[error]{error_msg}[/error]")
        raise typer.Exit(1)

    logger.info(f"Starting Lodestar MCP server for repository: {repo_root}")
    if dev:
        logger.info("Development mode enabled")

    # Create and run the MCP server
    from lodestar.mcp.server import create_server

    mcp_server = create_server(repo_root)

    # Run the server with selected transport
    try:
        if transport == "streamable-http":
            logger.info(f"MCP server starting on http://{host}:{port}/mcp")
            mcp_server.settings.host = host
            mcp_server.settings.port = port
            mcp_server.run(transport="sse")
        else:
            logger.info("MCP server starting on stdio transport")
            mcp_server.run(transport="stdio")
    except KeyboardInterrupt:
        logger.info("MCP server stopped by user")
    except Exception as e:
        logger.error(f"MCP server error: {e}")
        raise typer.Exit(1)


def _show_explain(json_output: bool) -> None:
    """Show command explanation."""
    explanation = {
        "command": "lodestar mcp serve",
        "purpose": "Start the Lodestar MCP server for client integration.",
        "options": [
            "--repo PATH: Specify repository path (default: auto-discover)",
            "--transport, -t: Transport type: 'stdio' (default) or 'streamable-http'",
            "--host: HTTP bind address, default 127.0.0.1 (streamable-http only)",
            "--port: HTTP port, default 8000 (streamable-http only)",
            "--log-file PATH: Write logs to file in addition to stderr",
            "--json-logs: Use JSON format for logs",
            "--dev: Enable development mode",
        ],
        "examples": [
            "lodestar mcp serve  # stdio transport (default)",
            "lodestar mcp serve -t streamable-http  # HTTP on localhost:8000",
            "lodestar mcp serve -t streamable-http --port 9000  # HTTP on port 9000",
        ],
        "notes": [
            "Server logs go to stderr by default",
            "Protocol messages are written to stdout (stdio) or HTTP responses",
            "Use --log-file to also log to a file",
            "Requires 'lodestar-cli[mcp]' to be installed",
            "HTTP transport binds to localhost only for security",
        ],
    }

    if json_output:
        print_json(explanation)
    else:
        console.print()
        console.print("[info]lodestar mcp serve[/info]")
        console.print()
        console.print("Start the Lodestar MCP server for client integration.")
        console.print()
        console.print("[bold]Options:[/bold]")
        for opt in explanation["options"]:
            console.print(f"  {opt}")
        console.print()
        console.print("[bold]Examples:[/bold]")
        for ex in explanation["examples"]:
            console.print(f"  {ex}")
        console.print()
        console.print("[bold]Notes:[/bold]")
        for note in explanation["notes"]:
            console.print(f"  • {note}")
        console.print()


@app.callback(invoke_without_command=True)
def mcp_callback(ctx: typer.Context) -> None:
    """MCP server management.

    Use these commands to run the Lodestar MCP server
    for integration with MCP clients like Claude Desktop.
    """
    if ctx.invoked_subcommand is None:
        console.print()
        console.print("[bold]MCP Commands[/bold]")
        console.print()
        console.print("  [command]lodestar mcp serve[/command]")
        console.print("      Start the MCP server (stdio by default)")
        console.print()
        console.print("  [command]lodestar mcp serve -t streamable-http[/command]")
        console.print("      Start HTTP server on localhost:8000")
        console.print()
        console.print("Run [command]lodestar mcp serve --help[/command] for more options.")
        console.print()
        console.print()
