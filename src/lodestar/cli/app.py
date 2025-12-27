"""Main Typer CLI application for Lodestar."""

from __future__ import annotations

import typer

from lodestar import __version__
from lodestar.cli.commands import agent, doctor, export, init, msg, status, task

# Main app
app = typer.Typer(
    name="lodestar",
    help="Agent-native repo orchestration for multi-agent coordination.",
    no_args_is_help=False,
    add_completion=False,
)

# Register subcommand groups
app.add_typer(agent.app, name="agent", help="Agent identity and management")
app.add_typer(task.app, name="task", help="Task management and scheduling")
app.add_typer(msg.app, name="msg", help="Agent messaging")
app.add_typer(export.app, name="export", help="Export repository state")

# Register top-level commands
app.command(name="init")(init.init_command)
app.command(name="status")(status.status_command)
app.command(name="doctor")(doctor.doctor_command)


def version_callback(value: bool) -> None:
    """Print version and exit."""
    if value:
        typer.echo(f"lodestar {__version__}")
        raise typer.Exit()


@app.callback(invoke_without_command=True)
def main(
    ctx: typer.Context,
    version: bool | None = typer.Option(
        None,
        "--version",
        "-v",
        help="Show version and exit.",
        callback=version_callback,
        is_eager=True,
    ),
    json_output: bool = typer.Option(
        False,
        "--json",
        help="Output in JSON format.",
    ),
) -> None:
    """Lodestar - Agent-native repo orchestration.

    Run 'lodestar' with no arguments for progressive discovery,
    or use a subcommand for specific operations.
    """
    # Store global options in context
    ctx.ensure_object(dict)
    ctx.obj["json"] = json_output

    # If no subcommand, show status (progressive discovery)
    if ctx.invoked_subcommand is None:
        # Import here to avoid circular imports
        from lodestar.cli.commands.status import status_command

        ctx.invoke(status_command, json_output=json_output)


if __name__ == "__main__":
    app()
