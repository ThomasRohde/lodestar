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
        console.print(
            "  [command]lodestar msg send --to task:<id> --from <agent-id> --text '...'[/command]"
        )
        console.print("      Leave context on a task thread (for handoffs)")
        console.print()
        console.print(
            "  [command]lodestar msg send --to agent:<id> --from <agent-id> --text '...'[/command]"
        )
        console.print("      Send a direct message to another agent")
        console.print()
        console.print("[info]Reading messages:[/info]")
        console.print("  [command]lodestar msg thread <task-id>[/command]")
        console.print("      Read the message thread for a task")
        console.print("      (accepts 'F001' or 'task:F001' format)")
        console.print()
        console.print("  [command]lodestar msg inbox --agent <agent-id>[/command]")
        console.print("      Read messages sent to you")
        console.print()
        console.print("  [command]lodestar msg search --keyword <term>[/command]")
        console.print("      Search messages by keyword")
        console.print()
        console.print("[info]Examples:[/info]")
        console.print("  lodestar msg send --to task:F001 --from A123 --text 'Blocked on X'")
        console.print("  lodestar msg thread F001        # Both formats work")
        console.print("  lodestar msg thread task:F001   # Both formats work")
        console.print("  lodestar msg search --keyword 'bug' --from A123")
        console.print()


@app.command(name="send")
def msg_send(
    to: str = typer.Option(
        ...,
        "--to",
        "-t",
        help="(REQUIRED) Recipient: 'task:<task-id>' or 'agent:<agent-id>'.",
    ),
    text: str = typer.Option(
        ...,
        "--text",
        "-m",
        help="(REQUIRED) Message text.",
    ),
    from_agent: str = typer.Option(
        ...,
        "--from",
        "-f",
        help="(REQUIRED) Your agent ID. Get it from 'lodestar agent join'.",
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
        help="Filter messages created after this timestamp (ISO format).",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        "-u",
        help="Filter messages created before this timestamp (ISO format).",
    ),
    from_agent: str | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Filter by sender agent ID.",
    ),
    limit: int = typer.Option(
        50,
        "--limit",
        "-n",
        help="Maximum messages to return.",
    ),
    unread_only: bool = typer.Option(
        False,
        "--unread-only",
        help="Show only unread messages.",
    ),
    show_read_status: bool = typer.Option(
        False,
        "--show-read-status",
        help="Display read timestamps in output.",
    ),
    mark_as_read: bool = typer.Option(
        True,
        "--mark-as-read/--no-mark-as-read",
        help="Mark messages as read when retrieving them (default: True).",
    ),
    count_only: bool = typer.Option(
        False,
        "--count",
        help="Only return the count of messages, not the full list.",
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
    """Read messages from your inbox.

    Supports filtering by sender, date range, read status, or combination of filters.

    Examples:
        lodestar msg inbox --agent A123
        lodestar msg inbox --agent A123 --count
        lodestar msg inbox --agent A123 --from B456
        lodestar msg inbox --agent A123 --unread-only
        lodestar msg inbox --agent A123 --show-read-status
        lodestar msg inbox --agent A123 --since 2025-01-01T00:00:00 --until 2025-12-31T23:59:59
    """
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
        count = 0
    else:
        db = RuntimeDatabase(runtime_path)

        # Parse timestamps
        since_dt = None
        until_dt = None

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid since timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid since timestamp: {since}[/error]")
                raise typer.Exit(1)

        if until:
            try:
                until_dt = datetime.fromisoformat(until)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid until timestamp: {until}").model_dump())
                else:
                    console.print(f"[error]Invalid until timestamp: {until}[/error]")
                raise typer.Exit(1)

        if count_only:
            # For count-only mode, we just get the count
            count = db.get_inbox_count(agent_id, since=since_dt)
            messages = []
        else:
            messages = db.get_inbox(
                agent_id,
                since=since_dt,
                until=until_dt,
                from_agent_id=from_agent,
                limit=limit,
                unread_only=unread_only,
                mark_as_read=mark_as_read,
            )
            count = len(messages)

    result = {
        "count": count,
    }

    if not count_only:
        result["messages"] = [
            {
                "message_id": m.message_id,
                "from": m.from_agent_id,
                "text": m.text,
                "created_at": m.created_at.isoformat(),
                "read_at": m.read_at.isoformat() if m.read_at else None,
            }
            for m in messages
        ]
        result["cursor"] = messages[-1].created_at.isoformat() if messages else None

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        if count_only:
            console.print(f"{count}")
        else:
            console.print()
            if not messages:
                status = "unread " if unread_only else ""
                console.print(f"[muted]No {status}messages in inbox.[/muted]")
            else:
                status = "unread " if unread_only else ""
                console.print(f"[bold]Inbox ({len(messages)} {status}messages)[/bold]")
                console.print()
                for msg in messages:
                    console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                    console.print(f"  From: [agent_id]{msg.from_agent_id}[/agent_id]")
                    if show_read_status:
                        if msg.read_at:
                            console.print(f"  [muted]Read: {msg.read_at.isoformat()}[/muted]")
                        else:
                            console.print("  [info]Unread[/info]")
                    console.print(f"  {msg.text}")
                    console.print()
            console.print()


@app.command(name="wait")
def msg_wait(
    agent_id: str = typer.Option(
        ...,
        "--agent",
        "-a",
        help="Your agent ID.",
    ),
    timeout: int | None = typer.Option(
        None,
        "--timeout",
        "-t",
        help="Timeout in seconds (default: wait indefinitely).",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Only wait for messages after this timestamp (ISO format).",
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
    """Block until a new message arrives in your inbox.

    This command will block until a new message is received or the timeout expires.
    If there are already unread messages (optionally after --since), returns immediately.

    Examples:
        lodestar msg wait --agent A123
        lodestar msg wait --agent A123 --timeout 60
        lodestar msg wait --agent A123 --since 2025-01-01T00:00:00
    """
    if explain:
        _show_explain_wait(json_output)
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
        if json_output:
            print_json(Envelope.error("Runtime database does not exist").model_dump())
        else:
            console.print("[error]Runtime database does not exist[/error]")
        raise typer.Exit(1)

    db = RuntimeDatabase(runtime_path)

    # Parse since timestamp
    since_dt = None
    if since:
        try:
            since_dt = datetime.fromisoformat(since)
        except ValueError:
            if json_output:
                print_json(Envelope.error(f"Invalid since timestamp: {since}").model_dump())
            else:
                console.print(f"[error]Invalid since timestamp: {since}[/error]")
            raise typer.Exit(1)

    # Wait for message
    received = db.wait_for_message(agent_id, timeout_seconds=timeout, since=since_dt)

    if received:
        # Get the count of messages
        count = db.get_inbox_count(agent_id, since=since_dt)
        result = {
            "received": True,
            "count": count,
        }

        if json_output:
            print_json(Envelope.success(result).model_dump())
        else:
            console.print(f"[success]New message received[/success] ({count} unread)")
    else:
        # Timeout occurred
        result = {
            "received": False,
            "timeout": True,
        }

        if json_output:
            print_json(Envelope.success(result).model_dump())
        else:
            console.print("[muted]Timeout: No new messages received[/muted]")


@app.command(name="search")
def msg_search(
    keyword: str | None = typer.Option(
        None,
        "--keyword",
        "-k",
        help="Search keyword to match in message text (case-insensitive).",
    ),
    from_agent: str | None = typer.Option(
        None,
        "--from",
        "-f",
        help="Filter by sender agent ID.",
    ),
    since: str | None = typer.Option(
        None,
        "--since",
        "-s",
        help="Filter messages created after this timestamp (ISO format).",
    ),
    until: str | None = typer.Option(
        None,
        "--until",
        "-u",
        help="Filter messages created before this timestamp (ISO format).",
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
    """Search messages with filters.

    Search across all messages with optional keyword matching and filters.
    At least one filter must be provided.

    Examples:
        lodestar msg search --keyword 'bug'
        lodestar msg search --from A123 --since 2025-01-01T00:00:00
        lodestar msg search --keyword 'error' --until 2025-12-31T23:59:59
    """
    if explain:
        _show_explain_search(json_output)
        return

    root = find_lodestar_root()
    if root is None:
        if json_output:
            print_json(Envelope.error("Not a Lodestar repository").model_dump())
        else:
            console.print("[error]Not a Lodestar repository[/error]")
        raise typer.Exit(1)

    # Validate at least one filter is provided
    if not any([keyword, from_agent, since, until]):
        if json_output:
            print_json(
                Envelope.error(
                    "At least one filter is required (--keyword, --from, --since, or --until)"
                ).model_dump()
            )
        else:
            console.print("[error]At least one filter is required[/error]")
            console.print("Use --keyword, --from, --since, or --until")
        raise typer.Exit(1)

    runtime_path = get_runtime_db_path(root)
    if not runtime_path.exists():
        messages = []
    else:
        db = RuntimeDatabase(runtime_path)

        # Parse timestamps
        since_dt = None
        until_dt = None

        if since:
            try:
                since_dt = datetime.fromisoformat(since)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid since timestamp: {since}").model_dump())
                else:
                    console.print(f"[error]Invalid since timestamp: {since}[/error]")
                raise typer.Exit(1)

        if until:
            try:
                until_dt = datetime.fromisoformat(until)
            except ValueError:
                if json_output:
                    print_json(Envelope.error(f"Invalid until timestamp: {until}").model_dump())
                else:
                    console.print(f"[error]Invalid until timestamp: {until}[/error]")
                raise typer.Exit(1)

        messages = db.search_messages(
            keyword=keyword,
            from_agent_id=from_agent,
            since=since_dt,
            until=until_dt,
            limit=limit,
        )

    result = {
        "messages": [
            {
                "message_id": m.message_id,
                "from": m.from_agent_id,
                "to": f"{m.to_type.value}:{m.to_id}",
                "text": m.text,
                "created_at": m.created_at.isoformat(),
            }
            for m in messages
        ],
        "count": len(messages),
        "filters": {
            "keyword": keyword,
            "from": from_agent,
            "since": since,
            "until": until,
        },
    }

    if json_output:
        print_json(Envelope.success(result).model_dump())
    else:
        console.print()
        if not messages:
            console.print("[muted]No messages found.[/muted]")
        else:
            console.print(f"[bold]Search Results ({len(messages)} messages)[/bold]")
            console.print()
            for msg in messages:
                console.print(f"  [muted]{msg.created_at.isoformat()}[/muted]")
                console.print(f"  From: [agent_id]{msg.from_agent_id}[/agent_id]")
                console.print(f"  To: {msg.to_type.value}:{msg.to_id}")
                console.print(f"  {msg.text}")
                console.print()
        console.print()


@app.command(name="thread")
def msg_thread(
    task_id: str = typer.Argument(
        ..., help="Task ID to view thread for (with or without 'task:' prefix)."
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

    # Strip 'task:' prefix if present for consistency
    if task_id.startswith("task:"):
        task_id = task_id[5:]

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


def _show_explain_search(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg search",
        "purpose": "Search messages with filters.",
        "examples": [
            "lodestar msg search --keyword 'bug'",
            "lodestar msg search --from A123 --since 2025-01-01T00:00:00",
            "lodestar msg search --keyword 'error' --until 2025-12-31T23:59:59",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg search[/info]\n")
        console.print("Search messages with filters.\n")


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


def _show_explain_wait(json_output: bool) -> None:
    explanation = {
        "command": "lodestar msg wait",
        "purpose": "Block until a new message arrives in your inbox.",
        "notes": [
            "Returns immediately if there are already unread messages",
            "Use --timeout to limit wait time",
            "Use --since to only wait for messages after a specific time",
        ],
    }
    if json_output:
        print_json(explanation)
    else:
        console.print("\n[info]lodestar msg wait[/info]\n")
        console.print("Block until a new message arrives in your inbox.\n")
