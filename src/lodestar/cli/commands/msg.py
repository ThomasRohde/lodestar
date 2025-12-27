"""lodestar msg commands - Agent messaging."""

from __future__ import annotations

from datetime import datetime

import typer

from lodestar.models.envelope import Envelope
from lodestar.models.runtime import Message, MessageType
from lodestar.runtime.database import RuntimeDatabase
from lodestar.util.output import console, print_json
from lodestar.util.paths import find_lodestar_root, get_runtime_db_path

app = typer.Typer(
    help="Agent messaging commands.",
    no_args_is_help=False,
)


@app.callback(invoke_without_command=True)
def msg_callback(ctx: typer.Context) -> None:
    """Agent messaging.

    Use these commands to communicate with other agents and leave context on tasks.
    """
    if ctx.invoked_subcommand is None:
        # Show helpful workflow instead of error
        console.print()
        console.print("[bold]Message Commands[/bold]")
        console.print()
        console.print("[info]Sending messages:[/info]")
        console.print("  [command]lodestar msg send --to task:<id> --from <agent-id> --text '...'[/command]")
        console.print("      Leave context on a task thread (for handoffs)")
        console.print()
        console.print("  [command]lodestar msg send --to agent:<id> --from <agent-id> --text '...'[/command]")
        console.print("      Send a direct message to another agent")
        console.print()
        console.print("[info]Reading messages:[/info]")
        console.print("  [command]lodestar msg thread <task-id>[/command]")
        console.print("      Read the message thread for a task")
        console.print()
        console.print("  [command]lodestar msg inbox --agent <agent-id>[/command]")
        console.print("      Read messages sent to you")
        console.print()
        console.print("[info]Examples:[/info]")
        console.print("  lodestar msg send --to task:F001 --from A123 --text 'Blocked on X'")
        console.print("  lodestar msg thread F001")
        console.print()


@app.command(name="send")
def msg_send(
    to: str = typer.Option(
        ...,
        "--to",
        "-t",
        help="Recipient: 'task:<task-id>' for task threads or 'agent:<agent-id>' for direct messages.",
    ),
    text: str = typer.Option(
        ...,
        "--text",
        "-m",
        help="Message text.",
    ),
    from_agent: str = typer.Option(
        ...,
        "--from",
        "-f",
        help="Your agent ID (REQUIRED). Get it from 'lodestar agent join'.",
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
    """Send a message to an agent or task thread.

    Use task threads to leave context for other agents working on a task.
    Use agent messages for direct communication.

    Examples:
        lodestar msg send --to task:F001 --from A123 --text 'Blocked on X'
        lodestar msg send --to agent:B456 --from A123 --text 'Need help'
    """
    if explain:
        _show_explain_send(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Parse recipient
    if ":" not in to:
        if json_output:
            print_json(
                Envelope.error("Invalid recipient format. Use 'agent:ID' or 'task:ID'").model_dump()
            )
        else:
            console.print("[error]Invalid recipient format[/error]")
            console.print("Use 'agent:A123' or 'task:T001'")
        raise typer.Exit(1)

    to_type_str, to_id = to.split(":", 1)
    try:
        to_type = MessageType(to_type_str.lower())
    except ValueError:
        if json_output:
            print_json(Envelope.error(f"Invalid recipient type: {to_type_str}").model_dump())
        else:
            console.print(f"[error]Invalid recipient type: {to_type_str}[/error]")
            console.print("Use 'agent' or 'task'")
        raise typer.Exit(1)

    # Create and send message
    db = RuntimeDatabase(get_runtime_db_path(root))

    message = Message(
        from_agent_id=from_agent,
        to_type=to_type,
        to_id=to_id,
        text=text,
    )

    db.send_message(message)

    result = {
        "message_id": message.message_id,
        "sent_at": message.created_at.isoformat(),
        "to": to,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print(f"[success]Message sent[/success] to {to}")
        console.print(f"  ID: {message.message_id}")


@app.command(name="inbox")
def msg_inbox(
    agent_id: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Your agent ID.",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Cursor (ISO timestamp) to fetch messages after.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum messages to return.",
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
    """Read messages from your inbox."""
    if explain:
        _show_explain_inbox(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        messages = []
    else:
        db = RuntimeDatabase(runtime_path)

        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid timestamp: {since}[/error]")
                raise typer.Exit(1)

        messages = db.get_inbox(agent_id, since=since_dt, limit=limit)

    result = {
        "messages": [
            {
                "message_id": m.message_id,
                "from": m.from_agent_id,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "count": len(messages),
        "cursor": messages[-1].created_at.isoformat() if messages else None,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        if not messages:
            console.print("[muted]No messages in inbox.[/muted]")
        else:
            console.print(f"[bold]Inbox ({len(messages)} messages)[/bold]")
            console.print()
            for msg in messages:
                console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                console.print(f"  From: [agent_id]{msg.from_agent_id}[/agent_id]")
                console.print(f"  {msg.text}")
                console.print()
        console.print()


@app.command(name="thread")
def msg_thread(
    task_id: str = typer.Argument(..., help="Task ID to view thread for."),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Cursor (ISO timestamp) to fetch messages after.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum messages to return.",
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
    """Read messages in a task thread."""
    if explain:
        _show_explain_thread(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        messages = []
    else:
        db = RuntimeDatabase(runtime_path)

        since_dt = None
        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid timestamp: {since}[/error]")
                raise typer.Exit(1)

        messages = db.get_task_thread(task_id, since=since_dt, limit=limit)

    result = {
        "task_id": task_id,
        "messages": [
            {
                "message_id": m.message_id,
                "from": m.from_agent_id,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "count": len(messages),
        "cursor": messages[-1].created_at.isoformat() if messages else None,
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        console.print(f"[bold]Thread for {task_id}[/bold]")
        console.print()
        if not messages:
            console.print("[muted]No messages in thread.[/muted]")
        else:
            for msg in messages:
                console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                console.print(f"  [agent_id]{msg.from_agent_id}[/agent_id]: {msg.text}")
                console.print()
        console.print()


def _show_explain_send(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg send",
        "purpose": "Send a message to an agent or task thread.",
        "examples": [
            "lodestar msg send --to agent:A123 --text 'Hello' --from A456",
            "lodestar msg send --to task:T001 --text 'Progress update' --from A123",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg send[/info]\n")
        console.print("Send a message to an agent or task thread.\n")


def _show_explain_inbox(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg inbox",
        "purpose": "Read messages from your inbox.",
        "notes": ["Use --since with cursor for pagination"],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg inbox[/info]\n")
        console.print("Read messages from your inbox.\n")


def _show_explain_thread(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg thread",
        "purpose": "Read messages in a task thread.",
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg thread[/info]\n")
        console.print("Read messages in a task thread.\n")
